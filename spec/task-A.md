# Task A — PyPI & OSV source adapters

| Field       | Value                                                                                    |
| ----------- | ---------------------------------------------------------------------------------------- |
| Goal        | Translate PyPI and OSV responses into validated domain records, with attributed failures |
| Owner       | Johann Hoffmann                                                                          |
| Branch      | `task-a` (from the `main` commit that adds this file)                                    |
| Depends on  | nothing; parallel with B and C                                                           |
| Merge order | 1 of 3 (see `design.md` §5.2)                                                            |
| Size        | small                                                                                    |

## 1. Scope

### Files you own (may create and modify)

- `src/dependency_intelligence/sources/pypi.py`
- `src/dependency_intelligence/sources/osv.py`
- `tests/test_task_a_pypi_osv.py` (new)
- `spec/merge.md`: **only** the `## Package A` section

### Read-only references

`domain.py`, `errors.py`, `http.py`, `upstream_models.py` (`PyPIResponse`,
`OSVResponse`, `parse_response`), `advisories.py` (`merge_advisories`),
`ports.py`, `fake_upstreams.py`, `tests/test_contract.py`.

### Must not touch

Everything else, in particular `sources/deps_dev.py` (Task B), `cache.py` and
`service.py` (Task C), `sources/__init__.py`, `pyproject.toml`, `tests/fakes.py`,
and the protected files (`SPEC.md`, `tests/test_contract.py`,
`checks/readiness.py`). If you think one needs to change, write it into your
`merge.md` section as a proposal instead.

## 2. Requirements and decisions

| Ref | Summary |
| --- | --- |
| REQ-SRC-01…04 | I/O only via the injected `JsonHttpClient` and `base_url`; validate with `parse_response`; return domain records or raise `SourceRequestError`; keep the public signatures |
| REQ-PYPI-01 | `GET {base}/pypi/{name}/json` |
| REQ-PYPI-02 | `PackageMetadata(info.version, info.requires_python)`; absent `requires_python` → `None` |
| REQ-PYPI-03 | malformed or unparseable version → `invalid_response` |
| REQ-OSV-01 | `POST {base}/v1/query` with `{"package": {"name", "ecosystem": "PyPI"}, "version"}` |
| REQ-OSV-02 | omitted `vulns` → `()` (successful empty answer) |
| REQ-OSV-03 | merge transitive aliases with `merge_advisories`; keep all aliases and an available summary |
| REQ-OSV-04 | `vulns` of the wrong type → `invalid_response` |
| Decision 8 | percent-encode the name path segment (`quote(name, safe="")`) |

Design reference: `design.md` §3.1 and §3.2.

## 3. Acceptance criteria (definition of done)

- [ ] `PyPIClient.fetch_metadata` and `OSVClient.fetch_vulnerabilities` are implemented; neither raises `NotImplementedError`.
- [ ] Constructor signatures, class names and `service_name` are unchanged.
- [ ] Every upstream failure surfaces as `SourceRequestError` attributed to `pypi` or `osv`, never as another exception type or a placeholder value.
- [ ] The contract fixture `{"vulns": [GHSA-1/CVE-1, PYSEC-1/CVE-1,CVE-2, PYSEC-2/CVE-2]}` yields **one** advisory `GHSA-1` with aliases `{CVE-1, CVE-2, PYSEC-1, PYSEC-2}`.
- [ ] Your own tests (below) pass, and so do `ruff check`, `ruff format --check` and strict `mypy` on your files.
- [ ] The `## Package A` section of `spec/merge.md` is written.

## 4. Tests you write — `tests/test_task_a_pypi_osv.py`

Set `pytestmark = pytest.mark.sources` at module level. Use `httpx.MockTransport`
with `JsonHttpClient(client, sleep=no_sleep)`, and no network. Suggested cases:

| # | Case | Expect |
| --- | --- | --- |
| A1 | PyPI happy path: check request method and path, `requires_python` present | `PackageMetadata("2.0", ">=3.10")` |
| A2 | PyPI without `requires_python` | `requires_python is None` |
| A3 | PyPI `info.version = "banana"` | `SourceRequestError`, kind `invalid_response`, service `pypi` |
| A4 | PyPI body without `info` | `invalid_response` |
| A5 | PyPI 404 | kind `not_found`, `retryable False`, `status_code 404`, service `pypi` |
| A6 | OSV request body equals `{"package": {"name": "demo", "ecosystem": "PyPI"}, "version": "1.0"}` | asserted inside the handler |
| A7 | OSV `{}` (no `vulns`) | `()` |
| A8 | OSV the contract alias fixture | one merged advisory (see §3) |
| A9 | OSV `{"vulns": "invalid"}` | `invalid_response`, service `osv` |
| A10 | OSV 503 twice | kind `unavailable`, `retryable True`, service `osv` |

## 5. Focused check

```bash
uv run pytest tests/test_task_a_pypi_osv.py -q
uv run ruff check src/dependency_intelligence/sources/pypi.py src/dependency_intelligence/sources/osv.py tests/test_task_a_pypi_osv.py
uv run ruff format --check src/dependency_intelligence/sources tests/test_task_a_pypi_osv.py
uv run mypy src tests checks
```

Expected limitation: `tests/test_contract.py::test_source_adapters_translate_valid_responses`
stays red on this branch, because it also calls deps.dev (Task B). It turns green
once A and B are merged. That is expected and not a defect of Task A.

## 6. Deliverables

1. Code and tests, in small imperative commits on `task-a`, for example:
   - `Implement PyPI metadata adapter`
   - `Implement OSV vulnerability adapter`
   - `Add PyPI and OSV adapter tests`
2. The `## Package A` section of `spec/merge.md`.

## 7. Prompt for the harness (copy and paste)

> You are implementing **Task A** from `spec/task-A.md`. Read `spec/task-A.md`,
> `spec/design.md` §3.1–3.2, `spec/requirements.md` (REQ-SRC, REQ-PYPI, REQ-OSV),
> `DECISIONS.md` Decision 8 and `AGENTS.md`. Modify **only** the files listed
> under "Files you own". Do not edit tests in `tests/test_contract.py`.
> Implement the PyPI and OSV adapters, write the tests in §4, run the focused
> check in §5, then write the `## Package A` section of
> `spec/merge.md`. Return: a diff summary, the check outputs, and any unresolved
> risk.
