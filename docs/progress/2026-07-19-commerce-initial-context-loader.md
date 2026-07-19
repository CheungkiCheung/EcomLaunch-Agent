# Commerce Case Agent — Verified Initial Context Loader

> Date: 2026-07-19
> Branch: `feature/commerce-case-agent`
> Status: deterministic initial ContextPacket loading complete
> Model requests: `0`

## Outcome

The first executable Commerce Agent context can now be reconstructed from durable business state instead of inferred from a Case title, chat history or deterministic ID.

`ContextPacketLoader` performs this chain:

```text
Workspace + running Investigation Run
→ Workspace-scoped Case
→ immutable CaseLineage
→ Dataset Manifest and current deterministic Dataset View
→ safe derived artifact path
→ exact artifact SHA-256
→ strict Case analysis artifact schema
→ Workspace / Case / Dataset / Seller / Window identity
→ Capability Profile equality
→ Anomaly / MetricObservation consistency
→ append-only Evidence and latest Hypothesis membership
→ compact canonical LeadContextPacket
→ initial GoalLoopState
→ zero-usage safe Checkpoint
```

The Loader fails closed for missing Run/Case/Lineage/Manifest/Artifact, unsafe paths, SHA-256 mismatch, identity mismatch, stale Capability context, hidden evaluation-label fields, Case-external Fact or Metric references and context token-budget overflow. Initial loading is allowed only after a Worker has acquired a fenced lease and moved the Investigation Run to `running`; a Run with an existing Checkpoint must use the future resume path instead of being initialized again.

The generated context does not contain raw CSV rows or the full source-Fact arrays carried by deterministic MetricObservations. It contains metric/anomaly digests, sample/formula metadata, source Fact counts and stable IDs that can be resolved later by scoped Tools. `ContextManifest` records Workspace, Case, Dataset, source artifact hash, included Evidence/Fact/Metric/Anomaly IDs, redactions, estimated tokens and a canonical context SHA-256.

## Decimal Precision Decision

The RED test exposed a serialization boundary bug: validating an already decoded Python dictionary selected `float` from the `MetricValue` union and lost precision from persisted Decimal values. That made an unchanged AnomalySignal appear inconsistent with its MetricSnapshot.

The Loader now scans decoded JSON only for hidden-label keys, then validates the artifact from the original JSON bytes using Pydantic JSON mode. This preserves exact Decimal values and keeps anomaly/metric equality deterministic.

## Checkpoint Safety

The Loader returns an initial zero-usage `GoalLoopCheckpoint`; it does not persist one without execution ownership. Integration coverage proves:

- a running Run rejects Checkpoint persistence without a lease;
- the active lease can persist sequence `1`;
- only the SHA-256 of an optional resume token enters State/Checkpoint;
- the raw resume token never appears in serialized Checkpoint JSON;
- a Run with an existing Checkpoint rejects duplicate initial loading.

## TDD Evidence

RED:

```text
PYTHONPATH=. .venv/bin/pytest -q tests/commerce/agents/test_context_loader.py
ModuleNotFoundError: No module named 'app.commerce.agents.context_loader'
exit code: 2
```

GREEN / focused verification:

```text
8 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Full deterministic Commerce regression:

```text
226 passed
1 unrelated LangChain pending-deprecation warning
exit code: 0
```

Static validation:

```text
Ruff: All checks passed
git diff --check: passed
```

No model request was made because Context loading, canonical hashing, membership checks and Checkpoint construction are deterministic control-plane work.

## Known Limits

- Agent behavior is still unverified.
- The actual Worker execution loop and Harness adapter are not implemented yet.
- Existing Checkpoints can be read after lease reacquisition, but process-restart resume logic is not yet connected.
- Metric/source Fact lookup Tools are not yet exposed to the Path Agent.
- PostgreSQL still lacks a live integration environment.

## Next

Run a fresh DeepSeek V4 preflight. If the server-side model identity, authentication and quota pass, implement the first real `FulfillmentPathAgent` request for `GC-FULFILLMENT-001` using this verified ContextPacket and persist complete model/tool/version telemetry. If the model gate fails, stop and report `blocked` without substituting a fake, replay or another model.
