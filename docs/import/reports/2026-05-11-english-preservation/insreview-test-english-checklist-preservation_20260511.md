# InsReview test 导入英文审查清单专项验证

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 验证日期 | 2026-05-11 |
| 平台 | InsReview / 智审平台 |
| 环境 | test |
| API | `https://test-contract-agent.qtech.cn/ai/review-rule/api` |
| 登录态 | 从本机 Chrome test 登录态刷新到 `.auth/feishu-login-test.codex-refresh.json` |
| 验证目标 | 解决用户导入英文审查清单会被翻译成中文的问题 |

## 前置说明

原有 `.auth/feishu-login-test.json` 调用 test 导入接口返回 `401 token验证失败`。本次使用本机 Chrome 已登录 cookie 刷新 Playwright storage state 后继续验证，非法 `txt` 探测返回预期 `400 Only doc/docx/xls/xlsx files are supported`，确认鉴权可用。

## 测试样本

临时生成英文 Word 与 Excel 样本，结构复用现有有效夹具的导入格式：

- 表头保留为 `审查项 / 审查标准 / 风险等级 / 处理建议`。
- 英文内容锚点：
  - `Confidentiality Notice Must Remain in English`
  - `The supplier shall keep all confidential information strictly protected and shall notify the buyer before any disclosure.`
  - `Request legal review before approval when the confidentiality clause is missing.`

## 执行结果

| 场景 | 任务结果 | 关键证据 | 结论 |
| --- | --- | --- | --- |
| 英文 Word 导入 | `FAILED` | `AI_DISPATCH_FAILED`, `AI service did not accept request, code=0, msg=parse failed` | 阻塞 |
| 中文基线 Word 导入 | `FAILED` | 现有 `valid-word.docx` 同样返回 `parse failed` | Word 解析链路当前不可用 |
| 英文 Excel 导入 | `DRAFT_READY`, `draftRuleCount=2` | 草稿规则名、规则内容、风险提示均为英文表达，未出现中文化 | 通过 |

英文 Excel 草稿片段：

```json
{
  "selectedRules": [
    {
      "name": "Confidentiality Notice Language Requirement",
      "content": "If the confidentiality notice in the sales agreement is not in English, or if the confidentiality clause is missing the requirement that the supplier shall keep all confidential information strictly protected and notify the buyer before any disclosure, then it is determined as a high - risk issue.",
      "riskTips": "Request legal review before approval when the confidentiality clause is missing."
    },
    {
      "name": "Checklist Language Requirement",
      "content": "If the language of the checklist is not English after import, then it is determined as a risk issue.",
      "riskTips": "Ensure the checklist language remains English after import."
    }
  ]
}
```

## 清理情况

本次仅创建导入解析任务，未保存正式审查清单；已对产生的任务执行 `dismiss` 清理。

## 结论

InsReview test 环境中，英文 Excel 导入不再被翻译成中文，本专项 Excel 场景通过；Word/docx 场景因解析链路对英文样本和中文基线样本均失败，需先恢复 Word 解析能力后再补测。
