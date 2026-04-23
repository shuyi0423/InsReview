# InsReview | 智审平台 UI 自动化测试

`InsReview` 现在作为“智审平台 UI 自动化测试”项目维护，基于 Python、pytest 和 Playwright，负责承载智审平台核心业务页面与主流程的 UI 自动化回归。

## 项目定位

- 统一沉淀智审平台 UI 自动化测试代码
- 复用飞书登录态与环境配置，减少重复扫码和重复搭环境成本
- 逐步把人工验证过的高价值测试场景迁成可重复执行的自动化回归
- 保存历史测试文件、报告和结果基线，便于后续比对

## 当前覆盖范围

- 飞书扫码登录与登录态复用
- AI 智能审查主流程
- 审查清单模块
- 审查规则模块
- 审查清单导入回归

## 目录总览

- `tests/`
  存放所有自动化用例与公共支持代码。
- `tests/conftest.py`
  统一测试分组标记，支持按套件运行。
- `tests/auth/test_feishu_login.py`
  飞书登录与登录态保存。
- `tests/review/test_intelligent_review_flow.py`
  智能审查主流程。
- `tests/checklist/test_checklist_module.py`
  审查清单模块。
- `tests/rule/test_review_rule_module.py`
  审查规则模块。
- `tests/import/test_review_checklist_import.py`
  审查清单导入自动化主用例。
- `tests/support/review_checklist_import_support.py`
  导入清单辅助函数、API 封装、页面操作和夹具加载。
- `tests/fixtures/import/review_checklist_import/`
  导入清单测试文件。
- `scripts/run_review_checklist_import.sh`
  导入清单快捷执行脚本。
- `scripts/run_ui_suite.sh`
  标准 UI 套件执行入口。
- `scripts/run_ui_smoke.sh`
  冒烟执行入口。
- `scripts/run_ui_full.sh`
  全量执行入口。
- `scripts/bootstrap.sh`
  依赖与浏览器安装脚本。
- `env/`
  标准环境 profile，支持 dev / test / online 切换。
- `docs/import/review-checklist-import-cases.md`
  导入清单完整迁移说明与用例矩阵。
- `docs/overview/ui-automation-guide.md`
  智审平台 UI 自动化测试标准执行指南。
- `docs/import/reports/2026-04-08/`
  本轮 dev 与线上历史报告归档。

## 环境依赖

- Python 3.10+
- `pytest`
- `playwright`

安装依赖：

```bash
./scripts/bootstrap.sh
```

## 登录与环境配置

项目现在支持“基础 `.env` + 环境 profile 覆盖”。

推荐流程：

1. 参考 `.env.example` 补齐共享 `.env`
2. 使用 `env/dev.env`、`env/test.env` 或 `env/online.env`
3. 准备对应环境的登录态文件
4. 再执行业务用例

当前已提供：

- `env/dev.env`
- `env/test.env`
- `env/online.env`

当前 `.env.example` 已预留导入清单回归相关可选项：

- `REVIEW_CHECKLIST_PAGE_URL`
- `REVIEW_CHECKLIST_API_BASE_URL`
- `REVIEW_CHECKLIST_TASK_TIMEOUT_MS`
- `REVIEW_CHECKLIST_OPEN_ATTEMPTS`
- `REVIEW_CHECKLIST_OPEN_WAIT_MS`
- `REVIEW_CHECKLIST_NAME_PREFIX`
- `REVIEW_CHECKLIST_FIXTURES_DIR`

## 常用命令

运行标准冒烟：

```bash
./scripts/run_ui_smoke.sh
./scripts/run_ui_smoke.sh dev
./scripts/run_ui_smoke.sh test
./scripts/run_ui_smoke.sh online
```

运行标准全量：

```bash
./scripts/run_ui_full.sh
./scripts/run_ui_full.sh dev
./scripts/run_ui_full.sh test
./scripts/run_ui_full.sh online
```

运行导入清单回归：

```bash
./scripts/run_review_checklist_import.sh
./scripts/run_review_checklist_import.sh dev
./scripts/run_review_checklist_import.sh test
./scripts/run_review_checklist_import.sh online
```

按套件运行：

```bash
./scripts/run_ui_suite.sh import
./scripts/run_ui_suite.sh dev import
./scripts/run_ui_suite.sh test import
./scripts/run_ui_suite.sh online import
./scripts/run_ui_suite.sh checklist
./scripts/run_ui_suite.sh review
./scripts/run_ui_suite.sh review-rule
./scripts/run_ui_suite.sh regression
```

直接运行导入清单 pytest：

```bash
python3 -m pytest tests/import/test_review_checklist_import.py -s
```

仅做收集校验：

```bash
./scripts/run_ui_suite.sh collect
```

## 导入清单迁移内容

这次已经迁入的内容包括：

- 8 条可直接执行的导入清单自动化用例
- 历史测试文件和扩展样例文件
- 2026-04-08 的 dev 测试报告、线上回归报告和结果 JSON
- 导入清单完整用例矩阵与执行说明

如果后续要扩成智审平台全量执行，建议继续在现有基础上补这几类：

- 10MB 边界与超限文件自动化
- 空白文档与扫描件识别
- 草稿页编辑、补充规则、空名称保存校验
- 任务中心刷新恢复、断网恢复、多浏览器兼容

## Git 说明

项目已经初始化为独立 git 仓库，后续可以直接在项目根目录执行常规 git 命令：

```bash
git status
git add .
git commit -m "..."
```
