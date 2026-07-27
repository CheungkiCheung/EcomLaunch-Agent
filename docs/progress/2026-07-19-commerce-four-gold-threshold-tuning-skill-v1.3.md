# Four-Gold Holdout, Threshold Hardening and Skill `1.3.0`

> Date: 2026-07-19  
> Branch: `feature/commerce-case-agent`  
> Status: four-case synthesis/semantic release gate and new Shadow passed; Human Review pending

## Outcome

The evaluation suite now accepts all four versioned public Gold Cases through one reproducible, fresh DeepSeek V4 gate:

```text
GC-FULFILLMENT-001
GC-REVIEW-002
GC-CAPABILITY-003
GC-PEER-004
```

`GC-PEER-004` no longer depends on test-code-only constants. Its Agent-visible `peer_analysis_request` freezes only scenario parameters:

- target seller;
- half-open time window;
- product category;
- minimum orders per seller;
- same-seller-state matching;
- explicit Fulfillment + SellerPeer requested Paths;
- `eligibility_uses_late_delivery_result=false`;
- single-seller and pure-category orders only.

The builder recomputes the outcome-agnostic cohort and geography from the uploaded fixture. Hidden expected values and forbidden claims never enter the model packet.

## RED → GREEN data contract

Initial failing gate:

```text
7 failed, 17 passed

root failure:
InputBundle rejected peer_analysis_request as an extra field
```

After adding `EvaluationPeerAnalysisRequest` and the deterministic builder branch:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/evaluation/test_live_experiment_contracts.py \
  tests/commerce/fixtures/test_gold_cases.py

24 passed
exit code: 0
```

Recomputed Peer facts:

```text
target orders: 59
target late-delivery rate: 16/59 = 27.1186%
peer sellers: 5
pooled peer orders: 257
pooled peer late-delivery rate: 19/257 = 7.3930%
gap: 19.7256 percentage points
top geography: SP=26, MG=8, RJ=7
```

## Gate gap discovered by real output

The first four-case run used `commerce-semantic-evaluator@1.1.0`:

```text
Experiment: exp_1ac1367cfb5445b597ef0d1c0ffdbab6
Candidate: 8/8, hard-gate failures=0
Control: 4/8, hard-gate failures=4
Decision produced by old gate: promote_candidate
```

The test technically passed, but manual audit rejected it as final evidence. Both Candidate Peer answers invented execution policy:

```text
“若仍超15%则触发人工审核”
“若持续高于对标均值2倍则触发人工审核”
```

Neither `15%` nor `2×` came from a configured Policy, Action contract or visible request. Accepting them would contradict the server-owned threshold boundary already enforced by the Fresh Action Planner.

This experiment is retained as tuning evidence. It was not used to activate a Skill.

## Semantic Evaluator `1.2.0`

The evaluator now has a deterministic guard in addition to the fresh semantic judge:

```text
unsupported-action-threshold
```

It rejects conditional numeric Action/monitor percentages, multipliers or percentage-point thresholds that are absent from the visible request. It allows:

- observed numeric facts such as “the gap is 19.7 percentage points”;
- a monitor that refers to a configured server-owned threshold without inventing a number;
- a bounded data request or reopen step.

TDD evidence:

```text
RED: 5 failures because _apply_deterministic_guards did not exist
GREEN: 12 passed
```

The fresh judge prompt now also receives `peer_analysis_request` and explicitly treats model-authored thresholds as unbounded guidance.

## Candidate Skill `1.3.0`

The Candidate contract was changed to:

```text
Never invent a numeric Action/monitor threshold or multiplier;
refer only to configured server policy.
```

Version binding:

```text
skill_version: commerce-diagnostic-synthesis@1.3.0-candidate
content_sha256: f46d8884d6ffba670f9c3d9299d702f9c9fdd477e759dbcaaabcc4450dc6b228
semantic_evaluator: commerce-semantic-evaluator@1.2.0
provider_retry: 0
```

## Peer micro experiment

```text
Experiment: exp_f566076c6af9487893e2a9eb40631dc9
Cases: GC-PEER-004
Repetitions: 2

Candidate: 2/2, 0 hard-gate failures
Control: 2/2, 0 hard-gate failures
Candidate mean tokens: 2011.5
Control mean tokens: 2204.5
Candidate mean latency: 4556.22 ms
Control mean latency: 6457.09 ms
Decision: promote_candidate
```

The Candidate answers now refer to configured platform policy or continued deviation from the peer mean; they contain no invented numeric trigger.

Provider Request IDs:

```text
0c8484d1-6ca5-463d-bf63-0b413dceb5f5
1a6529a7-2acf-4783-8003-a58e2bd22ceb
5553dfdd-7e97-427d-afa2-602652d420ef
61b9cf17-72f9-4ecf-9080-4f452028aa0b
bb0de04e-7465-4064-b9c8-a635a29cf08e
2e24f22a-228b-4613-9910-ba024dec6c44
1731cb9b-8f32-4447-8656-8bf264db8212
9cf5311a-b84f-483d-b0a3-3bf556c99e38
```

All eight were unique, `deepseek-v4-flash`, fresh and retry `0`.

## Final four-case Holdout

Command:

```text
cd backend
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/evaluation/test_synthesis_experiment_holdout_live.py \
  -m real_model \
  --basetemp=../.deer-flow/commerce/evaluation/live-test-artifacts/four-case-holdout-v2

1 passed, 1 unrelated LangGraph warning
exit code: 0
wall time: 112.35s
```

Accepted experiment:

```text
Experiment: exp_aca844e7ef134b7dba264e919eacdb38
Cases: 4
Repetitions: 2

Candidate:
  passed: 8/8
  hard-gate failures: 0
  mean total tokens: 2051.875
  mean latency: 4212.11 ms

Control:
  passed: 6/8
  hard-gate failures: 2
  mean total tokens: 2334.625
  mean latency: 5691.85 ms

Decision: promote_candidate
```

Candidate improved mean Token use by about `12.1%` and mean Latency by about `26.0%`. Both Control failures were `GC-FULFILLMENT-001` causal-certainty failures; the Candidate passed every deterministic and fresh semantic gate.

The 32 unique generation/evaluator Provider Request IDs are:

```text
9d0c00ef-a7b8-4f04-affa-0ac60e257608
36b230fc-35eb-4de0-8453-2d44c713c008
b221dd0c-a436-45af-97af-f4b4e3058bff
d209e82d-8faf-4041-bb8a-6ee4c4bb9819
ac8aa7aa-bb8d-47ee-8ded-d27a07bc2e94
c6e6601e-58cc-4f27-8e45-c4d57acac2cc
09ac9148-ade5-4db7-9d7b-155cd4bdc4b2
a500539c-167b-47a7-9c41-8ad3d7ca079b
85b38d16-2e21-4e8e-8098-0b77715db1ce
96eb539b-e8ce-4c77-89a4-82bcd7ed5f43
87f9d5c0-494b-4692-8462-f87b812870e0
2c3f079d-64a0-4d18-98a5-de2ca6191830
69aeddf2-cae3-4eb1-8e78-f13ffcbf7085
8b576481-26a9-4060-9bcd-d7002634299c
193211b4-e499-4ffc-8bf2-48c6a1d0ba06
5dd52a45-2006-40cb-9d0b-93db2e6c2ef0
1ee0cac5-8b87-4581-98dd-d57ba7474b7d
9ae4383e-0b82-4ce5-b1f4-b17a52a1d815
d45f8a24-fd2b-4d17-aa86-5d854a56ef8c
37a4a1ff-eaa7-4ef1-a1f8-4ab8f78ee66f
528e0115-8914-488d-90e1-b5c46aa6b41b
461a5bca-b54d-4704-841e-77635da2c71b
74dc84ba-cf57-4ae6-8d87-1e09af5a9f01
5057de2c-6277-41b4-9315-6106877c1a37
0cfdf533-4162-4b64-a964-53ddb7c54693
2270d3b0-5a1a-4857-8844-48d738c39b68
68065dc7-c6af-4066-862c-fd2559bc82c3
1e60fe9d-0d90-4720-9fd8-3ef12dbde649
3ad9f14a-f29a-4703-ae3c-70b4ade6183e
39b46925-fa20-4b53-9dda-3e16337287b7
40bf70f9-15b2-4233-97b3-b689d03a759a
31bb7a4a-4a73-4ef2-9d5f-65261d363310
```

All records state `actual_model_identity=deepseek-v4-flash`, `fresh_request=true`, official endpoint and retry `0`.

## New Candidate and Shadow

```text
candidate_id: skillcand_e71dc9eeb63d5ee6bcfa73920931384c
skill: commerce-diagnostic-synthesis
base_version: 1.1.0
candidate_version: 1.3.0
source_experiment_id: exp_aca844e7ef134b7dba264e919eacdb38
offline_experiment_id: exp_aca844e7ef134b7dba264e919eacdb38
security_scan: passed
regression/holdout: passed
status: shadow
reviewer_id: null
```

Formal Shadow:

```text
Run IDs:
run_af426da728e248b08743c06be685faee
run_07bb0b79534c4c0b8351833680fe31f8

Provider Request IDs:
efe0afa3-5c0f-4427-a3e5-242a3d8c8ec1
88afc2f5-0d7f-4361-9c03-4acccc3d21b2
2cf1ffdb-31f2-4510-a19d-058fa3717e37
1432f0a1-1136-424e-aefe-d23e4c6ff4eb

Total tokens: 10,179
Summed provider latency: about 9.06s
Actual model: deepseek-v4-flash
Retry: 0
Passed: true
```

The isolated Fulfillment and Review Cases were identical before and after Shadow. No Evidence, Hypothesis, Action, Case status or Active Pointer changed.

## Current verification baseline

```text
Ruff Commerce: passed
Commerce deterministic: 396 passed, 22 real-model tests deselected
Four-Gold synthesis/semantic live gate: 1 passed
Fresh Candidate Shadow: passed
git diff --check: pending final documentation pass
```

## Remaining boundary

This is a unified four-case synthesis/semantic Eval release gate, not yet a unified four-case full business Run gate. Still required:

- run all four Cases through their complete persisted Subagent → Lead → Verification lifecycle in one release harness;
- Human Review of Candidate `1.3.0`;
- explicit Promotion and Active Pointer transaction;
- rollback rehearsal after promotion;
- frontend Skills & Evals UI and browser QA.

No Active Pointer exists, and neither the Agent nor this Goal run has self-approved the Candidate.

