# ADR 0003: Live Eval Contracts Are Release Gates

Date: 2026-06-27

Status: accepted

## Context

Agent output is nondeterministic and long-running launch tasks can fail through small upstream deviations. Unit tests and replay tests are necessary but insufficient for the product claim that OpenSKU works as an agent system.

The project already completed 10 accepted live runs with an aggregate `PASS 420/420` score. That should remain the standard for major behavior claims.

## Decision

OpenSKU will use three validation layers:

| Layer | Role | Release Meaning |
|---|---|---|
| L1 unit and contract tests | fast regression checks | required but not sufficient |
| L2 replay and real-backend tests | protocol, UI, and integration stability | required for release candidate |
| L3 live agent validation | product truth for agent behavior | required for milestone acceptance |

For agent behavior, a milestone is accepted only when a real live run exercises:

- gateway/API path.
- `agent_name=ecom-launch`.
- lead agent construction.
- skill loading.
- subagent/tool path.
- artifact writing.
- artifact validation.
- run logging.

## Consequences

Positive:

- The project avoids claiming mock-only success.
- Evaluations stay connected to real runtime behavior.
- Artifact validators become meaningful release gates.

Tradeoff:

- Live validation costs time and model tokens.
- Some milestones need smaller focused live runs before broad suites.

## Implementation Notes

Knowledge injection must follow this contract. A unit test proving prompt construction is not enough. The acceptance run must be a real live case that writes `injected_knowledge_patterns` and still passes validation.
