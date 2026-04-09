# 智审平台 UI 自动化测试指南

这份指南用于统一 `InsReview` 的目录约定、套件划分和执行入口，方便后续持续扩展为完整的智审平台 UI 自动化仓库。

## 标准目录

- `tests/`
  自动化测试代码根目录。
- `tests/conftest.py`
  统一为测试文件打套件标记，支持按模块运行。
- `tests/fixtures/`
  测试输入文件、样例数据和历史夹具。
- `scripts/`
  标准执行入口与安装脚本。
- `docs/`
  测试说明、迁移说明、历史报告和项目指南。
- `.auth/`
  本地登录态缓存，不进入 git。
- `artifacts/`
  本地执行过程中的截图和临时产物，不进入 git。

## 当前套件划分

| 套件名 | pytest 标记 | 对应文件 |
| --- | --- | --- |
| 登录 | `auth` | `tests/test_feishu_login.py` |
| 智能审查流程 | `review_flow` | `tests/test_intelligent_review_flow.py` |
| 审查清单 | `checklist` | `tests/test_checklist_module.py` |
| 审查规则 | `review_rule` | `tests/test_review_rule_module.py` |
| 导入清单 | `checklist_import` | `tests/test_review_checklist_import.py` |
| 冒烟 | `smoke` | 当前默认覆盖 `导入清单` |
| 回归 | `regression` | 当前覆盖主业务回归套件 |

## 标准执行入口

统一入口：

```bash
./scripts/run_ui_suite.sh <suite>
```

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

执行导入清单：

```bash
./scripts/run_ui_suite.sh import
```

执行冒烟：

```bash
./scripts/run_ui_smoke.sh
```

执行全量：

```bash
./scripts/run_ui_full.sh
```

仅收集不执行：

```bash
./scripts/run_ui_suite.sh collect
```

## 后续扩展建议

- 新增业务模块时，优先沿用 `tests/test_<module>.py` 命名
- 在 `tests/conftest.py` 中补对应 suite marker
- 测试文件和历史样例统一放入 `tests/fixtures/`
- 模块专项说明放 `docs/`
- 稳定高价值场景优先进入 `smoke` 或 `regression`
