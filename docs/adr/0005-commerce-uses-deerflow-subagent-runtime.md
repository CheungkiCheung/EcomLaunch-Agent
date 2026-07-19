# ADR 0005: Commerce Uses the DeerFlow Subagent Runtime

Date: 2026-07-19

Status: accepted

## Context

Commerce Case Agent already has verified application contracts for Dataset,
Capability, Case, Run, Evidence, Hypothesis, ContextPacket, Budget, Checkpoint,
Lease/Fencing and Domain Events. It also has three independently verified Path
behaviors and one persisted Fulfillment Path to Lead to Verification loop.

The first implementation called role-specific Agent classes directly from
`CommerceInvestigationWorker`. Extending that pattern to multiple Paths,
continuous user dialogue, replan, action and skill evolution would duplicate
capabilities already present in the DeerFlow Harness:

- agent loops;
- subagent task execution;
- tools and skills;
- streaming;
- model configuration;
- sandboxing;
- LangGraph execution and checkpoint integration.

The project needs a recognizable Agent Harness architecture without allowing
chat history or a model-controlled graph to become the Commerce business source
of truth.

## Decision

DeerFlow is the primary Agent Harness. Commerce Path investigations and fresh
verification run as bounded DeerFlow subagents behind an application adapter.
LangGraph remains the execution engine used by DeerFlow; Commerce does not build
a second raw LangGraph runtime.

The target roles are:

- one continuous Commerce Lead Agent loop;
- `Fulfillment` subagent;
- `SellerPeer` subagent;
- `ReviewExperience` subagent;
- independent fresh-context `Verification` subagent.

`DynamicPathRouter` deterministically selects zero to three Path types from
persisted Capability, anomaly signals and explicit user intent. Selected Path
subagents may execute concurrently. Lead synthesis waits at an Evidence Barrier
until every selected Path is completed, blocked or failed and all accepted
Evidence is persisted.

Subagents cannot mutate Commerce state. They receive a minimal versioned
ContextPacket and return a structured `PathResult`. The adapter validates that
result and performs lease/fencing-protected persistence through the Commerce
unit of work.

Commerce Run, Checkpoint, Lease and Domain Event remain authoritative, as
established by ADR 0004. Harness Thread/Run state is an execution projection.

## Why Not the Alternatives

### Raw LangGraph

Rejected as the primary application framework because the repository already
contains a LangGraph-based DeerFlow Harness. Building a separate graph would
duplicate tool, subagent, streaming, skill and model infrastructure.

### Multica

Rejected as the Commerce runtime because Multica is a managed coding-agent
platform centered on issues, teammates, squads, boards and coding runtimes. It
can manage external coding agents but does not replace the ecommerce evidence,
metric, verification and action domain required here.

### DeepAgents

Rejected for migration because it overlaps with DeerFlow planning, filesystem,
tool and subagent capabilities. It would be a reasonable greenfield option but
adds migration cost without removing Commerce domain requirements.

### Pi Agent

Rejected as the main runtime because a minimal agent loop would require the
project to rebuild durable subagent execution, streaming, policy, checkpoint and
observability integrations already available in DeerFlow.

### Continue Role-Specific Worker Calls

Rejected as the final architecture because every new role would add bespoke
prepare, checkpoint, call, heartbeat, accounting, persistence and event code.
The existing Worker remains temporarily as a behavior and migration baseline.

## Consequences

Positive:

- the project demonstrates a real Harness and subagent architecture;
- Path fan-out can use a proven executor instead of custom task management;
- continuous dialogue can reuse the Lead loop without rerunning the full Case;
- Commerce contracts remain strict, testable and independent of prompts;
- the DeerFlow upstream/personal contribution boundary is explicit;
- runtime behavior can be compared against the accepted Worker baseline.

Tradeoffs:

- a `CommerceSubagentAdapter` and event bridge are required;
- DeerFlow checkpoints and Commerce checkpoints must not be confused;
- parallel Evidence writes still require optimistic concurrency and fencing;
- real-model parity tests consume more tokens during migration;
- the old and new path must coexist briefly until the release gate passes.

## Migration Gate

The old role-specific Worker can be removed only after the new Subagent loop:

1. passes deterministic domain and failure-path regression;
2. uses fresh identity-verified DeepSeek V4 calls;
3. produces traceable Evidence and fresh Verification;
4. preserves blocked, partial and replan semantics;
5. records Provider IDs, tokens, latency, retry, stop reason and versions;
6. passes the applicable Gold Case end to end;
7. has no forbidden `deerflow.* -> app.commerce.*` import.
