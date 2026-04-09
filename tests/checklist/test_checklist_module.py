from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Error, Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

from tests.review.test_intelligent_review_flow import (
    ARTIFACTS_DIR,
    ReviewConfig,
    build_ui_launch_options,
    create_authenticated_context,
    goto_page_with_retry,
    get_browser_launcher,
    load_review_config,
    open_authenticated_home,
    refresh_auth_state_if_needed,
    should_refresh_auth,
    wait_for_visible_text,
)


EXISTING_CHECKLIST_NAMES = ("舒译测试", "默认审查清单")
TEMP_RULE_GROUP_CANDIDATES = ("舒译新建-002", "舒译测试")
CHECKLIST_COPY_SOURCE_NAME = "舒译测试"
RULE_CATEGORY_NAME_PREFIX = "新建规则分类"
RULE_CATEGORY_EDIT_TARGET_CANDIDATES = ("舒译测试-004", "舒译新建-002", "舒译测试")
RULE_RISK_LEVEL = "警示风险"


def save_module_screenshot(page: Page, case_id: str, suffix: str) -> None:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    page.screenshot(
        path=str(ARTIFACTS_DIR / f"checklist-module-{case_id}-{suffix}.png"),
        full_page=True,
    )


def open_checklist_module(page: Page, config: ReviewConfig) -> None:
    for attempt in range(2):
        open_authenticated_home(page, config)
        try:
            wait_for_visible_text(page, "审查清单", timeout_ms=config.ui_timeout_ms, exact=True).click(force=True)
            page.wait_for_timeout(800)
        except Exception:
            pass
        try:
            goto_checklist_list_page(page, config)
            return
        except Exception:
            if attempt == 0 and should_refresh_auth(page):
                refresh_auth_state_if_needed(page, config)
                continue
            raise


def wait_for_checklist_route(page: Page, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        try:
            current_url = page.url
        except PlaywrightTimeoutError:
            current_url = ""
        if "/review-rule/checkList" in current_url or "/review-rule/" in current_url:
            return
        page.wait_for_timeout(250)
    raise AssertionError("未进入审查清单页面。")


def goto_checklist_list_page(page: Page, config: ReviewConfig) -> None:
    goto_page_with_retry(page, get_checklist_list_url(config))
    wait_for_checklist_route(page, config.review_config_timeout_ms)
    wait_for_checklist_list_loaded(page, config)


def checklist_page_looks_blank(page: Page) -> bool:
    try:
        body_text = page.locator("body").inner_text().strip()
    except Error:
        return False
    return not body_text


def checklist_micro_app_unmounted(page: Page) -> bool:
    try:
        if "/review-rule" not in page.url:
            return False
        return page.evaluate(
            """() => {
                const root = document.querySelector('#root-master');
                if (!root) {
                    return false;
                }
                const text = (document.body?.innerText || '').trim();
                return !text && root.children.length === 0;
            }"""
        )
    except Error:
        return False


def wait_for_checklist_list_loaded(page: Page, config: ReviewConfig) -> None:
    deadline = time.time() + (config.review_config_timeout_ms / 1000)
    reload_used = 0
    blank_started_at: float | None = None
    while time.time() < deadline:
        if checklist_page_looks_blank(page):
            if blank_started_at is None:
                blank_started_at = time.time()
            if reload_used < 2:
                page.reload(wait_until="domcontentloaded")
                reload_used += 1
                page.wait_for_timeout(1500)
                continue
        else:
            blank_started_at = None
        if blank_started_at is not None and time.time() - blank_started_at >= 10:
            raise AssertionError("审查清单子应用未挂载，当前页面为空白页。")
        try:
            if (
                has_visible_match(page.get_by_text("新建清单", exact=True))
                and has_visible_match(page.get_by_text("批量删除", exact=True))
            ):
                search_input = page.locator("input[placeholder='请输入审查清单名称']").first
                if search_input.count() and search_input.is_visible():
                    for checklist_name in EXISTING_CHECKLIST_NAMES:
                        wait_for_visible_text(
                            page,
                            checklist_name,
                            timeout_ms=min(5000, config.review_config_timeout_ms),
                            exact=False,
                        )
                    return
        except (AssertionError, Error):
            pass
        page.wait_for_timeout(500)
    raise AssertionError("审查清单列表页未加载完成。")


def assert_text_hidden(page: Page, text: str, timeout_ms: int) -> None:
    locator = page.get_by_text(text, exact=False)
    page.wait_for_timeout(800)
    for _ in range(max(1, timeout_ms // 250)):
        visible = False
        for index in range(locator.count()):
            if locator.nth(index).is_visible():
                visible = True
                break
        if not visible:
            return
        page.wait_for_timeout(250)
    raise AssertionError(f"文本仍然可见，期望被筛除: {text}")


def has_visible_match(locator: Locator) -> bool:
    for index in range(locator.count()):
        if locator.nth(index).is_visible():
            return True
    return False


def search_checklist(page: Page, keyword: str) -> None:
    search_input = page.locator("input[placeholder='请输入审查清单名称']").first
    search_input.fill(keyword)
    search_input.press("Enter")
    page.wait_for_timeout(1200)


def clear_search(page: Page) -> None:
    search_input = page.locator("input[placeholder='请输入审查清单名称']").first
    search_input.fill("")
    search_input.press("Enter")
    page.wait_for_timeout(1200)


def wait_for_button(page: Page, name: str, timeout_ms: int) -> None:
    page.get_by_role("button", name=name).wait_for(state="visible", timeout=timeout_ms)


def build_temp_checklist_name(prefix: str) -> str:
    return f"{prefix}_{int(time.time() * 1000)}"


def wait_for_checklist_row(page: Page, checklist_name: str, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        rows = page.locator("tr").filter(has_text=checklist_name)
        for index in range(rows.count()):
            row = rows.nth(index)
            if row.is_visible():
                return row
        page.wait_for_timeout(250)
    raise AssertionError(f"未在列表中找到审查清单行: {checklist_name}")


def get_checklist_row_name(row: Locator) -> str:
    visible_inputs = row.locator("input")
    for index in range(visible_inputs.count()):
        candidate = visible_inputs.nth(index)
        if not candidate.is_visible():
            continue
        if (candidate.get_attribute("type") or "").strip().lower() == "checkbox":
            continue
        value = candidate.input_value().strip()
        if value:
            return value

    cells = row.locator("td")
    if cells.count() < 2:
        return ""
    name_cell = cells.nth(1)
    return normalize_row_text(name_cell.inner_text())


def normalize_row_text(text: str) -> str:
    return " ".join(text.split()).strip()


def compact_text(text: str) -> str:
    return "".join(text.split()).strip()


def wait_for_checklist_row_exact(page: Page, checklist_name: str, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        rows = page.locator("tr")
        for index in range(rows.count()):
            row = rows.nth(index)
            if not row.is_visible():
                continue
            name_match = row.get_by_text(checklist_name, exact=True)
            if has_visible_match(name_match) or get_checklist_row_name(row) == checklist_name:
                return row
        page.wait_for_timeout(250)
    raise AssertionError(f"未在列表中找到精确匹配的审查清单行: {checklist_name}")


def wait_for_input_value_contains(page: Page, keyword: str, timeout_ms: int) -> tuple[Locator, str]:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        inputs = page.locator("input")
        for index in range(inputs.count()):
            candidate = inputs.nth(index)
            if not candidate.is_visible():
                continue
            value = candidate.input_value().strip()
            if keyword in value:
                return candidate, value
        page.wait_for_timeout(250)
    raise AssertionError(f"未找到包含目标值的输入框: {keyword}")


def wait_for_new_copied_name(page: Page, prefix: str, existing_names: set[str], timeout_ms: int) -> str:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        rows = page.locator("tr")
        for index in range(rows.count()):
            row = rows.nth(index)
            if not row.is_visible():
                continue
            row_name = get_checklist_row_name(row)
            if row_name.startswith(prefix) and row_name not in existing_names:
                return row_name
        page.wait_for_timeout(250)
    raise AssertionError(f"未找到新的复制结果，前缀: {prefix}")


def click_last_visible_text(page: Page, text: str) -> None:
    locator = page.get_by_text(text, exact=True)
    for index in range(locator.count() - 1, -1, -1):
        candidate = locator.nth(index)
        if candidate.is_visible():
            candidate.click(force=True)
            return
    raise AssertionError(f"未找到可点击文本: {text}")


def collect_visible_checklist_names(page: Page, prefix: str) -> set[str]:
    names: set[str] = set()
    rows = page.locator("tr")
    for index in range(rows.count()):
        row = rows.nth(index)
        if not row.is_visible():
            continue
        row_name = get_checklist_row_name(row)
        if row_name.startswith(prefix):
            names.add(row_name)
    return names


def click_row_delete_action(row: Locator) -> None:
    row.scroll_into_view_if_needed()
    row.hover()
    delete_buttons = row.locator("button").filter(has_text="删除")
    for index in range(delete_buttons.count() - 1, -1, -1):
        button = delete_buttons.nth(index)
        if button.is_visible():
            button.click(force=True)
            return
    row.get_by_text("删除", exact=True).click(force=True)


def click_visible_button(container: Locator | Page, text: str, *, timeout_ms: int = 30000) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    buttons = container.locator("button")
    visible_texts = container.locator("*")
    target_text = compact_text(text)
    while time.time() < deadline:
        for index in range(buttons.count() - 1, -1, -1):
            button = buttons.nth(index)
            try:
                if button.is_visible() and compact_text(button.inner_text()) == target_text:
                    button.click(force=True)
                    return
            except Error:
                continue
        for index in range(visible_texts.count() - 1, -1, -1):
            candidate = visible_texts.nth(index)
            try:
                if candidate.is_visible() and compact_text(candidate.inner_text()) == target_text:
                    candidate.click(force=True)
                    return
            except Error:
                continue
        if text == "删除" and not isinstance(container, Page):
            box = container.bounding_box()
            if box:
                clicked = container.page.evaluate(
                    r"""
                    ({ text, box }) => {
                        const compact = (value) => (value || '').replace(/\s+/g, '');
                        const isVisible = (el) => {
                            const rect = el.getBoundingClientRect();
                            if (!rect.width || !rect.height) {
                                return false;
                            }
                            const style = window.getComputedStyle(el);
                            return style.visibility !== 'hidden' && style.display !== 'none';
                        };
                        const isInsideBox = (el) => {
                            const rect = el.getBoundingClientRect();
                            const centerX = rect.left + rect.width / 2;
                            const centerY = rect.top + rect.height / 2;
                            return (
                                centerX >= box.x &&
                                centerX <= box.x + box.width &&
                                centerY >= box.y &&
                                centerY <= box.y + box.height
                            );
                        };
                        const candidates = [...document.querySelectorAll('button, [role="button"], span, div')];
                        for (let index = candidates.length - 1; index >= 0; index -= 1) {
                            const candidate = candidates[index];
                            if (!isVisible(candidate) || !isInsideBox(candidate)) {
                                continue;
                            }
                            if (compact(candidate.textContent) !== compact(text)) {
                                continue;
                            }
                            const clickable = candidate.closest('button, [role="button"]') || candidate;
                            clickable.click();
                            return true;
                        }
                        return false;
                    }
                    """,
                    {"text": text, "box": box},
                )
                if clicked:
                    container.page.wait_for_timeout(500)
                    if not container.is_visible():
                        return
                container.page.mouse.click(
                    box["x"] + box["width"] - 58,
                    box["y"] + box["height"] - 38,
                )
                container.page.wait_for_timeout(500)
                if not container.is_visible():
                    return
        if isinstance(container, Page):
            container.wait_for_timeout(250)
        else:
            container.page.wait_for_timeout(250)
    raise AssertionError(f"未找到可点击按钮: {text}")


def wait_for_modal(page: Page, title: str, timeout_ms: int) -> Locator:
    title_locator = page.get_by_text(title, exact=True)
    title_locator.wait_for(state="visible", timeout=timeout_ms)
    for index in range(title_locator.count() - 1, -1, -1):
        candidate = title_locator.nth(index)
        if candidate.is_visible():
            return candidate.locator("xpath=ancestor::*[contains(@class,'ant-modal-root')][1]")
    raise AssertionError(f"未找到可见弹窗: {title}")


def get_rule_library_modal_columns(
    modal: Locator,
    *,
    timeout_ms: int | None = None,
) -> tuple[Locator, Locator, Locator]:
    left_col = modal.locator(
        "xpath=.//*[normalize-space(text())='规则分类']"
        "/ancestor::div[.//button[normalize-space()='新建'] and .//li[contains(@class,'ant-list-item')]][1]"
    )
    middle_col = modal.locator(
        "xpath=.//*[normalize-space(text())='审查规则']"
        "/ancestor::div[.//button[contains(normalize-space(),'新建规则')] and "
        "(.//li[contains(@class,'ant-list-item')] or contains(normalize-space(.),'当前分组无审查规则'))][1]"
    )
    right_col = modal.locator(
        "xpath=.//*[normalize-space(text())='规则详情']"
        "/ancestor::div[(contains(normalize-space(.),'暂无数据') or .//*[normalize-space()='编辑'])][1]"
    )
    if timeout_ms is not None:
        left_col.wait_for(state="visible", timeout=timeout_ms)
        middle_col.wait_for(state="visible", timeout=timeout_ms)
        right_col.wait_for(state="visible", timeout=timeout_ms)
    return left_col, middle_col, right_col


def wait_for_popconfirm(page: Page, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        warnings = page.get_by_text("删除后不可恢复", exact=False)
        for index in range(warnings.count() - 1, -1, -1):
            candidate = warnings.nth(index)
            if not candidate.is_visible():
                continue
            containers = (
                candidate.locator("xpath=ancestor::*[@role='dialog'][1]"),
                candidate.locator("xpath=ancestor::*[contains(@class,'ant-modal-root')][1]"),
                candidate.locator("xpath=ancestor::*[contains(@class,'ant-popover')][1]"),
            )
            for container in containers:
                if container.count() and container.is_visible():
                    return container
            return candidate
        page.wait_for_timeout(250)
    raise AssertionError("未找到删除确认弹窗。")


def get_checklist_list_url(config: ReviewConfig) -> str:
    return config.home_url.replace("/home", "/review-rule/checkList")


def collect_visible_list_item_names(container: Locator) -> list[str]:
    names: list[str] = []
    items = container.locator(".ant-list-item")
    for index in range(items.count()):
        item = items.nth(index)
        if not item.is_visible():
            continue
        name = normalize_row_text(item.inner_text())
        if name:
            names.append(name)
    return names


def wait_for_list_item(container: Locator, text: str, timeout_ms: int, *, exact: bool = False) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        items = container.locator(".ant-list-item")
        for index in range(items.count()):
            item = items.nth(index)
            if not item.is_visible():
                continue
            text_match = item.get_by_text(text, exact=exact)
            if has_visible_match(text_match):
                return item
            item_text = normalize_row_text(item.inner_text())
            if exact and item_text == text:
                return item
            if not exact and text in item_text:
                return item
        container.page.wait_for_timeout(250)
    raise AssertionError(f"未找到列表项: {text}")


def wait_for_list_item_hidden(container: Locator, text: str, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        items = container.locator(".ant-list-item")
        visible = False
        for index in range(items.count()):
            item = items.nth(index)
            if not item.is_visible():
                continue
            item_text = normalize_row_text(item.inner_text())
            if text == item_text or text in item_text:
                visible = True
                break
        if not visible:
            return
        container.page.wait_for_timeout(250)
    raise AssertionError(f"列表项仍然可见，期望已消失: {text}")


def open_add_rule_modal_on_new_checklist(page: Page, config: ReviewConfig) -> Locator:
    open_new_checklist_page(page, config)
    page.get_by_role("button", name="添加规则").click(force=True)
    modal = wait_for_modal(page, "从规则库中选择规则", timeout_ms=config.review_config_timeout_ms)
    get_rule_library_modal_columns(modal, timeout_ms=config.review_config_timeout_ms)
    return modal


def wait_for_rule_categories_loaded(left_col: Locator, timeout_ms: int) -> list[str]:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        names = collect_visible_list_item_names(left_col)
        if names:
            return names
        left_col.page.wait_for_timeout(250)
    raise AssertionError("添加规则弹窗中的规则分类未按预期加载。")


def wait_for_rule_category_edit_textarea(left_col: Locator, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        textareas = left_col.locator("textarea")
        for index in range(textareas.count()):
            textarea = textareas.nth(index)
            if textarea.is_visible():
                return textarea
        left_col.page.wait_for_timeout(250)
    raise AssertionError("未进入规则分类编辑态。")


def wait_for_rule_category_edit_item(left_col: Locator, timeout_ms: int) -> tuple[Locator, Locator]:
    textarea = wait_for_rule_category_edit_textarea(left_col, timeout_ms=timeout_ms)
    item = textarea.locator("xpath=ancestor::li[contains(@class,'ant-list-item')][1]")
    item.wait_for(state="visible", timeout=timeout_ms)
    return item, textarea


def wait_for_rule_category_readonly_item(left_col: Locator, category_name: str, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        item = wait_for_list_item(left_col, category_name, timeout_ms=timeout_ms, exact=True)
        textareas = item.locator("textarea")
        has_visible_textarea = False
        for index in range(textareas.count()):
            if textareas.nth(index).is_visible():
                has_visible_textarea = True
                break
        if not has_visible_textarea:
            return item
        left_col.page.wait_for_timeout(250)
    raise AssertionError(f"规则分类未退出编辑态: {category_name}")


def hover_rule_category_item(item: Locator) -> None:
    item.wait_for(state="visible")
    box = item.bounding_box()
    if not box:
        return
    item.page.mouse.move(
        box["x"] + (box["width"] / 2),
        box["y"] + (box["height"] / 2),
    )
    item.page.wait_for_timeout(300)


def click_row_action_anchor(item: Locator, index: int) -> None:
    hover_rule_category_item(item)
    anchors = item.locator("a")
    visible_anchors: list[Locator] = []
    for anchor_index in range(anchors.count()):
        anchor = anchors.nth(anchor_index)
        if anchor.is_visible():
            visible_anchors.append(anchor)
    action_anchors = visible_anchors[-2:] if len(visible_anchors) >= 2 else visible_anchors
    if index >= len(action_anchors):
        raise AssertionError(f"未找到可点击的第 {index + 1} 个操作入口。")
    anchor = action_anchors[index]
    anchor.wait_for(state="visible")
    try:
        anchor.click(timeout=1500)
    except Error:
        anchor.evaluate("(el) => el.click()")


def save_rule_category_edit_state(
    page: Page,
    left_col: Locator,
    new_name: str,
    timeout_ms: int,
) -> str:
    edit_item, textarea = wait_for_rule_category_edit_item(left_col, timeout_ms=timeout_ms)
    textarea.fill(new_name)
    page.wait_for_timeout(300)
    click_row_action_anchor(edit_item, 0)
    wait_for_rule_category_readonly_item(left_col, new_name, timeout_ms=timeout_ms)
    return new_name


def enter_rule_category_edit_mode(
    page: Page,
    left_col: Locator,
    category_name: str,
    timeout_ms: int,
) -> Locator:
    for attempt in range(2):
        item = wait_for_rule_category_readonly_item(left_col, category_name, timeout_ms=timeout_ms)
        item.scroll_into_view_if_needed()
        click_row_action_anchor(item, 0)
        try:
            textarea = wait_for_rule_category_edit_textarea(
                left_col,
                timeout_ms=1500 if attempt == 0 else timeout_ms,
            )
            current_value = textarea.input_value().strip()
            assert current_value == category_name, f"规则分类编辑态值异常: {current_value} != {category_name}"
            page.wait_for_timeout(300)
            return textarea
        except AssertionError:
            if attempt == 0:
                page.wait_for_timeout(500)
                continue
            raise
    raise AssertionError(f"未进入规则分类编辑态: {category_name}")


def create_rule_category_in_modal(
    page: Page,
    left_col: Locator,
    category_name: str,
    timeout_ms: int,
) -> str:
    create_button = left_col.locator("button").filter(has_text="新建").first
    assert create_button.is_enabled(), "规则分类“新建”按钮不可用，无法创建临时分类。"
    create_button.click(force=True)
    _, textarea = wait_for_rule_category_edit_item(left_col, timeout_ms=timeout_ms)
    default_name = textarea.input_value().strip()
    assert default_name.startswith(RULE_CATEGORY_NAME_PREFIX), f"新建规则分类默认值异常: {default_name}"
    return save_rule_category_edit_state(page, left_col, category_name, timeout_ms=timeout_ms)


def edit_rule_category_in_modal(
    page: Page,
    left_col: Locator,
    source_name: str,
    target_name: str,
    timeout_ms: int,
) -> str:
    enter_rule_category_edit_mode(page, left_col, source_name, timeout_ms=timeout_ms)
    save_rule_category_edit_state(page, left_col, target_name, timeout_ms=timeout_ms)
    wait_for_list_item_hidden(left_col, source_name, timeout_ms=timeout_ms)
    return target_name


def wait_for_visible_popover(page: Page, title: str, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    popovers = page.locator(".ant-popover")
    while time.time() < deadline:
        for index in range(popovers.count() - 1, -1, -1):
            popover = popovers.nth(index)
            if not popover.is_visible():
                continue
            if title in normalize_row_text(popover.inner_text()):
                return popover
        page.wait_for_timeout(250)
    raise AssertionError(f"未找到可见弹层: {title}")


def delete_rule_category_in_modal(page: Page, left_col: Locator, category_name: str, timeout_ms: int) -> None:
    item = wait_for_list_item(left_col, category_name, timeout_ms=timeout_ms, exact=True)
    popover: Locator | None = None
    for attempt in range(2):
        click_row_action_anchor(item, 1)
        try:
            popover = wait_for_visible_popover(
                page,
                "删除确认",
                timeout_ms=min(timeout_ms, 2000) if attempt == 0 else timeout_ms,
            )
            break
        except AssertionError:
            if attempt == 0:
                item = wait_for_list_item(left_col, category_name, timeout_ms=timeout_ms, exact=True)
                continue
            raise
    assert popover is not None
    click_visible_button(popover, "删除", timeout_ms=timeout_ms)
    wait_for_list_item_hidden(left_col, category_name, timeout_ms=timeout_ms)


def create_rule_in_modal(
    page: Page,
    modal: Locator,
    category_name: str,
    rule_name: str,
    config: ReviewConfig,
) -> Locator:
    left_col, middle_col, _ = get_rule_library_modal_columns(
        modal,
        timeout_ms=config.review_config_timeout_ms,
    )

    wait_for_list_item(left_col, category_name, timeout_ms=config.review_config_timeout_ms, exact=True).click(
        force=True
    )
    page.wait_for_timeout(800)
    click_visible_button(middle_col, "新建规则", timeout_ms=config.ui_timeout_ms)
    page.wait_for_timeout(800)

    form_modal = wait_for_modal(
        page,
        f"{category_name}-添加规则",
        timeout_ms=config.review_config_timeout_ms,
    )
    form_modal.locator('input[placeholder="请输入规则名称"]').first.fill(rule_name)
    click_visible_button(form_modal, RULE_RISK_LEVEL, timeout_ms=config.ui_timeout_ms)
    form_modal.locator('textarea[placeholder="请输入审查逻辑"]').first.fill("测试审查逻辑：校验条款是否完整。")
    form_modal.locator('textarea[placeholder="请输入风险说明"]').first.fill(
        "测试风险说明：条款不完整可能带来履约风险。"
    )
    click_visible_button(form_modal, "保存", timeout_ms=config.ui_timeout_ms)
    form_modal.wait_for(state="hidden", timeout=config.review_config_timeout_ms)

    rule_item = wait_for_list_item(
        middle_col,
        rule_name,
        timeout_ms=config.review_config_timeout_ms,
        exact=False,
    )
    assert has_visible_match(rule_item.get_by_text(RULE_RISK_LEVEL, exact=False)), (
        f"新建规则后，未看到预期的风险等级标签: {RULE_RISK_LEVEL}"
    )
    return rule_item


def open_new_checklist_page(page: Page, config: ReviewConfig) -> None:
    wait_for_visible_text(page, "新建清单", timeout_ms=config.ui_timeout_ms, exact=True).click(force=True)
    wait_for_visible_text(page, "新建审查清单", timeout_ms=config.review_config_timeout_ms, exact=True)
    get_checklist_name_input(page, timeout_ms=config.ui_timeout_ms).wait_for(
        state="visible",
        timeout=config.ui_timeout_ms,
    )


def get_checklist_name_input(page: Page, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        inputs = page.locator("input")
        best_candidate: Locator | None = None
        best_y = float("inf")
        for index in range(inputs.count()):
            candidate = inputs.nth(index)
            if not candidate.is_visible():
                continue
            box = candidate.bounding_box()
            if not box:
                continue
            if box["y"] < best_y:
                best_candidate = candidate
                best_y = box["y"]
        if best_candidate is not None:
            return best_candidate
        page.wait_for_timeout(250)
    raise AssertionError("未找到审查清单名称输入框。")


def fill_checklist_name(page: Page, checklist_name: str, timeout_ms: int) -> None:
    input_locator = get_checklist_name_input(page, timeout_ms=timeout_ms)
    input_locator.fill("")
    input_locator.fill(checklist_name)
    page.wait_for_timeout(200)
    current_value = input_locator.input_value().strip()
    assert current_value == checklist_name, f"审查清单名称填写失败: {current_value} != {checklist_name}"


def choose_rule_group_for_new_checklist(page: Page, config: ReviewConfig) -> str:
    page.get_by_role("button", name="添加规则").click(force=True)
    modal = wait_for_modal(page, "从规则库中选择规则", timeout_ms=config.review_config_timeout_ms)
    _, middle_col, _ = get_rule_library_modal_columns(
        modal,
        timeout_ms=config.review_config_timeout_ms,
    )

    deadline = time.time() + (config.review_config_timeout_ms / 1000)
    while time.time() < deadline:
        for group_name in TEMP_RULE_GROUP_CANDIDATES:
            group_row = modal.locator(".ant-list-item").filter(has_text=group_name).first
            if not group_row.count():
                continue
            group_row.click(force=True)
            page.wait_for_timeout(800)
            rule_items = middle_col.locator(".ant-list-item")
            if not rule_items.count():
                continue
            rule_items.first.locator("input.ant-checkbox-input").check(force=True)
            page.wait_for_timeout(800)
            modal.locator(".ant-modal-footer button").last.click(force=True)
            modal.wait_for(state="hidden", timeout=config.ui_timeout_ms)
            return group_name
        page.wait_for_timeout(500)

    raise AssertionError("未找到可用于新建审查清单的规则分组。")


def save_checklist(page: Page, config: ReviewConfig) -> None:
    save_buttons = page.locator("xpath=//button[.//span[contains(normalize-space(),'保存')]]")
    deadline = time.time() + (config.ui_timeout_ms / 1000)
    while time.time() < deadline:
        for index in range(save_buttons.count() - 1, -1, -1):
            save_button = save_buttons.nth(index)
            if save_button.is_visible():
                save_button.click(force=True)
                page.wait_for_timeout(1500)
                if "checkList" not in page.url:
                    goto_checklist_list_page(page, config)
                else:
                    wait_for_checklist_route(page, config.review_config_timeout_ms)
                    wait_for_checklist_list_loaded(page, config)
                return
        page.wait_for_timeout(250)
    raise AssertionError("未找到可点击的保存按钮。")


def create_checklist(page: Page, config: ReviewConfig, checklist_name: str) -> str:
    goto_checklist_list_page(page, config)
    open_new_checklist_page(page, config)
    fill_checklist_name(page, checklist_name, timeout_ms=config.ui_timeout_ms)
    selected_group = choose_rule_group_for_new_checklist(page, config)
    fill_checklist_name(page, checklist_name, timeout_ms=config.ui_timeout_ms)
    save_checklist(page, config)
    search_checklist(page, checklist_name)
    wait_for_checklist_row(page, checklist_name, timeout_ms=config.review_config_timeout_ms)
    clear_search(page)
    return selected_group


def delete_checklist_by_name(page: Page, config: ReviewConfig, checklist_name: str) -> None:
    search_checklist(page, checklist_name)
    row = wait_for_checklist_row(page, checklist_name, timeout_ms=config.review_config_timeout_ms)
    click_row_delete_action(row)
    popconfirm = wait_for_popconfirm(page, timeout_ms=config.ui_timeout_ms)
    click_visible_button(popconfirm, "删除", timeout_ms=config.ui_timeout_ms)
    page.wait_for_timeout(1200)
    assert_text_hidden(page, checklist_name, timeout_ms=config.review_config_timeout_ms)
    clear_search(page)


def check_checklist_row(page: Page, checklist_name: str, timeout_ms: int) -> None:
    row = wait_for_checklist_row_exact(page, checklist_name, timeout_ms=timeout_ms)
    checkbox = row.locator("input.ant-checkbox-input")
    checkbox.wait_for(state="attached", timeout=timeout_ms)
    checkbox.check(force=True)


def assert_checklist_hidden_by_search(page: Page, checklist_name: str, timeout_ms: int) -> None:
    search_checklist(page, checklist_name)
    assert_text_hidden(page, checklist_name, timeout_ms=timeout_ms)
    clear_search(page)


def cleanup_checklists_by_prefix(page: Page, config: ReviewConfig, prefix: str) -> None:
    while True:
        matching_names = sorted(collect_visible_checklist_names(page, prefix), key=len, reverse=True)
        if not matching_names:
            break
        target_name = matching_names[0]
        row = wait_for_checklist_row(page, target_name, timeout_ms=config.review_config_timeout_ms)
        click_row_delete_action(row)
        popconfirm = wait_for_popconfirm(page, timeout_ms=config.ui_timeout_ms)
        click_visible_button(popconfirm, "删除", timeout_ms=config.ui_timeout_ms)
        page.wait_for_timeout(1500)


def copy_checklist_row(page: Page, config: ReviewConfig, source_name: str, copied_prefix: str) -> str:
    existing_names = collect_visible_checklist_names(page, copied_prefix)
    source_row = wait_for_checklist_row_exact(page, source_name, timeout_ms=config.review_config_timeout_ms)
    source_row.get_by_text("复制", exact=True).click(force=True)
    return wait_for_new_copied_name(
        page,
        copied_prefix,
        existing_names=existing_names,
        timeout_ms=config.review_config_timeout_ms,
    )


def test_checklist_list_and_search() -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            open_checklist_module(page, config)
            wait_for_checklist_list_loaded(page, config)

            search_checklist(page, "舒译测试")
            wait_for_visible_text(page, "舒译测试", timeout_ms=config.ui_timeout_ms, exact=False)
            assert_text_hidden(page, "默认审查清单", timeout_ms=config.ui_timeout_ms)

            clear_search(page)
            wait_for_visible_text(page, "默认审查清单", timeout_ms=config.ui_timeout_ms, exact=False)
            save_module_screenshot(page, "list-search", "success")
        except Exception:
            save_module_screenshot(page, "list-search", "failed")
            raise
        finally:
            context.close()
            browser.close()


def test_checklist_create_page_and_add_rule_modal() -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            open_checklist_module(page, config)
            wait_for_checklist_list_loaded(page, config)

            wait_for_visible_text(page, "新建清单", timeout_ms=config.ui_timeout_ms, exact=True).click(force=True)
            wait_for_visible_text(page, "新建审查清单", timeout_ms=config.review_config_timeout_ms, exact=True)
            page.locator("input[placeholder='请输入审查清单名称']").first.wait_for(
                state="visible",
                timeout=config.ui_timeout_ms,
            )
            wait_for_button(page, "添加规则", timeout_ms=config.ui_timeout_ms)
            wait_for_visible_text(page, "规则详情", timeout_ms=config.ui_timeout_ms, exact=True)

            page.get_by_role("button", name="添加规则").click(force=True)
            wait_for_visible_text(page, "从规则库中选择规则", timeout_ms=config.review_config_timeout_ms, exact=True)
            wait_for_visible_text(page, "规则分类", timeout_ms=config.ui_timeout_ms, exact=True)
            wait_for_visible_text(page, "审查规则", timeout_ms=config.ui_timeout_ms, exact=True)
            wait_for_visible_text(page, "规则详情", timeout_ms=config.ui_timeout_ms, exact=True)

            visible_category = any(
                page.get_by_text(category_name, exact=False).count()
                for category_name in ("舒译测试", "通用审查点")
            )
            assert visible_category, "添加规则弹窗中未看到预期的规则分类。"

            save_module_screenshot(page, "create-modal", "success")
        except Exception:
            save_module_screenshot(page, "create-modal", "failed")
            raise
        finally:
            context.close()
            browser.close()


def test_checklist_add_rule_modal_category_management_closed_loop() -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        modal: Locator | None = None
        left_col: Locator | None = None
        cleanup_category_name: str | None = None
        try:
            open_checklist_module(page, config)
            wait_for_checklist_list_loaded(page, config)

            modal = open_add_rule_modal_on_new_checklist(page, config)
            left_col, _, _ = get_rule_library_modal_columns(
                modal,
                timeout_ms=config.review_config_timeout_ms,
            )
            wait_for_rule_categories_loaded(left_col, timeout_ms=config.review_config_timeout_ms)
            created_category_name = build_temp_checklist_name("舒译弹窗分类")
            cleanup_category_name = create_rule_category_in_modal(
                page,
                left_col,
                created_category_name,
                timeout_ms=config.ui_timeout_ms,
            )
            edited_category_name = build_temp_checklist_name("舒译弹窗分类改")
            cleanup_category_name = edit_rule_category_in_modal(
                page,
                left_col,
                created_category_name,
                edited_category_name,
                timeout_ms=config.ui_timeout_ms,
            )
            delete_rule_category_in_modal(
                page,
                left_col,
                edited_category_name,
                timeout_ms=config.ui_timeout_ms,
            )
            cleanup_category_name = None
            save_module_screenshot(page, "add-rule-modal-category-management", "success")
        except Exception:
            save_module_screenshot(page, "add-rule-modal-category-management", "failed")
            raise
        finally:
            if cleanup_category_name:
                try:
                    if modal is None or not modal.is_visible():
                        modal = open_add_rule_modal_on_new_checklist(page, config)
                        left_col, _, _ = get_rule_library_modal_columns(
                            modal,
                            timeout_ms=config.review_config_timeout_ms,
                        )
                        wait_for_rule_categories_loaded(left_col, timeout_ms=config.review_config_timeout_ms)
                    assert left_col is not None
                    delete_rule_category_in_modal(
                        page,
                        left_col,
                        cleanup_category_name,
                        timeout_ms=config.ui_timeout_ms,
                    )
                except Exception:
                    pass
            context.close()
            browser.close()


def test_checklist_add_rule_modal_create_rule_closed_loop() -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        cleanup_category_name: str | None = None
        left_col: Locator | None = None
        try:
            open_checklist_module(page, config)
            wait_for_checklist_list_loaded(page, config)

            modal = open_add_rule_modal_on_new_checklist(page, config)
            left_col, _, _ = get_rule_library_modal_columns(
                modal,
                timeout_ms=config.review_config_timeout_ms,
            )
            wait_for_rule_categories_loaded(left_col, timeout_ms=config.review_config_timeout_ms)
            target_category_name = build_temp_checklist_name("舒译规则分类")
            cleanup_category_name = create_rule_category_in_modal(
                page,
                left_col,
                target_category_name,
                timeout_ms=config.ui_timeout_ms,
            )
            rule_name = build_temp_checklist_name("舒译规则")
            rule_item = create_rule_in_modal(
                page,
                modal,
                target_category_name,
                rule_name,
                config,
            )
            assert has_visible_match(rule_item.get_by_text(rule_name, exact=True)), "新建规则后，未在规则列表中看到规则名。"
            delete_rule_category_in_modal(
                page,
                left_col,
                target_category_name,
                timeout_ms=config.ui_timeout_ms,
            )
            cleanup_category_name = None
            save_module_screenshot(page, "add-rule-modal-create-rule", "success")
        except Exception:
            save_module_screenshot(page, "add-rule-modal-create-rule", "failed")
            raise
        finally:
            if cleanup_category_name and left_col is not None:
                try:
                    delete_rule_category_in_modal(
                        page,
                        left_col,
                        cleanup_category_name,
                        timeout_ms=config.ui_timeout_ms,
                    )
                except Exception:
                    pass
            context.close()
            browser.close()


def test_checklist_copy_edit_and_delete_closed_loop() -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            open_checklist_module(page, config)
            wait_for_checklist_list_loaded(page, config)

            copy_prefix = f"{CHECKLIST_COPY_SOURCE_NAME}__复制"
            try:
                cleanup_checklists_by_prefix(page, config, copy_prefix)
            except Exception:
                goto_checklist_list_page(page, config)

            first_copy_name = copy_checklist_row(
                page,
                config,
                source_name=CHECKLIST_COPY_SOURCE_NAME,
                copied_prefix=copy_prefix,
            )
            second_copy_name = copy_checklist_row(
                page,
                config,
                source_name=first_copy_name,
                copied_prefix=first_copy_name,
            )
            second_copy_row = wait_for_checklist_row_exact(
                page,
                second_copy_name,
                timeout_ms=config.review_config_timeout_ms,
            )
            second_copy_row.get_by_text("编辑", exact=True).click(force=True)

            wait_for_visible_text(page, "编辑审查清单", timeout_ms=config.review_config_timeout_ms, exact=True)
            _, current_name = wait_for_input_value_contains(
                page,
                second_copy_name,
                timeout_ms=config.review_config_timeout_ms,
            )
            assert current_name == second_copy_name, (
                f"编辑页名称与复制行名称不一致: {current_name} != {second_copy_name}"
            )
            wait_for_button(page, "添加规则", timeout_ms=config.ui_timeout_ms)
            wait_for_visible_text(page, "规则详情", timeout_ms=config.ui_timeout_ms, exact=True)
            goto_checklist_list_page(page, config)
            delete_checklist_by_name(page, config, second_copy_name)
            delete_checklist_by_name(page, config, first_copy_name)
            save_module_screenshot(page, "copy-edit-entry", "success")
        except Exception:
            save_module_screenshot(page, "copy-edit-entry", "failed")
            raise
        finally:
            context.close()
            browser.close()


def test_checklist_delete_confirmation_cancel() -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            open_checklist_module(page, config)
            wait_for_checklist_list_loaded(page, config)

            target_name = "默认审查清单"
            row = wait_for_checklist_row(page, target_name, timeout_ms=config.review_config_timeout_ms)
            row.get_by_text("删除", exact=True).click(force=True)

            wait_for_visible_text(page, f"删除“{target_name}”审查清单提醒", timeout_ms=config.ui_timeout_ms, exact=False)
            wait_for_visible_text(page, "确认删除该审查清单吗？删除后不可恢复。", timeout_ms=config.ui_timeout_ms, exact=False)
            click_last_visible_text(page, "取消")
            wait_for_checklist_row(page, target_name, timeout_ms=config.ui_timeout_ms)
            save_module_screenshot(page, "delete-cancel", "success")
        except Exception:
            save_module_screenshot(page, "delete-cancel", "failed")
            raise
        finally:
            context.close()
            browser.close()


def test_checklist_batch_delete_closed_loop() -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            open_checklist_module(page, config)
            wait_for_checklist_list_loaded(page, config)

            copy_prefix = f"{CHECKLIST_COPY_SOURCE_NAME}__复制"
            existing_copy_names = sorted(collect_visible_checklist_names(page, copy_prefix), key=len)

            if len(existing_copy_names) >= 2:
                first_copy_name, second_copy_name = existing_copy_names[:2]
            elif len(existing_copy_names) == 1:
                first_copy_name = existing_copy_names[0]
                second_copy_name = copy_checklist_row(
                    page,
                    config,
                    source_name=first_copy_name,
                    copied_prefix=first_copy_name,
                )
            else:
                first_copy_name = copy_checklist_row(
                    page,
                    config,
                    source_name=CHECKLIST_COPY_SOURCE_NAME,
                    copied_prefix=copy_prefix,
                )
                second_copy_name = copy_checklist_row(
                    page,
                    config,
                    source_name=first_copy_name,
                    copied_prefix=first_copy_name,
                )
            checklist_names = (first_copy_name, second_copy_name)

            for checklist_name in checklist_names:
                check_checklist_row(page, checklist_name, timeout_ms=config.review_config_timeout_ms)

            batch_delete_button = page.get_by_role("button", name="批量删除")
            assert batch_delete_button.is_enabled(), "勾选目标清单后，批量删除按钮仍不可用。"
            batch_delete_button.click(force=True)

            popconfirm = wait_for_popconfirm(page, timeout_ms=config.ui_timeout_ms)
            click_visible_button(popconfirm, "删除", timeout_ms=config.ui_timeout_ms)
            page.wait_for_timeout(1500)

            for checklist_name in checklist_names:
                assert_checklist_hidden_by_search(page, checklist_name, timeout_ms=config.review_config_timeout_ms)
            save_module_screenshot(page, "batch-delete", "success")
        except Exception:
            save_module_screenshot(page, "batch-delete", "failed")
            raise
        finally:
            context.close()
            browser.close()
