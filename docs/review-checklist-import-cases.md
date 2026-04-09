# 审查清单导入测试迁移说明

这份文档把本轮 `系统管理 > 智能审查规则管理 > 审查清单 > 导入清单` 的测试内容迁移到了 `InsReview` 项目中，方便后续在同一项目里持续执行。

## 已迁入内容

- 自动化主用例：`tests/import/test_review_checklist_import.py`
- 公共辅助代码：`tests/support/review_checklist_import_support.py`
- 测试夹具目录：`tests/fixtures/review_checklist_import/`
- 历史报告归档：`docs/reports/review-checklist-import/2026-04-08/`
- 快速执行脚本：`scripts/run_review_checklist_import.sh`

## 直接可执行的自动化覆盖

- 打开 `审查清单 > 导入清单` 弹窗
- 校验支持格式、`10MB` 限制文案、默认禁用态
- 通过 API 校验 `txt` 非法类型拦截
- `docx / xlsx / doc / xls` 导入解析
- 草稿生成后正式保存
- 清单删除与任务驳回清理
- `清除已完成` 接口校验

## 本轮完整用例矩阵

### Dev 范围

| Case ID | 场景 | 预期 |
| --- | --- | --- |
| IM-001 | 打开导入弹窗 | 弹出导入弹窗，展示支持格式、大小限制、取消/开始导入解析按钮 |
| IM-002 | 未选择文件 | 开始导入按钮禁用，不允许提交 |
| IM-003 | 上传有效 docx 文件 | 文件上传成功，可开始导入解析 |
| IM-004 | 上传有效 xlsx 文件 | 文件上传成功，可开始导入解析 |
| IM-005 | 上传 txt 非法类型 | 提示仅支持 Word/Excel，且不创建导入任务 |
| IM-006 | 上传超 10MB 文件 | 提示文件大小不能超过 10MB，且不创建导入任务 |
| IM-007 | 上传 10MB 临界值文件 | 10MB 文件允许上传并进入解析 |
| IM-008 | 上传 doc 旧版 Word 文件 | 允许上传并进入解析 |
| IM-009 | 上传 xls 旧版 Excel 文件 | 允许上传并进入解析 |
| IM-010 | 重复上传同名文件 | 允许重复导入并生成新任务，不应异常覆盖历史任务 |
| IM-011 | 文件名包含中文/空格/特殊字符 | 上传成功，任务中心和清单名称展示正常 |
| IM-012 | Word 导入解析 | 任务从 `PARSING` 进入 `DRAFT_READY/COMPLETED` |
| IM-013 | Excel 导入解析 | 任务从 `PARSING` 进入 `DRAFT_READY/COMPLETED` |
| IM-014 | 空白文档导入 | 系统给出明确结果且任务不挂起 |
| IM-015 | 图片型扫描件导入 | 系统给出明确结果且任务不挂起 |
| IM-016 | 任务中心展示 | 展示文件名、时间、状态、操作按钮 |
| IM-017 | 清除终态任务 | 终态任务被清理，待确认保存等未完成任务保留 |
| IM-018 | 默认清单名称回填 | 清单名称自动回填为文件名去后缀 |
| IM-019 | 规则数量与内容展示 | 展示规则名称、逻辑、风险等级、风险说明 |
| IM-020 | 不修改直接保存 | 成功生成正式审查清单 |
| IM-021 | 清单名称为空保存 | 拦截保存并提示名称必填 |
| IM-022 | 移除全部规则后保存 | 应阻止保存或给出明确提示 |
| IM-023 | 手工补充规则后保存 | 新增规则保存成功并出现在正式清单中 |
| IM-024 | 保存成功后列表落库 | 列表新增清单，名称和更新时间正确 |
| IM-025 | 任务中心状态回写 | 任务状态更新为已完成，带 `finalChecklistId` |
| IM-026 | 解析过程中刷新页面 | 刷新后任务状态保留，不丢失，后续仍可保存 |
| IM-027 | 网络中断后恢复 | 给出失败提示或可恢复机制，不应产生脏任务 |
| IM-028 | 无权限账号访问导入入口 | 隐藏导入按钮或点击后提示无权限 |
| IM-029 | 多浏览器兼容 | 关键主流程一致可用 |
| IM-030 | 连续批量导入多个文件 | 任务中心正确排队，无页面卡死或任务串乱 |

### 线上回归范围

| Case ID | 场景 | 预期 |
| --- | --- | --- |
| OLR-001 | 页面加载与入口可见 | 刷新后页面可进入可操作态，展示导入清单、任务中心、新建清单 |
| OLR-002 | 导入弹窗展示与开始按钮默认禁用 | 弹窗展示支持格式和 10MB 限制，未选文件时开始导入解析按钮禁用 |
| OLR-003 | UI 上传 Word 并创建解析任务 | 上传成功，开始导入解析按钮可用，并成功创建解析任务 |
| OLR-004 | 非法 txt 文件校验 | 拦截非法格式，返回 `Only doc/docx/xls/xlsx files are supported` |
| OLR-005 | 超 10MB 文件大小校验 | 拦截超限文件，返回 `上传文件超过大小限制，当前最大支持10MB` |
| OLR-006 | docx 导入解析并保存 | 解析完成后可保存为正式清单，并可删除清理 |
| OLR-007 | xlsx 导入解析并保存 | 解析完成后可保存为正式清单，并可删除清理 |
| OLR-008 | doc 旧版 Word 导入解析并保存 | 旧版 Word 可导入、保存并可删除清理 |
| OLR-009 | xls 旧版 Excel 导入解析并保存 | 旧版 Excel 可导入、保存并可删除清理 |
| OLR-010 | 任务中心清除已完成 | 清除已完成接口执行成功，已完成任务可被清理 |

## 运行方式

1. 确保 `.env` 里已有可用登录配置，且 `.auth/feishu-login-state.json` 有效。
2. 首次运行若 Playwright 浏览器未安装，执行 `python3 -m playwright install chromium`。
3. 运行单套导入回归：

```bash
./scripts/run_review_checklist_import.sh
```

也可以直接运行：

```bash
python3 -m pytest tests/import/test_review_checklist_import.py -s
```

## 环境变量补充

默认会复用项目现有的 `APP_LOGIN_URL` 与 `AUTH_STORAGE_STATE_PATH`。如果后续你想切换环境或接口地址，可以在 `.env` 中增加这些可选项：

- `REVIEW_CHECKLIST_PAGE_URL`
- `REVIEW_CHECKLIST_API_BASE_URL`
- `REVIEW_CHECKLIST_TASK_TIMEOUT_MS`
- `REVIEW_CHECKLIST_OPEN_ATTEMPTS`
- `REVIEW_CHECKLIST_OPEN_WAIT_MS`
- `REVIEW_CHECKLIST_NAME_PREFIX`
- `REVIEW_CHECKLIST_FIXTURES_DIR`
