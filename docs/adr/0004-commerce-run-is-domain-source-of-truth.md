# ADR 0004: Commerce Run Is the Domain Source of Truth

Date: 2026-07-19

Status: accepted

## Context

DeerFlow already provides a generic `RunManager`, `run_agent`, `StreamBridge`, LangGraph Checkpointer, Run Event Store, Tool/Sandbox middleware and token telemetry.

The generic `RunManager` is intentionally Chat/Thread-oriented:

- its statuses are `pending/running/success/error/timeout/interrupted`;
- its records are keyed by Thread and Assistant;
- the live `asyncio.Task` is process-local;
- startup reconciliation marks orphaned inflight runs as errors;
- its persisted run row is an execution/runtime record, not a Commerce business aggregate.

Commerce Case Agent has different product semantics:

- Case is long-lived while Run is bounded;
- Run phases and stop reasons are business-visible;
- Waiting and partial outcomes are first-class;
- Checkpoint recovery must preserve Evidence/Hypothesis references;
- Timeline and War Room must read authoritative Commerce Domain Events;
- an expired Worker must be fenced from writing after another Worker resumes the Run.

Using the generic Run row as the Commerce truth would either lose these semantics or force Commerce fields into the reusable Harness.

## Decision

`commerce_runs`, `commerce_run_checkpoints`, `commerce_run_leases` and Commerce Domain Events are the authoritative business state.

The Harness remains business-agnostic and is reused through an application adapter for:

- LangGraph execution;
- `StreamBridge` delivery;
- LangGraph Checkpointer storage;
- Tool and Sandbox middleware;
- token and model telemetry;
- cancellation and bounded shutdown primitives where their semantics match.

The adapter must map Harness execution changes into Commerce Run transitions and Domain Events. Harness status alone cannot advance a Commerce Case or Run.

Worker ownership uses an application-layer lease:

- only the lease-token SHA-256 is persisted;
- a monotonically increasing fencing token identifies the current owner;
- heartbeat extends the current lease without emitting fake business activity;
- expired-lease takeover increments the fencing token and returns the latest safe Checkpoint;
- stale Workers cannot heartbeat or append Checkpoints.

## Consequences

Positive:

- Commerce UI has one authoritative event/state model;
- the reusable Harness remains free of ecommerce imports;
- process-local execution primitives can evolve independently from business state;
- expired Worker recovery is explicit and testable;
- interview discussion can distinguish runtime infrastructure from domain orchestration.

Tradeoffs:

- an adapter must synchronize Harness execution with Commerce state;
- generic and Commerce run identifiers/configuration require deliberate mapping;
- exactly-once model execution is impossible, so fenced state writes and idempotent tools remain mandatory;
- Checkpoint recovery still depends on complete Case-to-data lineage.

## Rejected Alternatives

### Put Commerce fields into `deerflow.runtime.RunRecord`

Rejected because `deerflow.*` must not import or encode Commerce business concepts.

### Treat the Harness Run Store as the only Run database

Rejected because its lifecycle and restart behavior do not represent waiting, partial, approval, capability-blocked or follow-up states.

### Build a completely separate runtime

Rejected because `run_agent`, streaming, Checkpointer, Sandbox, Tool middleware and telemetry are valuable reusable infrastructure.

## Follow-up

Before the first real Path Agent execution, persist explicit Case lineage to Dataset, analysis windows, entity and derived MetricSnapshot artifact so the adapter can construct a reproducible initial `ContextPacket` rather than infer data from a Case title or deterministic ID.
