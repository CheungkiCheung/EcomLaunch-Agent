# Backend Instructions

先遵循仓库根目录 `AGENTS.md`，再遵循本文件。现有 DeerFlow 架构细节和命令见 `CLAUDE.md`。

## Boundary

- `packages/harness/deerflow/` 是通用 Harness；不得导入 `app.*`。
- Commerce 业务代码放在 `app/commerce/`，可以导入 `deerflow.*`。
- Commerce API 通过独立 Router 暴露，并且只在 `GatewayConfig.commerce_case_agent_enabled` 为 `true` 时挂载。
- Commerce 使用独立 Domain、Repository 和迁移入口；不得复用旧 OpenSKU Artifact 作为业务数据库。
- 确定性 Metric、Capability、异常扫描和状态转换不得交给 LLM 计算。

## Testing

- Domain、Metric、State、Repository、Event、Budget、Policy 和数据质量测试保持无模型。
- 任何 Lead、Path Agent、Router 模型判断、Tool Selection、Verification、Eval 或 E2E 测试必须通过真实 DeepSeek V4 Preflight。
- 禁止使用 Fake ChatModel、Mock LLM、Replay 或缓存响应证明 Commerce Agent 通过。
- 现有 DeerFlow 中使用 Fake/Replay 的上游测试可以作为历史基础设施参考，但不能作为 Commerce Agent 验收证据，也不要混入 Commerce Release Gate。
- 真实模型身份、请求 ID、Token、Latency、Retry 和版本元数据必须持久化。

## Implementation

- 新功能先写失败测试；只实现当前阶段最小合同。
- FastAPI Router 不直接承载业务规则；调用 application service。
- Domain 不依赖 FastAPI、LangChain、LangGraph、数据库 ORM 或前端类型。
- Agent 输入输出使用版本化结构化合同；解析失败必须显式进入 repair / blocked 流程。
- Domain Event 是前端状态的唯一权威来源。
- 更新后同步维护根 `README.md`、本目录 `CLAUDE.md` 和相关 ADR / 计划。
