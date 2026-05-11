from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect, sync_playwright

from tests.support.review_checklist_import_support import (
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
    get_review_checklist_import_task,
    list_review_checklist_import_tasks,
    list_review_checklists,
    load_review_checklist_fixtures,
    load_review_checklist_import_config,
    open_authenticated_session,
    open_review_checklist_import_modal,
    poll_review_checklist_import_task,
    poll_review_checklist_import_task_until_status,
    save_review_checklist_import_screenshot,
    select_review_checklist_import_file,
    upload_review_checklist_file,
)
from tests.review.test_intelligent_review_flow import load_review_config


SUCCESS_CASES = [
    ("docx", "word", "valid_word"),
    ("xlsx", "excel", "valid_excel"),
    ("doc", "old_word", "valid_old_word"),
    ("xls", "old_excel", "valid_old_excel"),
]

FAILED_TERMINAL_CASES = [
    ("empty_word", "empty_word"),
    ("empty_excel", "empty_excel"),
    ("scan_only_word", "scan_only_word"),
]

ENGLISH_LANGUAGE_CASES = [
    ("english_docx", "english_word"),
    ("english_xlsx", "english_excel"),
]


def file_stem(file_path) -> str:
    return file_path.name.rsplit(".", 1)[0]


def assert_english_draft_preserves_language(draft: dict, label: str) -> None:
    selected_rules = draft.get("selectedRules") or []
    assert selected_rules, f"{label} 草稿未返回规则: {draft}"

    rule_text = " ".join(
        str(rule.get(key) or "")
        for rule in selected_rules
        for key in ("name", "content", "riskTips")
    )
    assert not re.search(r"[\u4e00-\u9fff]", rule_text), f"{label} 草稿规则被中文化: {rule_text}"
    assert "English" in rule_text, f"{label} 草稿缺少 English 语义: {rule_text}"
    assert "confidential" in rule_text.lower(), f"{label} 草稿缺少 confidentiality 语义: {rule_text}"


def upload_create_and_poll(api, import_config, file_path):
    upload = upload_review_checklist_file(api, import_config, file_path)
    assert upload.response.status == 200, f"{file_path.name} 上传失败: {upload.json_body}"
    assert upload.json_body.get("success") is True

    review_rule_file_id = str((upload.json_body.get("data") or {}).get("reviewRuleFileId") or "")
    assert review_rule_file_id, f"{file_path.name} 未返回 reviewRuleFileId: {upload.json_body}"

    create_task = create_review_checklist_import_task(api, import_config, review_rule_file_id)
    assert create_task.response.status == 200, f"{file_path.name} 创建任务失败: {create_task.json_body}"
    task_id = str((create_task.json_body.get("data") or {}).get("taskId") or "")
    assert task_id, f"{file_path.name} 未返回 taskId: {create_task.json_body}"

    task = poll_review_checklist_import_task(api, import_config, task_id)
    return task_id, task, upload, create_task


def cleanup_task(api, import_config, task_id: str) -> None:
    if task_id:
        dismiss_review_checklist_import_task(api, import_config, task_id)


def cleanup_checklist(api, import_config, checklist_id: str) -> None:
    if checklist_id:
        delete_review_checklist(api, import_config, checklist_id)


def test_review_checklist_import_modal_copy_and_default_disabled() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)

    with sync_playwright() as playwright:
        browser, context, page = open_authenticated_session(playwright, review_config)
        try:
            dialog = open_review_checklist_import_modal(page, review_config, import_config)

            expect(dialog.get_by_text("Word (.doc, .docx)", exact=False)).to_be_visible()
            expect(dialog.get_by_text("Excel (.xls, .xlsx)", exact=False)).to_be_visible()
            expect(dialog.get_by_text("10 MB", exact=False)).to_be_visible()
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
            completed_task = poll_review_checklist_import_task_until_status(
                api,
                import_config,
                task_id,
                {"COMPLETED"},
                timeout_ms=120000,
            )
            assert completed_task.get("finalChecklistId") == checklist_id
        finally:
            if checklist_id:
                delete_review_checklist(api, import_config, checklist_id)
            if task_id:
                dismiss_review_checklist_import_task(api, import_config, task_id)
            api.dispose()


@pytest.mark.parametrize(
    ("label", "fixture_attr"),
    ENGLISH_LANGUAGE_CASES,
    ids=[case[0] for case in ENGLISH_LANGUAGE_CASES],
)
def test_review_checklist_import_english_files_keep_draft_language(
    label: str,
    fixture_attr: str,
) -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)
    file_path = getattr(fixtures, fixture_attr)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, file_path)
            assert task.get("status") == "DRAFT_READY", f"{label} 导入任务状态异常: {task}"

            draft = get_review_checklist_draft(api, import_config, task_id)
            assert_english_draft_preserves_language(draft, label)
        finally:
            cleanup_task(api, import_config, task_id)
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


def test_review_checklist_import_rejects_oversize_file_via_api() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        try:
            before_tasks = list_review_checklist_import_tasks(api, import_config).get("totalElements")
            result = upload_review_checklist_file(api, import_config, fixtures.oversize_word)
            after_tasks = list_review_checklist_import_tasks(api, import_config).get("totalElements")

            assert result.response.status == 413
            assert result.json_body.get("success") is False
            assert "10MB" in (result.json_body.get("msg") or "")
            assert after_tasks == before_tasks
        finally:
            api.dispose()


def test_review_checklist_import_boundary_10mb_file_can_parse_and_cleanup() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        try:
            task_id, task, upload, _ = upload_create_and_poll(api, import_config, fixtures.boundary_word)
            upload_data = upload.json_body.get("data") or {}

            assert upload_data.get("fileSize") == 10 * 1024 * 1024
            assert task.get("status") == "DRAFT_READY"
            assert (task.get("draftRuleCount") or 0) > 0
        finally:
            cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_duplicate_same_file_creates_distinct_tasks() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_ids: list[str] = []
        try:
            for _ in range(2):
                task_id, task, _, _ = upload_create_and_poll(api, import_config, fixtures.valid_word)
                task_ids.append(task_id)
                assert task.get("status") == "DRAFT_READY"

            assert len(set(task_ids)) == 2
        finally:
            for task_id in task_ids:
                cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_special_filename_keeps_default_name_and_rules() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        checklist_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, fixtures.special_name_word)
            assert task.get("status") == "DRAFT_READY"
            assert task.get("currentChecklistName") == file_stem(fixtures.special_name_word)

            draft = get_review_checklist_draft(api, import_config, task_id)
            assert draft.get("name") == file_stem(fixtures.special_name_word)
            assert len(draft.get("selectedRules") or []) >= 1
            for rule in draft.get("selectedRules") or []:
                assert rule.get("name")
                assert rule.get("content")
                assert "riskLevel" in rule

            checklist_name = build_unique_checklist_name(f"{import_config.checklist_name_prefix}_special")
            finalize = finalize_review_checklist_draft(
                api,
                import_config,
                task_id,
                checklist_name,
                extract_rule_refs(draft),
            )
            assert finalize.response.status == 200, finalize.json_body
            checklist_id = str((finalize.json_body.get("data") or {}).get("finalChecklistId") or "")
            assert checklist_id
        finally:
            cleanup_checklist(api, import_config, checklist_id)
            cleanup_task(api, import_config, task_id)
            api.dispose()


@pytest.mark.parametrize(
    ("label", "fixture_attr"),
    FAILED_TERMINAL_CASES,
    ids=[case[0] for case in FAILED_TERMINAL_CASES],
)
def test_review_checklist_import_unsupported_content_reaches_failed_terminal_state(
    label: str,
    fixture_attr: str,
) -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)
    file_path = getattr(fixtures, fixture_attr)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, file_path)
            assert task.get("status") == "FAILED", f"{label} 应明确失败且不挂起: {task}"
            assert task.get("sourceFileName") == file_path.name
        finally:
            cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_task_center_list_exposes_task_metadata() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, fixtures.batch_word_1)
            assert task.get("status") == "DRAFT_READY"

            tasks = list_review_checklist_import_tasks(api, import_config).get("content") or []
            matched = [item for item in tasks if str(item.get("taskId")) == task_id]
            assert matched, f"任务中心列表未展示任务: {task_id}"

            item = matched[0]
            assert item.get("sourceFileName") == fixtures.batch_word_1.name
            assert item.get("status") == "DRAFT_READY"
            assert item.get("parseRequestTime")
            assert "OPEN_RESULT" in (item.get("availableActions") or [])
        finally:
            cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_clear_completed_removes_terminal_failed_task() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, fixtures.empty_word)
            assert task.get("status") == "FAILED"

            result = clear_completed_review_checklist_import_tasks(api, import_config)
            assert result.response.status == 200

            tasks = list_review_checklist_import_tasks(api, import_config).get("content") or []
            assert all(str(item.get("taskId")) != task_id for item in tasks)
            task_id = ""
        finally:
            cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_finalize_rejects_empty_name() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, fixtures.valid_word)
            assert task.get("status") == "DRAFT_READY"
            draft = get_review_checklist_draft(api, import_config, task_id)

            result = finalize_review_checklist_draft(
                api,
                import_config,
                task_id,
                "",
                extract_rule_refs(draft),
            )
            assert result.response.status == 400
            assert "name must not be blank" in (result.json_body.get("msg") or "")
        finally:
            cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_finalize_rejects_empty_rule_refs() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, fixtures.valid_word)
            assert task.get("status") == "DRAFT_READY"

            result = finalize_review_checklist_draft(
                api,
                import_config,
                task_id,
                build_unique_checklist_name("empty_rules"),
                [],
            )
            assert result.response.status == 400
            assert "ruleRefs must not be empty" in (result.json_body.get("msg") or "")
        finally:
            cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_refresh_recovery_keeps_task_result_accessible() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_id = ""
        checklist_id = ""
        try:
            task_id, task, _, _ = upload_create_and_poll(api, import_config, fixtures.edit_rules_word)
            assert task.get("status") == "DRAFT_READY"

            reloaded_task = get_review_checklist_import_task(api, import_config, task_id)
            draft = get_review_checklist_draft(api, import_config, task_id)
            assert reloaded_task.get("status") == "DRAFT_READY"
            assert draft.get("taskId") == task_id

            checklist_name = build_unique_checklist_name(f"{import_config.checklist_name_prefix}_refresh")
            finalize = finalize_review_checklist_draft(
                api,
                import_config,
                task_id,
                checklist_name,
                extract_rule_refs(draft),
            )
            assert finalize.response.status == 200, finalize.json_body
            checklist_id = str((finalize.json_body.get("data") or {}).get("finalChecklistId") or "")
            completed_task = poll_review_checklist_import_task_until_status(
                api,
                import_config,
                task_id,
                {"COMPLETED"},
                timeout_ms=120000,
            )
            assert completed_task.get("finalChecklistId") == checklist_id
        finally:
            cleanup_checklist(api, import_config, checklist_id)
            cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_batch_files_create_independent_tasks() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)
    batch_files = [fixtures.batch_word_1, fixtures.batch_word_2, fixtures.batch_word_3]

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        task_ids: list[str] = []
        try:
            for file_path in batch_files:
                task_id, task, _, _ = upload_create_and_poll(api, import_config, file_path)
                task_ids.append(task_id)
                assert task.get("status") == "DRAFT_READY"
                assert (task.get("draftRuleCount") or 0) > 0

            assert len(set(task_ids)) == len(batch_files)
        finally:
            for task_id in task_ids:
                cleanup_task(api, import_config, task_id)
            api.dispose()


def test_review_checklist_import_network_failure_does_not_create_dirty_task() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)
    fixtures = load_review_checklist_fixtures(import_config)

    with sync_playwright() as playwright:
        browser, context, page = open_authenticated_session(playwright, review_config)
        api = create_review_checklist_api_context(playwright, review_config)
        try:
            before_tasks = list_review_checklist_import_tasks(api, import_config).get("totalElements")
            open_review_checklist_import_modal(page, review_config, import_config)
            select_review_checklist_import_file(page, fixtures.valid_word)

            page.route("**/review-checklists/import/tasks", lambda route: route.abort())
            page.get_by_role("button", name="开始导入解析").click(force=True)
            page.wait_for_timeout(2500)
            page.unroute("**/review-checklists/import/tasks")

            after_tasks = list_review_checklist_import_tasks(api, import_config).get("totalElements")
            assert after_tasks == before_tasks
        finally:
            api.dispose()
            close_authenticated_session(browser, context)


def test_review_checklist_import_no_permission_account_case_is_blocked() -> None:
    pytest.skip("缺少 test 环境无权限账号，无法真实验证 IM-028。")


def test_review_checklist_import_non_chromium_compatibility_case_is_blocked() -> None:
    pytest.skip("本机仅安装 Chromium/Chrome，未安装 Playwright Firefox/WebKit，无法真实验证 IM-029。")


def test_review_checklist_import_no_generated_prefix_residue() -> None:
    review_config = load_review_config()
    import_config = load_review_checklist_import_config(review_config)

    with sync_playwright() as playwright:
        api = create_review_checklist_api_context(playwright, review_config)
        try:
            checklists = list_review_checklists(api, import_config).get("content") or []
            matched = [
                item
                for item in checklists
                if str(item.get("name") or "").startswith(import_config.checklist_name_prefix)
            ]
            assert not matched, f"存在未清理的测试清单: {matched}"
        finally:
            api.dispose()
