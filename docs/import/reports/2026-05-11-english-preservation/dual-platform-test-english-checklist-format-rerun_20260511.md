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

| 平台 | 覆盖范围 | 执行结果 | 关键校验 |
| --- | --- | --- | --- |
| InsReview / 智审平台 | 英文 Word 导入；英文 Excel 导入 | `2 passed in 75.44s (0:01:15)` | 草稿 `selectedRules` 中保留 `English`、`confidential` 等英文内容，未出现中文化 |
| WisContract / 智书合同 | UI 英文 Word/Excel 导入；API 英文 Excel 导入 | UI：`2 passed (1.4m)`；API：`1 passed (29.2s)` | 页面导入草稿与 API 草稿均保持英文内容，未出现中文化 |

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
