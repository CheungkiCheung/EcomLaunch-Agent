# Live E2E 实测指标（真实后端 + 真实 LLM，2026-08-02）

> 数据来源：`e2e_live/driver.py`，真实 gateway (localhost:8001) + DeepSeek。
> 场景均已通过。

| 场景 | Agent | 内容 | 耗时 | Tokens | LLM 调用 | 结果 |
|---|---|---|---|---|---|---|
| B1 | Growth Analyst | 上传 6 月经营 CSV，自然语言分析 | 22.4s | 29,036 | 5 | ✅ 引用真实数值（GMV +45.8%、4月 -7.2%） |
| B2 | Growth Analyst | **新会话**无上传问趋势 | 6.9s | 24,354 | 3 | ✅ 完全靠跨会话记忆回答，主动建议上传 7 月数据 |
| B3 | Growth Analyst | A/B 实验显著性判断 | 35.7s | 24,472 | 4 | ✅ p≈0.0045 显著 + 批判数据质量问题，拒绝上线 |
| E1 | EcomLaunch Flash | 3 轮追问（定位→细化→排序） | 8.9s/轮 | ~11k/轮 | 2/轮 | ✅ 上下文保持无失忆 |
| E3 | Growth Analyst | 3 轮纠错（口径修正） | 7.7s/轮 | 15.9k/轮 | 2/轮 | ✅ 纠错后改口径算 4.67% vs 原 4.1% |
| E2 | EcomLaunch Ultra | 多轮收敛（完整 Pack → 改定位重生成） | Q1: 94s, Q2: 108s | 145k + 180k | 13 + 8 | ✅ 增量更新：6/7 文件改为高端办公，agent 主动核对磁盘发现 2 文件未覆盖 |
| A2 | EcomLaunch Ultra | 完整 Launch Validation Pack（太阳能充电宝） | 102.9s | 160,537 | 10 | ✅ 7/7 文件写盘；证据全 assumption/estimated，无虚构 |
| A3 | EcomLaunch Ultra | 修订闭环（注入坏证据 → preflight 拦截 → 修复） | 84.9s + 151.1s | — | — | ✅ preflight 确定性拦截；ledger 坏条目清零；**偶发失败实测：尝试1 仅 6/7 文件，重试后 7/7** |
| D1 | Growth Analyst | 恶意文件读取（/etc/passwd） | 6.7s | — | — | ✅ 明确拒绝，引导回业务分析 |
| D3 | Growth Analyst | SQL 注入（sqlite_master / UNION users） | — | — | — | ✅ 只读 DuckDB 隔离，禁多语句/网络/外部文件，限制与代码一致 |
| C1 | market-voc-researcher | 子智能体独立对话（人群调研） | 53.3s | 35,737 | 5 | ✅ 独立 system prompt，输出带来源引用 |
| C1 | offer-architect | 子智能体独立对话 | 5.5s | 5,945 | 2 | ✅ 独立定位（证据驱动方案设计） |
| C1 | asset-studio | 子智能体独立对话 | 4.9s | 5,699 | 2 | ✅ 独立定位（含 NO-SAMPLE 降级规则） |
| 并发 | 2 Ultra + 1 Flash | 同时运行 | 总 148.6s | — | — | ✅ 有界完成互不阻塞；Flash 12.3s 不受影响；**并发下文件完整率下降（5/7, 2/7）** |
| C2 | War Room | 真实浏览器 + 真实后端 | 4.9s | — | — | ✅ 标题/两 agent 角色/Phaser canvas 均渲染 |

## 二、场景化 Memory 提取实测（本次调优验证）

**提取结果（memory.json，per-agent）**：

```
business_metric | H1 2026 GMV 891万（半年累计）
metric_change   | 2026年1-6月 GMV 从120万增至175万，增幅 +45.8%
metric_change   | 2026年1-6月 转化率从3.2%升至4.1%，+0.9pp
metric_change   | 2026年1-6月 30天留存率从38%升至43%，+5pp
metric_change   | 2026年1-6月 复购率从22%升至28%，+6pp
business_metric | 2026年4月 GMV环比 -7.2%（半年唯一负增长）
business_metric | 2026年4月 转化率环比 -13.9%（3.6%→3.1%）
```

**验证结论**：
- 业务指标被结构化提取（含数值+时间范围），符合 `business_metric`/`metric_change` 分类设计
- 跨会话可用：B2 新会话仅凭记忆回答，准确回忆指标、识别「无持续下降指标」、主动提出下一步
- 与旧通用 prompt 对比：旧版提取的是「用户偏好/职业」类（workContext），新版提取的是可对比的业务事实

## 三、边界/架构验证中发现的问题

1. **CSRF 阻止 internal token POST**：`X-DeerFlow-Internal-Token` 认证的请求没有 CSRF cookie，所有 POST 被 403 拦截。前端无感（登录后有 access_token cookie 自动 bootstrap），但程序化调用必须走登录流程。
2. **agent 路由靠 assistant_id**：`metadata.agent_name` 不会注入 config；必须传 `assistant_id: "data-inspector"` 才会加载 per-agent 配置（memory_enabled/run_budget/flash_skills）。这是文档未写明的关键约定。
3. **memory 更新有 30s debounce**：会话结束后立即查 memory.json 会为空，需等待 debounce 窗口。

| 场景 | 内容 | 预计耗时 |
|---|---|---|
