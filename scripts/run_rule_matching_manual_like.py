#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import replace
from pathlib import Path

from playwright.sync_api import sync_playwright

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from tests.review.test_intelligent_review_flow import (
    ARTIFACTS_DIR,
    build_ui_launch_options,
    click_retry_action,
    create_authenticated_context,
    get_browser_launcher,
    load_review_config,
    open_authenticated_home,
    open_review_config,
    select_strength,
    select_smart_checklist,
    submit_review,
    upload_contract,
    wait_for_visible_text,
)
from tests.review.test_smart_generated_rule_matching import (
    collect_all_right_panel_text,
    match_keywords,
    select_available_stance,
)


DEFAULT_MANIFEST = Path(
    "/Users/shuyi/AIcodinghackathon/test_assets/smart_review_rule_matching/review_platform_cases.json"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run review platform rule matching with manual-like pacing.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--cases", default="")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    return parser.parse_args()


def load_cases(manifest_path: Path, requested: set[str]) -> list[dict]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    cases = []
    for item in payload["cases"]:
        if requested and item["case_id"] not in requested and item.get("scope") not in requested:
            continue
        cases.append(item)
    if not cases:
        raise AssertionError("未找到需要执行的合同样本。")
    return cases


def screenshot(page, case_id: str, stage: str) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    timestamp = time.strftime("%Y%m%d%H%M%S")
    path = ARTIFACTS_DIR / f"manual-like-{case_id}-{stage}-{timestamp}.png"
    page.screenshot(path=str(path), full_page=True)
    print(f"SCREENSHOT {stage}: {path}", flush=True)
    return path


def run_case(playwright, rule_case: dict, args: argparse.Namespace) -> None:
    case_id = rule_case["case_id"]
    file_path = Path(rule_case["file_path"])
    expected_keywords = tuple(rule_case["expected_rule_keywords"])
    min_expected_matches = int(rule_case["min_expected_matches"])

    config = replace(
        load_review_config(),
        review_file_path=file_path,
        headless=args.headless,
        slow_mo=int(os.getenv("SLOW_MO", "350")),
        ui_timeout_ms=int(os.getenv("UI_TIMEOUT_MS", "300000")),
        review_config_timeout_ms=int(os.getenv("REVIEW_CONFIG_TIMEOUT_MS", "420000")),
        review_result_timeout_ms=int(os.getenv("REVIEW_RESULT_TIMEOUT_MS", "1800000")),
        review_retry_limit=int(os.getenv("REVIEW_RETRY_LIMIT", "2")),
    )

    browser = get_browser_launcher(playwright, config.browser_name).launch(**build_ui_launch_options(config))
    context = create_authenticated_context(browser, config)
    context.set_default_timeout(config.ui_timeout_ms)
    page = context.new_page()
    try:
        print(f"CASE {case_id}: open home", flush=True)
        open_authenticated_home(page, config)
        page.wait_for_timeout(1500)
        screenshot(page, case_id, "home-ready")

        print(f"CASE {case_id}: upload contract", flush=True)
        upload_contract(page, config)
        page.wait_for_timeout(1000)
        screenshot(page, case_id, "uploaded")

        print(f"CASE {case_id}: open review config", flush=True)
        open_review_config(page, config)
        wait_for_visible_text(page, "审查立场", timeout_ms=config.review_config_timeout_ms, exact=True)
        wait_for_visible_text(page, "审查清单", timeout_ms=config.review_config_timeout_ms, exact=True)
        wait_for_visible_text(page, "立即审查", timeout_ms=config.review_config_timeout_ms, exact=True)
        page.wait_for_timeout(1000)
        screenshot(page, case_id, "config-ready")

        print(f"CASE {case_id}: select options", flush=True)
        select_available_stance(page, config)
        page.wait_for_timeout(500)
        select_strength(page, "中立", timeout_ms=config.ui_timeout_ms)
        page.wait_for_timeout(500)
        select_smart_checklist(page, timeout_ms=config.ui_timeout_ms)
        page.wait_for_timeout(1000)
        screenshot(page, case_id, "before-submit")

        print(f"CASE {case_id}: submit review", flush=True)
        submit_review(page, timeout_ms=config.ui_timeout_ms)
        screenshot(page, case_id, "after-submit")

        print(f"CASE {case_id}: wait result/failure", flush=True)
        deadline = time.time() + args.timeout_seconds
        retries = 0
        last_log = 0.0
        while time.time() < deadline:
            body = page.locator("body").inner_text(timeout=5000)
            compact = body.replace("\n", " | ")[:500]
            if "清单列表为空" in body:
                screenshot(page, case_id, "checklist-empty")
                raise AssertionError(f"{case_id} 页面出现清单列表为空。")
            if "智能审核失败" in body or ("审查失败" in body and ("重试" in body or "刷新" in body)):
                screenshot(page, case_id, f"review-failed-{retries}")
                if retries >= config.review_retry_limit:
                    raise AssertionError(f"{case_id} 页面显示审查失败，且已达到重试上限。")
                print(f"CASE {case_id}: retry review failure #{retries + 1}", flush=True)
                if not click_retry_action(page, timeout_ms=5000):
                    raise AssertionError(f"{case_id} 页面显示审查失败，但未找到可点击的重试/刷新。")
                retries += 1
                page.wait_for_timeout(3000)
                continue

            result_markers = ("待确认", "警示风险", "建议优化", "生成优化", "接受修订", "导出")
            still_processing = "正在审查" in body or "正在读取并理解合同内容中" in body
            if any(marker in body for marker in result_markers) and not still_processing:
                screenshot(page, case_id, "result")
                result_text = collect_all_right_panel_text(page)
                matched = match_keywords(result_text, expected_keywords)
                print(f"CASE {case_id}: matched={matched}", flush=True)
                print(f"CASE {case_id}: right_text_head={result_text.replace(chr(10), ' | ')[:1200]}", flush=True)
                if len(matched) < min_expected_matches:
                    raise AssertionError(
                        f"{case_id} {rule_case['contract_type']} 命中不足，"
                        f"期望至少 {min_expected_matches}，实际 {len(matched)}: {matched}"
                    )
                print(f"CASE {case_id}: PASS", flush=True)
                return

            now = time.time()
            if now - last_log >= 30:
                print(f"CASE {case_id}: WAITING {compact}", flush=True)
                last_log = now
            page.wait_for_timeout(3000)

        screenshot(page, case_id, "timeout")
        raise AssertionError(f"{case_id} 等待 {args.timeout_seconds} 秒仍未出现审查结果或失败态。")
    finally:
        context.close()
        browser.close()


def main() -> int:
    args = parse_args()
    requested = {item.strip() for item in args.cases.split(",") if item.strip()}
    cases = load_cases(Path(args.manifest), requested)
    with sync_playwright() as playwright:
        for rule_case in cases:
            run_case(playwright, rule_case, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
