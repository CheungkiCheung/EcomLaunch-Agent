# Commerce Case Agent — Fenced Path → Lead → Verification Loop

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: first real diagnosis Goal Loop completed
> Final acceptance requests: `6` (`3` fresh preflights + Path + Lead + Verifier)
> Final acceptance tokens: `13,690` total (`13,478` Agent + `212` preflight)

## Outcome

The first Commerce investigation now closes a real, fenced, auditable diagnosis Loop:

```text
queued Investigation Run
→ acquire lease + fencing token
→ verified initial Context
→ fresh Fulfillment Path
→ append Path Evidence
→ reload Case
→ build internally consistent completed-Path Lead Context
→ fresh Lead synthesis
→ atomically persist proposed Hypothesis v1
→ build fresh Verification Context without Lead reasoning
→ fresh Verifier
→ atomically persist supported/rejected Hypothesis v2
→ GoalLoop decision
→ completed(goal_achieved) or blocked(verification_replan_required)
```

The accepted `GC-FULFILLMENT-001` run produced four direct diagnostic claims:

- late-delivery rate increased;
- handling time decreased;
- transit time increased;
- observed deterioration is concentrated in transit rather than handling.

Every claim cites only Evidence emitted by the completed Fulfillment Path. The Verifier passed all four, and the system persisted each as `proposed` version 1 then `supported` version 2. The Run ended as `completed / verifying` with `goal_achieved`.

## Durable Boundaries

The final Event Stream contains 32 ordered Run events, including:

```text
3 × model.assigned
path.started / path.completed
lead.started / lead.completed
verification.started / verification.completed
8 × hypothesis.version_appended
goal_loop.stopped
run.status_changed → completed
```

Five Checkpoints preserve external-call uncertainty boundaries:

| Sequence | Boundary | Iteration | Tokens | Escalations |
|---:|---|---:|---:|---:|
| 1 | pre-Path | 0 | 0 | 0 |
| 2 | post-Path | 1 | 4,314 | 0 |
| 3 | pre-Lead | 1 | 4,314 | 1 |
| 4 | pre-Verification | 1 | 8,770 | 1 |
| 5 | post-Verification | 2 | 13,478 | 1 |

The final budget also records one Path Agent, zero Tool calls, zero verification repairs and about `12.43s` of Agent-request latency. Preflight usage is kept in each model audit and is not charged twice into the Commerce Agent usage snapshot.

Hypothesis batches and their completion events are committed in one SQL transaction. Writes carrying a Run ID require the current lease; a missing or takeover-fenced lease cannot append any part of the batch. The raw lease token never enters Checkpoints or Events.

## Context and Claim Policy Hardening

The completed-Path Lead Context now has one consistent scope:

- Evidence is limited to newly persisted Path Evidence;
- Analysis reuses the fulfillment-only Path metric/anomaly slice;
- Manifest Evidence/Metric/Anomaly IDs match that slice;
- Case identity must remain stable while its optimistic version may advance;
- canonical context hash is recomputed after scoping.

`evidence_ids` may contain only supplied `evd_*` IDs. Anomaly and Metric IDs cannot be placed into that field.

Lead and Verification share a deterministic overclaim guard. Claims containing unsupported causal or inferential markers such as `caused`, `driven by`, `attributable to`, `due to`, `indicating`, `suggesting` or `implying` fail closed. The accepted Lead prompt is `commerce.lead-synthesis@1.2.0`; the accepted Verification prompt is `commerce.verification@1.1.0`.

## Real-model Tuning Evidence

No failed run below was counted as PASS:

1. The initial sandboxed preflight returned `blocked_real_model_unavailable / APIConnectionError`. It made one attempt, zero retries and no Agent request. The test was rerun outside the restricted network to distinguish environment blocking from provider availability.
2. The first full external run reached completed/pass internally, but the test exposed a broad review-domain claim and `driven primarily by / attributable to` language. The result was rejected as an acceptance failure.
3. After Evidence-only scoping, Lead emitted `anom_*` values in `evidence_ids`; strict schema validation failed. Inspection showed full-Case Analysis remained visible while Evidence had been narrowed.
4. After Analysis/Manifest scoping, the next run stopped locally after a successful Path because CaseHeader equality incorrectly rejected the expected version increase caused by Evidence writes. Stable identity plus monotonic version replaced whole-object equality.
5. The next complete run correctly entered `verification_replan_required`: three claims passed, while `indicating carrier transit worsened` was rejected as unsupported causal language. The result consumed one repair budget and persisted a partial/blocked terminal state; it was not rewritten into pass.
6. Lead prompt `1.2.0` switched to direct observation statements and removed inferential connectors. A fully fresh six-request run then passed every boundary and behavior assertion.

This sequence is the concrete prompt/context/harness tuning record. The acceptance standard was tightened during debugging; no test was relaxed to admit a previously unsafe output.

## Final Fresh DeepSeek V4 Evidence

Path preflight:

```text
run_id: preflight-6340a68398fc42c398a09e98000c483e
provider_request_id: cfbd182c-5b6e-41c3-b139-1459f205c78f
actual_model_identity: deepseek-v4-flash
tokens: 59 input / 11 output / 70 total
latency: ~1082 ms
request_attempt_count: 1
retry_count: 0
```

Fulfillment Path:

```text
run_id: fulfillment-path-1647d76195a34e0e817bcbb233f1e32a
provider_request_id: 7a65f4c7-5729-45f7-b8ff-f4c938345fdf
actual_model_identity: deepseek-v4-flash
tokens: 3913 input / 401 output / 4314 total
latency: ~3733 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
profile: balanced_tool_user
effort: medium
invocation output cap: 1600
```

Lead preflight:

```text
run_id: preflight-8746b89cd933474d82f4aee57fa6c203
provider_request_id: 49209a3a-fd1c-4098-8451-5b34458ce270
actual_model_identity: deepseek-v4-flash
tokens: 60 input / 11 output / 71 total
latency: ~976 ms
request_attempt_count: 1
retry_count: 0
```

Lead:

```text
run_id: lead-synthesis-fe202a8e194f491db36d736a0cf307aa
provider_request_id: d0d969d4-7753-4726-ad4d-33b1c44cdf75
actual_model_identity: deepseek-v4-flash
tokens: 4031 input / 425 output / 4456 total
latency: ~3834 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
profile: strong_synthesizer
effort: high
escalation_count: 1
router output ceiling: 6000
invocation output cap: 1800
prompt_version: commerce.lead-synthesis@1.2.0
context_version: commerce-lead-path-synthesis-context@1.0.0
router_version: commerce-model-router@1.0.0
skill_version: commerce.lead-synthesis@1.0.0
```

Verification preflight:

```text
run_id: preflight-06ea85b2b6e34f58afb882533028754f
provider_request_id: 30db4ec3-fed3-4c19-accb-835197cf7262
actual_model_identity: deepseek-v4-flash
tokens: 60 input / 11 output / 71 total
latency: ~630 ms
request_attempt_count: 1
retry_count: 0
```

Verifier:

```text
run_id: verification-0483928c1b514e439c2ff449116127ac
provider_request_id: f7fa7b52-ba0c-4538-b4b4-e9e3e0861dca
actual_model_identity: deepseek-v4-flash
tokens: 4084 input / 624 output / 4708 total
latency: ~4859 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
profile: strong_verifier
effort: high
router output ceiling: 5000
invocation output cap: 1600
prompt_version: commerce.verification@1.1.0
context_version: commerce-verification-context@1.0.0
router_version: commerce-model-router@1.0.0
skill_version: commerce.claim-verification@1.0.0
```

The six successful requests used `13,690` total tokens and about `15.11s` of summed provider latency. The live pytest completed in `16.74s`.

Audits remain under Git-ignored directories and store metadata plus hashes, not Prompt text, raw response text, reasoning content, API keys or raw Dataset rows.

## Verification

TDD RED for the integrated Worker:

```text
TypeError: CommerceInvestigationWorker.__init__() got an unexpected keyword argument 'lead_agent'
exit code: 1
```

Final fresh live gate:

```text
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/agents/test_worker_lead_verification_loop_live.py

1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Full deterministic Commerce regression, explicitly excluding all seven live provider tests:

```text
241 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed.

## Known Limits

- `execute_fulfillment_case_loop` continues under the same live lease. Restart continuation from a completed Path Checkpoint is classified but not yet executed automatically.
- Invalid structured output still fails closed; a bounded structured-repair role is not implemented.
- A non-pass Verification ends the current investigation Run partial/blocked and records `verification_replan_required`; creation and execution of the next `RunType.REPLAN` is pending.
- Verification detail is persisted in the authoritative Event Stream rather than a dedicated query projection/table.
- Only Fulfillment is executable. SellerPeer and ReviewExperience still need real Path Agents before multi-Path synthesis is truthful.
- Zero Tool calls remain honest for this metric-in-context slice; model-selected Tool use is not yet verified.
- One accepted run is not a release gate; repeated-run, holdout, regression and all-Gold-Case evaluation remain pending.

## Next

Implement `SellerPeerPathAgent` over the existing outcome-agnostic cohort metrics, then add a multi-Path Worker cycle that can execute a Replan Run rather than stopping after `verification_replan_required`. Every new Agent behavior gate must use fresh DeepSeek V4 requests and preserve the same fencing, Context, Evidence, Verification and budget contracts.
