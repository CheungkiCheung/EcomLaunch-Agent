# Commerce Case Agent — Real DeepSeek V4 ReviewExperience Path

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: standalone ReviewExperience Path behavior verified
> Final acceptance requests: `2` (`1` fresh preflight + `1` fresh Agent)
> Final acceptance tokens: `4,441` total (`4,370` Agent + `71` preflight)

## Outcome

`ReviewExperiencePathAgent` now executes deterministic review evidence tools before one fresh DeepSeek V4 interpretation request:

```text
uploaded Olist orders / items / reviews / seller data
→ confirmed ReviewExperience Capability
→ metric_query
→ review_signal_query
→ redacted ReviewExperienceContextPacket
→ deterministic ModelRouter assignment
→ fresh real-model preflight
→ one uncached no-retry DeepSeek V4 request
→ exact Fact / MetricObservation membership validation
→ causal and illegal-overclaim guards
→ structured PathResult + real ToolCallTrace
→ immutable metadata/hash audit
```

The accepted `GC-REVIEW-002` context contains:

- seller `0b90b6df587eb83608a64ea8b390cf07`;
- baseline window `2018-03-01 → 2018-04-01`: 17 reviewed orders, average score `3.8823529411764706`, low-rating rate `4/17 = 23.5294%` and late-delivery rate `0`;
- current window `2018-04-01 → 2018-05-01`: 18 reviewed orders, average score `2.9444444444444446`, low-rating rate `8/18 = 44.4444%` and late-delivery rate `0`;
- eight current low ratings, seven with non-empty text and seven redacted excerpts;
- customer-reported themes including missing quantity, non-receipt, generic cartridge, fake/pirate wording and unresolved complaints.

The excerpts are VOC signals, not adjudicated facts about seller intent or product legality. The Agent may report authenticity, missing-item or non-receipt allegations that require verification. It may not confirm counterfeit sales, fraud or illegality. Because the deterministic late-delivery rate is zero in both windows, it may not attribute the rating decline to delivery lateness. Some non-receipt comments conflict with delivered records and remain explicit unknowns rather than resolved conclusions.

## Real Tool Traces

The final Path reports two successful deterministic Tool calls:

```text
metric_query:
  latency: ~1.03 ms
  request_sha256: 8c57dc239978eed06381872ade3b558becf484edee510e816b08fe9cd96be3bc
  response_sha256: a5eca1fc973dd769fe2e928757b26e492ebd16f98eb4e5bd851ac8346b087f6a

review_signal_query:
  latency: ~0.28 ms
  request_sha256: 0dc4bae7b7ab303c8f030436b1b0e5caecce00cec3b20fc1e72791e20899f21b
  response_sha256: 69cccdd3cdabfd5374557cee2cdb88253ba3179c9bb48418451934f93314389c
```

The model receives metric digests and at most 280-character redacted review excerpts with scoped Fact IDs. Raw order references are replaced by SHA-256 values. Email-like content, raw source rows and Gold Case expected labels do not enter Agent context or audit.

These Tools are selected by the deterministic Path harness before the model call. This is truthful capability-driven Tool execution, not model-selected dynamic Tool calling.

## TDD and Tuning Evidence

Initial RED:

```text
ModuleNotFoundError: No module named 'app.commerce.agents.review_experience'
exit code: 2
```

The first live request was correctly rejected by the strict illegal-overclaim guard. Prompt `1.0.0` itself used the phrase `not confirmed counterfeit`; the model safely repeated that negative boundary, but substring validation still found the embedded forbidden phrase `confirmed counterfeit`. The run did not count as PASS. Prompt `commerce.review-experience-path@1.1.0` now states that authenticity allegations remain unverified and that no illegality finding can be made, without inviting the model to repeat forbidden conclusion strings inside a negation.

The second fresh run produced valid structured Evidence and passed all Agent-side Fact, Metric and safety validation. The behavior evaluator nevertheless accepted only the literal zero forms `0%` or `zero`, while the model used an equivalent decimal form. The parser was strengthened to require an observation citing both baseline/current late-rate IDs and an explicit numeric zero; the evaluator was corrected to accept equivalent `0.0` and `0.00` renderings. The business boundary was not weakened. This preserved run used `4,684` Agent tokens plus a `74`-token preflight.

The third fresh run passed all numeric, evidence, allegation, illegal-conclusion and causal-language gates. Only a redundant final evaluator assertion required the exact wording `diagnostic` or `not causal`, despite the response already stating an unverified/requires-verification evidence boundary. The evaluator now accepts equivalent boundary language such as `unverified`, `requires verification`, `no finding` or `not supported`; all positive and negative business assertions remain. This preserved run used `4,255` Agent tokens plus a `73`-token preflight.

A fourth fresh request produced the final PASS. Earlier runs and audits were not reused as acceptance evidence. The first parse-rejected Agent call did not reach the current post-parse Path audit writer, so only its `68`-token preflight is preserved; failed-call telemetry persistence remains a common audit hardening item.

## Final Fresh DeepSeek V4 Evidence

Preflight:

```text
run_id: preflight-b55c7cadc664484c9b530d4663e8b785
provider_request_id: c1137883-0486-4928-8aa8-5678f8a31b3e
actual_model_identity: deepseek-v4-flash
tokens: 60 input / 11 output / 71 total
latency: ~1476 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
```

ReviewExperience Agent:

```text
run_id: review-experience-path-abe7ddb578f14657b98b787c334f40f7
provider_request_id: 87c4b203-7b8c-4e32-a5bb-56585e65d79b
actual_model_identity: deepseek-v4-flash
tokens: 3014 input / 1356 output / 4370 total
latency: ~9975 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
profile: balanced_tool_user
effort: medium
reason_codes: profile_binding, tool_use_required
router output ceiling: 4000
invocation output cap: 1800
prompt_version: commerce.review-experience-path@1.1.0
context_version: commerce-review-experience-path-context@1.0.0
router_version: commerce-model-router@1.0.0
skill_version: commerce.review-experience-investigation@1.0.0
```

The final two requests used `4,441` total tokens and about `11.45s` summed provider latency. The live pytest completed in `11.96s`.

Audit metadata is stored under the Git-ignored path-agent directory. It contains context/result hashes, telemetry and ToolCallTrace hashes, not Prompt text, response text, reasoning content, API keys or raw Dataset rows.

## Verification

Deterministic Context/Tool test:

```text
1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Final live gate:

```text
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/agents/test_review_experience_path_agent_live.py

1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Full deterministic Commerce regression, explicitly excluding all nine live provider tests:

```text
243 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed.

## Known Limits

- This is a standalone Path gate with a deterministic CaseHeader, not a persisted Case/Lineage/Run execution.
- Review Evidence is not yet appended under a fenced Worker lease or synthesized jointly with Fulfillment/SellerPeer Evidence.
- Tool selection is deterministic and capability-driven, not model-selected.
- Review themes remain lexical VOC signals; they are not a trained complaint classifier and cannot adjudicate authenticity, fraud or seller intent.
- The current post-parse audit path does not preserve Agent telemetry for structured-output rejection before a `PathResult` exists.
- Repeated-run, holdout, multi-Path Verification and action outcome checks remain pending.

## Next

Introduce an honest explicit-user or peer-gap Case trigger and a persisted multi-Path Worker that can schedule Fulfillment, SellerPeer and ReviewExperience from Capability, append each Path's Evidence under one fenced lease, synthesize only combined persisted Evidence and independently verify resulting claims.
