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

- Branch / commits:
- Files touched (must match `task-C.md` §1):
- Focused check output:
- Proposed decisions (for `DECISIONS.md`):
- Proposed changes to files outside my ownership:
- Things the merger must watch:

---

## Integration log (merger)

| Step | Branch | Diff only in owned files? | Focused check | Result / notes |
| --- | --- | --- | --- | --- |
| 1 | `task-a` | | `uv run pytest tests/test_task_a_pypi_osv.py` | |
| 2 | `task-b` | | `uv run pytest -m sources` | |
| 3 | `task-c` | | `uv run pytest -m "cache or orchestration or transport"` | |
| 4 | — | — | full quality gate | |
| 5 | — | — | runtime evidence (`EVIDENCE.md`) | |
