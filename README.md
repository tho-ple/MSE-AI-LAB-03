# Concurrent dependency intelligence lab

Start with [HANDOUT.md](HANDOUT.md). `SPEC.md` is the authoritative behavior
contract; `AGENTS.md` defines repository working rules.

This starter already contains the domain records, validated manifest parser,
bounded HTTP policy, FastAPI and agent-tool adapters, deterministic upstream
fixtures, and contract tests. The intentionally incomplete implementation seams
are isolated so a group can work in parallel:

- `sources/pypi.py`
- `sources/osv.py`
- `sources/deps_dev.py`
- `cache.py`
- `service.py`

Do not begin by assigning those files manually. First ask your harness
to derive independently reviewable tickets from `SPEC.md`, the public
interfaces, and the tests. Assign one owner and a focused check to each ticket.

## Start here

Use your harness of Choice throughout the lab.

```bash
uv sync --locked --extra dev
uv run python checks/readiness.py
uv run pytest -q
```

The untouched starter is expected to have failing acceptance tests. Collection,
the readiness check, and the tests for supplied infrastructure must succeed.
Record any environment failure instead of installing or switching harnesses
during the exercise.

## Final quality gate

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests checks
uv run pytest
```
