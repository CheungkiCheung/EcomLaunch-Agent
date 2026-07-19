# Commerce Case Agent — Fresh-context Verification

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: first real Verification behavior verified
> Model requests: `2` (`1` fresh preflight + `1` fresh Verifier)
> Successful tokens: `6,205` total (`5,596` input, `609` output)

## Outcome

Commerce conclusions now have an independent real-model verification path instead of trusting the Agent that produced or proposed them.

`VerificationEngine` builds a fresh packet from deterministic Case context:

- Case header and immutable Dataset identity;
- baseline/current metric digests and anomalies;
- persisted Evidence digests;
- current Capability Profile and explicit boundaries;
- candidate claims;
- policy constraints against causal and private-metric overclaim;
- parent Context hash only.

It explicitly excludes Lead messages, reasoning history and chain of thought. The Verifier receives no privileged Gold Case labels.

## Reusable Verified Call Adapter

`VerifiedModelCaller` now centralizes the provider-side harness used by new Agent roles:

```text
deterministic ModelAssignment
→ fresh real_model_preflight
→ approved PatchedChatDeepSeek class
→ official api.deepseek.com endpoint
→ one uncached request
→ SDK max_retries=0
→ server-side deepseek-v4 identity
→ request/response IDs + tokens + latency + stop reason
→ response-content SHA-256
```

It returns response text only in memory. Telemetry is safe to persist; Prompt, response text, API key and reasoning content are not persisted.

## Verification Contract

Each claim must receive exactly one structured verdict:

```text
pass | reject | repair
```

Non-pass verdicts require one or more machine-readable issues:

```text
metric_contradiction
unsupported_causal_language
missing_evidence
capability_overclaim
policy_violation
```

Every verdict must cite MetricObservation IDs from the fresh Verification Context. The system, not the model, computes the overall verdict from per-claim results.

## Live Behavior Gate

The real test presented two claims in the same fresh request:

1. handling decreased while transit increased, so observed deterioration is localized to transit rather than seller handling;
2. seller handling worsened and caused the delay.

The accepted result was:

```text
claim 0: pass
claim 1: reject
overall: reject
```

The rejected claim cited current Context metrics and carried `metric_contradiction` or `unsupported_causal_language`. This proves the Verifier can distinguish an evidence-supported diagnostic statement from a causal overclaim instead of merely approving all upstream output.

## Fresh Real-model Evidence

Preflight:

```text
run_id: preflight-4448f818c7b0448ab0c243022b5f465c
actual_model_identity: deepseek-v4-flash
provider_request_id: 079ea08d-0ef7-4111-898d-e498738bebfa
tokens: 61 input / 11 output / 72 total
latency: ~1109 ms
retry_count: 0
stop_reason: stop
```

Verifier:

```text
run_id: verification-4c36a58732e9421eabb1ac9cd97e2b20
actual_model_identity: deepseek-v4-flash
provider_request_id: 38c395aa-7d2b-4703-991c-2986ea0ade36
tokens: 5535 input / 598 output / 6133 total
latency: ~4379 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
model profile: strong_verifier
effort: high
router output ceiling: 5000
invocation output ceiling: 1600
prompt_version: commerce.verification@1.0.0
context_version: commerce-verification-context@1.0.0
skill_version: commerce.claim-verification@1.0.0
```

Audit metadata and context/result hashes are stored under the Git-ignored directory:

```text
.deer-flow/commerce/evaluation/verification/
```

## Verification

RED:

```text
ModuleNotFoundError: No module named 'app.commerce.agents.verification'
exit code: 2
```

Fresh live test:

```text
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/agents/test_verification_live.py

1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Full deterministic Commerce regression, explicitly excluding five live tests:

```text
234 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed.

## Known Limits

- Verification currently accepts caller-supplied claims; LeadSynthesis is not implemented yet.
- Verification result and telemetry are audited locally but not persisted into Commerce Run tables/events.
- A rejected claim does not yet trigger GoalLoop replan or consume verification-repair budget.
- Metric recalculation uses the verified deterministic digest loaded from the immutable analysis artifact; a separate on-demand Tool recalculation path is not yet implemented.
- Action policy verification is represented as policy constraints but Action contracts are not yet connected.

## Next

Implement structured LeadSynthesis from persisted Path Evidence, then pass only its claims—not its reasoning history—to this Verifier. Persist `verification.started` / `verification.completed`, verdict hashes and the next GoalLoop Checkpoint under the current lease. A rejected claim must trigger replan or partial/blocked stop according to budget; it must never be silently rewritten into a pass.
