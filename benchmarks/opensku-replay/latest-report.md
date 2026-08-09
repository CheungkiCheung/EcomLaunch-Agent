# OpenSKU Replay Benchmark

Generated: `2026-08-09T05:44:07Z`
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
| launch | 3 | 100.0% | 100.0% | 100.0% | 0.464s | 0.793s |
| growth | 3 | 100.0% | 100.0% | 100.0% | 0.066s | 0.066s |

## Evidence-gated optimization verdict

**Verdict:** `candidate_faster`

P50 latency changes (negative means faster; material only when both `5.0%` and `0.050s` thresholds are met):
- `growth`: `0.057s -> 0.066s`; `15.79%` / `+0.009s` (below gate)
- `launch`: `15.178s -> 0.464s`; `-96.94%` / `-14.714s` (material)

## Limitations

- The replay provider is deterministic and does not represent live provider quality.
- Token metrics are reported only when the runtime records them; replay runs may disable token tracking.
- The current golden suite covers one Launch workflow and one Growth workflow; expand the case manifest before treating this as a broad benchmark.
