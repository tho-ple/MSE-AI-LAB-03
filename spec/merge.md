# Merge log

Owner of this file's structure: **merger**. Each worker edits **only** their own
`## Package X` section. The merger fills the integration log.

Merge order and gates: `design.md` §5.2.

---

## Package A — PyPI & OSV adapters

- Branch / commits:
- Files touched (must match `task-A.md` §1):
- Focused check output:
- Proposed decisions (for `DECISIONS.md`):
- Proposed changes to files outside my ownership:
- Things the merger must watch:

## Package B — deps.dev adapter

- Branch / commits:
- Files touched (must match `task-B.md` §1):
- Focused check output:
- Proposed decisions (for `DECISIONS.md`):
- Proposed changes to files outside my ownership:
- Things the merger must watch:

## Package C — cache & scanner

- Branch / commits: `task-c`, based on `8ec7f71`
  - `Implement async TTL/LRU cache`: `cache.py` + `tests/test_task_c_cache.py`
  - `Orchestrate concurrent, cached, cancellable package scans`: `service.py`
  - `Add scanner tests for failures, cancellation, limits, and caching`: `tests/test_task_c_scanner.py`
  - `Fill Package C merge notes`: this section
  - `Attribute captured failures to the calling source`: review fix in `service.py` + test
  - `Fix extended ruff findings in Task C files`: lint fixes (RUF002, PT011, D101)
- Files touched (must match `task-C.md` §1): `src/dependency_intelligence/cache.py`,
  `src/dependency_intelligence/service.py`, `tests/test_task_c_cache.py` (new),
  `tests/test_task_c_scanner.py` (new), `spec/merge.md` (this section only).
  No other file changed. Check with `git diff --name-only main...task-c`.
- Focused check output (on `task-c`, before A and B are merged):
  - `uv run pytest tests/test_task_c_cache.py tests/test_task_c_scanner.py -q` → 18 passed
  - `uv run pytest -m "cache or orchestration or transport" -q` → 27 passed, 6 deselected
  - `uv run ruff check .` → all checks passed; `uv run ruff format --check .` → 40 files already formatted
  - `uv run mypy src tests checks` → no issues in 28 source files
  - `uv run pytest -q` → 31 passed, 2 failed. The 2 failures are the `sources`
    contract tests (`NotImplementedError` in the deps.dev / PyPI adapters), which
    belong to Tasks A and B. Expected.
  - Mutation check: four deliberate bugs, one at a time (catching
    `BaseException`, caching partial results, a semaphore per call, leaking
    exception text). Each one is caught by at least one test.
  - Code review of `cache.py` / `service.py`: one fix applied (failure
    attribution now comes from the calling source, not from the adapter's
    error). Extended linting with `ruff --select ALL` on the Task C files
    (config unchanged): RUF002, PT011, D101 fixed; the rest conflicts with
    the repo's established style.
- Proposed decisions (for `DECISIONS.md`): none new. Implements Decisions 1, 2,
  3, 6, 7, 10, 11 as written. One detail for Decision 2: `put()` only purges
  expired entries when the cache is over capacity, so a dead entry is dropped
  before a live LRU entry. `size()` and `get()` purge as specified.
- Proposed changes to files outside my ownership: none.
- Things the merger must watch:
  - **Known limitation (supplied `singleflight.py`):** when the last waiter
    leaves, `SingleFlight` cancels the flight task but does not await it. The
    source calls do observe cancellation (contract test and S5), but they may
    finish their cleanup a few loop iterations after `scan()` has returned.
    Mention this in the `EVIDENCE.md` risk section.
  - **Decision 11 fairness:** the package limit is shared by all concurrent
    scans of one scanner (process-wide in the API). A large request can delay a
    small one. This is a latency issue, not a correctness one.
  - A `CancelledError` raised by a source itself propagates out of
    `assess()`/`scan()`; it is never reported as a failure (REQ-FAIL-05,
    tested). Adapters A and B must therefore not raise `CancelledError` for
    anything other than a real cancellation.
  - **Open review point (needs a merger decision, no code change yet):** a
    source that raises `CancelledError` *without* the scan being cancelled
    currently aborts the whole scan (the API then sends no normal response).
    Alternative: in `_capture`, re-raise only if
    `asyncio.current_task().cancelling()` is set, and otherwise report
    `unexpected`. This would refine REQ-FAIL-05, so it needs a decision first.
  - Review note: at full capacity, every `put()` of a new key scans all entries
    once for expired ones (O(n), n ≤ `CACHE_MAX_ENTRIES` = 2000). This is
    acceptable at lab scale.
  - After merging A and B, the expected full-suite result is **all green**. Run
    `uv run pytest -q` after step 3.

---

## Integration log (merger)

| Step | Branch | Diff only in owned files? | Focused check | Result / notes |
| --- | --- | --- | --- | --- |
| 1 | `task-a` | | `uv run pytest tests/test_task_a_pypi_osv.py` | |
| 2 | `task-b` | | `uv run pytest -m sources` | |
| 3 | `task-c` | | `uv run pytest -m "cache or orchestration or transport"` | |
| 4 | — | — | full quality gate | |
| 5 | — | — | runtime evidence (`EVIDENCE.md`) | |
