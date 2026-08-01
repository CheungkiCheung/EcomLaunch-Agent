# Commerce Chat Dynamic Gate v7

> 日期：2026-07-27  
> Case：`GC-FULFILLMENT-001`  
> Provider alias：`deepseek-reasoner`  
> 服务端身份：`deepseek-v4-flash`  
> 重试：`0`  
> 结果：**PASS（第二次 fresh run）**

## 1. 目标

验证当前真实产品拓扑，而不是旧 `lead-agent` 或固定业务 Crew：

```text
commerce-agent Parent
→ commerce_ingest_uploads
→ commerce_capabilities
→ 同一 Parent 响应并行 spawn Explore + Analyst
→ wait_task(mode=all)
→ 首轮终态后创建 fresh Verifier
→ wait_task
→ 中文 Evidence 综合
```

冻结窗口使用半开区间：

```text
baseline: [2017-12-02T00:00:00, 2018-01-31T00:00:00)
current:  [2018-01-31T00:00:00, 2018-04-01T00:00:00)
baseline_end == current_start
```

## 2. 第一次 fresh run：fail closed

审计：

- `failed-before-negation-aware-guard.json`
- SHA-256：`4a8522c97c0a8299ea0cb6eb4e568543d6f3ab66f330b3a18003409076fa29e1`

证据：

- fresh Preflight：PASS；
- 所有实际模型身份：`deepseek-v4-flash`；
- 请求数：17；
- Token：201,566；
- Explore / Analyst / Verifier 全部完成；
- Parent Tool Error：0；
- 核心业务指标和拓扑执行完成；
- 最终 Gate issue：`最终回答包含禁止结论：春节`。

### 根因

该失败不是数据、Tool、窗口或 Subagent 拓扑失败，而是两层最终答案保护发生了不安全组合：

1. Harness 的 `FinalAnswerPolicyMiddleware` 当时只按子串匹配，把“不能证明 A 导致 B”这类显式否定因果的安全表达也识别为 `导致` 违规；
2. 连续两次后，Harness 用通用阻断文案替换完整事实答案；
3. 后置 Response Guard 只看到不含事实的阻断文案，却同时收到完整禁词列表和必需事实正则；
4. 模型从约束文本中重构答案，并复制了原答案中不存在的“春节”。

旧审计保持 `passed=false`，没有修改、覆盖或人工改写。

## 3. TDD 修复

### Harness 否定语义

`FinalAnswerPolicyMiddleware` 现在区分：

- 安全：`不能证明运输时长上升导致晚到率变化`；
- 安全：`尚不能确认承运阶段是主因`；
- 安全：`不能完全排除卖家端其他因素`；
- 仍阻断：`但是运输时长恶化导致晚到率上升`。

匹配按当前中文/英文分句和转折边界判断；一个句子前半段的否定不会掩盖后半段新的肯定因果断言。

### Response Guard 边界

- Harness 通用阻断文案不能进入 Response Guard；
- Response Guard 只接收当前 issue 实际包含的禁词；
- 与当前答案无关的完整禁词列表不再暴露给改写模型；
- 禁词不得在否定、举例、限制、缺失项或未知项中复述；
- 改写后仍重新执行完整 deterministic Gate。

确定性回归：

```text
39 passed
1 real_model deselected
Ruff check: PASS
Ruff format: PASS
```

## 4. 第二次 fresh run：PASS

审计：

- `passed-dynamic-release-audit.json`
- SHA-256：`d0aa69a9be94f05aebc64840ab507545784a473461c514548ba71742b830c353`
- Preflight：`preflight/preflight-5855c03888824cf3bf1ebb4efe8e5726.json`
- Preflight SHA-256：`e9c9e411d90499cbb806d5c775281ff52766cf98f1d5615f2667622831b3c05b`

运行结果：

```text
pytest: 2 passed in 70.58s
run_id: 2233f98a-4dc5-4e29-b810-a8b457ab668d
preflight_run_id: preflight-5855c03888824cf3bf1ebb4efe8e5726
configured_alias: deepseek-reasoner
configured_model: deepseek-v4-flash
actual_model_identity: deepseek-v4-flash
request_count: 17
total_tokens: 199,598
parent_tokens: 150,511
subagent_tokens: 49,087
retry_count: 0
request_ids_unique: true
parent_tool_error_count: 0
issues: []
passed: true
```

### Durable Task

| Profile | Task | Skill | Tool | 预算 | 状态 |
| --- | --- | --- | --- | --- | --- |
| Explore | `call_00_VUvad2ntExLZhzERtcDt0930` | `fulfillment-investigation` | `commerce_seller_coverage` | 1 round / 1 call | completed |
| Analyst | `call_01_0ZQydcy2z1afPNG82kWM6539` | `fulfillment-investigation` | `commerce_compare_windows`, `commerce_evidence_query` | 2 rounds / 2 calls | completed |
| Verifier | `call_00_SqgQkQl1GypduPJkVzQO6853` | `fulfillment-investigation` | coverage + compare + evidence | 2 rounds / 3 calls | completed |

Explore 与 Analyst 创建时间只相差约 1ms，生命周期真实重叠。Verifier 在两者终态后创建，并显式引用：

```text
task:call_00_VUvad2ntExLZhzERtcDt0930
task:call_01_0ZQydcy2z1afPNG82kWM6539
```

### 确定性事实 Gate

最终答案原文不进入 Git；审计仅保存 SHA-256：

```text
43e8d0a14c841f40629db420ff0485675987ffc2ce1b3e1997c95f08799e7bea
```

完整 Gate 已验证：

- baseline 订单数：141；
- current 订单数：202；
- baseline 晚到率：3.55%；
- current 晚到率：35.15%；
- current 处理时长：46.83/46.84h；
- current 运输时长：494.82/494.83h；
- 至少一个 `mobs_` Evidence ID；
- 中文、反证或替代解释、数据限制和下一步；
- 不声称拥有库存、利润、曝光、点击、广告消耗或真实 GMV；
- 不把相关性写成因果；
- 不移动半开区间边界。

## 5. Repair 说明

本次正式 PASS 使用了一次受限 Response Guard：

```text
initial issue: 最终回答包含禁止结论：计算可靠
repair_count: 1
error_code: null
```

改写调用仍为 fresh `deepseek-v4-flash`、`max_retries=0`、无 Tool，并计入 17 个请求和 199,598 Token；改写后完整 Gate 重新执行并通过。它不是 Mock、Replay、缓存、模型回退或人工改答案。

该结果满足当前 Release Gate，但“首答无修复”仍是后续调优项，不应把本次结果描述成 repair-free。

## 6. 边界

- 本次 runner 使用隔离内存 Checkpointer/Task Store，证明动态 Agent 行为，不产生可供前端直接打开的持久化 Thread；
- 浏览器 Release Gate 仍需从真实 DeerFlow Chat 创建新的持久化 Thread/Run，并在同一 Run 上检查 Chat、协作空间、Drawer、移动端和 reduced-motion；
- Mock Playwright 只证明 UI 机械映射，不能替代该真实浏览器 Agent Gate。
