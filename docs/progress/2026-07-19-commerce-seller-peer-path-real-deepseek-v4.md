# Commerce Case Agent — Real DeepSeek V4 SellerPeer Path

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: standalone SellerPeer Path behavior verified
> Final acceptance requests: `2` (`1` fresh preflight + `1` fresh Agent)
> Final acceptance tokens: `3,277` total (`3,206` Agent + `71` preflight)

## Outcome

`SellerPeerPathAgent` now executes real deterministic evidence tools before one fresh DeepSeek V4 interpretation request:

```text
uploaded multi-seller Olist data
→ confirmed SellerPeer Capability
→ peer_cohort_query
→ geographic_order_count_query
→ compact SellerPeerContextPacket
→ deterministic ModelRouter assignment
→ fresh real-model preflight
→ one uncached no-retry DeepSeek V4 request
→ strict MetricObservation membership / overclaim validation
→ structured PathResult + real ToolCallTrace
→ immutable metadata/hash audit
```

The accepted `GC-PEER-004` context contains:

- target seller: `59` comparable orders, `16` late, `27.1186%` late-delivery rate;
- five eligible peer sellers: `257` pooled orders, `19` late, `7.3930%` late-delivery rate;
- target-minus-peer gap: `19.7256` percentage points;
- target customer-state counts including SP `26`, MG `8`, RJ `7`;
- explicit cohort policy: same time window, pure category, seller state, single-seller attribution and at least 20 orders;
- `eligibility_uses_late_delivery_result=false`.

The model explained the target/peer gap, sample boundary and geography while citing only supplied MetricObservation IDs. It explicitly labeled the peer gap diagnostic rather than causal and did not invent private metrics.

## Real Tool Traces

The Path honestly reports two successful deterministic Tool calls:

```text
peer_cohort_query:
  latency: ~4.81 ms
  request_sha256: 7a70ae7c9e8a9648620f75217a989aaa0d8db34e064d4a35c32d4932314b66d4
  response_sha256: 0e9b90b955e91170cd97958fe9d126381c7d3a70a0b02cc4c88d68d04ba2475e

geographic_order_count_query:
  latency: ~2.00 ms
  request_sha256: ccd9cd6c0e33f9fd7abe536b055a8ce55a2adeee1fb112b018ef772693cc9ef8
  response_sha256: bd0137b6cd15af1eccf4dd5b91f9dee98358540ec47cd7b8aa3543f30123d075
```

Raw peer seller rows, customer rows and full source Fact arrays do not enter Agent context or audit. Tool traces prove execution and content identity without persisting raw results.

These Tools are currently selected by the deterministic Path harness before the model call. This is truthful Tool use, but not yet model-selected dynamic Tool calling.

## TDD and Tuning Evidence

Initial RED:

```text
ModuleNotFoundError: No module named 'app.commerce.agents.seller_peer'
exit code: 2
```

The first live request calculated and described the correct business values, but returned two standalone policy/boundary observations with empty Metric ID arrays. Strict schema validation rejected the result. It was not counted as PASS.

Prompt `commerce.seller-peer-path@1.1.0` then required policy and diagnostic-not-causal boundaries to be merged into the target-versus-peer observation citing both rate Metric IDs; the Evidence schema was not relaxed.

The second fresh Agent behavior passed every business assertion, but the test failed afterward because the evaluator called a nonexistent `ExpectedBehavior.required_fact()` helper. Inspection confirmed:

- Agent behavior assertions had all passed;
- hidden labels were loaded only after the Agent returned;
- `ExpectedBehavior` exposes a `required_facts` tuple, not a lookup method.

Only the evaluator lookup was corrected; the Agent and acceptance assertions were unchanged. A third fresh run produced the final PASS.

## Final Fresh DeepSeek V4 Evidence

Preflight:

```text
run_id: preflight-3ad2c58345e2457db764a07e038478a3
provider_request_id: c1c7990c-4ec9-4fbf-bba6-721245b2bc80
actual_model_identity: deepseek-v4-flash
tokens: 60 input / 11 output / 71 total
latency: ~912 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
```

SellerPeer Agent:

```text
run_id: seller-peer-path-e7d3130cc65243d3a2c7de355749b0ac
provider_request_id: a20b89a2-c4b7-468c-b754-ab1591cd247c
actual_model_identity: deepseek-v4-flash
tokens: 2670 input / 536 output / 3206 total
latency: ~4033 ms
request_attempt_count: 1
retry_count: 0
stop_reason: stop
profile: balanced_tool_user
effort: medium
reason_codes: profile_binding, tool_use_required
router output ceiling: 4000
invocation output cap: 1800
prompt_version: commerce.seller-peer-path@1.1.0
context_version: commerce-seller-peer-path-context@1.0.0
router_version: commerce-model-router@1.0.0
skill_version: commerce.seller-peer-investigation@1.0.0
```

The final two requests used `3,277` total tokens and about `4.94s` summed provider latency. The live pytest completed in `5.59s`.

Audit metadata is stored under the Git-ignored path-agent directory. It includes context/result hashes and ToolCallTrace hashes, not Prompt text, response text, reasoning content, API keys or raw Dataset rows.

## Verification

Deterministic Context/Tool test:

```text
1 passed
1 unrelated LangChain pending-deprecation warning
```

Final live gate:

```text
PYTHONPATH=. .venv/bin/pytest -q -s \
  tests/commerce/agents/test_seller_peer_path_agent_live.py

1 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Full deterministic Commerce regression, explicitly excluding all eight live provider tests:

```text
242 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Ruff and `git diff --check` passed.

## Known Limits

- This is a standalone Path gate with a deterministic CaseHeader, not a persisted Case/Lineage/Run execution.
- SellerPeer Evidence is not yet appended under a fenced Worker lease or synthesized jointly with Fulfillment Evidence.
- Tool selection is deterministic and capability-driven, not model-selected.
- Peer comparison currently uses one configured category/window policy; product-side policy selection and user confirmation are pending.
- Geographic Tool failure/unknown output has deterministic metric coverage but is not yet exercised in the real Agent gate.
- Repeated-run, holdout and multi-Path Verification remain pending.

## Next

Implement `ReviewExperiencePathAgent`, then introduce a persisted explicit-user or peer-gap Case trigger and a multi-Path Worker that can execute Fulfillment plus SellerPeer, synthesize their combined Evidence and independently verify the resulting claims.
