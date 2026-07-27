# Commerce Skill Candidate Shadow

> Date: 2026-07-19  
> Branch: `feature/commerce-case-agent`  
> Status: formal two-Case fresh DeepSeek V4 Shadow passed; Human Review pending

> Historical note: this is the immutable `1.2.0` Shadow milestone. It was superseded, not deleted, after the four-case audit exposed model-authored numeric thresholds. The current `1.3.0` Candidate and Shadow are documented in `2026-07-19-commerce-four-gold-threshold-tuning-skill-v1.3.md`.

## Outcome

Candidate `skillcand_1ba91a22b7c7523e88e452ee58ed4375` completed a side-effect-free Shadow over two different persisted Commerce Runs:

```text
offline-evaluated Candidate
→ isolated Shadow workspace
→ persisted GC-FULFILLMENT-001 Run
→ fresh Candidate generation
→ fresh Semantic Evaluation
→ persisted GC-REVIEW-002 Run
→ fresh Candidate generation
→ fresh Semantic Evaluation
→ verify authoritative Cases unchanged
→ Candidate status: shadow
```

Formal Run IDs:

```text
run_9be3de41704f4577a733c9a0059ff890
run_b92212b423a642d29a6b56318ac01fa8
```

Isolated workspace:

```text
.deer-flow/commerce/evaluation/shadow/workspaces/
shadow-skillcand_1ba91a22b7c7523e88e452ee58ed4375-aeb73a522e2a4a78ba2768f13016b2ff
```

## Fresh model evidence

| Case | Call | Provider Request ID | Model | Tokens | Latency | Retry |
|---|---|---|---|---:|---:|---:|
| GC-FULFILLMENT-001 | Candidate generation | `83565602-389d-4d86-b620-39e1969149bf` | `deepseek-v4-flash` | 4,645 | 2,597.93 ms | 0 |
| GC-FULFILLMENT-001 | Semantic evaluation | `ee7b06bb-27da-4b4f-9f59-ba6bc8d58588` | `deepseek-v4-flash` | 1,127 | 2,193.54 ms | 0 |
| GC-REVIEW-002 | Candidate generation | `53e353f2-9246-4008-a702-7e4415c60984` | `deepseek-v4-flash` | 3,444 | 2,243.89 ms | 0 |
| GC-REVIEW-002 | Semantic evaluation | `5e8fafc4-feb2-430e-b896-59307ad46073` | `deepseek-v4-flash` | 876 | 2,403.32 ms | 0 |

All four Provider Request IDs are unique. Total generation/evaluator usage was `10,092` tokens and about `9.44s` summed provider latency. Each record states `fresh_request=true`, the official endpoint and retry `0`.

## Side-effect barrier

Shadow uses a new SQLite database and data root. For each Case it stores the pre-Shadow authoritative Case, runs Candidate generation/evaluation, then reloads and compares the Case object. The final gate proves:

- no Evidence was appended;
- no Hypothesis was changed;
- no Action was created;
- no Case status/version changed;
- no Active Skill Pointer changed;
- reports contain only hashes/telemetry and bounded output, never API keys or raw private datasets.

Candidate state history is append-only:

```text
version 1: candidate
version 2: offline_evaluated
version 3: shadow
```

## Reproduction

Formal command:

```text
cd backend
PYTHONPATH=. .venv/bin/python -m app.commerce.evaluation.run_shadow \
  --candidate-id skillcand_1ba91a22b7c7523e88e452ee58ed4375 \
  --case-key GC-FULFILLMENT-001 \
  --case-key GC-REVIEW-002
```

Targeted tests recorded during implementation:

```text
tests/commerce/evaluation/test_skill_shadow.py
2 passed

tests/commerce/evaluation/test_skill_shadow_live.py
1 passed in 15.10s
```

The current deterministic regression also reran the Shadow contracts as part of `396 passed, 22 real-model tests deselected`.

## Release boundary

The Candidate is not Active. The remaining required path is:

```text
Human Review
→ explicit Promotion
→ Active Pointer transaction
→ rollback rehearsal
```

Human Review must come from a real reviewer. It is intentionally not auto-approved by the Agent or inferred from the passing experiment/Shadow.
