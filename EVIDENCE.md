# Verification evidence and acceptance decision

## Quality gate

| Command | Exit | Concise result |
| --- | ---: | --- |
| `uv run ruff check .` | | |
| `uv run ruff format --check .` | | |
| `uv run mypy src tests checks` | | |
| `uv run pytest` | | |

## Concurrency evidence

Command or test:

Observed timing/start-order evidence:

Why this proves overlap rather than only fast execution:

## Cache evidence

Run the same API request twice, then inspect `GET http://127.0.0.1:8090/_admin/calls`.

First response cache state:

Second response cache state:

Upstream counters before/after the second request:

## Partial-failure evidence

Scan `unavailable-osv-demo==1.0.0` against the fixtures.

Successful fields retained:

Attributed failure:

Why `vulnerabilities: null` is different from `vulnerabilities: []`:

## Agent-tool boundary evidence

Attempt `../requirements.lock` through the tool adapter.

Observed result:

Boundary being enforced:

## Specification trace

| Acceptance criterion | Implementing commit(s) | Test or runtime evidence |
| --- | --- | --- |
| AC-01 | | |

## Human acceptance decision

- Decision: accept / reject / accept with stated limitation
- Evidence supporting the decision:
- Unresolved production risk:
- Why passing tests alone are or are not sufficient here:
