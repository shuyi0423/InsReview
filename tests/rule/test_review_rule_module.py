from __future__ import annotations

import time
from typing import Any

from playwright.sync_api import Error as PlaywrightError, Locator, Page, sync_playwright

from tests.checklist.test_checklist_module import (
    RULE_CATEGORY_EDIT_TARGET_CANDIDATES,
    RULE_CATEGORY_NAME_PREFIX,
    RULE_RISK_LEVEL,
    build_temp_checklist_name,
    click_visible_button,
    compact_text,
    collect_visible_list_item_names,
    delete_rule_category_in_modal,
    enter_rule_category_edit_mode,
    normalize_row_text,
    open_checklist_module,
    save_rule_category_edit_state,
    wait_for_checklist_list_loaded,
    wait_for_list_item,
    wait_for_list_item_hidden,
    wait_for_modal,
    wait_for_rule_categories_loaded,
    wait_for_rule_category_edit_item,
    wait_for_visible_popover,
)
from tests.review.test_intelligent_review_flow import (
    ARTIFACTS_DIR,
    build_ui_launch_options,
    create_authenticated_context,
    get_browser_launcher,
    load_review_config,
    wait_for_visible_text,
)


COMMON_RULE_CATEGORY_NAME = "通用审查点"
COMMON_RULE_TOTAL_TEXT = "共 53 条"
COMMON_RULE_EDIT_HINT = (
    "此规则为系统通用审查规则，其名称、等级与逻辑不可修改。但您可以根据业务需要自定义风险说明。"
)
TEMP_RULE_CATEGORY_PREFIX = "规则页分类"
TEMP_RULE_NAME_PREFIX = "规则页规则"


def save_rule_module_screenshot(page: Page, case_id: str, suffix: str) -> None:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    try:
        if page.is_closed():
            return
        page.screenshot(
            path=str(ARTIFACTS_DIR / f"review-rule-module-{case_id}-{suffix}.png"),
            full_page=True,
        )
    except PlaywrightError:
        return


def open_review_rule_page(page: Page) -> tuple[Any, Locator, Locator, Locator]:
    config = load_review_config()
    open_checklist_module(page, config)
    wait_for_checklist_list_loaded(page, config)
    wait_for_visible_text(page, "审查规则", timeout_ms=config.ui_timeout_ms, exact=True).click(force=True)
    left_col, middle_col, right_col = get_rule_page_columns(page)
    wait_for_rule_page_loaded(page, left_col, middle_col, right_col, config.ui_timeout_ms, config.review_config_timeout_ms)
    return config, left_col, middle_col, right_col


def get_rule_page_columns(page: Page) -> tuple[Locator, Locator, Locator]:
    columns = page.locator(".ant-pro-card-col")
    return columns.nth(0), columns.nth(1), columns.nth(2)


def wait_for_rule_page_loaded(
    page: Page,
    left_col: Locator,
    middle_col: Locator,
    right_col: Locator,
    ui_timeout_ms: int,
    review_timeout_ms: int,
) -> None:
    wait_for_rule_categories_loaded(left_col, timeout_ms=review_timeout_ms)
    wait_for_visible_text(page, "新建规则", timeout_ms=ui_timeout_ms, exact=True)
    right_col.wait_for(state="visible", timeout=ui_timeout_ms)


def collect_visible_rule_rows(middle_col: Locator) -> list[Locator]:
    rows: list[Locator] = []
    items = middle_col.locator(".ant-list-item")
    for index in range(items.count()):
        item = items.nth(index)
        if item.is_visible():
            rows.append(item)
    return rows


def hover_rule_row(row: Locator) -> None:
    row.wait_for(state="visible")
    box = row.bounding_box()
    if not box:
        return
    row.page.mouse.move(box["x"] + (box["width"] / 2), box["y"] + (box["height"] / 2))
    row.page.wait_for_timeout(300)


def collect_rule_categories_by_prefix(left_col: Locator, prefix: str) -> list[str]:
    names: list[str] = []
    items = left_col.locator(".ant-list-item")
    for index in range(items.count()):
        item = items.nth(index)
        if not item.is_visible():
            continue
        item_text = normalize_row_text(item.inner_text())
        if item_text.startswith(prefix):
            names.append(item_text)
    return names


def cleanup_rule_categories_by_prefix(page: Page, left_col: Locator, prefix: str, timeout_ms: int) -> None:
    while True:
        matches = collect_rule_categories_by_prefix(left_col, prefix)
        if not matches:
            return
        delete_rule_category_in_modal(page, left_col, matches[0], timeout_ms=timeout_ms)


def create_rule_category_on_rule_page(
    page: Page,
    left_col: Locator,
    category_name: str,
    timeout_ms: int,
) -> str:
    _, textarea = open_new_rule_category_draft(page, left_col, timeout_ms)
    default_name = textarea.input_value().strip()
    assert default_name, "新建规则分类编辑态未带出默认名称。"
    return save_rule_category_on_rule_page(page, left_col, category_name, timeout_ms=timeout_ms)


def open_new_rule_category_draft(page: Page, left_col: Locator, timeout_ms: int) -> tuple[Locator, Locator]:
    create_button = left_col.locator("button").filter(has_text="新建").first
    existing_names = set(collect_visible_list_item_names(left_col))
    create_button.click(force=True)
    assert not create_button.is_enabled(), "新建规则分类未完成时，“新建”按钮应为置灰不可点击状态。"
    page.wait_for_timeout(500)

    try:
        return wait_for_rule_category_edit_item(left_col, timeout_ms=1500)
    except Exception:
        deadline = time.monotonic() + (timeout_ms / 1000)
        fallback_name: str | None = None
        while time.monotonic() < deadline:
            current_names = collect_visible_list_item_names(left_col)
            for candidate in current_names:
                if candidate not in existing_names and candidate.startswith(RULE_CATEGORY_NAME_PREFIX):
                    fallback_name = candidate
                    break
            if fallback_name:
                break
            page.wait_for_timeout(250)
        if not fallback_name:
            raise AssertionError("点击“新建”后，未找到新的规则分类草稿。")
        enter_rule_category_edit_mode(page, left_col, fallback_name, timeout_ms=timeout_ms)
        return wait_for_rule_category_edit_item(left_col, timeout_ms=timeout_ms)


def save_rule_category_on_rule_page(
    page: Page,
    left_col: Locator,
    new_name: str,
    timeout_ms: int,
) -> str:
    edit_item, textarea = wait_for_rule_category_edit_item(left_col, timeout_ms=timeout_ms)
    textarea.fill(new_name)
    page.wait_for_timeout(300)
    trigger_rule_category_submit_on_rule_page(page, edit_item)

    deadline = time.monotonic() + (timeout_ms / 1000)
    target_name = compact_text(new_name)
    while time.monotonic() < deadline:
        loading_icons = edit_item.locator("[aria-label='loading'], .anticon-loading")
        if is_any_visible(loading_icons):
            page.wait_for_timeout(250)
            continue
        if not is_any_visible(left_col.locator("textarea")):
            visible_names = [compact_text(name) for name in collect_visible_list_item_names(left_col)]
            if target_name in visible_names:
                return new_name
        page.wait_for_timeout(250)

    raise AssertionError(f"规则分类保存后未看到目标名称: {new_name}")


def trigger_rule_category_submit_on_rule_page(page: Page, edit_item: Locator) -> None:
    check_icon = edit_item.locator("[aria-label='check-circle']").first
    if check_icon.count() and check_icon.is_visible():
        check_icon.click(force=True)
        page.wait_for_timeout(400)


def build_indexed_temp_name(prefix: str, index: int) -> str:
    return f"{build_temp_checklist_name(prefix)}_{index}"


def is_any_visible(locator: Locator) -> bool:
    for index in range(locator.count()):
        if locator.nth(index).is_visible():
            return True
    return False


def count_category_items_by_name(left_col: Locator, category_name: str) -> int:
    target_name = compact_text(category_name)
    return sum(1 for name in collect_visible_list_item_names(left_col) if compact_text(name) == target_name)


def get_last_visible_button_by_text(container: Locator | Page, text: str, timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    target = compact_text(text)
    while time.monotonic() < deadline:
        buttons = container.locator("button, .ant-btn, [role='button']")
        for index in range(buttons.count() - 1, -1, -1):
            button = buttons.nth(index)
            if not button.is_visible():
                continue
            if compact_text(button.inner_text()) == target:
                return button
        if isinstance(container, Locator):
            container.page.wait_for_timeout(250)
        else:
            container.wait_for_timeout(250)
    raise AssertionError(f"未找到可见按钮: {text}")


def click_visible_link(page: Page, text: str, timeout_ms: int) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    target = normalize_row_text(text)
    while time.monotonic() < deadline:
        links = page.locator("a")
        for index in range(links.count()):
            link = links.nth(index)
            if not link.is_visible():
                continue
            if normalize_row_text(link.inner_text()) == target:
                try:
                    link.click(force=True)
                except Exception:
                    link.evaluate("(el) => el.click()")
                return
        page.wait_for_timeout(250)
    raise AssertionError(f"未找到可点击链接: {text}")


def wait_for_any_visible_popover(page: Page, timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    popovers = page.locator(".ant-popover")
    while time.monotonic() < deadline:
        for index in range(popovers.count() - 1, -1, -1):
            popover = popovers.nth(index)
            if popover.is_visible():
                return popover
        page.wait_for_timeout(250)
    raise AssertionError("未找到可见气泡弹层。")


def wait_for_visible_popover_with_actions(page: Page, actions: tuple[str, ...], timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        popover = wait_for_any_visible_popover(page, timeout_ms=1000)
        text = normalize_row_text(popover.inner_text())
        if any(action in text for action in actions):
            return popover
        page.wait_for_timeout(250)
    raise AssertionError(f"未找到包含目标动作的气泡弹层: {actions}")


def wait_for_visible_confirmation_layer(page: Page, keywords: tuple[str, ...], timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    layers = page.locator(".ant-modal-confirm, .ant-popover, .ant-modal-wrap .ant-modal-content")
    while time.monotonic() < deadline:
        for index in range(layers.count() - 1, -1, -1):
            layer = layers.nth(index)
            if not layer.is_visible():
                continue
            text = normalize_row_text(layer.inner_text())
            if all(keyword in text for keyword in keywords):
                return layer
        page.wait_for_timeout(250)
    raise AssertionError(f"未找到确认层: {keywords}")


def click_rightmost_visible_button_in_layer(layer: Locator, texts: tuple[str, ...], timeout_ms: int) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    targets = {compact_text(text) for text in texts}
    while time.monotonic() < deadline:
        candidates: list[tuple[float, float, Locator]] = []
        buttons = layer.locator("button, .ant-btn, [role='button']")
        for index in range(buttons.count()):
            button = buttons.nth(index)
            try:
                if not button.is_visible():
                    continue
                if compact_text(button.inner_text()) not in targets:
                    continue
                box = button.bounding_box()
                if not box:
                    continue
                candidates.append((box["x"], box["y"], button))
            except PlaywrightError:
                continue
        if candidates:
            _, _, target = sorted(candidates, key=lambda item: (item[1], item[0]), reverse=True)[0]
            target.click(force=True)
            return
        layer.page.wait_for_timeout(250)
    raise AssertionError(f"未找到确认按钮: {texts}")


def get_existing_target_category_name(left_col: Locator) -> str:
    visible_names = collect_visible_list_item_names(left_col)
    for candidate in RULE_CATEGORY_EDIT_TARGET_CANDIDATES:
        if candidate in visible_names:
            return candidate
    raise AssertionError(f"未找到可用于批量修改规则分类的目标分类: {RULE_CATEGORY_EDIT_TARGET_CANDIDATES}")


def open_rule_editor(page: Page, left_col: Locator, middle_col: Locator, category_name: str, timeout_ms: int) -> None:
    wait_for_list_item(left_col, category_name, timeout_ms=timeout_ms, exact=True).click(force=True)
    page.wait_for_timeout(800)
    click_visible_button(middle_col, "新建规则", timeout_ms=timeout_ms)
    page.locator('input[placeholder="请输入规则名称"]').first.wait_for(state="visible", timeout=timeout_ms)


def fill_rule_form(page: Page, rule_name: str) -> None:
    page.locator('input[placeholder="请输入规则名称"]').first.fill(rule_name)
    page.locator("#riskLevel").get_by_text(RULE_RISK_LEVEL, exact=True).click(force=True)
    page.locator('textarea[placeholder="请输入审查逻辑"]').first.fill("测试审查逻辑：校验条款是否完整。")
    page.locator('textarea[placeholder="请输入风险说明"]').first.fill("测试风险说明：条款不完整可能带来履约风险。")


def close_rule_editor_if_visible(page: Page) -> None:
    buttons = page.locator("button")
    for index in range(buttons.count() - 1, -1, -1):
        button = buttons.nth(index)
        if not button.is_visible():
            continue
        if normalize_row_text(button.inner_text()) == "取消":
            button.click(force=True)
            page.wait_for_timeout(600)
            return


def create_rule_on_rule_page(
    page: Page,
    left_col: Locator,
    middle_col: Locator,
    right_col: Locator,
    category_name: str,
    rule_name: str,
    timeout_ms: int,
) -> Locator:
    open_rule_editor(page, left_col, middle_col, category_name, timeout_ms)
    fill_rule_form(page, rule_name)
    get_last_visible_button_by_text(page, "保存", timeout_ms=timeout_ms).click(force=True)
    page.wait_for_timeout(1500)

    rule_item = wait_for_rule_item(middle_col, rule_name, timeout_ms=timeout_ms)
    rule_text = normalize_row_text(rule_item.inner_text())
    assert RULE_RISK_LEVEL in rule_text, f"新建规则后未看到风险等级标签: {RULE_RISK_LEVEL}"
    return rule_item


def count_rule_items_by_name(middle_col: Locator, rule_name: str) -> int:
    count = 0
    target_name = compact_text(rule_name)
    items = middle_col.locator(".ant-list-item")
    for index in range(items.count()):
        item = items.nth(index)
        if not item.is_visible():
            continue
        item_text = compact_text(item.inner_text())
        if target_name in item_text:
            count += 1
    return count


def wait_for_rule_item(middle_col: Locator, rule_name: str, timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    target_name = compact_text(rule_name)
    while time.monotonic() < deadline:
        items = middle_col.locator(".ant-list-item")
        for index in range(items.count()):
            item = items.nth(index)
            if not item.is_visible():
                continue
            if target_name in compact_text(item.inner_text()):
                return item
        middle_col.page.wait_for_timeout(250)
    raise AssertionError(f"未找到规则列表项: {rule_name}")


def check_rule_row(middle_col: Locator, rule_name: str, timeout_ms: int) -> None:
    row = wait_for_rule_item(middle_col, rule_name, timeout_ms=timeout_ms)
    checkbox = row.locator("input.ant-checkbox-input")
    checkbox.wait_for(state="attached", timeout=timeout_ms)
    checkbox.check(force=True)


def wait_for_button_with_candidates(container: Locator | Page, candidates: tuple[str, ...], timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        buttons = container.locator("button")
        for index in range(buttons.count()):
            button = buttons.nth(index)
            if not button.is_visible():
                continue
            text = normalize_row_text(button.inner_text())
            if any(candidate in text for candidate in candidates):
                return button
        container.page.wait_for_timeout(250) if isinstance(container, Locator) else container.wait_for_timeout(250)
    raise AssertionError(f"未找到任一候选按钮: {candidates}")


def delete_rule_on_rule_page(page: Page, middle_col: Locator, rule_name: str, timeout_ms: int) -> None:
    row = wait_for_rule_item(middle_col, rule_name, timeout_ms=timeout_ms)
    hover_rule_row(row)
    row.get_by_text("删除", exact=True).click(force=True)
    popover = wait_for_visible_popover(page, "删除审查规则", timeout_ms=timeout_ms)
    click_visible_button(popover, "确定", timeout_ms=timeout_ms)
    wait_for_list_item_hidden(middle_col, rule_name, timeout_ms=timeout_ms)


def open_common_rule_edit_modal(
    page: Page,
    middle_col: Locator,
    right_col: Locator,
    timeout_ms: int,
) -> Locator:
    first_rule = middle_col.locator(".ant-list-item").first
    first_rule.click(force=True)
    page.wait_for_timeout(800)
    right_col.get_by_text(COMMON_RULE_EDIT_HINT, exact=False).wait_for(state="visible", timeout=timeout_ms)
    right_col.get_by_text("编辑", exact=True).click(force=True)
    return wait_for_modal(page, f"{COMMON_RULE_CATEGORY_NAME}-编辑规则", timeout_ms=timeout_ms)


def assert_visible_system_rule_rows_have_system_badges(middle_col: Locator) -> None:
    rows = collect_visible_rule_rows(middle_col)
    assert rows, "通用审查点下未加载出任何审查规则。"
    for row in rows:
        row_text = normalize_row_text(row.inner_text())
        assert "系统" in row_text, f"系统规则行缺少“系统”标识: {row_text}"


def wait_for_text_in_locator(locator: Locator, expected_text: str, timeout_ms: int) -> None:
    deadline = time.monotonic() + (timeout_ms / 1000)
    last_seen = ""
    while time.monotonic() < deadline:
        last_seen = normalize_row_text(locator.inner_text())
        if expected_text in last_seen:
            return
        locator.page.wait_for_timeout(300)
    raise AssertionError(f"未在目标区域内看到文案: {expected_text}，当前文本: {last_seen}")


def test_review_rule_common_category_inventory_and_system_badges() -> None:
    with sync_playwright() as playwright:
        config = load_review_config()
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            _, left_col, middle_col, _ = open_review_rule_page(page)
            common_item = wait_for_list_item(left_col, COMMON_RULE_CATEGORY_NAME, timeout_ms=config.ui_timeout_ms, exact=True)
            assert common_item.locator("img.always-show-action").is_visible(), "通用审查点分类未显示锁定标识。"
            assert common_item.locator("a").count() == 0, "通用审查点分类不应出现编辑或删除操作。"

            common_item.click(force=True)
            wait_for_text_in_locator(middle_col, COMMON_RULE_TOTAL_TEXT, timeout_ms=config.ui_timeout_ms)
            assert_visible_system_rule_rows_have_system_badges(middle_col)
            save_rule_module_screenshot(page, "common-category", "success")
        except Exception:
            save_rule_module_screenshot(page, "common-category", "failed")
            raise
        finally:
            context.close()
            browser.close()


def test_review_rule_common_rule_edit_modal_allows_only_risk_description() -> None:
    with sync_playwright() as playwright:
        config = load_review_config()
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            _, left_col, middle_col, right_col = open_review_rule_page(page)
            wait_for_list_item(left_col, COMMON_RULE_CATEGORY_NAME, timeout_ms=config.ui_timeout_ms, exact=True).click(
                force=True
            )
            wait_for_text_in_locator(middle_col, COMMON_RULE_TOTAL_TEXT, timeout_ms=config.ui_timeout_ms)

            first_rule = middle_col.locator(".ant-list-item").first
            hover_rule_row(first_rule)
            assert first_rule.locator("a").count() == 0, "通用审查点下的系统规则不应支持删除。"

            modal = open_common_rule_edit_modal(page, middle_col, right_col, timeout_ms=config.ui_timeout_ms)

            rule_name_input = modal.locator('input[placeholder="请输入规则名称"]').first
            risk_description = modal.locator('textarea[placeholder="请输入风险说明"]').first
            rule_logic = modal.locator('textarea[placeholder="请输入审查逻辑"]')

            rule_name_input.wait_for(state="visible", timeout=config.ui_timeout_ms)
            risk_description.wait_for(state="visible", timeout=config.ui_timeout_ms)
            assert rule_name_input.is_disabled(), "系统规则的规则名称不应可编辑。"
            assert risk_description.is_editable(), "系统规则的风险说明应保持可编辑。"
            assert rule_logic.count() == 0 or not rule_logic.first.is_visible(), "系统规则编辑弹窗不应暴露审查逻辑编辑框。"

            visible_fields = []
            editable_fields = []
            for locator in modal.locator("input, textarea").all():
                if not locator.is_visible():
                    continue
                visible_fields.append(locator)
                if locator.is_editable():
                    editable_fields.append(locator)
            assert len(visible_fields) >= 2, "系统规则编辑弹窗字段数量异常。"
            assert len(editable_fields) == 1, "系统规则编辑弹窗中仅应存在一个可编辑字段。"

            original_risk_description = risk_description.input_value()
            updated_risk_description = f"{original_risk_description}测试"
            risk_description.fill(updated_risk_description)
            assert risk_description.input_value() == updated_risk_description, "风险说明输入框未表现出可编辑能力。"
            risk_description.fill(original_risk_description)

            click_visible_button(modal, "取消", timeout_ms=config.ui_timeout_ms)
            modal.wait_for(state="hidden", timeout=config.ui_timeout_ms)
            save_rule_module_screenshot(page, "common-rule-edit", "success")
        except Exception:
            save_rule_module_screenshot(page, "common-rule-edit", "failed")
            raise
        finally:
            context.close()
            browser.close()


def test_review_rule_create_and_delete_closed_loop() -> None:
    with sync_playwright() as playwright:
        config = load_review_config()
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        created_category_name: str | None = None
        created_rule_name: str | None = None
        left_col: Locator | None = None
        middle_col: Locator | None = None
        right_col: Locator | None = None
        try:
            _, left_col, middle_col, right_col = open_review_rule_page(page)
            cleanup_rule_categories_by_prefix(page, left_col, TEMP_RULE_CATEGORY_PREFIX, timeout_ms=config.ui_timeout_ms)

            created_category_name = build_temp_checklist_name(TEMP_RULE_CATEGORY_PREFIX)
            create_rule_category_on_rule_page(
                page,
                left_col,
                created_category_name,
                timeout_ms=config.ui_timeout_ms,
            )

            created_rule_name = build_temp_checklist_name(TEMP_RULE_NAME_PREFIX)
            rule_item = create_rule_on_rule_page(
                page,
                left_col,
                middle_col,
                page,
                created_category_name,
                created_rule_name,
                timeout_ms=config.ui_timeout_ms,
            )
            rule_text = normalize_row_text(rule_item.inner_text())
            assert created_rule_name in rule_text, "新建规则后未看到规则名称。"
            assert "人工" in rule_text, "新建自定义规则后未看到“人工”标识。"
            assert "系统" not in rule_text, "新建自定义规则不应带有“系统”标识。"

            delete_rule_on_rule_page(
                page,
                middle_col,
                created_rule_name,
                timeout_ms=config.ui_timeout_ms,
            )
            created_rule_name = None

            delete_rule_category_in_modal(
                page,
                left_col,
                created_category_name,
                timeout_ms=config.ui_timeout_ms,
            )
            created_category_name = None
            save_rule_module_screenshot(page, "create-delete-closed-loop", "success")
        except Exception:
            save_rule_module_screenshot(page, "create-delete-closed-loop", "failed")
            raise
        finally:
            if left_col is not None and created_category_name:
                try:
                    delete_rule_category_in_modal(
                        page,
                        left_col,
                        created_category_name,
                        timeout_ms=config.ui_timeout_ms,
                    )
                except Exception:
                    pass
            context.close()
            browser.close()


def test_review_rule_duplicate_category_name_is_rejected() -> None:
    with sync_playwright() as playwright:
        config = load_review_config()
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        left_col: Locator | None = None
        created_category_name: str | None = None
        try:
            _, left_col, _, _ = open_review_rule_page(page)
            cleanup_rule_categories_by_prefix(page, left_col, TEMP_RULE_CATEGORY_PREFIX, timeout_ms=config.ui_timeout_ms)
            created_category_name = build_temp_checklist_name(TEMP_RULE_CATEGORY_PREFIX)
            create_rule_category_on_rule_page(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)
            assert count_category_items_by_name(left_col, created_category_name) == 1, "前置分类创建失败。"

            edit_item, textarea = open_new_rule_category_draft(page, left_col, timeout_ms=config.ui_timeout_ms)
            textarea.fill(created_category_name)
            trigger_rule_category_submit_on_rule_page(page, edit_item)
            page.wait_for_timeout(2000)

            assert count_category_items_by_name(left_col, created_category_name) == 1, "规则分类出现了重复名称。"
            save_rule_module_screenshot(page, "duplicate-category", "success")
        except Exception:
            save_rule_module_screenshot(page, "duplicate-category", "failed")
            raise
        finally:
            if left_col is not None:
                try:
                    cleanup_rule_categories_by_prefix(page, left_col, TEMP_RULE_CATEGORY_PREFIX, timeout_ms=config.ui_timeout_ms)
                except Exception:
                    pass
            context.close()
            browser.close()


def test_review_rule_duplicate_rule_name_is_rejected() -> None:
    with sync_playwright() as playwright:
        config = load_review_config()
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        left_col: Locator | None = None
        middle_col: Locator | None = None
        created_category_name: str | None = None
        created_rule_name: str | None = None
        try:
            _, left_col, middle_col, _ = open_review_rule_page(page)
            cleanup_rule_categories_by_prefix(page, left_col, TEMP_RULE_CATEGORY_PREFIX, timeout_ms=config.ui_timeout_ms)
            created_category_name = build_temp_checklist_name(TEMP_RULE_CATEGORY_PREFIX)
            create_rule_category_on_rule_page(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)

            created_rule_name = build_indexed_temp_name(TEMP_RULE_NAME_PREFIX, 1)
            create_rule_on_rule_page(
                page,
                left_col,
                middle_col,
                page,
                created_category_name,
                created_rule_name,
                timeout_ms=config.ui_timeout_ms,
            )
            before_count = count_rule_items_by_name(middle_col, created_rule_name)
            assert before_count == 1, "前置规则创建失败。"

            open_rule_editor(page, left_col, middle_col, created_category_name, timeout_ms=config.ui_timeout_ms)
            fill_rule_form(page, created_rule_name)
            save_button = get_last_visible_button_by_text(page, "保存", timeout_ms=config.ui_timeout_ms)
            if save_button.is_enabled():
                save_button.click(force=True)
                page.wait_for_timeout(1500)
            else:
                close_rule_editor_if_visible(page)

            assert count_rule_items_by_name(middle_col, created_rule_name) == 1, "规则名称重复时仍然新增了第二条规则。"
            close_rule_editor_if_visible(page)
            save_rule_module_screenshot(page, "duplicate-rule", "success")
        except Exception:
            save_rule_module_screenshot(page, "duplicate-rule", "failed")
            raise
        finally:
            close_rule_editor_if_visible(page)
            if middle_col is not None and created_rule_name:
                try:
                    delete_rule_on_rule_page(page, middle_col, created_rule_name, timeout_ms=config.ui_timeout_ms)
                except Exception:
                    pass
            if left_col is not None and created_category_name:
                try:
                    delete_rule_category_in_modal(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)
                except Exception:
                    pass
            context.close()
            browser.close()


def test_review_rule_batch_delete_closed_loop() -> None:
    with sync_playwright() as playwright:
        config = load_review_config()
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        left_col: Locator | None = None
        middle_col: Locator | None = None
        created_category_name: str | None = None
        created_rule_names: list[str] = []
        try:
            _, left_col, middle_col, _ = open_review_rule_page(page)
            cleanup_rule_categories_by_prefix(page, left_col, TEMP_RULE_CATEGORY_PREFIX, timeout_ms=config.ui_timeout_ms)
            created_category_name = build_temp_checklist_name(TEMP_RULE_CATEGORY_PREFIX)
            create_rule_category_on_rule_page(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)

            for index in (1, 2):
                rule_name = build_indexed_temp_name(TEMP_RULE_NAME_PREFIX, index)
                create_rule_on_rule_page(
                    page,
                    left_col,
                    middle_col,
                    page,
                    created_category_name,
                    rule_name,
                    timeout_ms=config.ui_timeout_ms,
                )
                created_rule_names.append(rule_name)

            for rule_name in created_rule_names:
                check_rule_row(middle_col, rule_name, timeout_ms=config.ui_timeout_ms)
                page.wait_for_timeout(600)

            click_visible_link(page, "批量删除", timeout_ms=config.ui_timeout_ms)
            confirmation_layer = wait_for_visible_confirmation_layer(
                page,
                ("批量删除", "删除"),
                timeout_ms=config.ui_timeout_ms,
            )
            click_rightmost_visible_button_in_layer(
                confirmation_layer,
                ("删除", "确定"),
                timeout_ms=config.ui_timeout_ms,
            )
            page.wait_for_timeout(1500)

            for rule_name in created_rule_names:
                wait_for_list_item_hidden(middle_col, rule_name, timeout_ms=config.ui_timeout_ms)
            created_rule_names = []

            delete_rule_category_in_modal(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)
            created_category_name = None
            save_rule_module_screenshot(page, "batch-delete", "success")
        except Exception:
            save_rule_module_screenshot(page, "batch-delete", "failed")
            raise
        finally:
            if middle_col is not None:
                for rule_name in created_rule_names:
                    try:
                        delete_rule_on_rule_page(page, middle_col, rule_name, timeout_ms=config.ui_timeout_ms)
                    except Exception:
                        pass
            if left_col is not None and created_category_name:
                try:
                    delete_rule_category_in_modal(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)
                except Exception:
                    pass
            context.close()
            browser.close()


def test_review_rule_batch_change_category_closed_loop() -> None:
    with sync_playwright() as playwright:
        config = load_review_config()
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        left_col: Locator | None = None
        middle_col: Locator | None = None
        created_category_name: str | None = None
        target_category_name: str | None = None
        moved_rule_names: list[str] = []
        try:
            _, left_col, middle_col, _ = open_review_rule_page(page)
            cleanup_rule_categories_by_prefix(page, left_col, TEMP_RULE_CATEGORY_PREFIX, timeout_ms=config.ui_timeout_ms)

            created_category_name = build_temp_checklist_name(TEMP_RULE_CATEGORY_PREFIX)
            create_rule_category_on_rule_page(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)
            target_category_name = build_temp_checklist_name(TEMP_RULE_CATEGORY_PREFIX)
            create_rule_category_on_rule_page(page, left_col, target_category_name, timeout_ms=config.ui_timeout_ms)

            for index in (1, 2):
                rule_name = build_indexed_temp_name(TEMP_RULE_NAME_PREFIX, index)
                create_rule_on_rule_page(
                    page,
                    left_col,
                    middle_col,
                    page,
                    created_category_name,
                    rule_name,
                    timeout_ms=config.ui_timeout_ms,
                )
                moved_rule_names.append(rule_name)

            for rule_name in moved_rule_names:
                check_rule_row(middle_col, rule_name, timeout_ms=config.ui_timeout_ms)
                page.wait_for_timeout(600)

            click_visible_link(page, "修改规则分类", timeout_ms=config.ui_timeout_ms)
            popover = wait_for_visible_popover(page, "修改规则分类", timeout_ms=config.ui_timeout_ms)
            popover.locator(".ant-select").first.click(force=True)
            option = page.locator(".ant-select-item-option").filter(has_text=target_category_name).first
            option.wait_for(state="visible", timeout=config.ui_timeout_ms)
            option.click(force=True)
            click_rightmost_visible_button_in_layer(
                popover,
                ("确定",),
                timeout_ms=config.ui_timeout_ms,
            )
            final_confirmation_layer = wait_for_visible_confirmation_layer(
                page,
                ("修改规则分类", "修改"),
                timeout_ms=config.ui_timeout_ms,
            )
            click_rightmost_visible_button_in_layer(
                final_confirmation_layer,
                ("修改", "确定"),
                timeout_ms=config.ui_timeout_ms,
            )
            page.wait_for_timeout(1500)

            for rule_name in moved_rule_names:
                wait_for_list_item_hidden(middle_col, rule_name, timeout_ms=config.ui_timeout_ms)

            wait_for_list_item(left_col, target_category_name, timeout_ms=config.ui_timeout_ms, exact=True).click(force=True)
            page.wait_for_timeout(1000)
            for rule_name in moved_rule_names:
                wait_for_list_item(middle_col, rule_name, timeout_ms=config.ui_timeout_ms, exact=False)

            for rule_name in moved_rule_names:
                delete_rule_on_rule_page(page, middle_col, rule_name, timeout_ms=config.ui_timeout_ms)
            moved_rule_names = []

            wait_for_list_item(left_col, created_category_name, timeout_ms=config.ui_timeout_ms, exact=True).click(force=True)
            delete_rule_category_in_modal(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)
            created_category_name = None
            delete_rule_category_in_modal(page, left_col, target_category_name, timeout_ms=config.ui_timeout_ms)
            target_category_name = None
            save_rule_module_screenshot(page, "batch-change-category", "success")
        except Exception:
            save_rule_module_screenshot(page, "batch-change-category", "failed")
            raise
        finally:
            if middle_col is not None and target_category_name and moved_rule_names:
                try:
                    wait_for_list_item(left_col, target_category_name, timeout_ms=config.ui_timeout_ms, exact=True).click(force=True)
                    page.wait_for_timeout(800)
                    for rule_name in moved_rule_names:
                        try:
                            delete_rule_on_rule_page(page, middle_col, rule_name, timeout_ms=config.ui_timeout_ms)
                        except Exception:
                            pass
                except Exception:
                    pass
            if left_col is not None and created_category_name:
                try:
                    delete_rule_category_in_modal(page, left_col, created_category_name, timeout_ms=config.ui_timeout_ms)
                except Exception:
                    pass
            if left_col is not None and target_category_name:
                try:
                    delete_rule_category_in_modal(page, left_col, target_category_name, timeout_ms=config.ui_timeout_ms)
                except Exception:
                    pass
            context.close()
            browser.close()
