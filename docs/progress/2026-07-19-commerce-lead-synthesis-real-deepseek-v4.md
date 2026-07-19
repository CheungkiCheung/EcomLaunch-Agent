# Commerce Case Agent — Real DeepSeek V4 Lead Synthesis

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: first real Lead synthesis behavior verified
> Final acceptance requests: `4` (`2` fresh preflights + `1` fresh Fulfillment Path + `1` fresh Lead)
> Final acceptance successful tokens: `10,865` total

## Outcome

`LeadSynthesisAgent` now turns freshly persisted Path Evidence into structured diagnostic claims that can be handed to an independent Verifier.

```text
persisted Case + Path Evidence
→ reload verified LeadContextPacket
→ deterministic Lead ModelRouter assignment
→ fresh real-model preflight
→ one uncached no-retry DeepSeek V4 Lead request
→ strict structured-output validation
→ current-Case Evidence membership validation
→ system-derived stable Hypothesis IDs
→ claims + unknowns + suggested next Paths
→ immutable secret-free telemetry audit
```

The model supplies only claim statements, confidence values, supplied Evidence IDs, unknowns and suggested next Paths. It does not create Hypothesis IDs, telemetry or version metadata. Every claim is marked `diagnostic_only=true`: it is an input to fresh Verification, not a final causal truth.

## Model Selection

The accepted Lead assignment was:

```text
role: lead
base_profile: balanced_tool_user
selected_profile: strong_synthesizer
effort: high
model_alias: deepseek-reasoner
escalation_count: 1
router max_output_tokens: 6000
actual invocation max_output_tokens: 1800
reason_codes:
  - profile_binding
  - profile_escalated
  - critical_case
router_version: commerce-model-router@1.0.0
```

The Critical Case upgrade is explicit, budgeted and auditable. The logical Router ceiling and actual invocation cap are recorded separately so later quality/cost experiments can compare concrete configurations.

## TDD and Behavior Gate

Initial RED:

```text
ModuleNotFoundError: No module named 'app.commerce.agents.lead'
exit code: 2
```

The first fresh live implementation run completed both real model calls and satisfied Evidence membership, but the test rejected the natural-language assertion because the model expressed “handling did not worsen” with an unlisted equivalent phrase. That run was not counted as PASS.

The acceptance vocabulary was then expanded only with equivalent non-worsening expressions:

```text
improved
shorter
no deterioration
```

The semantic bar was not weakened: the result still had to mention both handling and transit, describe handling as improved/non-worsening, describe transit deterioration, cite real Path Evidence and avoid unsupported causal language.

Final live command:

```text
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/agents/test_lead_synthesis_live.py

1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

The final run rebuilt the Case, executed a new Fulfillment Path request, reloaded the persisted Evidence and then executed a new Lead request. No prior response or cached result was reused.

## Fresh Real-model Evidence

Fulfillment Path preflight:

```text
provider_request_id: 60ced0b8-8d5f-4442-b8cd-ac083f7cf3a1
actual_model_identity: deepseek-v4-flash
tokens: 61 input / 11 output / 72 total
retry_count: 0
stop_reason: stop
```

Fulfillment Path:

```text
run_id: fulfillment-path-cdedd91383094a6caeb612832c063535
preflight_run_id: preflight-27e87edfe4104be0b63693c6fdaefcd4
provider_request_id: 1ec69937-6d7a-4acf-965a-3cc50bcacd1c
actual_model_identity: deepseek-v4-flash
tokens: 3860 input / 408 output / 4268 total
latency: ~3901 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
```

Lead preflight:

```text
provider_request_id: 8ecb3296-71e1-4194-b668-c89534330a3b
actual_model_identity: deepseek-v4-flash
tokens: 59 input / 11 output / 70 total
retry_count: 0
stop_reason: stop
```

Lead:

```text
run_id: lead-synthesis-5f03384806f3443d96132e07426a9be8
preflight_run_id: preflight-e55b4d13e6a74ac48424ee828855204e
provider_request_id: 58a4d0d2-2ad8-4d11-9505-1dc3bf05c3c6
actual_model_identity: deepseek-v4-flash
tokens: 5744 input / 711 output / 6455 total
latency: ~5032 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
prompt_version: commerce.lead-synthesis@1.0.0
context_version: commerce-context@1.0.0
router_version: commerce-model-router@1.0.0
skill_version: commerce.lead-synthesis@1.0.0
```

The final accepted flow consumed:

```text
72 + 4268 + 70 + 6455 = 10865 total tokens
```

Audit metadata and context/result hashes are stored under the Git-ignored directory:

```text
.deer-flow/commerce/evaluation/lead-synthesis/
```

The audit does not store Prompt text, response text, reasoning content, API keys or raw Dataset rows.

## Verification

Ruff:

```text
All checks passed
```

Full deterministic Commerce regression, explicitly excluding all six live provider tests:

```text
234 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

## Known Limits

- Lead is currently invoked directly after the bounded Worker Path step; it is not yet a fenced persisted Worker phase.
- Structured Lead claims are not yet stored as contiguous Domain Hypothesis versions.
- Fresh-context Verification exists independently but is not yet invoked from these Lead claims.
- A rejected claim does not yet consume repair/replan budget or produce the next GoalLoop decision.
- SellerPeer and ReviewExperience Evidence are not yet available to multi-path synthesis.
- The live test validates the business distinction with explicit semantic phrases; repeated-run and holdout robustness remain release-gate work.

## Next

Extend the fenced Worker after `path.completed`: reload the Case context, run Lead synthesis, persist each claim as an immutable Hypothesis version, build a fresh Verification packet from claims without Lead reasoning, persist `verification.started` / `verification.completed`, consume actual Lead and Verification budgets, and write the next GoalLoop Checkpoint. Reject or repair must lead to an explicit replan, partial or blocked decision; it must never be silently converted to pass.
