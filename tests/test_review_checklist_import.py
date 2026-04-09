from __future__ import annotations

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.review_checklist_import_support import (
    build_unique_checklist_name,
    clear_completed_review_checklist_import_tasks,
    close_authenticated_session,
    create_review_checklist_api_context,
    create_review_checklist_import_task,
    delete_review_checklist,
    dismiss_review_checklist_import_task,
    extract_rule_refs,
    finalize_review_checklist_draft,
    get_review_checklist_draft,
    load_review_checklist_fixtures,
    load_review_checklist_import_config,
    open_authenticated_session,
    open_review_checklist_import_modal,
    poll_review_checklist_import_task,
    save_review_checklist_import_screenshot,
    select_review_checklist_import_file,
    upload_review_checklist_file,
)
from tests.test_intelligent_review_flow import load_review_config


SUCCESS_CASES = [
    ("docx", "word", "valid_word"),
    ("xlsx", "excel", "valid_excel"),
    ("doc", "old_word", "valid_old_word"),
    ("xls", "old_excel", "valid_old_excel"),
]


def test_review_checklist_import_modal_copy_and_default_disabled() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)

    with sync_playwright() as playwright:
        browser, context, page = open_authenticated_session(playwright, review_config)
        try:
            dialog = open_review_checklist_import_modal(page, review_config, import_config)

            expect(dialog.get_by_text("Word (.doc, .docx)", exact=True)).to_be_visible()
            expect(dialog.get_by_text("Excel (.xls, .xlsx)", exact=True)).to_be_visible()
            expect(dialog.get_by_text("10MB", exact=False)).to_be_visible()
            expect(page.get_by_role("button", name="开始导入解析")).to_be_disabled()
        except Exception:
            save_review_checklist_import_screenshot(page, "review-checklist-import-modal-failed.png")
            raise
        finally:
            close_authenticated_session(browser, context)


def test_review_checklist_import_rejects_invalid_type_via_api() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        try:
            result = upload_review_checklist_file(api, import_config, fixtures.invalid_type)
            assert result.response.status == 400
            assert result.json_body.get("msg") == "Only doc/docx/xls/xlsx files are supported"
        finally:
            api.dispose()


@pytest.mark.parametrize(
    ("label", "name_suffix", "fixture_attr"),
    SUCCESS_CASES,
    ids=[case[0] for case in SUCCESS_CASES],
)
def test_review_checklist_import_valid_files_can_finalize_and_cleanup(
    label: str,
    name_suffix: str,
    fixture_attr: str,
) -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)
    file_path = getattr(fixtures, fixture_attr)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        checklist_id = ""
        try:
            upload = upload_review_checklist_file(api, import_config, file_path)
            assert upload.response.status == 200, f"{label} 上传失败: {upload.json_body}"
            assert upload.json_body.get("success") is True

            review_rule_file_id = str((upload.json_body.get("data") or {}).get("reviewRuleFileId") or "")
            assert review_rule_file_id, f"{label} 未返回 reviewRuleFileId: {upload.json_body}"

            create_task = create_review_checklist_import_task(api, import_config, review_rule_file_id)
            assert create_task.response.status == 200, f"{label} 创建任务失败: {create_task.json_body}"
            task_id = str((create_task.json_body.get("data") or {}).get("taskId") or "")
            assert task_id, f"{label} 未返回 taskId: {create_task.json_body}"

            task = poll_review_checklist_import_task(api, import_config, task_id)
            assert task.get("status") == "DRAFT_READY", f"{label} 导入任务状态异常: {task}"

            draft = get_review_checklist_draft(api, import_config, task_id)
            rule_refs = extract_rule_refs(draft)
            assert rule_refs, f"{label} 草稿页未返回可保存规则: {draft}"

            checklist_name = build_unique_checklist_name(f"{import_config.checklist_name_prefix}_{name_suffix}")
            finalize = finalize_review_checklist_draft(api, import_config, task_id, checklist_name, rule_refs)
            assert finalize.response.status == 200, f"{label} 保存失败: {finalize.json_body}"

            checklist_id = str((finalize.json_body.get("data") or {}).get("finalChecklistId") or "")
            assert checklist_id, f"{label} 保存后未返回 finalChecklistId: {finalize.json_body}"
        finally:
            if checklist_id:
                delete_review_checklist(api, import_config, checklist_id)
            if task_id:
                dismiss_review_checklist_import_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_start_button_enables_after_selecting_valid_word() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        browser, context, page = open_authenticated_session(playwright, review_config)
        try:
            open_review_checklist_import_modal(page, review_config, import_config)
            select_review_checklist_import_file(page, fixtures.valid_word)
            expect(page.get_by_role("button", name="开始导入解析")).to_be_enabled()
        except Exception:
            save_review_checklist_import_screenshot(page, "review-checklist-import-select-file-failed.png")
            raise
        finally:
            close_authenticated_session(browser, context)


def test_review_checklist_import_can_clear_completed_tasks() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        try:
            result = clear_completed_review_checklist_import_tasks(api, import_config)
            assert result.response.status == 200
        finally:
            api.dispose()
