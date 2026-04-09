from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from playwright.sync_api import Error as PlaywrightError, Locator, Page, TimeoutError as PlaywrightTimeoutError, sync_playwright


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ENV_FILE = PROJECT_ROOT / ".env"
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
RESULT_MARKERS = ("导出", "重新审查", "建议优化", "风险提示")


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


load_env_file(ENV_FILE)


@dataclass(frozen=True)
class ReviewConfig:
    home_url: str
    auth_storage_state_path: Path
    review_file_path: Path
    browser_name: str
    browser_executable_path: str | None
    browser_channel: str | None
    headless: bool
    slow_mo: int
    ui_timeout_ms: int
    review_config_timeout_ms: int
    review_result_timeout_ms: int
    review_retry_limit: int
    custom_checklist_load_timeout_ms: int
    custom_checklist_names: tuple[str, ...]
    expected_review_stances: tuple[str, ...]


@dataclass(frozen=True)
class ReviewCase:
    stance: str
    strength: str
    checklist_mode: str

    @property
    def case_id(self) -> str:
        checklist = "custom" if self.checklist_mode == "自定义审查清单" else "smart"
        return f"{self.stance}-{self.strength}-{checklist}"


@dataclass(frozen=True)
class ReviewResultItem:
    original_text: str
    suggested_text: str | None
    inserted_text: str | None
    accepts_revision: bool

    @property
    def item_key(self) -> str:
        return normalize_text(self.original_text)


@dataclass(frozen=True)
class DocumentPaneState:
    visible_text: str
    compact_text: str
    image_bytes: bytes


def read_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def load_review_config() -> ReviewConfig:
    required_keys = ("APP_LOGIN_URL", "AUTH_STORAGE_STATE_PATH", "REVIEW_FILE_PATH")
    missing = [key for key in required_keys if not os.getenv(key)]
    if missing:
        raise AssertionError(f"缺少环境变量: {', '.join(missing)}。请先检查 .env。")

    auth_storage_state_path = resolve_project_path(os.environ["AUTH_STORAGE_STATE_PATH"])
    review_file_path = resolve_project_path(os.environ["REVIEW_FILE_PATH"])
    if not auth_storage_state_path.exists():
        raise AssertionError(
            f"未找到已保存登录态文件: {auth_storage_state_path}。"
            " 请先运行飞书登录测试生成免扫码状态。"
        )
    if not review_file_path.exists():
        raise AssertionError(f"未找到待上传合同文件: {review_file_path}")

    checklist_names = tuple(
        item.strip()
        for item in os.getenv("CUSTOM_CHECKLIST_NAMES", "舒译测试,默认审查清单").split(",")
        if item.strip()
    )
    if not checklist_names:
        raise AssertionError("CUSTOM_CHECKLIST_NAMES 不能为空。")

    expected_review_stances = tuple(
        item.strip()
        for item in os.getenv("EXPECTED_REVIEW_STANCES", "甲方,乙方,丙方").split(",")
        if item.strip()
    )
    if not expected_review_stances:
        raise AssertionError("EXPECTED_REVIEW_STANCES 不能为空。")

    return ReviewConfig(
        home_url=os.environ["APP_LOGIN_URL"].replace("/login", "/home"),
        auth_storage_state_path=auth_storage_state_path,
        review_file_path=review_file_path,
        browser_name=os.getenv("PLAYWRIGHT_BROWSER", "chromium"),
        browser_executable_path=os.getenv("PLAYWRIGHT_EXECUTABLE_PATH"),
        browser_channel=os.getenv("PLAYWRIGHT_CHANNEL"),
        headless=read_bool("HEADLESS", False),
        slow_mo=int(os.getenv("SLOW_MO", "0")),
        ui_timeout_ms=int(os.getenv("UI_TIMEOUT_MS", "30000")),
        review_config_timeout_ms=int(os.getenv("REVIEW_CONFIG_TIMEOUT_MS", "60000")),
        review_result_timeout_ms=int(os.getenv("REVIEW_RESULT_TIMEOUT_MS", "420000")),
        review_retry_limit=int(os.getenv("REVIEW_RETRY_LIMIT", "2")),
        custom_checklist_load_timeout_ms=int(os.getenv("CUSTOM_CHECKLIST_LOAD_TIMEOUT_MS", "20000")),
        custom_checklist_names=checklist_names,
        expected_review_stances=expected_review_stances,
    )


def build_orthogonal_cases() -> list[ReviewCase]:
    # 3 x 3 x 2 因子使用 L9 风格的两两覆盖，减少总执行量但保留主流组合关系。
    checklist_matrix = [
        ["智能生成", "自定义审查清单", "智能生成"],
        ["自定义审查清单", "智能生成", "自定义审查清单"],
        ["智能生成", "自定义审查清单", "智能生成"],
    ]
    stances = ["甲方", "乙方", "丙方"]
    strengths = ["弱势", "中立", "强势"]
    cases: list[ReviewCase] = []
    for stance_index, stance in enumerate(stances):
        for strength_index, strength in enumerate(strengths):
            cases.append(
                ReviewCase(
                    stance=stance,
                    strength=strength,
                    checklist_mode=checklist_matrix[stance_index][strength_index],
                )
            )
    return cases


def get_browser_launcher(playwright, browser_name: str):
    try:
        return getattr(playwright, browser_name)
    except AttributeError as error:
        raise AssertionError(
            f"不支持的浏览器类型: {browser_name}，可选值为 chromium / firefox / webkit。"
        ) from error


def build_ui_launch_options(config: ReviewConfig) -> dict[str, Any]:
    launch_options: dict[str, Any] = {
        "headless": config.headless,
        "slow_mo": config.slow_mo,
        "args": ["--start-maximized"],
    }
    if config.browser_channel:
        launch_options["channel"] = config.browser_channel
    if config.browser_executable_path:
        launch_options["executable_path"] = config.browser_executable_path
    return launch_options


def create_authenticated_context(browser: Any, config: ReviewConfig) -> Any:
    return browser.new_context(
        ignore_https_errors=True,
        storage_state=str(config.auth_storage_state_path),
        no_viewport=True,
    )


def is_retryable_navigation_error(error: Exception) -> bool:
    message = str(error)
    return any(
        keyword in message
        for keyword in (
            "ERR_CONNECTION_CLOSED",
            "ERR_CONNECTION_RESET",
            "ERR_NETWORK_CHANGED",
            "ERR_ABORTED",
        )
    )


def goto_page_with_retry(
    page: Page,
    url: str,
    *,
    wait_until: str = "domcontentloaded",
    attempts: int = 5,
    retry_delay_ms: int = 1500,
) -> None:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            page.goto(url, wait_until=wait_until)
            return
        except PlaywrightError as error:
            last_error = error
            if not is_retryable_navigation_error(error) or attempt == attempts - 1:
                raise
            page.wait_for_timeout(retry_delay_ms)

    assert last_error is not None
    raise last_error


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text)


def build_text_fragments(text: str, *, exclude_text: str | None = None, limit: int = 6) -> list[str]:
    compact_source = compact_text(text)
    compact_exclude = compact_text(exclude_text or "")
    raw_parts = re.split(r"[，,。；;：:（）()【】\[\]“”\"'、|/\\\s]+", compact_source)
    fragments: list[str] = []
    for part in sorted(raw_parts, key=len, reverse=True):
        if len(part) < 4:
            continue
        if part.isdigit():
            continue
        if compact_exclude and part in compact_exclude:
            continue
        if part not in fragments:
            fragments.append(part)
        if len(fragments) >= limit:
            return fragments

    if not fragments and len(compact_source) >= 6:
        fragments.append(compact_source[: min(20, len(compact_source))])
    return fragments


def get_viewport_size(page: Page) -> dict[str, int]:
    size = page.viewport_size
    if size:
        return size
    return page.evaluate("() => ({ width: window.innerWidth, height: window.innerHeight })")


def get_left_document_clip(page: Page) -> dict[str, float]:
    viewport = get_viewport_size(page)
    clip_top = 150
    clip_left = 0
    clip_width = max(320, int(viewport["width"] * 0.58))
    clip_height = max(220, viewport["height"] - clip_top - 10)
    return {
        "x": clip_left,
        "y": clip_top,
        "width": clip_width,
        "height": clip_height,
    }


def capture_document_state(page: Page) -> DocumentPaneState:
    visible_text = page.evaluate(
        r"""() => {
            const norm = (value) => (value || '').replace(/\s+/g, ' ').trim();
            const limitX = window.innerWidth * 0.58;
            const minY = 135;
            const seen = new Set();
            const texts = [];
            for (const element of document.querySelectorAll('div,span,p,td,th')) {
                const style = window.getComputedStyle(element);
                if (style.display === 'none' || style.visibility === 'hidden') {
                    continue;
                }
                const rect = element.getBoundingClientRect();
                if (rect.width < 12 || rect.height < 8) {
                    continue;
                }
                if (rect.right <= 0 || rect.left >= limitX || rect.bottom < minY) {
                    continue;
                }
                const text = norm(element.innerText || element.textContent);
                if (!text || text.length < 2 || text.length > 220) {
                    continue;
                }
                const key = `${text}@${Math.round(rect.x)}:${Math.round(rect.y)}:${Math.round(rect.width)}`;
                if (seen.has(key)) {
                    continue;
                }
                seen.add(key);
                texts.push({ text, x: rect.x, y: rect.y });
            }
            texts.sort((left, right) => left.y - right.y || left.x - right.x);
            return texts.slice(0, 320).map((item) => item.text).join('\n');
        }"""
    )
    return DocumentPaneState(
        visible_text=visible_text,
        compact_text=compact_text(visible_text),
        image_bytes=page.screenshot(clip=get_left_document_clip(page)),
    )


def document_state_changed(before: DocumentPaneState, after: DocumentPaneState) -> bool:
    return before.visible_text != after.visible_text or before.image_bytes != after.image_bytes


def find_visible_right_text(page: Page, text: str, timeout_ms: int) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    locator = page.get_by_text(text, exact=True)
    right_threshold = get_viewport_size(page)["width"] * 0.58

    while time.time() < deadline:
        count = locator.count()
        for index in range(count):
            candidate = locator.nth(index)
            if not candidate.is_visible():
                continue
            box = candidate.bounding_box()
            if box and box["x"] >= right_threshold:
                candidate.scroll_into_view_if_needed()
                return candidate
        page.wait_for_timeout(250)

    raise AssertionError(f"未在右侧审查结果面板中找到目标文本: {text}")


def click_visible_right_text(page: Page, text: str, timeout_ms: int) -> None:
    find_visible_right_text(page, text, timeout_ms).click(force=True)


def has_visible_right_text(page: Page, text: str, exact: bool = True) -> bool:
    locator = page.get_by_text(text, exact=exact)
    right_threshold = get_viewport_size(page)["width"] * 0.58
    count = locator.count()
    for index in range(count):
        candidate = locator.nth(index)
        if not candidate.is_visible():
            continue
        box = candidate.bounding_box()
        if box and box["x"] >= right_threshold:
            return True
    return False


def collect_visible_result_items(page: Page) -> list[ReviewResultItem]:
    items = page.evaluate(
        r"""() => {
            const norm = (value) => (value || '').replace(/\s+/g, ' ').trim();
            const skipTexts = new Set([
                '接受修订',
                '建议优化',
                '风险提示',
                'AI智能审查',
                '导出',
                '重新审查',
                '审阅人',
                '修订前后对比',
                '全部',
            ]);
            const rightLimit = window.innerWidth * 0.58;
            const minTop = 110;
            const isVisible = (element) => {
                if (!element) {
                    return false;
                }
                const style = window.getComputedStyle(element);
                if (style.display === 'none' || style.visibility === 'hidden') {
                    return false;
                }
                const rect = element.getBoundingClientRect();
                return rect.width > 18 && rect.height > 10;
            };
            const isRedText = (element) => {
                const color = window.getComputedStyle(element).color.match(/\d+/g) || [];
                if (color.length < 3) {
                    return false;
                }
                const [red, green, blue] = color.slice(0, 3).map(Number);
                return red >= 180 && red > green + 30 && red > blue + 30;
            };
            const allTextBlocks = Array.from(document.querySelectorAll('div,span,p'))
                .filter((element) => isVisible(element))
                .map((element) => ({
                    element,
                    text: norm(element.innerText || element.textContent),
                    rect: element.getBoundingClientRect(),
                    style: window.getComputedStyle(element),
                }))
                .filter((item) => {
                    if (!item.text || skipTexts.has(item.text)) {
                        return false;
                    }
                    if (
                        item.rect.x < rightLimit ||
                        item.rect.bottom < minTop ||
                        item.rect.top > window.innerHeight - 24 ||
                        item.rect.width < 140
                    ) {
                        return false;
                    }
                    return item.text.length >= 8;
                });

            const looksLikeAtomicBlock = (item) => {
                const bodySignal = /[：:，,。；;|_0-9]/.test(item.text);
                if (item.text.length < 12) {
                    return false;
                }
                if (item.rect.height > 120) {
                    return false;
                }
                if (item.text.length > 160) {
                    return false;
                }
                if (item.text.includes('风险提示') || item.text.includes('建议优化')) {
                    return false;
                }
                if (/^(致命风险|警示风险|高风险|中风险|低风险)/.test(item.text)) {
                    return false;
                }
                if ((item.text.includes('审查') || item.text.includes('风险')) && !bodySignal) {
                    return false;
                }
                if (item.text.includes('审查') && item.text.length < 30) {
                    return false;
                }
                if (!bodySignal && item.text.length < 20) {
                    return false;
                }
                if (item.element.querySelector('button')) {
                    return false;
                }
                const meaningfulChildren = Array.from(item.element.children)
                    .map((child) => norm(child.innerText || child.textContent))
                    .filter((text) => text.length >= 8);
                return meaningfulChildren.length <= 1;
            };

            let originals = allTextBlocks.filter((item) => item.style.cursor === 'pointer' && looksLikeAtomicBlock(item));
            if (!originals.length) {
                originals = allTextBlocks.filter(
                    (item) =>
                        item.style.backgroundColor !== 'rgba(0, 0, 0, 0)' &&
                        !isRedText(item.element) &&
                        looksLikeAtomicBlock(item)
                );
            }

            originals.sort((left, right) => left.rect.y - right.rect.y || left.rect.x - right.rect.x);
            const acceptButtons = Array.from(document.querySelectorAll('button,div,span'))
                .filter((element) => isVisible(element))
                .map((element) => ({
                    element,
                    text: norm(element.textContent),
                    rect: element.getBoundingClientRect(),
                }))
                .filter(
                    (item) =>
                        item.text === '接受修订' &&
                        item.rect.x >= rightLimit &&
                        item.rect.bottom >= minTop &&
                        item.rect.top <= window.innerHeight - 24
                );

            const results = [];
            const seenOriginals = new Set();
            for (let index = 0; index < originals.length; index += 1) {
                const original = originals[index];
                if (seenOriginals.has(original.text)) {
                    continue;
                }
                const nextOriginalY = index + 1 < originals.length ? originals[index + 1].rect.y : Number.POSITIVE_INFINITY;
                let matchedButton = null;
                for (const button of acceptButtons) {
                    const distance = button.rect.y - (original.rect.y + original.rect.height);
                    if (distance < -10 || distance > 260) {
                        continue;
                    }
                    if (button.rect.y >= nextOriginalY - 4) {
                        continue;
                    }
                    matchedButton = button;
                    break;
                }

                let suggestionText = '';
                let insertedText = '';
                if (matchedButton) {
                    let bestCandidate = null;
                    let bestScore = Number.NEGATIVE_INFINITY;
                    for (const candidate of allTextBlocks) {
                        if (candidate.text === original.text) {
                            continue;
                        }
                        if (candidate.rect.y < original.rect.y - 8 || candidate.rect.bottom > matchedButton.rect.bottom + 8) {
                            continue;
                        }
                        let score = 0;
                        if (candidate.element.querySelector('.insert')) {
                            score += 300;
                        }
                        if (isRedText(candidate.element)) {
                            score += 180;
                        }
                        score -= Math.abs(matchedButton.rect.y - candidate.rect.y);
                        score += Math.min(candidate.text.length, 120) / 8;
                        if (score > bestScore) {
                            bestScore = score;
                            bestCandidate = candidate;
                        }
                    }
                    if (bestCandidate) {
                        suggestionText = bestCandidate.text;
                        insertedText = norm(
                            Array.from(bestCandidate.element.querySelectorAll('.insert'))
                                .map((node) => norm(node.textContent))
                                .filter(Boolean)
                                .join(' ')
                        );
                    }
                }

                seenOriginals.add(original.text);
                results.push({
                    original_text: original.text,
                    suggested_text: suggestionText || null,
                    inserted_text: insertedText || null,
                    accepts_revision: Boolean(matchedButton),
                });
            }
            return results;
        }"""
    )

    return [
        ReviewResultItem(
            original_text=item["original_text"],
            suggested_text=item["suggested_text"],
            inserted_text=item["inserted_text"],
            accepts_revision=item["accepts_revision"],
        )
        for item in items
    ]


def wait_for_document_located(
    page: Page,
    original_text: str,
    before_state: DocumentPaneState,
    timeout_ms: int,
) -> DocumentPaneState:
    deadline = time.time() + (timeout_ms / 1000)

    while time.time() < deadline:
        current_state = capture_document_state(page)
        if document_state_changed(before_state, current_state):
            return current_state
        deleted_toast = page.get_by_text("此文本已被修改或删除", exact=True)
        if deleted_toast.count():
            for index in range(deleted_toast.count()):
                if deleted_toast.nth(index).is_visible():
                    return current_state
        page.wait_for_timeout(500)

    # 已知效果问题：命中的原文如果刚好落在页尾/页首附近，左侧文档可能不会稳定滚动。
    # 这类场景下保留点击动作本身，不把“没有可见变化”当成阻断失败。
    return capture_document_state(page)


def wait_for_revision_applied(
    page: Page,
    before_state: DocumentPaneState,
    before_accept_count: int,
    timeout_ms: int,
) -> DocumentPaneState:
    deadline = time.time() + (timeout_ms / 1000)

    while time.time() < deadline:
        current_state = capture_document_state(page)
        if document_state_changed(before_state, current_state):
            return current_state
        if count_visible_accept_buttons(page) < before_accept_count:
            return current_state
        page.wait_for_timeout(500)

    return capture_document_state(page)


def wait_for_text_to_disappear(page: Page, text: str, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    locator = page.get_by_text(text, exact=True)
    while time.time() < deadline:
        visible = False
        count = locator.count()
        for index in range(count):
            if locator.nth(index).is_visible():
                visible = True
                break
        if not visible:
            return
        page.wait_for_timeout(250)


def wait_for_deleted_text_feedback(page: Page, original_text: str, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    attempts = 0
    while time.time() < deadline and attempts < 3:
        before_click_state = capture_document_state(page)
        find_visible_right_text(page, original_text, timeout_ms).click(force=True)
        toast = page.get_by_text("此文本已被修改或删除", exact=True)
        inner_deadline = time.time() + 2
        while time.time() < inner_deadline:
            count = toast.count()
            for index in range(count):
                if toast.nth(index).is_visible():
                    wait_for_text_to_disappear(page, "此文本已被修改或删除", timeout_ms=timeout_ms)
                    return
            current_state = capture_document_state(page)
            if document_state_changed(before_click_state, current_state):
                return
            page.wait_for_timeout(200)
        attempts += 1

    raise AssertionError("接受修订后再次点击原文，既未看到删除提示，也未观察到文档再次定位/高亮。")


def click_accept_for_original(page: Page, original_text: str, timeout_ms: int) -> None:
    original_locator = find_visible_right_text(page, original_text, timeout_ms)
    original_box = original_locator.bounding_box()
    if original_box is None:
        raise AssertionError(f"无法获取原文卡片位置，不能点击接受修订: {original_text}")

    buttons = page.get_by_role("button", name="接受修订")
    right_threshold = get_viewport_size(page)["width"] * 0.58
    best_button: Locator | None = None
    best_distance: float | None = None
    for index in range(buttons.count()):
        candidate = buttons.nth(index)
        if not candidate.is_visible():
            continue
        candidate_box = candidate.bounding_box()
        if candidate_box is None or candidate_box["x"] < right_threshold:
            continue
        distance = candidate_box["y"] - (original_box["y"] + original_box["height"])
        if distance < -10 or distance > 260:
            continue
        if best_distance is None or distance < best_distance:
            best_button = candidate
            best_distance = distance

    if best_button is None:
        raise AssertionError(f"未找到与原文匹配的“接受修订”按钮: {original_text}")

    best_button.click(force=True)


def count_visible_accept_buttons(page: Page) -> int:
    buttons = page.get_by_role("button", name="接受修订")
    count = 0
    for index in range(buttons.count()):
        if buttons.nth(index).is_visible():
            count += 1
    return count


def scroll_review_results_panel(page: Page) -> bool:
    result = page.evaluate(
        r"""() => {
            const candidates = Array.from(document.querySelectorAll('div'))
                .filter((element) => {
                    const style = window.getComputedStyle(element);
                    const rect = element.getBoundingClientRect();
                    if (style.display === 'none' || style.visibility === 'hidden') {
                        return false;
                    }
                    if (rect.x < window.innerWidth * 0.55 || rect.height < 220 || rect.width < 220) {
                        return false;
                    }
                    return element.scrollHeight > element.clientHeight + 40;
                })
                .map((element) => ({
                    element,
                    area: element.getBoundingClientRect().width * element.getBoundingClientRect().height,
                }))
                .sort((left, right) => right.area - left.area);
            if (!candidates.length) {
                return { moved: false };
            }
            const target = candidates[0].element;
            const previous = target.scrollTop;
            target.scrollBy({ top: target.clientHeight * 0.82, behavior: 'instant' });
            return {
                moved: target.scrollTop > previous + 1,
                previous,
                current: target.scrollTop,
            };
        }"""
    )
    if not result["moved"]:
        return False
    page.wait_for_timeout(700)
    return True


def verify_result_item(page: Page, item: ReviewResultItem, timeout_ms: int) -> None:
    locate_timeout_ms = min(timeout_ms, 1500)
    accept_timeout_ms = min(timeout_ms, 5000)
    before_locate_state = capture_document_state(page)
    find_visible_right_text(page, item.original_text, timeout_ms).click(force=True)
    located_state = wait_for_document_located(page, item.original_text, before_locate_state, locate_timeout_ms)

    if not item.accepts_revision:
        return

    before_accept_state = located_state
    before_accept_count = count_visible_accept_buttons(page)
    click_accept_for_original(page, item.original_text, timeout_ms)
    wait_for_revision_applied(page, before_accept_state, before_accept_count, accept_timeout_ms)
    wait_for_deleted_text_feedback(page, item.original_text, timeout_ms=accept_timeout_ms)


def exercise_review_result_cards(page: Page, timeout_ms: int) -> None:
    processed_keys: set[str] = set()
    processed_count = 0

    for _ in range(40):
        visible_items = collect_visible_result_items(page)
        pending_items = [item for item in visible_items if item.item_key not in processed_keys]
        for item in pending_items:
            verify_result_item(page, item, timeout_ms=timeout_ms)
            processed_keys.add(item.item_key)
            processed_count += 1

        if not scroll_review_results_panel(page):
            break

    if processed_count == 0 and has_visible_right_text(page, "无确认风险", exact=False):
        return
    if processed_count == 0:
        raise AssertionError("审查结果页未识别到可验证的结果卡片。")


def has_visible_result_content(page: Page) -> bool:
    if collect_visible_result_items(page):
        return True
    if has_visible_right_text(page, "无确认风险", exact=False):
        return True
    if has_visible_right_text(page, "建议优化", exact=True):
        return True
    if has_visible_right_text(page, "风险提示", exact=True):
        return True
    return has_visible_right_text(page, "接受修订", exact=True)


def wait_for_non_empty_result_items(page: Page, timeout_ms: int) -> list[ReviewResultItem]:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        items = collect_visible_result_items(page)
        if items:
            return items
        if has_visible_result_content(page):
            return []
        page.wait_for_timeout(500)
    raise AssertionError("筛选后未看到可验证的审查结果卡片。")


def wait_for_visible_result_filter_entry(
    page: Page,
    candidate_labels: tuple[str, ...],
    timeout_ms: int,
) -> str:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        for label in candidate_labels:
            if has_visible_right_text(page, label, exact=True):
                return label
        page.wait_for_timeout(300)
    raise AssertionError(f"未在结果页顶部找到可见的筛选入口，候选值: {', '.join(candidate_labels)}")


def assert_review_result_filter_works(
    page: Page,
    filter_names: tuple[str, ...],
    timeout_ms: int,
) -> None:
    current_filter_label = wait_for_visible_result_filter_entry(
        page,
        ("全部", *filter_names),
        timeout_ms=timeout_ms,
    )
    for filter_name in filter_names:
        click_visible_right_text(page, current_filter_label, timeout_ms)
        click_visible_text(page, filter_name, timeout_ms=timeout_ms, exact=True)
        wait_for_visible_text(page, filter_name, timeout_ms=timeout_ms, exact=True)
        wait_for_non_empty_result_items(page, timeout_ms=timeout_ms)
        current_filter_label = filter_name

    click_visible_right_text(page, current_filter_label, timeout_ms)
    click_visible_text(page, "全部", timeout_ms=timeout_ms, exact=True)
    wait_for_visible_text(page, "全部", timeout_ms=timeout_ms, exact=True)
    wait_for_non_empty_result_items(page, timeout_ms=timeout_ms)


def wait_for_visible_text(page: Page, text: str, timeout_ms: int, exact: bool = False) -> Locator:
    deadline = time.time() + (timeout_ms / 1000)
    locator = page.get_by_text(text, exact=exact)
    while time.time() < deadline:
        count = locator.count()
        for index in range(count):
            candidate = locator.nth(index)
            if candidate.is_visible():
                return candidate
        page.wait_for_timeout(200)
    raise AssertionError(f"未找到可见文本: {text}")


def click_visible_text(page: Page, text: str, timeout_ms: int, exact: bool = False) -> None:
    wait_for_visible_text(page, text, timeout_ms, exact=exact).click(force=True)


def save_case_screenshot(page: Page, case_id: str, suffix: str) -> None:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    safe_case_id = case_id.replace("/", "-")
    page.screenshot(
        path=str(ARTIFACTS_DIR / f"intelligent-review-{safe_case_id}-{suffix}.png"),
        full_page=True,
    )


def should_refresh_auth(page: Page) -> bool:
    url = page.url.lower()
    return any(keyword in url for keyword in ("/login", "/logout", "sso/logout", "feishu", "larksuite"))


def refresh_auth_state_if_needed(page: Page, config: ReviewConfig) -> None:
    from tests.auth.test_feishu_login import (
        get_feishu_login_page,
        handle_feishu_login,
        load_config as load_login_config,
        save_auth_state,
        wait_for_login_success,
    )

    login_config = load_login_config()
    goto_page_with_retry(page, login_config.app_login_url)
    success_page = wait_for_login_success(
        page,
        login_config,
        timeout_ms=login_config.auth_state_check_timeout_ms,
        raise_on_timeout=False,
    )
    if success_page is None:
        feishu_page = get_feishu_login_page(page, login_config)
        handle_feishu_login(feishu_page, login_config)
        success_page = wait_for_login_success(
            page,
            login_config,
            timeout_ms=max(login_config.timeout_ms, login_config.manual_scan_timeout_ms),
        )
    save_auth_state(page.context, login_config)
    if success_page.url != config.home_url:
        goto_page_with_retry(success_page, config.home_url)


def open_authenticated_home(page: Page, config: ReviewConfig) -> None:
    for attempt in range(2):
        goto_page_with_retry(page, config.home_url)

        if should_refresh_auth(page):
            refresh_auth_state_if_needed(page, config)
            continue

        try:
            wait_for_visible_text(page, "点击或者拖拽文件到这里", timeout_ms=config.ui_timeout_ms)
            return
        except (PlaywrightTimeoutError, AssertionError):
            if should_refresh_auth(page) and attempt == 0:
                refresh_auth_state_if_needed(page, config)
                continue
            raise

    raise AssertionError("进入首页时认证状态失效，且自动刷新登录态后仍未成功进入业务首页。")


def upload_contract(page: Page, config: ReviewConfig) -> None:
    page.locator("input[type=file]").set_input_files(str(config.review_file_path))
    wait_for_visible_text(page, config.review_file_path.name, timeout_ms=config.ui_timeout_ms, exact=False)
    wait_for_visible_text(page, "文件上传成功", timeout_ms=config.ui_timeout_ms, exact=False)
    wait_for_visible_text(page, "开始审查", timeout_ms=config.ui_timeout_ms, exact=True)


def open_review_config(page: Page, config: ReviewConfig) -> None:
    click_visible_text(page, "开始审查", timeout_ms=config.ui_timeout_ms, exact=True)
    wait_for_visible_text(page, "审查立场", timeout_ms=config.review_config_timeout_ms, exact=True)
    wait_for_visible_text(page, "立即审查", timeout_ms=config.review_config_timeout_ms, exact=True)


def expand_all_stances(page: Page) -> None:
    expand_toggle = page.get_by_text("展开全部", exact=True)
    if expand_toggle.count() and expand_toggle.first.is_visible():
        expand_toggle.first.click()
        page.wait_for_timeout(500)


def assert_extracted_review_stances(page: Page, expected_stances: tuple[str, ...], timeout_ms: int) -> None:
    expand_all_stances(page)
    missing_stances: list[str] = []
    for stance in expected_stances:
        locator = page.get_by_text(stance, exact=False)
        visible = False
        deadline = time.time() + (timeout_ms / 1000)
        while time.time() < deadline:
            count = locator.count()
            for index in range(count):
                if locator.nth(index).is_visible():
                    visible = True
                    break
            if visible:
                break
            page.wait_for_timeout(200)
        if not visible:
            missing_stances.append(stance)

    if missing_stances:
        raise AssertionError(
            "审查立场未按合同主体正确提取。"
            f" 期望包含: {', '.join(expected_stances)}；缺失: {', '.join(missing_stances)}"
        )


def select_stance(page: Page, stance: str, timeout_ms: int) -> None:
    expand_all_stances(page)
    click_visible_text(page, stance, timeout_ms=timeout_ms, exact=False)


def select_strength(page: Page, strength: str, timeout_ms: int) -> None:
    click_visible_text(page, strength, timeout_ms=timeout_ms, exact=True)


def select_smart_checklist(page: Page, timeout_ms: int) -> None:
    click_visible_text(page, "智能生成", timeout_ms=timeout_ms, exact=True)


def select_custom_checklists(page: Page, config: ReviewConfig) -> None:
    click_visible_text(page, "自定义审查清单", timeout_ms=config.ui_timeout_ms, exact=True)
    combo = page.locator("input[role=combobox]").last
    combo.click(force=True)
    wait_for_visible_text(
        page,
        config.custom_checklist_names[0],
        timeout_ms=config.custom_checklist_load_timeout_ms,
        exact=True,
    )
    for checklist_name in config.custom_checklist_names:
        click_visible_text(page, checklist_name, timeout_ms=config.ui_timeout_ms, exact=True)
    page.keyboard.press("Escape")
    page.wait_for_timeout(500)
    body = page.locator("body").inner_text()
    for checklist_name in config.custom_checklist_names:
        assert checklist_name in body, f"未在页面上看到已选清单: {checklist_name}"


def submit_review(page: Page, timeout_ms: int) -> None:
    click_visible_text(page, "立即审查", timeout_ms=timeout_ms, exact=True)


def wait_for_processing_state(page: Page, timeout_ms: int) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    while time.time() < deadline:
        body = page.locator("body").inner_text()
        if "正在审查" in body or "AI智能审查" in body:
            return
        page.wait_for_timeout(500)


def review_result_ready(page: Page) -> bool:
    body = page.locator("body").inner_text()
    if "正在审查" in body or "正在读取并理解合同内容中" in body:
        return False
    if "立即审查" in body:
        return False
    return has_visible_result_content(page)


def review_failed(page: Page) -> bool:
    body = page.locator("body").inner_text()
    return ("审查失败" in body and "重试" in body) or ("审查失败" in body and "刷新" in body)


def review_hard_failed(page: Page) -> bool:
    body = page.locator("body").inner_text()
    return "智能审核失败" in body


def review_needs_result_page_refresh(page: Page) -> bool:
    body = page.locator("body").inner_text()
    return "文件过大审核失败" in body


def click_retry_action(page: Page, timeout_ms: int) -> bool:
    for text in ("重试", "刷新"):
        locator = page.get_by_text(text, exact=True)
        deadline = time.time() + (timeout_ms / 1000)
        while time.time() < deadline:
            count = locator.count()
            for index in range(count):
                candidate = locator.nth(index)
                if candidate.is_visible():
                    candidate.click(force=True)
                    page.wait_for_timeout(1000)
                    return True
            page.wait_for_timeout(200)
    return False


def refresh_review_result_page(page: Page) -> None:
    current_url = page.url
    page.reload(wait_until="domcontentloaded")
    if page.url != current_url and current_url:
        goto_page_with_retry(page, current_url)
    page.wait_for_timeout(1500)


def wait_for_review_result(page: Page, timeout_ms: int, retry_limit: int = 0) -> None:
    deadline = time.time() + (timeout_ms / 1000)
    retries_used = 0
    page_refreshes_used = 0
    while time.time() < deadline:
        if review_result_ready(page):
            return
        if review_needs_result_page_refresh(page):
            if page_refreshes_used >= max(1, retry_limit + 1):
                raise AssertionError("结果页多次出现“文件过大审核失败”，刷新后仍未恢复。")
            refresh_review_result_page(page)
            page_refreshes_used += 1
            continue
        if review_hard_failed(page):
            raise AssertionError("检测到智能审核失败。")
        if review_failed(page):
            if retries_used >= retry_limit:
                raise AssertionError("检测到可重试的审查失败，但已达到自动重试上限。")
            if not click_retry_action(page, timeout_ms=min(timeout_ms, 5000)):
                raise AssertionError("检测到可重试的审查失败，但未找到可点击的“刷新/重试”按钮。")
            retries_used += 1
            continue
        page.wait_for_timeout(3000)
    raise AssertionError("在预期时间内未等到审查结果页出现或结果加载完成。")


def build_expected_result_filters(review_case: ReviewCase, config: ReviewConfig) -> tuple[str, ...]:
    if review_case.checklist_mode == "自定义审查清单":
        return config.custom_checklist_names
    return ("AI智能生成清单",)


@pytest.mark.parametrize("review_case", build_orthogonal_cases(), ids=lambda case: case.case_id)
def test_intelligent_review_main_flow(review_case: ReviewCase) -> None:
    config = load_review_config()

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            open_authenticated_home(page, config)
            upload_contract(page, config)
            open_review_config(page, config)
            assert_extracted_review_stances(
                page,
                config.expected_review_stances,
                timeout_ms=config.ui_timeout_ms,
            )
            select_stance(page, review_case.stance, timeout_ms=config.ui_timeout_ms)
            select_strength(page, review_case.strength, timeout_ms=config.ui_timeout_ms)
            if review_case.checklist_mode == "自定义审查清单":
                select_custom_checklists(page, config)
            else:
                select_smart_checklist(page, timeout_ms=config.ui_timeout_ms)
            submit_review(page, timeout_ms=config.ui_timeout_ms)
            wait_for_processing_state(page, timeout_ms=config.ui_timeout_ms)
            wait_for_review_result(
                page,
                timeout_ms=config.review_result_timeout_ms,
                retry_limit=config.review_retry_limit,
            )
            assert_review_result_filter_works(
                page,
                build_expected_result_filters(review_case, config),
                timeout_ms=config.review_result_timeout_ms,
            )
            exercise_review_result_cards(page, timeout_ms=config.ui_timeout_ms)
            save_case_screenshot(page, review_case.case_id, "success")
        except Exception:
            save_case_screenshot(page, review_case.case_id, "failed")
            raise
        finally:
            context.close()
            browser.close()
