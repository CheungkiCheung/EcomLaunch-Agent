# OpenSKU Replay Benchmark

Generated: `2026-08-09T09:14:13Z`
Provider: `deterministic_replay`
Repeats per scenario: `3`

> This report measures the real Gateway and deterministic product contracts. It is not a live-model quality score. No prompts, model responses, uploaded rows, or artifact contents are stored in the report.

## Overall

| Metric | Result |
| --- | ---: |
| Scenarios | 2 |
| Runs | 6 |
| Run success rate | 100.0% |
| Contract-complete run rate | 100.0% |
| Contract check pass rate | 100.0% |
| Replay misses | 0 |

## Scenario summary

| Scenario | Runs | Run success | Contract-complete | Checks | P50 | P95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| launch | 3 | 100.0% | 100.0% | 100.0% | 0.427s | 0.826s |
| growth | 3 | 100.0% | 100.0% | 100.0% | 0.049s | 0.071s |

## Contract comparison

No candidate/baseline comparison was supplied. This run establishes a deterministic contract baseline; it makes no optimization claim.

## Limitations

- The replay provider is deterministic and does not represent live provider quality.
- Token metrics are reported only when the runtime records them; replay runs may disable token tracking.
- The current golden suite covers one Launch workflow and one Growth workflow; expand the case manifest before treating this as a broad benchmark.
