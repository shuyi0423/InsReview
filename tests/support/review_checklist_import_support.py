from __future__ import annotations

import os
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from playwright.sync_api import APIRequestContext, APIResponse, Error, Locator, Page, Playwright

from tests.checklist.test_checklist_module import get_checklist_list_url
from tests.review.test_intelligent_review_flow import (
    ARTIFACTS_DIR,
    ReviewConfig,
    build_ui_launch_options,
    create_authenticated_context,
    goto_page_with_retry,
    get_browser_launcher,
    load_review_config,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures" / "import" / "review_checklist_import"


@dataclass(frozen=True)
class ReviewChecklistImportConfig:
    page_url: str
    api_base_url: str
    task_timeout_ms: int
    open_attempts: int
    open_wait_ms: int
    checklist_name_prefix: str
    fixtures_dir: Path


@dataclass(frozen=True)
class ReviewChecklistFixtures:
    fixtures_dir: Path
    valid_word: Path
    valid_excel: Path
    valid_old_word: Path
    valid_old_excel: Path
    invalid_type: Path
    round_archive_dir: Path
    oversize_word: Path
    boundary_word: Path
    empty_word: Path
    empty_excel: Path
    scan_only_word: Path
    special_name_word: Path


@dataclass(frozen=True)
class ApiResult:
    response: APIResponse
    json_body: dict[str, Any]


def resolve_project_path(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def default_review_checklist_api_base(review_config: ReviewConfig) -> str:
    parsed = urlparse(review_config.home_url)
    return f"{parsed.scheme}://{parsed.netloc}/ai/review-rule/api"


def load_review_checklist_import_config(
    review_config: ReviewConfig | None = None,
) -> ReviewChecklistImportConfig:
    review_config = review_config or load_review_config()

    page_url = os.getenv("REVIEW_CHECKLIST_PAGE_URL", get_checklist_list_url(review_config)).strip()
    api_base_url = os.getenv(
        "REVIEW_CHECKLIST_API_BASE_URL",
        default_review_checklist_api_base(review_config),
    ).strip()
    fixtures_dir = resolve_project_path(
        os.getenv("REVIEW_CHECKLIST_FIXTURES_DIR", str(DEFAULT_FIXTURES_DIR))
    )

    return ReviewChecklistImportConfig(
        page_url=page_url.rstrip("/"),
        api_base_url=api_base_url.rstrip("/"),
        task_timeout_ms=int(os.getenv("REVIEW_CHECKLIST_TASK_TIMEOUT_MS", "300000")),
        open_attempts=int(os.getenv("REVIEW_CHECKLIST_OPEN_ATTEMPTS", "6")),
        open_wait_ms=int(os.getenv("REVIEW_CHECKLIST_OPEN_WAIT_MS", "2000")),
        checklist_name_prefix=os.getenv("REVIEW_CHECKLIST_NAME_PREFIX", "insreview_checklist").strip(),
        fixtures_dir=fixtures_dir,
    )


def load_review_checklist_fixtures(
    import_config: ReviewChecklistImportConfig | None = None,
) -> ReviewChecklistFixtures:
    import_config = import_config or load_review_checklist_import_config()
    archive_dir = import_config.fixtures_dir / "round_20260408"
    fixtures = ReviewChecklistFixtures(
        fixtures_dir=import_config.fixtures_dir,
        valid_word=import_config.fixtures_dir / "valid-word.docx",
        valid_excel=import_config.fixtures_dir / "valid-excel.xlsx",
        valid_old_word=import_config.fixtures_dir / "valid-old-word.doc",
        valid_old_excel=import_config.fixtures_dir / "valid-old-excel.xls",
        invalid_type=import_config.fixtures_dir / "invalid-type.txt",
        round_archive_dir=archive_dir,
        oversize_word=archive_dir / "qa_oversize_20260408_153608.docx",
        boundary_word=archive_dir / "qa_boundary_10mb_word_20260408.docx",
        empty_word=archive_dir / "qa_empty_word_20260408_160156.docx",
        empty_excel=archive_dir / "qa_empty_excel_20260408_160156.xlsx",
        scan_only_word=archive_dir / "qa_scan_only_word_20260408.docx",
        special_name_word=archive_dir / "QA 特殊 文件名 @审查清单 20260408_160156.docx",
    )

    for path in (
        fixtures.valid_word,
        fixtures.valid_excel,
        fixtures.valid_old_word,
        fixtures.valid_old_excel,
        fixtures.invalid_type,
    ):
        ensure_fixture_exists(path)

    return fixtures


def ensure_fixture_exists(file_path: Path) -> None:
    if not file_path.exists():
        raise AssertionError(f"缺少导入清单测试夹具文件: {file_path}")


def has_visible_locator(locator: Locator) -> bool:
    for index in range(locator.count()):
        try:
            if locator.nth(index).is_visible():
                return True
        except Error:
            continue
    return False


def wait_for_import_button(page: Page, timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    while time.monotonic() < deadline:
        button = page.get_by_role("button", name="导入清单")
        if has_visible_locator(button):
            for index in range(button.count() - 1, -1, -1):
                candidate = button.nth(index)
                if candidate.is_visible():
                    return candidate
        page.wait_for_timeout(250)
    raise AssertionError("未找到可见的“导入清单”按钮。")


def wait_for_import_dialog(page: Page, timeout_ms: int) -> Locator:
    deadline = time.monotonic() + (timeout_ms / 1000)
    probe = page.get_by_text("导入审查清单", exact=True)
    while time.monotonic() < deadline:
        for index in range(probe.count() - 1, -1, -1):
            candidate = probe.nth(index)
            if not candidate.is_visible():
                continue
            containers = (
                candidate.locator("xpath=ancestor::*[@role='dialog'][1]"),
                candidate.locator("xpath=ancestor::*[contains(@class,'ant-modal-root')][1]"),
                candidate.locator("xpath=ancestor::*[contains(@class,'ant-modal')][1]"),
            )
            for container in containers:
                if container.count() and container.is_visible():
                    return container
        page.wait_for_timeout(250)
    raise AssertionError("导入清单弹窗未按预期展示。")


def open_review_checklist_import_modal(
    page: Page,
    review_config: ReviewConfig,
    import_config: ReviewChecklistImportConfig,
) -> Locator:
    last_error: AssertionError | None = None

    for attempt in range(import_config.open_attempts):
        try:
            goto_page_with_retry(page, import_config.page_url)
            page.wait_for_timeout(1500)
            button = wait_for_import_button(
                page,
                timeout_ms=min(review_config.review_config_timeout_ms, 30000),
            )
            button.click(force=True)
            return wait_for_import_dialog(page, review_config.ui_timeout_ms)
        except AssertionError as error:
            last_error = error
            if attempt == import_config.open_attempts - 1:
                break
            page.reload(wait_until="domcontentloaded")
            page.wait_for_timeout(import_config.open_wait_ms)

    assert last_error is not None
    raise last_error


def select_review_checklist_import_file(page: Page, file_path: Path) -> None:
    ensure_fixture_exists(file_path)
    dialog = wait_for_import_dialog(page, timeout_ms=10000)
    file_inputs = dialog.locator("input[type='file']")
    if not file_inputs.count():
        file_inputs = page.locator("input[type='file']")
    file_inputs.last.set_input_files(str(file_path))
    page.wait_for_timeout(1200)


def save_review_checklist_import_screenshot(page: Page, filename: str) -> Path:
    ARTIFACTS_DIR.mkdir(exist_ok=True)
    target = ARTIFACTS_DIR / filename
    page.screenshot(path=str(target), full_page=True)
    return target


def open_authenticated_session(playwright: Playwright, review_config: ReviewConfig) -> tuple[Any, Any, Page]:
    browser = get_browser_launcher(playwright, review_config.browser_name).launch(
        **build_ui_launch_options(review_config)
    )
    context = create_authenticated_context(browser, review_config)
    page = context.new_page()
    page.set_default_timeout(review_config.ui_timeout_ms)
    return browser, context, page


def close_authenticated_session(browser: Any, context: Any) -> None:
    try:
        context.close()
    finally:
        browser.close()


def create_review_checklist_api_context(
    playwright: Playwright,
    review_config: ReviewConfig,
) -> APIRequestContext:
    return playwright.request.new_context(
        storage_state=str(review_config.auth_storage_state_path),
        ignore_https_errors=True,
    )


def mime_type_for(file_path: Path) -> str:
    suffix = file_path.suffix.lower()
    if suffix == ".doc":
        return "application/msword"
    if suffix == ".docx":
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if suffix == ".xls":
        return "application/vnd.ms-excel"
    if suffix == ".xlsx":
        return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    if suffix == ".txt":
        return "text/plain"
    return "application/octet-stream"


def upload_review_checklist_file(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    file_path: Path,
) -> ApiResult:
    ensure_fixture_exists(file_path)
    response = api.post(
        f"{import_config.api_base_url}/review-import-files/upload",
        multipart={
            "file": {
                "name": file_path.name,
                "mimeType": mime_type_for(file_path),
                "buffer": file_path.read_bytes(),
            }
        },
    )
    return ApiResult(response=response, json_body=response.json())


def create_review_checklist_import_task(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    review_rule_file_id: str,
) -> ApiResult:
    response = api.post(
        f"{import_config.api_base_url}/review-checklists/import/tasks",
        data={
            "reviewRuleFileId": review_rule_file_id,
            "clientRequestId": str(uuid.uuid4()),
        },
    )
    return ApiResult(response=response, json_body=response.json())


def get_review_checklist_import_task(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    task_id: str,
) -> dict[str, Any]:
    response = api.get(f"{import_config.api_base_url}/review-checklists/import/tasks/{task_id}")
    return response.json()["data"]


def poll_review_checklist_import_task(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    task_id: str,
) -> dict[str, Any]:
    deadline = time.monotonic() + (import_config.task_timeout_ms / 1000)
    while time.monotonic() < deadline:
        task = get_review_checklist_import_task(api, import_config, task_id)
        if task.get("status") != "PARSING":
            return task
        time.sleep(3)
    raise AssertionError(f"导入任务轮询超时: {task_id}")


def get_review_checklist_draft(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    task_id: str,
) -> dict[str, Any]:
    response = api.get(f"{import_config.api_base_url}/review-checklists/import/tasks/{task_id}/draft")
    return response.json()["data"]


def extract_rule_refs(draft: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("selectedRuleRefs", "ruleRefs"):
        value = draft.get(key)
        if isinstance(value, list) and value:
            return value
    return []


def finalize_review_checklist_draft(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    task_id: str,
    name: str,
    rule_refs: list[dict[str, Any]],
) -> ApiResult:
    response = api.post(
        f"{import_config.api_base_url}/review-checklists/import/tasks/{task_id}/finalize",
        data={
            "name": name,
            "contractCategory": ["-1"],
            "reviewStage": [30, 3],
            "ruleRefs": rule_refs,
        },
    )
    return ApiResult(response=response, json_body=response.json())


def dismiss_review_checklist_import_task(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    task_id: str,
) -> ApiResult:
    response = api.post(f"{import_config.api_base_url}/review-checklists/import/tasks/{task_id}/dismiss")
    return ApiResult(response=response, json_body=response.json())


def clear_completed_review_checklist_import_tasks(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
) -> ApiResult:
    response = api.post(f"{import_config.api_base_url}/review-checklists/import/tasks/clear-completed")
    return ApiResult(response=response, json_body=response.json())


def delete_review_checklist(
    api: APIRequestContext,
    import_config: ReviewChecklistImportConfig,
    checklist_id: str,
) -> ApiResult:
    response = api.delete(f"{import_config.api_base_url}/review-checklists/{checklist_id}")
    return ApiResult(response=response, json_body=response.json())


def build_unique_checklist_name(prefix: str) -> str:
    stamp = time.strftime("%Y%m%d%H%M%S")
    return f"{prefix}_{stamp}"
