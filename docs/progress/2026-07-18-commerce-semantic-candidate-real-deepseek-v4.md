# Commerce Semantic Candidate — Real DeepSeek V4 Evidence

> Date: 2026-07-18
> Branch: `feature/commerce-case-agent`
> Status: candidate layer implemented; live request verified
> Model requests: `2` in the successful live test (one preflight + one candidate call)

## Contract

`SemanticCandidateParser` and `keep_candidates_unconfirmed` enforce the boundary:

```text
deterministic profile
  → LLM candidate JSON
  → profile-grounded candidate validation
  → MappingSource.LLM_CANDIDATE + MappingStatus.NEEDS_CONFIRMATION
  → explicit Workspace confirmation
  → MappingStatus.CONFIRMED
```

The parser rejects invalid JSON, unknown table/column references and repeated candidate columns. Existing confirmed mappings always win; an LLM response cannot overwrite them.

`SemanticCandidateService`:

- runs `run_real_model_preflight` before every candidate request;
- uses the configured official `PatchedChatDeepSeek` provider;
- disables response cache and model retries for the candidate call;
- injects a fresh per-run nonce;
- verifies the candidate response server-side model identity is `deepseek-v4...`;
- requires provider request/response IDs, token usage and stop reason;
- persists immutable, secret-free telemetry with model/config version metadata;
- never persists prompt or response text, only SHA-256 hashes.

The API route is:

```text
POST /api/commerce/datasets/{dataset_id}/semantic-candidates
```

It returns the candidate envelope, the unconfirmed mapping view and telemetry. If preflight or the candidate call is unavailable, identity is unverified, authentication/quota fails, or structured JSON cannot be parsed, the route returns a blocked/error result rather than falling back to another model.

## Live verification

The first attempt inside the default sandbox made a real preflight request and returned:

```text
blocked_real_model_unavailable
```

It was not counted as a pass and no fallback was used. After a controlled external-network execution, the same test made fresh requests and passed:

```text
PYTHONPATH=. .venv/bin/pytest -q -m real_model \
  tests/commerce/data/test_semantic_candidate_service_live.py -vv

1 passed
exit code: 0
```

The successful preflight audit recorded:

```text
actual_model_identity: deepseek-v4-flash
endpoint: https://api.deepseek.com/v1
provider_class: deerflow.models.patched_deepseek:PatchedChatDeepSeek
request_attempt_count: 1
retry_count: 0
token_usage: 60 input / 11 output / 71 total
stop_reason: stop
latency: ~935 ms
```

The candidate call also passed the same server-identity and telemetry checks. Its temporary audit record was written to the test isolated audit directory and was intentionally not committed to Git. The repository never stores prompt, response body, API key or raw uploaded row values in source control.

## Deterministic verification

The candidate parser and confirmation boundary are covered without a model:

```text
PYTHONPATH=. .venv/bin/pytest -q \
  tests/commerce/data/test_semantic_candidates.py

3 passed
exit code: 0
```

The full deterministic Commerce regression continues to exclude live model tests. Any future Agent, Router, Verification, Eval or Release Gate test must follow the same fresh DeepSeek V4 rule.
