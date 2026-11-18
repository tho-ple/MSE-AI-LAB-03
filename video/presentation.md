# Concurrent Dependency Intelligence — Lab 03

> Group video · documentation walkthrough · narration by a synthetic voice (Kokoro TTS)

| Role | Person | Package |
| --- | --- | --- |
| Worker | Johann | **A**: PyPI & OSV adapters |
| Worker | Michael | **B**: deps.dev adapter |
| Worker + Merger | Thomas | **C**: cache & scanner · integration |

---

## Scene 1 — Mission and method

```mermaid
flowchart LR
    IN["exact dependencies<br/>API or requirements.lock"] --> SCN["DependencyScanner"]
    SCN --> P["PyPI<br/>latest version"]
    SCN --> O["OSV<br/>vulnerabilities"]
    SCN --> D["deps.dev<br/>licenses, graph"]
    P & O & D --> R["one report<br/>complete · partial · failed"]
```

```mermaid
flowchart LR
    S["SPEC.md"] --> R["requirements.md<br/>~60 traced"] --> DEC["DECISIONS.md<br/>12 decisions"] --> T["3 tickets"] --> M["merge.md"] --> E["EVIDENCE.md"]
```

---

## Scene 2 — The cut: independence over equal size

```mermaid
flowchart LR
    subgraph A["Package A"]
        PYPI["PyPI adapter"]
        OSV["OSV adapter"]
    end
    subgraph B["Package B"]
        DEPS["deps.dev adapter"]
    end
    subgraph C["Package C"]
        SCN["Scanner"]
        CACHE["Cache"]
    end
    PORTS["Ports (frozen interfaces)"]
    A -. implements .-> PORTS
    B -. implements .-> PORTS
    C -- uses only --> PORTS
```

- No package imports another package's code
- Scanner tested only against fake sources
- Same base commit · **zero code conflicts**

---

## Scene 3 — AC-03: source concurrency

> All three sources start before any may finish; the two deps.dev calls overlap.

```mermaid
sequenceDiagram
    participant L as Scanner
    participant P as PyPI
    participant O as OSV
    participant D as deps.dev
    par TaskGroup
        L->>P: metadata
    and
        L->>O: vulnerabilities
    and
        L->>D: metadata + graph (own TaskGroup)
    end
```

| Proof | Result |
| --- | --- |
| Test: `StartGate` opens only when **all** calls started | passes |
| Runtime: 4 calls × 2 s each | **2.10 s** instead of 8 s |

---

## Scene 4 — Who owns concurrency and the cache

| Concern | Single owner |
| --- | --- |
| package limit | one semaphore per scanner (process-wide) |
| identical misses | SingleFlight: one load per key → `miss` / `coalesced` |
| 3 sources of a package | TaskGroup inside that load |
| cache writes | only the load, **only complete results** |
| cancellation | TaskGroups cancel *and await*; last waiter cancels the load |

---

## Scene 5 — Cache reuse and a partial failure

| Same request twice | 1st | 2nd |
| --- | --- | --- |
| cache_status | miss | **hit** |
| time | 0.246 s | **0.022 s** |
| upstream calls | 8 | **+0** |

```mermaid
flowchart LR
    P["PyPI ✔"] --> R
    O["OSV ✘ 503"] --> R
    D["deps.dev ✔"] --> R
    R["HTTP 200 · partial<br/>vulnerabilities: null<br/>1 failure: osv, retryable"]
    R -. "not cached" .-> X["next scan asks OSV again"]
```

`[]` = OSV answered, nothing known · `null` = no trustworthy answer

---

## Scene 6 — Quality gate and one diff

| ruff | format | mypy strict | pytest |
| :---: | :---: | :---: | :---: |
| ✔ | ✔ | ✔ | **59 passed** |

**Decision 12, found in code review**

```diff
+    except asyncio.CancelledError:
+        task = asyncio.current_task()
+        if task is None or task.cancelling():
+            raise                                   # real cancellation → 504
+        return None, _unexpected(service, "CancelledError")  # faulty source → partial
```

---

## Scene 7 — Acceptance decision

### ✔ Accept with stated limitation

- AC-01 … AC-10: each has a deterministic test, plus runtime evidence
- 422 before any upstream call · 503 when all fail · 504 at the deadline
- agent tool rejects `../`, absolute paths, other filenames

**Remaining production risk:** only deterministic fixtures were tested. Real
services have rate limits and may spell versions differently than our strict
identity check expects.
