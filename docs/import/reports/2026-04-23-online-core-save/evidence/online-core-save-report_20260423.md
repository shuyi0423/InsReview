# 智审平台线上核心保存场景回归报告

- 执行环境：online
- 执行页面：https://contract-agent.qfei.cn/review-rule/checkList
- API Base：https://contract-agent.qfei.cn/ai/review-rule/api
- 执行日期：2026-04-23
- 执行人：王舒译
- 执行结果：9 passed, 16 deselected；残留复核 1 passed, 24 deselected。
- 结论：可以上线。未发现稳定产品缺陷，测试数据已清理。

## 用例结果

| ID | 用例标题 | 优先级 | 状态 | 实际结果 |
| --- | --- | --- | --- | --- |
| ON-001 | docx 有效文件导入保存闭环 | P0 | 通过 | 执行通过。 |
| ON-002 | xlsx 有效文件导入保存闭环 | P0 | 通过 | 执行通过。 |
| ON-003 | doc 旧版 Word 导入保存闭环 | P1 | 通过 | 执行通过。 |
| ON-004 | xls 旧版 Excel 导入保存闭环 | P1 | 通过 | 执行通过。 |
| ON-005 | 特殊文件名导入后保存 | P1 | 通过 | 执行通过。 |
| ON-006 | 保存时清单名称为空拦截 | P1 | 通过 | 执行通过。 |
| ON-007 | 保存时规则引用为空拦截 | P1 | 通过 | 执行通过。 |
| ON-008 | 刷新恢复后继续保存 | P1 | 通过 | 执行通过。 |
| ON-009 | 线上测试数据残留校验 | P0 | 通过 | 执行通过。 |

## 配置修正

已将 `env/online.env` 的线上智审地址修正为 `contract-agent.qfei.cn`，避免误用合同平台 `contract.qfei.cn`。
