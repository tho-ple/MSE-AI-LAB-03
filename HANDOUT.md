# Lab 3 — specification-driven concurrent dependency scanning

## Mission

Complete a service that scans exact Python dependencies against three
independent sources:

- PyPI for the latest version and Python requirement;
- OSV for known vulnerability advisories; and
- deps.dev for license, publication, and dependency-graph information.

The feature must run independent work concurrently, bound resource use, reuse
complete results from a cache, and preserve useful data when one source fails.
The same application service powers an HTTP endpoint and a workspace-bounded
agent tool.

This is not a speed-prompting exercise. Your assessed process is:

```text
specification → independent tickets → bounded implementation
              → deterministic evidence → human acceptance decision
```

## Open and verify the lab

Use local Ollama, your dedicated API key or you personal subscription for commercial harnesses.
Keep the same harness for the full lab.

Open the repository and run:

```bash
uv sync --locked --extra dev
uv run python checks/readiness.py
aider --version   # Aider groups
pi --version      # Pi groups
```

## Split the specification into independent tickets

Start the harness in the repository root. Give it this task,
with your actual group size substituted:

> Read `SPEC.md`, `AGENTS.md`, the public interfaces under `src/`, and
> `tests/test_contract.py`. Do not edit code. Split the feature into independent,
> reviewable tickets for a group of **N**. For each ticket state its acceptance
> criteria, owned files, focused test command, dependencies, and merge order.
> Minimize overlapping production files.

Before implementation, check that:

- every required behavior maps to at least one ticket;
- every ticket has a focused, observable completion check;
- production-file ownership does not overlap;
- interfaces needed by parallel work are already stable;
- integration order is explicit; and
- one person owns final integration rather than every ticket editing the
  composition root.

Assign one owner to each ticket, then proceed with bounded implementation.

## Implement independent tickets

Each owner asks the same harness to implement only their ticket. A
useful request names:

1. the ticket and acceptance criteria;
2. the files it may modify;
3. the focused tests it must run; and
4. the evidence it must return: diff summary, checks, and unresolved risk.

Review every proposed change. The harness may inspect supplied infrastructure,
but it must not broaden scope or change the contract tests. Commit one coherent
ticket at a time with an imperative summary.

Run focused checks with markers:

```bash
uv run pytest -m sources
uv run pytest -m cache
uv run pytest -m orchestration
uv run pytest -m transport
```

## Integrate deliberately

The integrator merges or cherry-picks one ticket at a time.

For each ticket:

1. inspect the diff against its allowed files;
2. run the ticket’s focused test command;
3. resolve contract mismatches at the interface, not with special cases; and
4. record a material decision in `DECISIONS.md`.

Then run the full quality gate:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests checks
uv run pytest
```

## Collect production evidence

Start the deterministic fixtures and API in separate terminals:

```bash
uv run dependency-fake-upstreams
```

```bash
PYPI_BASE_URL=http://127.0.0.1:8090 \
OSV_BASE_URL=http://127.0.0.1:8090 \
DEPS_DEV_BASE_URL=http://127.0.0.1:8090 \
uv run dependency-api
```

Use the commands in `EVIDENCE.md` to prove:

- source and package calls overlap;
- a second identical scan is served from cache without more upstream calls;
- one source outage produces a partial report with attributed failure; and
- the agent tool rejects a parent-path escape.

Paste concise outputs into `EVIDENCE.md`. Do not paste credentials or an entire
harness transcript.

## Decide and explain

Complete the acceptance decision in `EVIDENCE.md`, then record one group video
that covers:

1. one acceptance criterion and how the implementation satisfies it;
2. concurrency and cache ownership in the final design;
3. cache reuse and one partial failure;
4. the quality gate and one meaningful diff; and
5. the acceptance decision and one remaining production risk.

A passing test run without a defensible specification trace does not complete the lab.

## Submission

Submit:

- the repository with ticket commits;
- completed `DECISIONS.md` and `EVIDENCE.md`; and
- one group video.

Do not submit API keys, local model files, `.env` files, raw credentials, or
solution materials.
