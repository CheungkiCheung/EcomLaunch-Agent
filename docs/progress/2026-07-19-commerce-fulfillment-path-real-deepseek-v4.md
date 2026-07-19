# Commerce Case Agent — Real DeepSeek V4 Fulfillment Path

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: first real Path Agent behavior verified
> Final acceptance requests: `2` (`1` preflight + `1` Agent)
> Implementation-session successful requests: `4` across two independent live runs
> Implementation-session successful tokens: `8,709` total (`7,857` input, `852` output)

## Outcome

`FulfillmentPathAgent` is the first Commerce investigation path connected to the verified Case context and a fresh real DeepSeek V4 request.

The path now performs:

```text
verified LeadContextPacket
→ fulfillment-only Context slice
→ required Capability check
→ deterministic ModelRouter assignment
→ fresh real_model_preflight
→ one fresh uncached no-retry DeepSeek V4 request
→ strict JSON parsing
→ MetricObservation membership and required-comparison validation
→ deterministic Evidence ID / semantic status / cost / trace hydration
→ structured PathResult
→ immutable secret-free telemetry audit
```

The model cannot create telemetry, IDs or semantic provenance. It may only return concise observation summaries, confidence, supplied MetricObservation IDs, explicit unknowns and suggested next Paths. The system creates Evidence IDs deterministically, marks observations as derived from deterministic metrics, supplies the ModelAssignment and records versions/cost.

The Path context omits non-fulfillment metrics except evidence already linked to selected fulfillment observations. It includes baseline/current values for order count, late delivery, handling, transit and total delivery duration, plus fulfillment anomaly digests. Raw CSV rows and full source-Fact arrays remain outside the prompt.

## Model Selection Baseline

Final accepted assignment:

```text
role: path
base_profile: balanced_tool_user
selected_profile: balanced_tool_user
effort: medium
model_alias: deepseek-reasoner
router max_output_tokens: 4000
actual invocation max_output_tokens: 1600
timeout_seconds: 120
reason_codes: critical_case, profile_binding
escalation_count: 0
router_version: commerce-model-router@1.0.0
```

The separate invocation cap is deliberate and audited. It provides a concrete baseline for later cost/quality experiments instead of treating the Router ceiling as an implicit provider setting.

## Fresh Real-model Evidence

The final accepted preflight returned:

```text
run_id: preflight-df91655c8ef640ae8538843fd70cee19
actual_model_identity: deepseek-v4-flash
provider_request_id: 96d8a9a4-f100-46a5-bd34-af61025eb698
tokens: 58 input / 11 output / 69 total
latency: ~974 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
```

The final accepted Fulfillment Path request returned:

```text
run_id: fulfillment-path-1916290de9204ec6b6ebae9ec7ebeb83
actual_model_identity: deepseek-v4-flash
provider_request_id: 4c6db5c4-2a03-47d5-9e44-cd5b0c0ab4f0
tokens: 3878 input / 415 output / 4293 total
latency: ~4285 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
prompt_version: commerce.fulfillment-path@1.0.0
context_version: commerce-fulfillment-path-context@1.0.0
router_version: commerce-model-router@1.0.0
skill_version: commerce.fulfillment-investigation@1.0.0
```

The immutable audit record is stored under the Git-ignored runtime directory:

```text
.deer-flow/commerce/evaluation/path-agents/
```

It stores response and PathResult SHA-256 hashes, not Prompt text, response text, reasoning content, API keys or raw Dataset rows.

## Behavior Gate

The live test uses the real `GC-FULFILLMENT-001` uploaded files, deterministic analysis, persisted Case/Lineage/Run, fenced Worker lease and verified initial ContextPacket. Hidden expected behavior is loaded only by the evaluator after the Agent returns and never enters Agent context.

The accepted PathResult proves:

- handling-time baseline/current MetricObservation IDs are cited together;
- the observation explicitly says handling decreased or did not worsen;
- transit-time baseline/current MetricObservation IDs are cited together;
- the observation explicitly says transit increased or worsened;
- every output MetricObservation ID belongs to the Path Context;
- Provider identity, request ID, token, latency, retry and versions match the audit;
- none of the Gold Case forbidden private-metric or unsupported-causal phrases appears;
- the structured result honestly reports zero Tool calls.

## TDD and Verification

RED:

```text
ModuleNotFoundError: No module named 'app.commerce.agents.fulfillment'
exit code: 2
```

Final live command:

```text
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/agents/test_fulfillment_path_agent_live.py
```

Result:

```text
1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Deterministic Commerce regression, explicitly excluding all live provider tests:

```text
226 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed.

## Known Limits

- This is one bounded Path call, not the full Worker/Goal Loop execution shell.
- The first slice uses metrics already present in verified Path context and therefore has zero Tool calls; model-selected Tool use remains unverified.
- Invalid structured output fails closed; repair is not implemented yet.
- PathResult Evidence candidates are not yet atomically persisted into the Case/Event stream by a Worker.
- SellerPeerPathAgent, ReviewExperiencePathAgent, Lead Agent and fresh-context Verification remain unimplemented.
- One successful Gold Case is not a release gate; repeated runs, holdout and regression evaluation remain required.

## Next

Connect the fenced Worker execution shell so it persists the initial Checkpoint and `model.assigned` event before the call, consumes actual token/wall-time budget, appends accepted Path Evidence and a post-Path Checkpoint atomically, and can recover from an expired lease. Only after this lifecycle is durable should the next real Path Agent be added.
