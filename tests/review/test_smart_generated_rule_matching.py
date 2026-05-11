from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path

import pytest
from playwright.sync_api import Page, sync_playwright

from tests.review.test_intelligent_review_flow import (
    ARTIFACTS_DIR,
    ReviewConfig,
    build_ui_launch_options,
    click_visible_text,
    create_authenticated_context,
    get_browser_launcher,
    has_visible_right_text,
    load_review_config,
    open_authenticated_home,
    open_review_config,
    save_case_screenshot,
    scroll_review_results_panel,
    select_smart_checklist,
    select_strength,
    submit_review,
    upload_contract,
    wait_for_processing_state,
    wait_for_review_result,
    wait_for_visible_text,
)


MANIFEST_PATH = Path(
    os.getenv(
        "SMART_REVIEW_RULE_MATCHING_MANIFEST",
        "/Users/shuyi/AIcodinghackathon/test_assets/smart_review_rule_matching/rule_matching_cases.json",
    )
)


@dataclass(frozen=True)
class RuleMatchingCase:
    case_id: str
    scope: str
    contract_type: str
    file_path: Path
    expected_rule_keywords: tuple[str, ...]
    min_expected_matches: int


def compact_text(text: str) -> str:
    return re.sub(r"[\s/／|｜,，。；;:：\"'“”‘’()（）【】\[\]_-]+", "", text)


def load_rule_matching_cases() -> list[RuleMatchingCase]:
    if not MANIFEST_PATH.exists():
        pytest.skip(
            f"缺少智能生成规则匹配样本清单: {MANIFEST_PATH}",
            allow_module_level=True,
        )
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    requested_cases = {
        item.strip()
        for item in os.getenv("SMART_REVIEW_RULE_MATCHING_CASES", "").split(",")
        if item.strip()
    }
    cases: list[RuleMatchingCase] = []
    for item in payload["cases"]:
        if requested_cases and item["case_id"] not in requested_cases and item["scope"] not in requested_cases:
            continue
        cases.append(
            RuleMatchingCase(
                case_id=item["case_id"],
                scope=item["scope"],
                contract_type=item["contract_type"],
                file_path=Path(item["file_path"]),
                expected_rule_keywords=tuple(item["expected_rule_keywords"]),
                min_expected_matches=int(item["min_expected_matches"]),
            )
        )
    return cases


def collect_visible_right_panel_text(page: Page) -> str:
    return page.evaluate(
        r"""() => {
            const normalize = (value) => (value || '').replace(/\s+/g, ' ').trim();
            const rightLimit = window.innerWidth * 0.55;
            const texts = [];
            const seen = new Set();
            for (const element of document.querySelectorAll('div,span,p,button')) {
                const style = window.getComputedStyle(element);
                if (style.display === 'none' || style.visibility === 'hidden') {
                    continue;
                }
                const rect = element.getBoundingClientRect();
                if (
                    rect.x < rightLimit ||
                    rect.width < 12 ||
                    rect.height < 8 ||
                    rect.bottom < 80 ||
                    rect.top > window.innerHeight - 8
                ) {
                    continue;
                }
                const text = normalize(element.textContent);
                if (!text || text.length < 2 || seen.has(text)) {
                    continue;
                }
                seen.add(text);
                texts.push(text);
            }
            return texts.join('\n');
        }"""
    )


def collect_all_right_panel_text(page: Page) -> str:
    chunks: list[str] = []
    for _ in range(45):
        chunks.append(collect_visible_right_panel_text(page))
        if not scroll_review_results_panel(page):
            break
    return "\n".join(chunks)


def match_keywords(result_text: str, expected_keywords: tuple[str, ...]) -> list[str]:
    compact_result_text = compact_text(result_text)
    return [keyword for keyword in expected_keywords if compact_text(keyword) in compact_result_text]


def assert_smart_generated_results_visible(page: Page) -> None:
    body_text = page.locator("body").inner_text()
    result_markers = ("待确认", "警示风险", "建议优化", "生成优化", "接受修订")
    if not any(marker in body_text for marker in result_markers):
        raise AssertionError("结果页未展示智能生成审查结果。")


def save_rule_case_screenshot(page: Page, case_id: str, stage: str) -> None:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d%H%M%S")
    safe_case_id = case_id.replace("/", "-")
    page.screenshot(
        path=str(ARTIFACTS_DIR / f"rule-matching-{safe_case_id}-{stage}-{timestamp}.png"),
        full_page=True,
    )


def select_available_stance(page: Page, config: ReviewConfig) -> None:
    for candidate in ("甲方", "买方", "委托方", "乙方", "卖方"):
        locator = page.get_by_text(candidate, exact=False)
        for index in range(locator.count()):
            if locator.nth(index).is_visible():
                locator.nth(index).click(force=True)
                return
    raise AssertionError("未找到可用于提交智能审查的审查立场。")


def wait_for_review_config_ready(page: Page, config: ReviewConfig) -> None:
    wait_for_visible_text(page, "审查立场", timeout_ms=config.review_config_timeout_ms, exact=True)
    wait_for_visible_text(page, "审查强度", timeout_ms=config.review_config_timeout_ms, exact=True)
    wait_for_visible_text(page, "审查清单", timeout_ms=config.review_config_timeout_ms, exact=True)
    wait_for_visible_text(page, "智能生成", timeout_ms=config.review_config_timeout_ms, exact=True)
    wait_for_visible_text(page, "立即审查", timeout_ms=config.review_config_timeout_ms, exact=True)
    page.wait_for_timeout(3000)


@pytest.mark.parametrize("rule_case", load_rule_matching_cases(), ids=lambda case: case.case_id)
def test_smart_generated_rule_matching(rule_case: RuleMatchingCase) -> None:
    config = replace(
        load_review_config(),
        review_file_path=rule_case.file_path,
        expected_review_stances=("甲方", "乙方"),
    )

    with sync_playwright() as playwright:
        launch_options = build_ui_launch_options(config)
        browser = get_browser_launcher(playwright, config.browser_name).launch(**launch_options)
        context = create_authenticated_context(browser, config)
        context.set_default_timeout(config.ui_timeout_ms)
        page = context.new_page()

        try:
            open_authenticated_home(page, config)
            page.wait_for_timeout(3000)
            upload_contract(page, config)
            open_review_config(page, config)
            wait_for_review_config_ready(page, config)
            select_available_stance(page, config)
            page.wait_for_timeout(1500)
            select_strength(page, "中立", timeout_ms=config.ui_timeout_ms)
            page.wait_for_timeout(1500)
            select_smart_checklist(page, timeout_ms=config.ui_timeout_ms)
            wait_for_visible_text(page, "立即审查", timeout_ms=config.review_config_timeout_ms, exact=True)
            page.wait_for_timeout(3000)
            save_rule_case_screenshot(page, rule_case.case_id, "before-submit")
            submit_review(page, timeout_ms=config.ui_timeout_ms)
            wait_for_processing_state(page, timeout_ms=config.ui_timeout_ms)
            save_rule_case_screenshot(page, rule_case.case_id, "after-submit")
            wait_for_review_result(
                page,
                timeout_ms=config.review_result_timeout_ms,
                retry_limit=config.review_retry_limit,
            )
            assert_smart_generated_results_visible(page)
            save_rule_case_screenshot(page, rule_case.case_id, "result")

            result_text = collect_all_right_panel_text(page)
            matched = match_keywords(result_text, rule_case.expected_rule_keywords)
            assert len(matched) >= rule_case.min_expected_matches, (
                f"{rule_case.contract_type} 智能生成结果未命中足够的内置规则。"
                f" 期望至少 {rule_case.min_expected_matches} 条，实际命中 {len(matched)} 条: {matched}"
            )
            save_case_screenshot(page, f"rule-matching-{rule_case.case_id}", "success")
        except Exception:
            save_rule_case_screenshot(page, rule_case.case_id, "failed")
            save_case_screenshot(page, f"rule-matching-{rule_case.case_id}", "failed")
            raise
        finally:
            context.close()
            browser.close()
