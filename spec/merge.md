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
