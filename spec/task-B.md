# Task B — deps.dev supply-chain adapter

| Field       | Value                                                                                     |
| ----------- | ----------------------------------------------------------------------------------------- |
| Goal        | Two **overlapping** deps.dev calls → validated, identity-checked `SupplyChainInformation` |
| Owner       | Michael Auß                                                                              |
| Branch      | `task-b` (from the `main` commit that adds this file)                                     |
| Depends on  | nothing; parallel with A and C                                                            |
| Merge order | 2 of 3 (see `design.md` §5.2)                                                             |
| Size        | small, but concurrency-sensitive                                                          |

## 1. Scope

### Files you own (may create and modify)

- `src/dependency_intelligence/sources/deps_dev.py`
- `tests/test_task_b_deps_dev.py` (new)
- `spec/merge.md`: **only** the `## Package B` section

### Read-only references

`domain.py`, `errors.py`, `http.py`, `upstream_models.py` (`DepsMetadata`,
`DepsGraph`, `VersionKey`, `parse_response`), `ports.py`, `fake_upstreams.py`,
`tests/test_contract.py` (`GateHttp`, `test_deps_dev_requests_start_concurrently`),
`tests/fakes.py` (`StartGate`).

### Must not touch

Everything else, in particular `sources/pypi.py` and `sources/osv.py` (Task A),
`cache.py` and `service.py` (Task C), `upstream_models.py`, `sources/__init__.py`,
`pyproject.toml`, and the protected files. If you think one needs to change,
write it into your `merge.md` section as a proposal instead.

## 2. Requirements and decisions

| Ref | Summary |
| --- | --- |
| REQ-SRC-01…04 | I/O only via the injected `JsonHttpClient` and `base_url`; validate with `parse_response`; return a domain record or raise `SourceRequestError`; keep the public signature |
| REQ-DEPS-01 | `GET {base}/v3/systems/PYPI/packages/{name}/versions/{version}` and `…/versions/{version}:dependencies` |
| REQ-DEPS-02 | both requests **start before either finishes** |
| REQ-DEPS-03 | `licenses` → tuple, `published_at` (may be `None`), `direct_dependency_count` = number of `DIRECT` nodes |
| REQ-DEPS-04 | exactly one `SELF` root, no graph or node errors → otherwise `invalid_response` (the model enforces it) |
| REQ-DEPS-05 | missing repeated fields → empty; missing required structure → `invalid_response` |
| REQ-DEPS-06 | one failing call → one `deps.dev` failure; sibling call cancelled |
| REQ-DEPS-07 | `versionKey` in metadata **and** in the `SELF` node must match the coordinate → otherwise `invalid_response` |
| Decision 4 | identity check: normalized name equality + `packaging.version.Version` equality |
| Decision 5 | `TaskGroup`; on `ExceptionGroup` re-raise the first `SourceRequestError`; never let a group escape |
| Decision 8 | percent-encode the name and version path segments |

Design reference: `design.md` §3.3, including the sequence diagram and the
`ExceptionGroup` hint.

## 3. Acceptance criteria (definition of done)

- [ ] `DepsDevClient.fetch_supply_chain` is implemented; the signature and `service_name` are unchanged.
- [ ] `tests/test_contract.py::test_deps_dev_requests_start_concurrently` passes.
- [ ] The adapter never raises `ExceptionGroup`; every failure is a `SourceRequestError` attributed to `deps.dev`.
- [ ] When one endpoint fails, the other in-flight request is cancelled (observable with `StartGate.cancelled`).
- [ ] A `versionKey` mismatch (name or version) → `invalid_response`; `1.0` vs `1.0.0` counts as a **match**.
- [ ] Your own tests (below) pass, and so do `ruff check`, `ruff format --check` and strict `mypy`.
- [ ] The `## Package B` section of `spec/merge.md` is written.

## 4. Tests you write — `tests/test_task_b_deps_dev.py`

Set `pytestmark = pytest.mark.sources` at module level. Use `httpx.MockTransport`,
or a fake object with an async `request_json` (like `GateHttp` in the contract
tests), and no network. Suggested cases:

| # | Case | Expect |
| --- | --- | --- |
| B1 | happy path (contract fixture shape) | `licenses ("MIT",)`, `direct_dependency_count 1`, `published_at` set; both URLs requested |
| B2 | metadata without `licenses` or `publishedAt` | `licenses ()`, `published_at None` |
| B3 | graph without `nodes` / empty `nodes` | `invalid_response` |
| B4 | graph with a second `SELF` node / first node not `SELF` | `invalid_response` |
| B5 | graph `error` non-empty / a node with `errors` | `invalid_response` |
| B6 | metadata `versionKey.name` = another package | `invalid_response` |
| B7 | `SELF` node version `2.0` for coordinate `1.0` | `invalid_response` |
| B8 | `SELF` node version `1.0.0` for coordinate `1.0` | success (Version equality) |
| B9 | metadata 503 twice, graph slow (blocked on a gate) | exactly one `SourceRequestError(deps.dev, unavailable)`; the graph call is cancelled |
| B10 | both endpoints 404 | one `SourceRequestError(deps.dev, not_found)`, not an `ExceptionGroup` |
| B11 | `{"licenses": "invalid"}` (fixture `broken-deps-*`) | `invalid_response` |

## 5. Focused check

```bash
uv run pytest tests/test_task_b_deps_dev.py "tests/test_contract.py::test_deps_dev_requests_start_concurrently" -q
uv run ruff check src/dependency_intelligence/sources/deps_dev.py tests/test_task_b_deps_dev.py
uv run ruff format --check src/dependency_intelligence/sources/deps_dev.py tests/test_task_b_deps_dev.py
uv run mypy src tests checks
```

Expected limitation: `test_source_adapters_translate_valid_responses` stays red
on this branch, because it calls PyPI and OSV first (Task A). It turns green once
A and B are merged.

## 6. Deliverables

1. Code and tests, in small imperative commits on `task-b`, for example:
   - `Implement deps.dev adapter with overlapping requests`
   - `Reject deps.dev responses for a different coordinate`
   - `Add deps.dev adapter tests`
2. The `## Package B` section of `spec/merge.md`.

## 7. Prompt for the harness (copy and paste)

> You are implementing **Task B** from `spec/task-B.md`. Read `spec/task-B.md`,
> `spec/design.md` §3.3, `spec/requirements.md` (REQ-SRC, REQ-DEPS), `DECISIONS.md`
> Decisions 4, 5 and 8, and `AGENTS.md`. Modify **only** the files listed under
> "Files you own". Do not edit `tests/test_contract.py` or `upstream_models.py`.
> Implement the deps.dev adapter with two overlapping requests in an
> `asyncio.TaskGroup`, the identity check, and `ExceptionGroup` unwrapping. Write
> the tests in §4, run the focused check in §5, then write
> the `## Package B` section of `spec/merge.md`. Return: a diff summary, the check
> outputs, and any unresolved risk.
