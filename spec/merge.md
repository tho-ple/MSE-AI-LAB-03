# Merge log

Owner of this file's structure: **merger**. Each worker edits **only** their own
`## Package X` section. The merger fills the integration log.

Merge order and gates: `design.md` §5.2.

---

## Package A — PyPI & OSV adapters

- Branch / commits: `TaskA/PyPi_OSV_source_adapters` (stands in for `task-a`),
  branched from `main` at `8ec7f71`. Commits:
  `Implement PyPI metadata adapter`, `Implement OSV vulnerability adapter`,
  `Add PyPI and OSV adapter tests`, `Fill in Package A merge notes`.
- Files touched (must match `task-A.md` §1):
  `src/dependency_intelligence/sources/pypi.py`,
  `src/dependency_intelligence/sources/osv.py`,
  `tests/test_task_a_pypi_osv.py` (new), and this section of `spec/merge.md`.
  Nothing else.
- Focused check output:

  ```text
  $ uv run pytest tests/test_task_a_pypi_osv.py -q
  10 passed in 0.69s
  $ uv run ruff check src/dependency_intelligence/sources/pypi.py src/dependency_intelligence/sources/osv.py tests/test_task_a_pypi_osv.py
  All checks passed!
  $ uv run ruff format --check src/dependency_intelligence/sources tests/test_task_a_pypi_osv.py
  5 files already formatted
  $ uv run mypy src tests checks
  Success: no issues found in 27 source files
  ```

  Full suite on this branch: 15 passed, 10 failed. The 10 failures are the
  same `NotImplementedError` seams of packages B and C as on `main`.
  `test_source_adapters_translate_valid_responses` now gets past PyPI and OSV
  and stops at `TODO: implement the deps.dev adapter`, as `task-A.md` §5 expects.
- Proposed decisions (for `DECISIONS.md`): none. The adapters follow
  `design.md` §3.1–3.2 and Decision 8 as written. Decision 8 applies only to the
  PyPI name segment, because the PyPI URL has no version and OSV sends the
  coordinate in the JSON body.
- Proposed changes to files outside my ownership: none.
- Things the merger must watch:
  - The branch name differs from `task-a` in `design.md` §5.1. Use
    `TaskA/PyPi_OSV_source_adapters` in integration-log step 1.
  - After merging B, `uv run pytest -m sources` should be fully green. If the
    contract translate test still fails there, the cause lies in the OSV or
    PyPI part of that test, not in deps.dev.
  - Test A10 expects exactly two HTTP calls for a repeated 503, so it relies on
    the supplied `JsonHttpClient` default `max_attempts=2`.
  - The test file defines its own `no_sleep` helper instead of adding one to
    `tests/fakes.py`, which nobody owns.

## Package B — deps.dev adapter

- Branch / commits: `task-b` / `63d1059` (`Implement deps.dev supply-chain adapter`).
- Files touched (must match `task-B.md` §1): `src/dependency_intelligence/sources/deps_dev.py`, `tests/test_task_b_deps_dev.py`, this section.
- Focused check output: PASS — 16 tests; `uv run ruff check src/dependency_intelligence/sources/deps_dev.py tests/test_task_b_deps_dev.py`; `uv run ruff format --check src/dependency_intelligence/sources/deps_dev.py tests/test_task_b_deps_dev.py`; `uv run mypy src tests checks`.
- Proposed decisions (for `DECISIONS.md`): none.
- Proposed changes to files outside my ownership: none.
- Things the merger must watch: the contract test verifies overlap; the package tests also cover cancellation after one endpoint fails, graph validation, identity matching, and encoded local-version path segments.

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
| 1 | `TaskA/PyPi_OSV_source_adapters` → `71c3f23` | yes: `pypi.py`, `osv.py`, own test, own section | `uv run pytest tests/test_task_a_pypi_osv.py` | 10 passed. Full suite 15 passed / 10 failed (B and C still open, expected) |
| 2 | `task-b` → `bd766f6` | yes: `deps_dev.py`, own test, own section | `uv run pytest -m sources` | 27 passed, including `test_source_adapters_translate_valid_responses` (needs A + B). Full suite 32 passed / 8 failed (C open, expected) |
| 3 | `task-c` → `9bfcd92` | yes: `cache.py`, `service.py`, own tests, own section | `uv run pytest -m "cache or orchestration or transport"` | 27 passed |
| 4 | — | — | full quality gate | `ruff check` ✔ · `ruff format --check` ✔ (42 files) · `mypy src tests checks` ✔ (30 files) · `pytest` **58 passed** · readiness READY |
| 5 | — | — | runtime evidence (`EVIDENCE.md`) | open |

Notes:
- All three branches start from `8ec7f71`. `spec/merge.md` merged without
  conflicts (separate sections).
- Code review before each merge: A and B match `design.md` §3.1–3.3 and
  Decisions 4, 5, 8. No proposed decisions and no changes to files outside
  their ownership in any package.
- Open for the merger: the Package C review point about a `CancelledError`
  raised by a source (refines REQ-FAIL-05) needs a decision; known
  limitations (SingleFlight not awaited, Decision 9, Decision 11 fairness) go
  into the `EVIDENCE.md` risk section.
