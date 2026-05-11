# 双平台 test 导入英文审查清单格式修正复测报告

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 复测日期 | 2026-05-11 |
| 涉及平台 | InsReview / 智审平台；WisContract / 智书合同 |
| 环境 | test |
| 模块 | 审查清单 > 导入清单 |
| 复测目标 | 英文审查清单标准样例格式修正后，导入草稿内容保持英文，不被翻译成中文 |
| 结论 | 通过 |

## 样例修正

| 样例 | 修正内容 | 固定路径 | 结构校验 |
| --- | --- | --- | --- |
| 英文 Word | 改为段落式规则块，不再使用 Word 表格承载规则 | `InsReview/tests/fixtures/import/review_checklist_import/english-word.docx`；`WisContract/tests/fixtures/review-checklist-import/english-word.docx` | `33` 个段落，`0` 个表格 |
| 英文 Excel | 固定 `审查清单` sheet，补齐元信息、标准表头与 5 条英文规则 | `InsReview/tests/fixtures/import/review_checklist_import/english-excel.xlsx`；`WisContract/tests/fixtures/review-checklist-import/english-excel.xlsx` | `10` 行，`5` 列 |

同版标准样例已同步放入本机下载目录：

- `/Users/shuyi/Downloads/english-review-checklist-sample.docx`
- `/Users/shuyi/Downloads/english-review-checklist-sample.xlsx`

共享样例源文件：

- `/Users/shuyi/AIcodinghackathon/english-checklist-samples/english-review-checklist-sample.docx`
- `/Users/shuyi/AIcodinghackathon/english-checklist-samples/english-review-checklist-sample.xlsx`

## 执行范围与结果

### 用例明细

| 用例编号 | 平台 | 自动化用例 | 样例文件 | 校验点 | 实际结果 | 结论 |
| --- | --- | --- | --- | --- | --- | --- |
| ENG-IR-001 | InsReview / 智审平台 | `test_review_checklist_import_english_files_keep_draft_language[english_docx]` | `tests/fixtures/import/review_checklist_import/english-word.docx` | 上传成功；创建导入任务成功；任务进入 `DRAFT_READY`；草稿 `selectedRules` 有规则；规则名称、内容、风险提示不含中文；包含 `English` 与 `confidential` 语义 | 通过，任务完成后已 `dismiss` 清理 | 通过 |
| ENG-IR-002 | InsReview / 智审平台 | `test_review_checklist_import_english_files_keep_draft_language[english_xlsx]` | `tests/fixtures/import/review_checklist_import/english-excel.xlsx` | 上传成功；创建导入任务成功；任务进入 `DRAFT_READY`；草稿 `selectedRules` 有规则；规则名称、内容、风险提示不含中文；包含 `English` 与 `confidential` 语义 | 通过，任务完成后已 `dismiss` 清理 | 通过 |
| ENG-WC-001 | WisContract / 智书合同 | `keeps english docx checklist draft content in English` | `tests/fixtures/review-checklist-import/english-word.docx` | 上传成功；创建导入任务成功；任务进入 `DRAFT_READY`；草稿 `selectedRules` 有规则；规则名称、内容、风险提示不含中文；包含 `English` 与 `confidential` 语义 | 通过，任务完成后已 `dismiss` 清理 | 通过 |
| ENG-WC-002 | WisContract / 智书合同 | `keeps english xlsx checklist draft content in English` | `tests/fixtures/review-checklist-import/english-excel.xlsx` | 上传成功；创建导入任务成功；任务进入 `DRAFT_READY`；草稿 `selectedRules` 有规则；规则名称、内容、风险提示不含中文；包含 `English` 与 `confidential` 语义 | 通过，任务完成后已 `dismiss` 清理 | 通过 |
| ENG-WC-003 | WisContract / 智书合同 | `keeps imported English xlsx checklist draft content in English` | `tests/fixtures/review-checklist-import/english-excel.xlsx` | API 上传成功；创建导入任务成功；任务进入 `DRAFT_READY`；草稿 `selectedRules` 有规则；规则名称、内容、风险提示不含中文；包含 `English` 与 `confidential` 语义 | 通过，任务完成后已 `dismiss` 清理 | 通过 |

### 执行汇总

| 平台 | 执行层 | 用例数 | 通过 | 失败 | 命令结果 |
| --- | --- | ---: | ---: | ---: | --- |
| InsReview / 智审平台 | pytest 导入清单接口闭环 | 2 | 2 | 0 | `2 passed in 75.44s (0:01:15)` |
| WisContract / 智书合同 | Playwright spec 导入清单闭环 | 2 | 2 | 0 | `2 passed (1.4m)` |
| WisContract / 智书合同 | Playwright API 导入清单回归 | 1 | 1 | 0 | `1 passed (29.2s)` |
| 合计 | 双平台 test 英文导入复测 | 5 | 5 | 0 | 全部通过 |

## 执行命令

InsReview：

```bash
APP_LOGIN_URL=https://test-contract-agent.qtech.cn/login \
AUTH_STORAGE_STATE_PATH=.auth/feishu-login-test.codex-refresh.json \
REVIEW_CHECKLIST_PAGE_URL=https://test-contract-agent.qtech.cn/review-rule/checkList \
REVIEW_CHECKLIST_API_BASE_URL=https://test-contract-agent.qtech.cn/ai/review-rule/api \
REVIEW_CHECKLIST_NAME_PREFIX=insreview_test_checklist \
python3 -m pytest -s 'tests/import/test_review_checklist_import.py::test_review_checklist_import_english_files_keep_draft_language'
```

WisContract UI：

```bash
PLAYWRIGHT_STORAGE_STATE=/Users/shuyi/PycharmProjects/InsReview/.auth/feishu-login-test.codex-refresh.json \
PLAYWRIGHT_REVIEW_CHECKLIST_URL=https://test-contract.qtech.cn/admin/review-rules/check-list \
PLAYWRIGHT_REVIEW_CHECKLIST_API_BASE=https://test-contract.qtech.cn/ai/review-rule/api \
PLAYWRIGHT_REVIEW_CHECKLIST_FIXTURES=tests/fixtures/review-checklist-import \
npx playwright test tests/specs/review-checklist-import.spec.ts --grep "keeps english" --workers=1
```

WisContract API：

```bash
PLAYWRIGHT_STORAGE_STATE=/Users/shuyi/PycharmProjects/InsReview/.auth/feishu-login-test.codex-refresh.json \
PLAYWRIGHT_REVIEW_CHECKLIST_API_BASE=https://test-contract.qtech.cn/ai/review-rule/api \
PLAYWRIGHT_REVIEW_CHECKLIST_FIXTURES=tests/fixtures/review-checklist-import \
npx playwright test tests/api/review-checklist-import.api.spec.ts --grep "English xlsx" --workers=1
```

## 结论

双平台 test 环境复测通过。英文 Word 样例已修正为无表格的段落式格式，英文 Excel 样例已固定为标准导入文件；InsReview 与 WisContract 的英文导入场景均能生成英文草稿，未复现“英文审查清单被翻译成中文”的问题。

## 备注

- 登录态文件仅本地使用，未纳入提交。
- 本机无 `soffice` 可执行文件，未使用 LibreOffice 渲染；已通过文档结构校验确认 Word 样例不含表格，并用 macOS Quick Look 生成缩略图预览。
- 本报告为格式修正后的双平台联合复测结论；此前分平台专项报告保留为历史初测记录。
