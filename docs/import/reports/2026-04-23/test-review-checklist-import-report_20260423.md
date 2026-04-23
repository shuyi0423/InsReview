# Test 环境审查清单导入回归报告

- 执行日期：2026-04-23
- 执行环境：test
- 页面地址：https://test-contract-agent.qtech.cn/review-rule/checkList
- API 基址：https://test-contract-agent.qtech.cn/ai/review-rule/api
- 执行命令：`HEADLESS=1 SLOW_MO=0 ./scripts/run_review_checklist_import.sh test --junitxml=artifacts/test-import-20260423/junit.xml`
- 执行结果：通过
- 用例统计：共 8 条，通过 8 条，失败 0 条，错误 0 条，跳过 0 条
- 执行耗时：251.16 秒

## 残留数据检查

- 任务中心残留：0 条
- 清理已完成任务接口：HTTP 200
- `insreview_test_checklist` 前缀清单残留：0 条

## 执行明细

| 用例 | 场景 | 状态 | 耗时秒 | 备注 |
| --- | --- | --- | ---: | --- |
| `test_review_checklist_import_modal_copy_and_default_disabled` | 导入弹窗文案、格式提示、默认按钮禁用态校验 | 通过 | 58.44 | - |
| `test_review_checklist_import_rejects_invalid_type_via_api` | 非法文件类型上传接口拦截校验 | 通过 | 1.09 | - |
| `test_review_checklist_import_valid_files_can_finalize_and_cleanup[docx]` | docx 导入、解析、保存正式清单并清理 | 通过 | 45.26 | - |
| `test_review_checklist_import_valid_files_can_finalize_and_cleanup[xlsx]` | xlsx 导入、解析、保存正式清单并清理 | 通过 | 44.04 | - |
| `test_review_checklist_import_valid_files_can_finalize_and_cleanup[doc]` | doc 旧版 Word 导入、解析、保存正式清单并清理 | 通过 | 14.32 | - |
| `test_review_checklist_import_valid_files_can_finalize_and_cleanup[xls]` | xls 旧版 Excel 导入、解析、保存正式清单并清理 | 通过 | 13.36 | - |
| `test_review_checklist_import_start_button_enables_after_selecting_valid_word` | 选择合法 Word 后开始解析按钮可用态校验 | 通过 | 73.72 | - |
| `test_review_checklist_import_can_clear_completed_tasks` | 任务中心清除已完成任务接口校验 | 通过 | 0.84 | - |

## 结论

本轮 test 环境“审查清单 > 导入清单”自动化回归通过，未发现可复现缺陷。测试产生的导入任务和正式清单已在用例内清理，回归后复核未发现残留数据。
