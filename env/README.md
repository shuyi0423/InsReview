# Environment Profiles

`env/` 存放智审平台 UI 自动化测试的环境 profile。

当前已提供：

- `dev.env`
- `online.env`

使用方式：

```bash
./scripts/run_ui_suite.sh dev import
./scripts/run_ui_suite.sh online smoke
./scripts/run_ui_full.sh dev
./scripts/run_review_checklist_import.sh online
```

约定说明：

- `.env`
  放共享基础配置，例如浏览器参数、公共超时、默认测试文件路径。
- `env/<profile>.env`
  放环境专属配置，例如站点地址、登录态文件路径、导入清单 API 地址。
- 执行脚本会先加载 `env/<profile>.env`，测试代码随后再读取 `.env` 补充未覆盖的共享参数。
