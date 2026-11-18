# Task C — TTL/LRU cache & scanner orchestration

| Field       | Value                                                                                                                                              |
| ----------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| Goal        | A concurrency-safe TTL/LRU cache, plus `DependencyScanner`: concurrent sources, bounded packages, single-flight, cache-only-complete, cancellation |
| Owner       | Thomas Pleiner                                                                                                                                     |
| Branch      | `task-c` (from the `main` commit that adds this file)                                                                                              |
| Depends on  | nothing; built **only** against the ports and `tests/fakes.py`, never against the real adapters                                                    |
| Merge order | 3 of 3 (see `design.md` §5.2)                                                                                                                      |
| Size        | large; the core of the lab                                                                                                                         |

## 1. Scope

### Files you own (may create and modify)

- `src/dependency_intelligence/cache.py`
- `src/dependency_intelligence/service.py`
- `tests/test_task_c_cache.py` (new)
- `tests/test_task_c_scanner.py` (new)
- `spec/merge.md`: **only** the `## Package C` section

### Read-only references

`domain.py` (`PackageAssessment.complete`, `DependencyScanResult.complete/useful`,
`ProjectScanReport.status`), `ports.py`, `errors.py`, `singleflight.py`,
`api.py`, `agent_tool.py`, `bootstrap.py`, `tests/fakes.py`,
`tests/test_contract.py`.

### Must not touch

Everything else, in particular `sources/*.py` (Tasks A and B), `singleflight.py`,
`domain.py`, `reporting.py`, `api.py`, `tests/fakes.py`, `pyproject.toml`, and the
protected files. If you think one needs to change, write it into your `merge.md`
section as a proposal instead.

## 2. Requirements and decisions

| Ref | Summary |
| --- | --- |
| REQ-CACHE-01…10 | async, lock-protected; monotonic injected clock; expiry fixed at insertion; LRU eviction; `size()` purges expired entries; key = `coordinate.cache_key`; **only complete** results stored; `hit` / `miss` / `coalesced` |
| REQ-CON-01 | the 3 sources of one package start before any finishes |
| REQ-CON-02/03 | at most `max_concurrent_packages` at once; results in input order |
| REQ-CON-05 | cancelling `scan` cancels **and awaits** the child tasks |
| REQ-CON-06/07 | one load per coordinate in flight; a cancelled waiter doesn't kill another's load; the last waiter leaving cancels the sources |
| REQ-FAIL-04/05/06 | `SourceRequestError` → `.failure`; other `Exception` → `unexpected`; `CancelledError` is never caught; one failure → partial |
| REQ-ASM-01…04 | `None` only for a failed source, `()` stays `()`; all failed → `assessment None`; failure order fixed |
| REQ-OUT-05 | deadline → `api.py` cancels `scan` → the sources observe cancellation |
| Decision 1 | all three failed → `assessment = None` |
| Decision 2 | expired when `now >= inserted_at + ttl`; reads touch LRU, not expiry |
| Decision 3 | unexpected → `SourceFailure(service, UNEXPECTED, False, "unexpected <Type>")`, with no exception message |
| Decision 6 | cache check → `SingleFlight.run`; starter = `miss`, joined = `coalesced` (also when partial); only `_load` writes, only complete results |
| Decision 7 | failure order PyPI → OSV → deps.dev |
| Decision 10/11 | one `asyncio.Semaphore` per scanner instance, wrapping the whole `assess()` per package |

Design reference: `design.md` §3.4 and §3.5, including all three sequence diagrams.

## 3. Acceptance criteria (definition of done)

- [ ] `AsyncTTLCache.get/put/size` and `DependencyScanner.scan/assess` are implemented; the signatures are unchanged.
- [ ] All contract tests marked `cache`, `orchestration` and `transport` pass:
  - `test_cache_expires_and_evicts_lru`
  - `test_three_sources_start_concurrently`
  - `test_package_limit_and_order_are_preserved`
  - `test_partial_result_is_attributed_and_not_cached`
  - `test_complete_result_is_cached_and_identical_misses_coalesce`
  - `test_cancelling_final_waiter_cancels_sources`
  - `test_api_maps_complete_and_failed_reports`
  - `test_agent_tool_rejects_parent_escape` (already green; must stay green)
  - `test_project_report_status_semantics`
- [ ] `CancelledError` is never caught as a failure (no `except BaseException` and no bare `except` in `service.py`).
- [ ] No exception message text from a source appears in a `SourceFailure.detail`.
- [ ] Your own tests (below) pass, and so do `ruff check`, `ruff format --check` and strict `mypy`.
- [ ] The `## Package C` section of `spec/merge.md` is written.

## 4. Tests you write

Use only `tests/fakes.py` (`FakeMetadataSource`, `StartGate`, `FakeClock`,
`MemoryCache`, `source_failure`). Add small local fakes inside your test file if
needed, for example a source that raises `RuntimeError`. Do not use `sleep`-based
timing.

### `tests/test_task_c_cache.py` (`pytestmark = pytest.mark.cache`)

| # | Case | Expect |
| --- | --- | --- |
| C1 | `get` refreshes LRU: put a, b; get a; put c | b evicted, a kept |
| C2 | `get` does **not** extend the TTL: put at t=0, get at t=9, check at t=10 | miss at t=10 |
| C3 | `put` on an existing key overwrites the value and resets its expiry | new value; lives until `t_put + ttl` |
| C4 | `size()` purges expired entries | count of live entries only |
| C5 | 50 concurrent `put`/`get` via `asyncio.gather` with `max_entries=10` | `size() <= 10`; no exception |

### `tests/test_task_c_scanner.py` (`pytestmark = pytest.mark.orchestration`)

| # | Case | Expect |
| --- | --- | --- |
| S1 | all three fakes fail | `assessment is None`; 3 failures in order pypi, osv, deps.dev; `report.status == FAILED` |
| S2 | OSV succeeds with `()`, PyPI fails | `vulnerabilities == ()` (not `None`); `metadata is None` |
| S3 | a source raises `RuntimeError("secret-body")` | kind `unexpected`, `retryable False`; `"secret-body"` not in the detail |
| S4 | failures complete in reverse order (gated) | the order is still pypi → osv → deps.dev |
| S5 | cancel `scan([a, b])` while the sources are blocked on a gate | `CancelledError`; `gate.cancelled == 6` |
| S6 | two waiters on one flight, cancel one | the other still gets a complete result; the sources were **not** cancelled |
| S7 | two concurrent `scan()` calls on one scanner with limit 2 | at most 2 packages in sources at any time (Decision 11) |
| S8 | a complete result is cached; after `FakeClock` passes the TTL, the next `assess` | `miss` and new source calls |

## 5. Focused check

```bash
uv run pytest tests/test_task_c_cache.py tests/test_task_c_scanner.py -q
uv run pytest -m "cache or orchestration or transport" -q
uv run ruff check src/dependency_intelligence/cache.py src/dependency_intelligence/service.py tests/test_task_c_cache.py tests/test_task_c_scanner.py
uv run ruff format --check src/dependency_intelligence/cache.py src/dependency_intelligence/service.py tests/test_task_c_cache.py tests/test_task_c_scanner.py
uv run mypy src tests checks
```

On this branch, the two `sources` contract tests stay red (Tasks A and B). That
is expected.

## 6. Deliverables

1. Code and tests, in small imperative commits on `task-c`, for example:
   - `Implement async TTL/LRU cache`
   - `Assess one package with concurrent sources`
   - `Coalesce identical misses and cache complete results`
   - `Scan packages with a bounded limit in input order`
   - `Add cache and scanner tests`
2. The `## Package C` section of `spec/merge.md`. Include the known limitations: `SingleFlight` cancels but does not
   await the flight task (supplied code), and the fairness of the
   per-scanner semaphore (Decision 11).

## 7. Prompt for the harness (copy and paste)

> You are implementing **Task C** from `spec/task-C.md`. Read `spec/task-C.md`,
> `spec/design.md` §3.4–3.5, `spec/requirements.md` (REQ-CACHE, REQ-CON, REQ-FAIL,
> REQ-ASM), `DECISIONS.md` Decisions 1, 2, 3, 6, 7, 10 and 11, and `AGENTS.md`.
> Modify **only** the files listed under "Files you own". Build against the
> ports and `tests/fakes.py`; do not edit the source adapters, `singleflight.py`
> or `tests/test_contract.py`. Implement the cache and the scanner, write the tests
> in §4, run the focused check in §5, then write the
> `## Package C` section of `spec/merge.md`. Return: a diff summary, the check
> outputs, and any unresolved risk.
