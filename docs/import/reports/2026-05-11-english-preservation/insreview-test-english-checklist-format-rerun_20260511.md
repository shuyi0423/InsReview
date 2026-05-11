# InsReview test 导入英文审查清单格式修正复测

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 复测日期 | 2026-05-11 |
| 平台 | InsReview / 智审平台 |
| 环境 | test |
| 页面 | `https://test-contract-agent.qtech.cn/review-rule/checkList` |
| API | `https://test-contract-agent.qtech.cn/ai/review-rule/api` |
| 登录态 | 复用本机 Chrome test 登录态刷新出的 `.auth/feishu-login-test.codex-refresh.json` |
| 复测目标 | 英文审查清单标准样例格式修正后，导入草稿内容保持英文，不被翻译成中文 |

## 样例修正

| 样例 | 固定路径 | 修正内容 | 结构校验 |
| --- | --- | --- | --- |
| 英文 Word | `tests/fixtures/import/review_checklist_import/english-word.docx` | 改为段落式规则块，不再使用 Word 表格承载规则 | `33` 个段落，`0` 个表格 |
| 英文 Excel | `tests/fixtures/import/review_checklist_import/english-excel.xlsx` | 固定 `审查清单` sheet，补齐元信息、标准表头与 5 条英文规则 | `10` 行，`5` 列 |

同版样例已同步放入本机下载目录：

- `/Users/shuyi/Downloads/english-review-checklist-sample.docx`
- `/Users/shuyi/Downloads/english-review-checklist-sample.xlsx`

## 执行命令

```bash
APP_LOGIN_URL=https://test-contract-agent.qtech.cn/login \
AUTH_STORAGE_STATE_PATH=.auth/feishu-login-test.codex-refresh.json \
REVIEW_CHECKLIST_PAGE_URL=https://test-contract-agent.qtech.cn/review-rule/checkList \
REVIEW_CHECKLIST_API_BASE_URL=https://test-contract-agent.qtech.cn/ai/review-rule/api \
REVIEW_CHECKLIST_NAME_PREFIX=insreview_test_checklist \
python3 -m pytest -s 'tests/import/test_review_checklist_import.py::test_review_checklist_import_english_files_keep_draft_language'
```

## 复测结果

| 用例 | 结果 | 关键校验 |
| --- | --- | --- |
| 英文 Word 导入草稿语言保持英文 | 通过 | 草稿 `selectedRules` 中保留 `English`、`confidential` 等英文内容，未出现中文化 |
| 英文 Excel 导入草稿语言保持英文 | 通过 | 草稿 `selectedRules` 中保留 `English`、`confidential` 等英文内容，未出现中文化 |

命令结果：`2 passed in 75.44s (0:01:15)`。

## 结论

InsReview test 环境复测通过。英文 Word 样例已修正为无表格的段落式格式，英文 Excel 样例已固定为标准导入文件；两类英文导入均能生成英文草稿，未复现“英文审查清单被翻译成中文”的问题。

## 备注

- 登录态文件仅本地使用，未纳入提交。
- 本机无 `soffice` 可执行文件，未使用 LibreOffice 渲染；已通过文档结构校验确认 Word 样例不含表格，并用 macOS Quick Look 生成缩略图预览。
