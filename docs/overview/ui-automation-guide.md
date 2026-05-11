# 智审平台 UI 自动化测试指南

这份指南用于统一 `InsReview` 的目录约定、套件划分和执行入口，方便后续持续扩展为完整的智审平台 UI 自动化仓库。

## 标准目录

- `tests/`
  自动化测试代码根目录。
- `tests/conftest.py`
  统一为测试文件打套件标记，支持按模块运行。
- `tests/fixtures/<module>/`
  按模块管理测试输入文件、样例数据和历史夹具。
- `scripts/`
  标准执行入口与安装脚本。
- `docs/<module>/`
  按模块管理测试说明、迁移说明和历史报告。
- `docs/overview/`
  项目级共享说明与执行指南。
- `env/`
  按环境管理 dev / test / online profile。
- `.auth/`
  本地登录态缓存，不进入 git。
- `artifacts/`
  本地执行过程中的截图和临时产物，不进入 git。

## 当前套件划分

| 套件名 | pytest 标记 | 对应文件 |
| --- | --- | --- |
| 登录 | `auth` | `tests/auth/test_feishu_login.py` |
| 智能审查流程 | `review_flow` | `tests/review/test_intelligent_review_flow.py` |
| 审查清单 | `checklist` | `tests/checklist/test_checklist_module.py` |
| 审查规则 | `review_rule` | `tests/rule/test_review_rule_module.py` |
| 导入清单 | `checklist_import` | `tests/import/test_review_checklist_import.py` |
| 冒烟 | `smoke` | 当前默认覆盖 `导入清单` |
| 回归 | `regression` | 当前覆盖主业务回归套件 |

## 标准执行入口

统一入口：

```bash
./scripts/run_ui_suite.sh [profile] <suite>
```

可用 profile：

- `local`
- `dev`
- `test`
- `online`

可用值：

- `all`
- `smoke`
- `auth`
- `review`
- `checklist`
- `review-rule`
- `import`
- `regression`
- `collect`

## 常用命令

安装依赖与浏览器：

```bash
./scripts/bootstrap.sh
```

从本机 Chrome Profile 刷新登录态，减少人工扫码：

```bash
./scripts/refresh_auth_from_chrome.py test --chrome-profile Default
./scripts/refresh_auth_from_chrome.py dev --chrome-profile Default
./scripts/refresh_auth_from_chrome.py online --chrome-profile Default
```

如果企业账号在其他 Chrome Profile 中，把 `Default` 改成 `Profile 1`、`Profile 2` 等实际目录名。

执行导入清单：

```bash
./scripts/run_ui_suite.sh import
./scripts/run_ui_suite.sh dev import
./scripts/run_ui_suite.sh test import
./scripts/run_ui_suite.sh online import
```

执行冒烟：

```bash
./scripts/run_ui_smoke.sh
./scripts/run_ui_smoke.sh dev
./scripts/run_ui_smoke.sh test
./scripts/run_ui_smoke.sh online
```

执行全量：

```bash
./scripts/run_ui_full.sh
./scripts/run_ui_full.sh dev
./scripts/run_ui_full.sh test
./scripts/run_ui_full.sh online
```

仅收集不执行：

```bash
./scripts/run_ui_suite.sh collect
./scripts/run_ui_suite.sh dev collect
./scripts/run_ui_suite.sh test collect
```

## 环境配置约定

- `.env`
  保存共享基础配置。
- `env/dev.env`
  保存开发环境专属地址与登录态路径。
- `env/test.env`
  保存测试环境专属地址与登录态路径。
- `env/online.env`
  保存线上环境专属地址与登录态路径。
- 脚本加载 profile 后，测试代码再读取 `.env` 补齐未覆盖的共享项。

## 后续扩展建议

- 新增业务模块时，优先沿用 `tests/test_<module>.py` 命名
- 在 `tests/conftest.py` 中补对应 suite marker
- 测试文件和历史样例统一放入 `tests/fixtures/<module>/`
- 模块专项说明统一放入 `docs/<module>/`
- 稳定高价值场景优先进入 `smoke` 或 `regression`
