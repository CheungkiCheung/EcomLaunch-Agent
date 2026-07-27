# Four-Gold Full Agent Investigation Release Gate

> Date: 2026-07-20  
> Branch: `feature/commerce-case-agent`  
> Status: passed with fresh DeepSeek V4; Action/Follow-up execution is outside this investigation-only gate

## Outcome

All four versioned public Gold Cases now pass one unified persisted Agent investigation flow:

```text
uploaded public fixture
→ deterministic Data Intake / Capability / Metric / Case
→ persisted Run + Lease/Fencing
→ Capability-first Router
→ 1–2 concurrent DeerFlow Path Subagents
→ Evidence Barrier
→ persisted multi-Path Lead synthesis
→ Hypothesis versions
→ independent Fresh Verification Subagent
→ Goal Loop stop
→ completed Run + released Lease
→ deterministic + semantic Gold scorecard
```

Accepted command:

```text
cd backend
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/evaluation/test_gold_agent_release_live.py \
  -m real_model \
  --basetemp=../.deer-flow/commerce/evaluation/live-test-artifacts/four-gold-agent-release-v11

1 passed, 1 unrelated LangGraph warning
94.19s
```

The accepted report is stored in the Git-ignored live-artifact directory:

```text
.deer-flow/commerce/evaluation/live-test-artifacts/
  four-gold-agent-release-v11/
  test_four_gold_cases_complete_0/
  four-gold-agent-release/
  report-096576d6cf8b41a9acd45bc761ad9996.json
```

## Case results

| Case | Expected Paths | Actual Paths | Run | Events | Checkpoints | Verification | Lease | Tokens |
| --- | --- | --- | --- | ---: | ---: | --- | --- | ---: |
| `GC-FULFILLMENT-001` | Fulfillment, ReviewExperience | Fulfillment, ReviewExperience | `run_0677a7185baf43c5b7b9973a0097e7e8` | 49 | 8 | pass | released | 24,119 |
| `GC-REVIEW-002` | ReviewExperience | ReviewExperience | `run_89ad2f4b47fa48f7bf9b0b6f177f4833` | 31 | 6 | pass | released | 14,101 |
| `GC-CAPABILITY-003` | Fulfillment | Fulfillment | `run_4d8567b043254914b5fa36fe7f3d9535` | 33 | 6 | pass | released | 12,475 |
| `GC-PEER-004` | Fulfillment, SellerPeer | Fulfillment, SellerPeer | `run_0b7d58e3953249ee9595692d44f93114` | 41 | 8 | pass | released | 20,783 |

Every Case has:

- `scorecard.release_gate_eligible=true`;
- `run_status=completed`;
- `stop_reason=goal_achieved`;
- exact expected/actual Path parity;
- every selected Path at `completed`, not partial success;
- Fresh Verification `pass`;
- final `run.lease_released` event.

This gate does not execute an Action, Approval, Rollback or Follow-up transaction. Those capabilities have separate deterministic and live evidence and must not be described as part of the four-Case investigation run.

## Real-model evidence

Aggregate accepted evidence:

```text
actual model identity: deepseek-v4-flash
Agent Provider requests: 14
unique Provider Request IDs: 14/14
provider retry: 0 for every request
total Agent tokens: 71,478
summed Agent latency: 85,681.81 ms
pytest wall time: 94.19 s
```

Provider Request IDs:

```text
d195cbca-57e4-4360-9192-3972afab5b9c
cd5b24aa-eaa2-4e85-9fd6-0779d63b1ba9
1e97e647-8e07-4393-b40f-6221f1cbdfdf
24140f73-ccc5-4691-b05e-1922b76e0154
deccb7f4-bf59-4e7d-90b0-a14980c95561
a2d9e25e-7bf8-4d17-9585-4eff0d52597d
24cf78fe-ba0a-49a6-8536-a99fedf97b40
bca0632b-9810-4841-9542-0cbaeef6f504
001ad46d-6468-4f3f-aaec-28561f2641f2
8dbb9427-f8cd-43e3-97cd-985170eb14a9
b3eaf2af-6191-4fd2-a1fe-52acdc331920
aea06994-98d2-4646-b809-4ee29111b3a3
39f36543-0bb1-49fd-ac6b-f9aeb0102d96
58cd5bc3-ebe5-4427-8936-34d2a48902c4
```

No Mock, Fake, Stub, Replay, cached response, fallback provider or alternate model is accepted by the gate. Each Agent request is identity-checked against the server response and must report one fresh request with retry `0`.

## Failure analysis retained from v1–v10

The accepted v11 result was not reached by hiding failed runs. Every prior directory remains immutable for audit.

| Version | Real failure | Resulting hardening |
| --- | --- | --- |
| v1 | ReviewExperience returned `invalid_path_result` with insufficient diagnostics. | Path error classification and safer diagnostics were expanded. |
| v2 | ReviewExperience output failed its schema. | Review schema failures became location/type diagnostics without raw model output. |
| v3 | Fulfillment rejected a valid multi-turn runtime as `runtime_telemetry_missing`; Review returned malformed JSON. | Provider lineage now supports 1–N fresh Tool-loop turns; JSON repair remains limited to trailing commas. |
| v4 | Review observations cited neither Fact nor Metric IDs. | Empty standalone observation noise is removed, while coverage still fails closed. |
| v5 | Fresh Verification required every Claim to cite a Metric, blocking Fact/VOC Claims. | Versioned Claim-to-Evidence input and Fact/Metric-aware verification were added. |
| v6 | The expanded eight-Claim verification JSON was truncated by a fixed 1,600-token output cap. | Output capacity now scales by Claim count from 1,600 to 5,000 and reasons are bounded. |
| v7 | The model supplied valid Fact/Metric IDs but left redundant Evidence IDs empty. | The server derives final Evidence lineage only from the Claim's original supporting Evidence. |
| v8 | The model supplied Evidence IDs but omitted Fact/Metric IDs. | The server completes the inverse source lineage from persisted Evidence; all-three-empty still fails. |
| v9 | Explicit Peer investigation requested Fulfillment without a fabricated Anomaly; Fulfillment incorrectly required an Anomaly. Unclosed async provider clients also surfaced at teardown. | Explicit-user Fulfillment may compare baseline/current snapshots with `anomalies=()`; sync/async model clients now close explicitly on their owning execution path. |
| v10 | ReviewExperience hallucinated an opaque source ID outside its packet. | Review output now chooses semantic `review_metrics`, `late_delivery_metrics` or `voc_excerpts` scopes; the server maps scopes to deterministic IDs. |
| v11 | No failed Path, schema, identity, lifecycle, budget, scorecard, Run or Lease gate. | Accepted release evidence. |

## Contract changes proven by the failures

### Fresh Verification

- Each Claim is bound to its original persisted supporting Evidence.
- Final Claim verdicts persist non-empty Evidence lineage and the required Fact and/or Metric lineage.
- Model-supplied IDs can only be subsets of the Claim's original Evidence.
- Evidence-only or source-only drafts are normalized by the server; invented and cross-bound references still fail.
- Pure Metric Claims end with Metric references; Fact/VOC Claims can remain Fact-backed.
- Passing unsupported causal language remains forbidden.

### ReviewExperience

- The model judges semantics and selects versioned reference scopes instead of copying opaque IDs.
- `review_metrics` maps to baseline/current review score and low-rating observations.
- `late_delivery_metrics` maps to the two late-delivery observations.
- `voc_excerpts` maps to the packet's redacted review Fact IDs.
- Legacy explicit IDs remain supported but are checked against the fresh Context Manifest.

### Explicit Fulfillment

- Detected-anomaly Cases still require deterministic Anomaly records.
- An explicit user request may run Fulfillment from baseline/current deterministic snapshots without fabricating an Anomaly.
- The Path goal explicitly states that no anomaly was detected and only observed window differences may be described.

### Model lifecycle

- Subagent models close async and sync provider roots before returning from the isolated event loop.
- Preflight, VerifiedModelCaller, legacy Fulfillment and Semantic Candidate sync paths close provider-owned clients in `finally`.
- v11 completed without the v9 `httpx` / `Event loop is closed` teardown failures.

## Deterministic regression after v11

```text
PYTHONPATH=. .venv/bin/pytest -q -m 'not real_model' tests/commerce
413 passed, 23 real-model tests deselected

.venv/bin/ruff check app/commerce tests/commerce
All checks passed

.venv/bin/ruff check \
  packages/harness/deerflow/models/lifecycle.py \
  packages/harness/deerflow/subagents/executor.py \
  tests/test_model_lifecycle.py \
  tests/test_subagent_executor.py
All checks passed

git diff --check
passed
```

## Remaining release boundaries

- live PostgreSQL integration, migration and concurrency gate;
- external merchant Connector(s), credentials and sandbox/policy validation;
- full failure injection, security and performance release audit;
- Human Review and explicit Active Skill promotion transaction;
- Commerce React Workspace, per-page generated visual approval, War Room, browser E2E, responsive and accessibility QA;
- final Demo, architecture diagram and interview material package.
