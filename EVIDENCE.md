# Verification evidence and acceptance decision

**Group video (4:23, unlisted):** https://youtu.be/v5zIaBPWbWw. Slides: `video/presentation.md`, narration: `video/script.md`.

Collected on 2026-11-18 on `main` at `afe2a81` (packages A, B, C plus Decision
12), Windows 11, Python 3.12.16 via uv 0.13.9. All runtime evidence uses the
deterministic fixtures (`uv run dependency-fake-upstreams`, port 8090). No live
services or credentials were used.

API instances used:

| Port | Command | Purpose |
| --- | --- | --- |
| 8000 | `PYPI_BASE_URL=… OSV_BASE_URL=… DEPS_DEV_BASE_URL=http://127.0.0.1:8090 uv run dependency-api` | default settings (packages 8, pool 24, deadline 30 s) |
| 8001 | same + `SCAN_TIMEOUT_SECONDS=1`, started via `uv run uvicorn dependency_intelligence.bootstrap:build_app --factory --port 8001` | deadline evidence |
| 8002 | same + `MAX_CONCURRENT_PACKAGES=2 MAX_HTTP_CONNECTIONS=100`, port 8002 | package-limit evidence |

## Quality gate

| Command | Exit | Concise result |
| --- | ---: | --- |
| `uv run ruff check .` | 0 | All checks passed! |
| `uv run ruff format --check .` | 0 | 42 files already formatted |
| `uv run mypy src tests checks` | 0 | Success: no issues found in 30 source files (strict) |
| `uv run pytest` | 0 | 59 passed (15 contract/supplied + 44 package tests) |

## Concurrency evidence

Command or test:

- Unit level: `test_three_sources_start_concurrently`,
  `test_deps_dev_requests_start_concurrently`,
  `test_package_limit_and_order_are_preserved` (contract), plus the package
  tests for the shared limit (S7) and cancellation (S5, S6).
- Runtime: `POST /v1/scans` with `slow-*` packages. The fixture sleeps **2 s in
  every upstream call** (PyPI, OSV, deps.dev metadata, deps.dev graph), so one
  package makes 4 slow calls.

Observed timing/start-order evidence:

| API | Request | Upstream calls | Time | Sequential would be |
| --- | --- | --- | ---: | ---: |
| :8000 | 1 slow package | `{"pypi":1,"osv":1,"deps":1,"deps_graph":1}` | **2.10 s** | 8 s |
| :8000 | 3 slow packages | 3 × 4 = 12 calls | **2.14 s** | 24 s |
| :8000 | 8 slow packages | 8 × 4 = 32 calls | **4.19 s** | 64 s |
| :8002 (limit 2) | 2 slow packages | 8 calls | **2.14 s** | 16 s |
| :8002 (limit 2) | 3 slow packages | 12 calls | **4.12 s** | 24 s |
| :8002 (limit 2) | 5 slow packages | 20 calls | **6.25 s** | 40 s |

Order: the request `slow-z, fast-a, slow-y, fast-b` returned
`['slow-z', 'fast-a', 'slow-y', 'fast-b']`, so the input order is kept although
the fast packages finish first.

Why this proves overlap rather than only fast execution:

- Every single upstream call **cannot** take less than 2 s. One package needs 4
  such calls, so 2.10 s is only possible if all four (PyPI, OSV, both deps.dev
  endpoints) were in flight at the same time (AC-03).
- With limit 2, the time grows in exact 2-second steps of ⌈n / 2⌉ (2 → 2.1 s,
  3 → 4.1 s, 5 → 6.3 s). Packages run in waves of at most two, which is the
  configured bound (AC-04).
- The 8-package run on :8000 takes two waves (4.19 s) although 8 packages are
  allowed. 32 calls exceed the HTTP pool of `MAX_HTTP_CONNECTIONS=24`, so the
  bounded shared pool (SPEC 5) is visible too. With 3 packages (12 calls < 24),
  one wave suffices.

## Cache evidence

Run the same API request twice, then inspect `GET http://127.0.0.1:8090/_admin/calls`.

Request: `{"dependencies":[{"name":"fastapi","version":"0.115.0"},{"name":"jinja2","version":"2.4.1"}]}`
on :8000, after `POST /_admin/reset`.

First response cache state: HTTP 200 in 0.246 s, `status: complete`;
`fastapi` → `cache_status: miss`, `jinja2` → `cache_status: miss`.
`jinja2` carries `GHSA-demo-0001`; `summary.vulnerable_dependencies: 1`.

Second response cache state: HTTP 200 in 0.022 s, `status: complete`;
`fastapi` → `cache_status: hit`, `jinja2` → `cache_status: hit`, with
identical data.

Upstream counters before/after the second request:

```text
after first : {"pypi":2,"osv":2,"deps":2,"deps_graph":2}
after second: {"pypi":2,"osv":2,"deps":2,"deps_graph":2}   ← no new upstream calls
```

Coalescing of simultaneous identical misses (1 `miss` + 4 `coalesced`, a single
load) is proven by `test_complete_result_is_cached_and_identical_misses_coalesce`.
Expiry and eviction are proven by `test_cache_expires_and_evicts_lru` and the
package test S8.

## Partial-failure evidence

Scan `unavailable-osv-demo==1.0.0` against the fixtures.

Successful fields retained: HTTP **200**, `status: partial`. PyPI data kept
(`latest_version: 2.0.0`, `update_status: outdated`), deps.dev data kept
(`licenses: ["MIT"]`, `direct_dependency_count: 1`, `published_at`),
`complete: false`, `cache_status: miss`.

Attributed failure:

```json
{"dependency": "unavailable-osv-demo==1.0.0", "service": "osv",
 "kind": "unavailable", "retryable": true,
 "detail": "service returned HTTP 503", "status_code": 503}
```

Counters `{"pypi":1,"osv":2,"deps":1,"deps_graph":1}`: OSV was tried twice (the
supplied retry policy for 503), and every other source was tried once. A second
identical request again reported `cache_status: miss` and raised the counters to
`{"pypi":2,"osv":4,"deps":2,"deps_graph":2}`, so **the partial result was not
cached** and the missing source was called again (SPEC 6, AC-06).

Why `vulnerabilities: null` is different from `vulnerabilities: []`:
`[]` (as for `fastapi` above) means OSV **answered** and knows no advisory.
`null` means OSV gave **no trustworthy answer**, so nothing is known. The
summary therefore reports `vulnerable_dependencies: 0` without claiming the
package is safe (SPEC 8, SPEC 10), and the failure list says why the data is
missing.

Additional failure evidence:

- Complete failure, `missing-demo==1.0.0`: HTTP **503**, `status: failed`,
  three failures `pypi/not_found/404`, `osv/not_found/404`,
  `deps.dev/not_found/404`, each `retryable: false` (AC-07).
- Deadline, `slow-e-0==1.0.0` on :8001 (`SCAN_TIMEOUT_SECONDS=1`): HTTP **504**
  after 1.03 s, body `{"status":"failed","code":"scan_timeout",…}`. All four
  upstream calls had started (`{"pypi":1,"osv":1,"deps":1,"deps_graph":1}`).
  That the source operations observe cancellation is proven by
  `test_cancelling_final_waiter_cancels_sources` and package test S5 (AC-08).
- Invalid input, duplicate normalized names `demo` / `Demo`: HTTP **422**,
  upstream counters stayed `{}` (AC-01).

## Agent-tool boundary evidence

Attempt `../requirements.lock` through the tool adapter.

Observed result:

```text
$ uv run dependency-agent-tool --workspace sample-project --manifest ../requirements.lock
{"status": "invalid_manifest_path", "message": "hidden and parent path components are not allowed"}   exit 2
$ … --manifest C:/Windows/requirements.lock
{"status": "invalid_manifest_path", "message": "manifest path must be relative to the workspace"}     exit 2
$ uv run dependency-agent-tool --workspace . --manifest pyproject.toml
{"status": "invalid_manifest_path", "message": "manifest filename is not allowed"}                    exit 2
$ uv run dependency-agent-tool --workspace sample-project
status complete, same report keys as the API (dependencies, failures, status, summary);
fastapi 0.115.0 complete, jinja2 2.4.1 complete with GHSA-demo-0001                                     exit 0
```

Boundary being enforced: the tool reads only a file named `requirements.lock`
at a relative path inside the resolved workspace root. Absolute paths, `..` and
hidden components, other filenames and symlinks resolving outside the root are
rejected **before** any file is read or any scan starts. The contract test
`test_agent_tool_rejects_parent_escape` uses a scanner that fails if it is
called. The tool never writes to the workspace (AC-09).

## Specification trace

| Acceptance criterion | Implementing commit(s) | Test or runtime evidence |
| --- | --- | --- |
| AC-01 | supplied (`a793719`: `api.py`, `manifest.py`, `domain.py`) | `test_coordinate_and_manifest_validation`; runtime 422 with `{}` upstream calls |
| AC-02 | A `29cf9b0`, `2fbe5a3` (merge `71c3f23`); B `63d1059` (merge `bd766f6`) | `test_source_adapters_translate_valid_responses`; `tests/test_task_a_pypi_osv.py` (10); `tests/test_task_b_deps_dev.py` (15) |
| AC-03 | B `63d1059`; C `988a787` | `test_three_sources_start_concurrently`, `test_deps_dev_requests_start_concurrently`; runtime 1 package = 2.10 s for 4 × 2 s calls |
| AC-04 | C `988a787` | `test_package_limit_and_order_are_preserved`, S7; runtime ⌈n/2⌉ × 2 s with limit 2; order kept |
| AC-05 | C `3ca4fec`, `988a787` | `test_complete_result_is_cached_and_identical_misses_coalesce`, `test_cache_expires_and_evicts_lru`, C1–C5, S8; runtime miss → hit, counters unchanged |
| AC-06 | C `988a787`, `bea6ebf` | `test_partial_result_is_attributed_and_not_cached`, `test_project_report_status_semantics`; runtime `unavailable-osv-demo`: 200, partial, `null`, not cached |
| AC-07 | C `988a787` (Decision 1) | `test_api_maps_complete_and_failed_reports`, S1; runtime `missing-demo`: 503, `failed`, 3 attributed failures |
| AC-08 | C `988a787`, `8437500` (Decision 12) | `test_cancelling_final_waiter_cancels_sources`, S5, S6, `_capture` cancellation test; runtime 504 `scan_timeout` after 1.03 s |
| AC-09 | supplied (`agent_tool.py`, `tool_cli.py`) + C scanner | `test_agent_tool_rejects_parent_escape`; runtime: `..`, absolute path and other filename rejected; valid manifest gives the same report shape |
| AC-10 | all packages; review fixes `bea6ebf`, `cd7779c` | quality gate above (all exit 0); layering unchanged (I/O only in adapters, orchestration only in `service.py`) |

## Human acceptance decision

- Decision: **accept with stated limitation**
- Evidence supporting the decision: every acceptance criterion AC-01…AC-10
  has at least one deterministic test **and**, where observable, runtime
  evidence against the fixtures (table above). The quality gate is clean. Each
  package was reviewed against its owned files before merging and integrated
  one at a time with a green focused check (`spec/merge.md`). The deliberately
  broken variants of `service.py` (catching `BaseException`, caching partial
  results, a semaphore per call, leaking exception text, wrong cancellation
  handling) each made at least one test fail.
- Unresolved production risk:
  1. `SingleFlight` (supplied) cancels a load when its last waiter leaves but
     does not await it. Source calls observe cancellation, but their cleanup
     can finish shortly after the scan has returned.
  2. The package limit is shared per scanner (Decision 11). One large request
     can delay a small one (fairness, not correctness).
  3. `tool_cli.py` does not apply `MAX_HTTP_CONNECTIONS` (Decision 9); the CLI
     pool is bounded only by httpx's default of 100.
  4. Only the deterministic fixtures were exercised. The real PyPI, OSV and
     deps.dev APIs may differ in details the fixtures don't model (rate limits,
     deps.dev version spelling for the strict identity check of Decision 4).
- Why passing tests alone are or are not sufficient here: they are **not**
  sufficient on their own. The tests prove the logic with fakes that never take
  real time. Overlap, the package bound and the HTTP pool bound only become
  visible under real timing. The runtime measurements show them: 4 calls of
  2 s finishing in 2.1 s, ⌈n/2⌉ waves with limit 2, and the 24-connection pool
  forcing a second wave. In the same way, cache reuse is only convincing when
  the upstream call counters stay unchanged. The tests also cannot show whether
  the fixtures resemble the real services, which is why risk 4 remains.
