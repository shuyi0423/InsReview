# dev 环境审查清单导入全量测试报告

## 一、测试结论

dev 环境审查清单导入全量执行已完成。刷新登录态后全量首跑 21 通过、2 失败、2 跳过；2 个失败均为导入任务 PARSING 超时，定点复跑全部通过，最终无遗留失败。业务矩阵 27 通过、3 阻塞/未执行，未发现稳定产品缺陷；清理后无导入任务和测试清单残留。

## 二、执行信息

| 项目 | 内容 |
| --- | --- |
| 项目 | InsReview / 智审平台 UI 自动化测试 |
| 模块 | 系统管理 > 智能审查规则管理 > 审查清单 > 导入清单 |
| 环境 | dev |
| 首页地址 | https://dev-contract-agent.qtech.cn/home |
| 审查清单地址 | https://dev-contract-agent.qtech.cn/review-rule/checkList |
| API Base | https://dev-contract-agent.qtech.cn/ai/review-rule/api |
| 执行日期 | 2026-04-23 |
| 报告生成时间 | 2026-04-23 17:07:03 |
| 全量执行命令 | `HEADLESS=1 SLOW_MO=0 ./scripts/run_review_checklist_import.sh dev --junitxml=artifacts/dev-import-full-20260423/junit.xml` |
| 失败定点复跑命令 | `HEADLESS=1 SLOW_MO=0 ./scripts/run_review_checklist_import.sh dev -q -k 'special_filename or finalize_rejects_empty_rule_refs' --junitxml=artifacts/dev-import-full-20260423/junit-rerun-failures.xml` |

## 三、统计汇总

| 维度 | 总数 | 通过 | 失败 | 跳过/阻塞 | 耗时 |
| --- | ---: | ---: | ---: | ---: | ---: |
| 刷新登录态后全量首跑 | 25 | 21 | 2 | 2 | 1165.38s |
| 失败用例定点复跑 | 2 | 2 | 0 | 0 | 69.54s |
| 最终自动化判定 | 25 | 23 | 0 | 2 | - |
| 业务用例矩阵 | 30 | 27 | 0 | 3 | - |
| 初始登录态过期探测 | 25 | 0 | 23 | 2 | 386.58s |

## 四、业务用例矩阵

| Case ID | 场景 | 优先级 | 结果 | 证据 | 说明 |
| --- | --- | --- | --- | --- | --- |
| IM-001 | 打开导入弹窗 | P0 | 通过 | test_review_checklist_import_modal_copy_and_default_disabled | 刷新 dev 登录态后通过。 |
| IM-002 | 未选择文件 | P0 | 通过 | test_review_checklist_import_modal_copy_and_default_disabled | 开始导入解析按钮默认禁用。 |
| IM-003 | 上传有效 docx 文件 | P0 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[docx] | docx 上传、解析、保存、回写 finalChecklistId、清理均成功。 |
| IM-004 | 上传有效 xlsx 文件 | P0 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[xlsx] | xlsx 上传、解析、保存、回写 finalChecklistId、清理均成功。 |
| IM-005 | 上传 txt 非法类型 | P0 | 通过 | test_review_checklist_import_rejects_invalid_type_via_api | 接口返回非法类型拦截。 |
| IM-006 | 上传超 10MB 文件 | P0 | 通过 | test_review_checklist_import_rejects_oversize_file_via_api | 接口返回超限拦截，任务数量不增加。 |
| IM-007 | 上传 10MB 临界值文件 | P1 | 通过 | test_review_checklist_import_boundary_10mb_file_can_parse_and_cleanup | 10MB 临界文件允许上传并生成规则。 |
| IM-008 | 上传 doc 旧版 Word 文件 | P1 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[doc] | doc 旧版 Word 可导入、保存并清理。 |
| IM-009 | 上传 xls 旧版 Excel 文件 | P1 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[xls] | xls 旧版 Excel 可导入、保存并清理。 |
| IM-010 | 重复上传同名文件 | P1 | 通过 | test_review_checklist_import_duplicate_same_file_creates_distinct_tasks | 同一文件连续上传生成不同 taskId。 |
| IM-011 | 文件名包含中文/空格/特殊字符 | P1 | 通过 | test_review_checklist_import_special_filename_keeps_default_name_and_rules | 全量首跑解析超时，定点复跑通过；未复现为稳定缺陷。 |
| IM-012 | Word 导入解析 | P0 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[docx] | Word 文件解析进入 DRAFT_READY/COMPLETED。 |
| IM-013 | Excel 导入解析 | P0 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[xlsx] | Excel 文件解析进入 DRAFT_READY/COMPLETED。 |
| IM-014 | 空白文档导入 | P1 | 通过 | test_review_checklist_import_unsupported_content_reaches_failed_terminal_state[empty_word] / [empty_excel] | 空白 Word/Excel 均进入 FAILED 终态。 |
| IM-015 | 图片型扫描件导入 | P1 | 通过 | test_review_checklist_import_unsupported_content_reaches_failed_terminal_state[scan_only_word] | 扫描件进入 FAILED 终态。 |
| IM-016 | 任务中心展示 | P0 | 通过 | test_review_checklist_import_task_center_list_exposes_task_metadata | 任务列表展示文件名、状态、解析时间和操作。 |
| IM-017 | 清除终态任务 | P1 | 通过 | test_review_checklist_import_clear_completed_removes_terminal_failed_task | 终态 FAILED 任务可清除。 |
| IM-018 | 默认清单名称回填 | P1 | 通过 | test_review_checklist_import_special_filename_keeps_default_name_and_rules | 特殊文件名场景定点复跑通过，草稿名等于文件名去后缀。 |
| IM-019 | 规则数量与内容展示 | P0 | 通过 | test_review_checklist_import_special_filename_keeps_default_name_and_rules | 特殊文件名场景定点复跑通过，规则字段存在。 |
| IM-020 | 不修改直接保存 | P0 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[docx/xlsx/doc/xls] | 直接保存成功生成正式审查清单并清理。 |
| IM-021 | 清单名称为空保存 | P1 | 通过 | test_review_checklist_import_finalize_rejects_empty_name | 接口返回名称必填拦截。 |
| IM-022 | 移除全部规则后保存 | P1 | 通过 | test_review_checklist_import_finalize_rejects_empty_rule_refs | 全量首跑前置解析超时，定点复跑通过，空 ruleRefs 返回拦截。 |
| IM-023 | 手工补充规则后保存 | P2 | 阻塞/未执行 | 未纳入本轮自动化执行 | 缺少稳定测试规则库选择器/可控测试规则组，未真实执行。 |
| IM-024 | 保存成功后列表落库 | P0 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[docx/xlsx/doc/xls] | 保存接口返回 finalChecklistId，清单可删除。 |
| IM-025 | 任务中心状态回写 | P0 | 通过 | test_review_checklist_import_valid_files_can_finalize_and_cleanup[docx/xlsx/doc/xls] | 保存后任务 COMPLETED，finalChecklistId 一致。 |
| IM-026 | 解析过程中刷新页面 | P1 | 通过 | test_review_checklist_import_refresh_recovery_keeps_task_result_accessible | 重新获取任务与草稿仍可访问，并可继续保存完成。 |
| IM-027 | 网络中断后恢复 | P1 | 通过 | test_review_checklist_import_network_failure_does_not_create_dirty_task | 拦截创建任务请求后任务总数不增加。 |
| IM-028 | 无权限账号访问导入入口 | P1 | 阻塞/未执行 | test_review_checklist_import_no_permission_account_case_is_blocked | 缺少 dev 环境无权限账号，本轮跳过。 |
| IM-029 | 多浏览器兼容 | P2 | 阻塞/未执行 | test_review_checklist_import_non_chromium_compatibility_case_is_blocked | 本机仅安装 Chromium/Chrome，未安装 Playwright Firefox/WebKit。 |
| IM-030 | 连续批量导入多个文件 | P1 | 通过 | test_review_checklist_import_batch_files_create_independent_tasks | 3 个文件连续导入生成独立任务，均已清理。 |

## 五、自动化执行明细

| 序号 | pytest 用例 | 全量首跑 | 定点复跑 | 耗时(s) | 备注 |
| ---: | --- | --- | --- | ---: | --- |
| 1 | `test_review_checklist_import_modal_copy_and_default_disabled` | 通过 | - | 78.978 |  |
| 2 | `test_review_checklist_import_rejects_invalid_type_via_api` | 通过 | - | 0.524 |  |
| 3 | `test_review_checklist_import_valid_files_can_finalize_and_cleanup[docx]` | 通过 | - | 50.670 |  |
| 4 | `test_review_checklist_import_valid_files_can_finalize_and_cleanup[xlsx]` | 通过 | - | 37.905 |  |
| 5 | `test_review_checklist_import_valid_files_can_finalize_and_cleanup[doc]` | 通过 | - | 10.189 |  |
| 6 | `test_review_checklist_import_valid_files_can_finalize_and_cleanup[xls]` | 通过 | - | 13.689 |  |
| 7 | `test_review_checklist_import_start_button_enables_after_selecting_valid_word` | 通过 | - | 46.545 |  |
| 8 | `test_review_checklist_import_can_clear_completed_tasks` | 通过 | - | 0.625 |  |
| 9 | `test_review_checklist_import_rejects_oversize_file_via_api` | 通过 | - | 9.426 |  |
| 10 | `test_review_checklist_import_boundary_10mb_file_can_parse_and_cleanup` | 通过 | - | 11.494 |  |
| 11 | `test_review_checklist_import_duplicate_same_file_creates_distinct_tasks` | 通过 | - | 93.165 |  |
| 12 | `test_review_checklist_import_special_filename_keeps_default_name_and_rules` | 失败 | 通过 | 302.176 | AssertionError: 导入任务轮询超时: 1126008888789827694 |
| 13 | `test_review_checklist_import_unsupported_content_reaches_failed_terminal_state[empty_word]` | 通过 | - | 4.889 |  |
| 14 | `test_review_checklist_import_unsupported_content_reaches_failed_terminal_state[empty_excel]` | 通过 | - | 0.582 |  |
| 15 | `test_review_checklist_import_unsupported_content_reaches_failed_terminal_state[scan_only_word]` | 通过 | - | 4.162 |  |
| 16 | `test_review_checklist_import_task_center_list_exposes_task_metadata` | 通过 | - | 13.884 |  |
| 17 | `test_review_checklist_import_clear_completed_removes_terminal_failed_task` | 通过 | - | 3.846 |  |
| 18 | `test_review_checklist_import_finalize_rejects_empty_name` | 通过 | - | 43.824 |  |
| 19 | `test_review_checklist_import_finalize_rejects_empty_rule_refs` | 失败 | 通过 | 302.034 | AssertionError: 导入任务轮询超时: 1126010490808434814 |
| 20 | `test_review_checklist_import_refresh_recovery_keeps_task_result_accessible` | 通过 | - | 19.830 |  |
| 21 | `test_review_checklist_import_batch_files_create_independent_tasks` | 通过 | - | 44.427 |  |
| 22 | `test_review_checklist_import_network_failure_does_not_create_dirty_task` | 通过 | - | 71.348 |  |
| 23 | `test_review_checklist_import_no_permission_account_case_is_blocked` | 跳过 | - | 0.000 | 缺少 test 环境无权限账号，无法真实验证 IM-028。 |
| 24 | `test_review_checklist_import_non_chromium_compatibility_case_is_blocked` | 跳过 | - | 0.000 | 本机仅安装 Chromium/Chrome，未安装 Playwright Firefox/WebKit，无法真实验证 IM-029。 |
| 25 | `test_review_checklist_import_no_generated_prefix_residue` | 通过 | - | 1.034 |  |

## 六、残留数据检查

| 检查项 | 结果 |
| --- | --- |
| 清除已完成接口状态 | 200 |
| 任务列表查询状态 | 200 |
| 导入任务残留数量 | 0 |
| 测试清单前缀 | `insreview_dev_checklist` |
| 测试清单残留数量 | 0 |

## 七、缺陷与阻塞

- 产品缺陷：本轮未发现稳定产品缺陷。
- 观察项：2 个用例在全量首跑中出现 PARSING 超时，定点复跑均通过，建议后续继续观察 dev 解析服务耗时波动。
- 阻塞项：IM-023 手工补充规则后保存，缺少稳定测试规则库选择器/可控测试规则组，未真实执行。
- 阻塞项：IM-028 无权限账号访问导入入口，缺少 dev 环境无权限账号，本轮跳过。
- 阻塞项：IM-029 多浏览器兼容，本机仅安装 Chromium/Chrome，未安装 Playwright Firefox/WebKit。

