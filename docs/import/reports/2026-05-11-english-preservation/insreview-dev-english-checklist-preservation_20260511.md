# InsReview 导入英文审查清单专项验证

## 基本信息

| 项目 | 内容 |
| --- | --- |
| 验证日期 | 2026-05-11 |
| 平台 | InsReview / 智审平台 |
| 环境 | dev |
| API | `https://dev-contract-agent.qtech.cn/ai/review-rule/api` |
| 登录态 | `.auth/feishu-login-state.refreshed.json` |
| 验证目标 | 解决用户导入英文审查清单会被翻译成中文的问题 |

## 测试样本

临时生成英文 Word 与 Excel 样本，结构复用现有有效夹具的导入格式：

- 表头保留为 `审查项 / 审查标准 / 风险等级 / 处理建议`，避免把解析失败误判为语言问题。
- 业务内容使用英文锚点：
  - `Confidentiality Notice Must Remain in English`
  - `The supplier shall keep all confidential information strictly protected and shall notify the buyer before any disclosure.`
  - `Request legal review before approval when the confidentiality clause is missing.`

## 执行结果

| 场景 | 任务结果 | 关键证据 | 结论 |
| --- | --- | --- | --- |
| 英文 Word 导入 | `FAILED` | `AI_DISPATCH_FAILED`, `AI service did not accept request, code=0, msg=parse failed` | 不通过 |
| 中文基线 Word 导入 | `FAILED` | 现有 `valid-word.docx` 同样返回 `parse failed` | Word 解析链路当前不可用，英文 Word 无法完成语言保持验证 |
| 英文 Excel 导入 | `DRAFT_READY`, `draftRuleCount=2` | 草稿 `selectedRules.name/content/riskTips` 被生成成中文，未包含英文锚点 | 不通过 |

英文 Excel 草稿片段：

```json
{
  "selectedRules": [
    {
      "name": "保密条款英文保持审查",
      "content": "如果保密通知未保持英文，或者保密条款中供应商未对所有机密信息进行严格保护，且在披露前未通知买方，则判定为重大风险",
      "riskTips": "在批准前，若保密条款缺失，需请求法律审查"
    },
    {
      "name": "审查清单语言英文保持审查",
      "content": "如果导入后审查清单的语言未保持英文，则判定为警示风险",
      "riskTips": "确保导入后审查清单语言为英文"
    }
  ]
}
```

## 清理情况

本次仅创建导入解析任务，未保存正式审查清单；已对产生的任务执行 `dismiss` 清理。

## 结论

InsReview dev 本次专项验证未通过。英文 Excel 清单仍被中文化；Word 导入解析链路当前对中文基线样本也失败，需要先恢复 Word 解析能力后再补测英文 Word。
