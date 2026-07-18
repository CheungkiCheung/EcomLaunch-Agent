# Commerce Case Agent Phase 4 — Context, Dynamic Router, and Budget

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: deterministic orchestration contracts complete
> Model requests: `0`

## Outcome

The first Agent-layer code is implemented under `app/commerce/agents/` while the reusable `deerflow.*` Harness remains business-agnostic.

Implemented:

- Lead, Path and Verification `ContextPacket` variants;
- `ContextManifest` with Case identity, context hash, token estimate and included source IDs;
- hidden evaluation-label metadata rejection;
- traceable `EvidenceDigest` and `HypothesisDigest`;
- three versioned `PathAgentSpec` records;
- deterministic Capability-first `DynamicPathRouter` selecting zero to three paths;
- route decisions with selected/skipped reason codes;
- layered `AgentBudgetLimit`, immutable usage snapshots and concurrency-safe `BudgetManager`.

## Context boundary

Path packets carry only the local goal, required Capability, relevant Evidence, allowed tools, forbidden claims, output schema and local budget. Verification packets have claims, evidence, capability boundaries and policy constraints, but no Lead reasoning history field. Models use `extra=forbid`, and metadata keys such as `expected_behavior`, `hidden_labels`, `gold_answer` and `expected_facts` are rejected.

## Dynamic routing evidence

The router is rule-first:

```text
Capability unavailable → skip + capability_unavailable
Capability available but no signal → skip + no_relevant_signal
Capability available + signal/request → assignment + selected reason
```

Gold Case regressions prove:

- GC-REVIEW-002 has Fulfillment capability but a review-only signal starts only `ReviewExperiencePathAgent`;
- GC-CAPABILITY-003 cannot start Review when that capability is missing;
- GC-PEER-004 can start SellerPeer only when the peer metric/capability exists;
- an empty signal summary starts zero Path Agents.

## Budget semantics

`BudgetManager.consume` takes one multi-dimension delta under an async lock. It computes every resulting dimension before committing. If any dimension exceeds its limit, the entire consume is rejected and no partial token/tool/iteration usage is recorded.

A concurrency test submitted twenty tool calls against a limit of ten and observed exactly ten commits and ten `BudgetExceededError` results.

## Verification

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/agents/test_contracts.py \
  tests/commerce/agents/test_dynamic_router.py \
  tests/commerce/agents/test_budget.py

8 passed
exit code: 0
```

Full deterministic Commerce regression:

```text
181 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

No model request was made. ModelRouter, GoalLoopController, Structured PathResult, live Path Agent behavior and Verification remain subject to future fresh DeepSeek V4 tests.
