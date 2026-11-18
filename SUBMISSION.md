# Lab 03 — Submission info card

**Concurrent dependency intelligence** · specification-driven group project

| | |
| --- | --- |
| **Repository** | https://github.com/tho-ple/MSE-AI-LAB-03 |
| **Submitted state** | tag [`lab03-submission`](https://github.com/tho-ple/MSE-AI-LAB-03/tree/lab03-submission) on `main` |
| **Group video** (4:23) | https://youtu.be/v5zIaBPWbWw |
| **Acceptance decision** | ✔ accept with stated limitation ([details](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/EVIDENCE.md#human-acceptance-decision)) |

## Team

| Person | Role | Package | Branch |
| --- | --- | --- | --- |
| Johann Hoffmann | Worker | **A**: PyPI & OSV source adapters | `TaskA/PyPi_OSV_source_adapters` |
| Michael Auß | Worker | **B**: deps.dev source adapter | `task-b` |
| Thomas Pleiner | Worker + Merger | **C**: TTL/LRU cache & scanner orchestration · integration | `task-c`, `integration` |

## Required deliverables

| Deliverable (HANDOUT) | Where |
| --- | --- |
| Repository with ticket commits | [commit history](https://github.com/tho-ple/MSE-AI-LAB-03/commits/main) · one merge per package: A `71c3f23`, B `bd766f6`, C `9bfcd92` |
| Completed `DECISIONS.md` | [DECISIONS.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/DECISIONS.md): 12 decisions, each recorded before code depended on it |
| Completed `EVIDENCE.md` | [EVIDENCE.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/EVIDENCE.md): quality gate, runtime evidence, AC-01…AC-10 trace, acceptance decision |
| Group video | https://youtu.be/v5zIaBPWbWw · slides [presentation.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/video/presentation.md) · narration [script.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/video/script.md) |

## How we worked: the specification trace

`SPEC.md` was never edited. Everything we derived from it lives in
[`spec/`](https://github.com/tho-ple/MSE-AI-LAB-03/tree/main/spec):

| Step | Document | Content |
| --- | --- | --- |
| 1. Requirements | [requirements.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/spec/requirements.md) | ~60 numbered requirements, each with its origin (SPEC section / AC); test-to-requirement map; 10 open points |
| 2. Decisions | [DECISIONS.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/DECISIONS.md) | open points → Decisions 1–11 before implementation; Decision 12 from code review |
| 3. Design | [design.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/spec/design.md) | architecture, frozen interfaces, the cut into 3 independent packages, merge order, shared-file rules |
| 4. Tickets | [task-A.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/spec/task-A.md) · [task-B.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/spec/task-B.md) · [task-C.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/spec/task-C.md) | per package: goal, owner, owned / must-not-touch files, requirements, done checklist, tests to write, focused check, harness prompt |
| 5. Integration | [merge.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/spec/merge.md) | one section per package written by its owner, plus the merger's step-by-step integration log |

**Cut chosen for independence over equal size:** no package imports another
package's code, all branches started from the same commit (`8ec7f71`), and the
code merged without conflicts.

## Results

| Check | Result |
| --- | --- |
| `uv run ruff check .` · `uv run ruff format --check .` | exit 0 |
| `uv run mypy src tests checks` (strict) | exit 0 |
| `uv run pytest` | **59 passed**: 11 contract + 4 supplied + 44 own package tests (starter: 10 failing) |
| Protected files (`SPEC.md`, `tests/test_contract.py`, `checks/readiness.py`) | unchanged since the starter |

Runtime evidence against the deterministic fixtures (details in
[EVIDENCE.md](https://github.com/tho-ple/MSE-AI-LAB-03/blob/main/EVIDENCE.md)):

- **Concurrency:** one package = 4 upstream calls of 2 s each → **2.10 s** instead of 8 s
- **Package limit:** with limit 2, time grows in waves of ⌈n/2⌉ × 2 s
- **Cache:** second identical scan reports `hit`, with **0** new upstream calls
- **Partial failure:** OSV 503 → HTTP 200 `partial`, `vulnerabilities: null`, one retryable OSV failure, not cached
- **Failure / deadline / validation:** 503 `failed` · 504 `scan_timeout` after 1.03 s · 422 with 0 upstream calls
- **Agent tool:** `../`, absolute paths and other filenames rejected before any read

**Remaining production risk:** only deterministic fixtures were exercised, not
the real PyPI, OSV and deps.dev services (rate limits, version spellings).
Three smaller limitations are listed in `EVIDENCE.md`.

## Reproduce

```bash
git clone https://github.com/tho-ple/MSE-AI-LAB-03.git && cd MSE-AI-LAB-03
git checkout lab03-submission
uv sync --locked --extra dev
uv run python checks/readiness.py
uv run pytest
```

Verified on a fresh clone (Windows 11, Python 3.12.16, uv 0.13.9).

## AI usage

| Who | Tool | Used for |
| --- | --- | --- |
| Thomas, Johann | Claude Code (Claude Opus 5.5) | requirements, design and task documents; implementation of packages A and C; review; integration; evidence |
| Michael | GitHub Copilot | implementation of package B |
| Video | Kokoro TTS (voice `af_heart`), rendered locally | narration of the group video; disclosed in the video |

AI-assisted commits carry a `Co-authored-by` trailer. Each package was reviewed
against its ticket before merging. No credentials appear in the repository,
prompts or video.
