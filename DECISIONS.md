# Engineering decisions

Record only decisions that affect behavior, interfaces, failure semantics, or
verification. “The AI suggested it” is not a rationale.

Each decision references its open point (OP-xx) and requirements in
`spec/requirements.md`. Agreed by the team on 2026-11-18, before implementation.

## Decision 1

All sources failed → no assessment (OP-01)

- Context: `ProjectScanReport.status` returns `failed` only when no result is
  `useful`, and `useful` means `assessment is not None`. SPEC 2 defines `failed`
  as "no source produced useful data".
- Options considered: (a) always build a `PackageAssessment`, with `None` for
  each failed source; (b) set `assessment = None` when all three sources failed.
- Decision: (b). With at least one successful source, build a
  `PackageAssessment` with `None` only for the failed parts.
- Consequences and risk: option (a) would report `partial` / HTTP 200 for a
  total outage. Option (b) relies on the domain's `useful` definition staying
  unchanged.
- Specification or acceptance criteria affected: SPEC 2, SPEC 7, AC-07;
  REQ-ASM-03.
- Evidence that will verify it: `test_api_maps_complete_and_failed_reports`
  (503 + `failed`); a scanner test with all three fakes failing.

## Decision 2

Cache expiry boundary (OP-02)

- Context: SPEC 6 fixes expiry at insertion but doesn't define the boundary.
  The contract test advances the clock by exactly the TTL and expects a miss.
- Options considered: expired when `now > inserted_at + ttl`, or when
  `now >= inserted_at + ttl`.
- Decision: an entry is expired when `now >= inserted_at + ttl`. Reads never
  extend the expiry; a successful read only refreshes LRU recency.
- Consequences and risk: an entry lives slightly less than one full TTL at the
  boundary. That is harmless.
- Specification or acceptance criteria affected: SPEC 6, AC-05; REQ-CACHE-04/05.
- Evidence that will verify it: `test_cache_expires_and_evicts_lru`.

## Decision 3

Mapping unexpected source exceptions (OP-03)

- Context: SPEC 7 lists the `unexpected` kind and forbids leaking upstream
  bodies or credentials. A raw exception message might contain either.
- Options considered: (a) let the exception propagate and fail the whole scan;
  (b) map it to a failure that includes `str(error)`; (c) map it to a failure
  with a generic detail.
- Decision: (c). The scanner maps any exception from a source other than
  `SourceRequestError` and `asyncio.CancelledError` to
  `SourceFailure(service, unexpected, retryable=False, detail="unexpected <ExceptionType>", status_code=None)`.
  Cancellation always propagates.
- Consequences and risk: debugging detail is lost from the report and must come
  from logs instead. A programming bug in one adapter becomes a partial result
  rather than a crash.
- Specification or acceptance criteria affected: SPEC 7, AC-06, AC-08;
  REQ-FAIL-04/05.
- Evidence that will verify it: a scanner unit test with a fake source raising
  `RuntimeError("secret body")` asserts kind `unexpected` and that "secret body"
  does not appear in the detail.

## Decision 4

deps.dev identity check (OP-04)

- Context: deps.dev returns a `versionKey` in the version metadata and in the
  graph's `SELF` node. SPEC 4.3 doesn't say whether it must match the request.
- Options considered: lenient (ignore `versionKey`); strict (a mismatch is an
  invalid response).
- Decision: strict. Both `versionKey`s must match the requested coordinate. The
  name is compared after normalization (`VersionKey.coordinate()`), and the
  version is compared with `packaging.version.Version` equality, so `1.0` equals
  `1.0.0`. A mismatch raises `SourceRequestError(deps.dev, invalid_response, retryable=False)`.
- Consequences and risk: data for the wrong package is never presented as
  correct. Risk: false rejections if deps.dev ever reports a different but
  equivalent spelling. Normalization covers the known cases.
- Specification or acceptance criteria affected: SPEC 4.3, AC-02; REQ-DEPS-07.
- Evidence that will verify it: our own adapter test with a mismatching
  `versionKey` (expects `invalid_response`); the contract fixtures still pass.

## Decision 5

deps.dev partial endpoint failure (OP-05)

- Context: the adapter must make two overlapping calls but report the deps.dev
  source as one result. With `asyncio.TaskGroup`, errors arrive wrapped in an
  `ExceptionGroup`.
- Options considered: (a) wait for both calls and report all their errors;
  (b) cancel the sibling call on the first failure and report one error.
- Decision: (b). Run both calls in a `TaskGroup`. On failure, the adapter
  re-raises the first `SourceRequestError` from the group, so it never raises
  an `ExceptionGroup`. Other exceptions propagate to the scanner (Decision 3).
- Consequences and risk: if both calls fail, only one cause is visible. That is
  acceptable, because the source fails either way.
- Specification or acceptance criteria affected: SPEC 4.3, SPEC 5, SPEC 7;
  REQ-DEPS-02/06.
- Evidence that will verify it: `test_deps_dev_requests_start_concurrently`;
  our own adapter test where one endpoint returns 503 (expects exactly one
  `deps.dev` failure).

## Decision 6

Cache, single-flight, and cache-status semantics (OP-06)

- Context: SPEC 6 requires `hit`, `miss` and `coalesced`, and AC-05 requires
  exactly one load for simultaneous misses.
- Options considered: check the cache only before joining the flight, or also
  inside the flight.
- Decision: `assess()` checks the cache first; a cache hit reports `hit`.
  Otherwise it joins `SingleFlight.run(coordinate.cache_key, load)`. The caller
  that started the flight reports `miss`; callers that joined it
  (`shared=True`) report `coalesced`, even when the shared result is partial.
  Only the load function writes to the cache, and only complete results.
- Consequences and risk: if a load finishes between a caller's cache miss and
  its joining the flight, that caller may start one extra load. That is safe,
  because results are idempotent, and the cache keeps the latest complete
  value.
- Specification or acceptance criteria affected: SPEC 5, SPEC 6, AC-05, AC-06;
  REQ-CON-06/07, REQ-CACHE-08/09.
- Evidence that will verify it:
  `test_complete_result_is_cached_and_identical_misses_coalesce`,
  `test_partial_result_is_attributed_and_not_cached`; two identical API calls
  against the fixtures, compared through `/_admin/calls`.

## Decision 7

Failure order within a package (OP-07)

- Context: SPEC 8 requires stable output, but sources finish in any order.
- Options considered: completion order, or a fixed source order.
- Decision: fixed order PyPI → OSV → deps.dev.
- Consequences and risk: none. The output stays deterministic.
- Specification or acceptance criteria affected: SPEC 8; REQ-ASM-04.
- Evidence that will verify it: a scanner test with two failing sources that
  complete in reverse order.

## Decision 8

Percent-encoding of path segments (OP-08)

- Context: the adapters build URLs from the name and version. Normalized names
  are URL-safe, but local versions may contain `+`.
- Decision: percent-encode the name and version path segments with
  `urllib.parse.quote(..., safe="")`. The OSV request carries them in its JSON
  body and needs no encoding.
- Consequences and risk: none for the fixtures, whose names and versions
  contain no reserved characters.
- Specification or acceptance criteria affected: SPEC 4.1, SPEC 4.3; REQ-SRC-01.
- Evidence that will verify it: the contract source tests still pass.

## Decision 9

Agent-tool CLI connection pool (OP-09)

- Context: `tool_cli.py` creates an `httpx.AsyncClient` without the
  `MAX_HTTP_CONNECTIONS` limits (it uses httpx's default of 100). The API path
  in `bootstrap.py` does apply the configured limits.
- Decision: no change to the supplied code. The pool stays bounded, but not by
  our setting. We record this as a known limitation.
- Consequences and risk: the CLI may open more connections than configured.
  This is relevant only for the agent-tool path.
- Specification or acceptance criteria affected: SPEC 5; REQ-CON-04.
- Evidence that will verify it: listed as an unresolved risk in the
  `EVIDENCE.md` acceptance decision.

## Decision 10

Package limit scope (OP-10)

- Context: SPEC 5 bounds concurrent packages but doesn't say whether
  cache hits count against the limit.
- Decision: the semaphore wraps the whole `assess()` call per package,
  including cache lookups.
- Consequences and risk: cached packages briefly occupy a slot, which costs
  only throughput. The design is simpler, and the limit holds for the source
  work.
- Specification or acceptance criteria affected: SPEC 5, AC-04; REQ-CON-02.
- Evidence that will verify it: `test_package_limit_and_order_are_preserved`.

## Decision 11

Scope of the package concurrency limit

- Context: SPEC 5 requires a configurable package limit; SPEC 1 asks to bound
  concurrency and memory. The bootstrap shares one `DependencyScanner` per API
  process across all requests.
- Options considered: (a) a new semaphore per `scan()` call, which bounds one
  request only; (b) one semaphore per scanner instance, which bounds the whole
  process.
- Decision: (b). `DependencyScanner.__init__` creates one
  `asyncio.Semaphore(max_concurrent_packages)`. Every `scan()` acquires a slot
  around each package's `assess()`. Coalesced waiters hold a slot while
  waiting, but they cannot deadlock, because the shared flight task itself
  needs no slot.
- Consequences and risk: concurrent requests share the limit, so one large
  request can delay a small one. That is a fairness concern, not a correctness
  one, and acceptable for the lab.
- Specification or acceptance criteria affected: SPEC 1, SPEC 5, AC-04;
  REQ-CON-02.
- Evidence that will verify it: `test_package_limit_and_order_are_preserved`;
  Package C's own test, in which two concurrent `scan()` calls on one scanner
  never exceed the limit together.
