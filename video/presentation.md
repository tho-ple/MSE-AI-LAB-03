# Concurrent Dependency Intelligence — Lab 03

<!-- Published video (4:23): https://youtu.be/v5zIaBPWbWw -->

> Group video · documentation walkthrough · narration by a synthetic voice (Kokoro TTS)

| Role | Person | Package |
| --- | --- | --- |
| Worker | Johann | **A**: PyPI & OSV adapters |
| Worker | Michael | **B**: deps.dev adapter |
| Worker + Merger | Thomas | **C**: cache & scanner · integration |

---

## Scene 1 — The mission

```mermaid
flowchart LR
    IN["exact dependencies<br/>API or requirements.lock"] --> SCN["DependencyScanner"]
    SCN --> P["PyPI<br/>latest version"]
    SCN --> O["OSV<br/>vulnerabilities"]
    SCN --> D["deps.dev<br/>licenses, graph"]
    P & O & D --> R["one report<br/>complete · partial · failed"]
```

- concurrent · bounded · cached only when complete · useful when a source fails

---

## Scene 2 — Spec-driven: the `spec/` folder

```mermaid
flowchart LR
    SPEC["SPEC.md<br/>contract · never edited"] --> REQ
    subgraph S["spec/"]
        REQ["requirements.md<br/>~60 numbered requirements<br/>each with its origin"]
        DES["design.md<br/>architecture · frozen interfaces<br/>cut · merge order"]
        TA["task-A.md"]
        TB["task-B.md"]
        TC["task-C.md"]
        MER["merge.md<br/>one section per package<br/>+ integration log"]
    end
    REQ --> DEC["DECISIONS.md<br/>12 decisions"]
    REQ --> DES
    DEC --> DES
    DES --> TA & TB & TC
    TA & TB & TC --> MER
    MER --> EV["EVIDENCE.md<br/>trace AC-01…AC-10"]
```

**Rule:** an open question becomes a recorded decision **before** code depends on it.

---

## Scene 3 — One package = one task file

| Section of `task-B.md` | What it fixes |
| --- | --- |
| header | goal · owner · branch · depends on: nothing · merge order |
| §1 Scope | files you own · read-only references · **must not touch** |
| §2 Requirements | REQ-DEPS-01…07 · Decisions 4, 5, 8 |
| §3 Acceptance | done checklist |
| §4 Tests | 11 test cases to write (B1–B11) |
| §5 Focused check | exact `uv run …` commands |
| §7 Prompt | ready-made prompt for the coding assistant |

Same structure for `task-A.md` and `task-C.md` · each worker writes **only** their
own section of `merge.md`: commits · check output · proposed decisions · what to watch

---

## Scene 4 — One requirement, end to end

```mermaid
flowchart LR
    S["SPEC 4.3<br/>silent on identity"] --> OP["OP-04<br/>open point"]
    OP --> D["Decision 4<br/>strict"]
    D --> R["REQ-DEPS-07<br/>versionKey must match"]
    R --> T["task-B.md<br/>§2 + §3"]
    T --> C["deps_dev.py<br/>_matches_coordinate"]
    C --> X["3 tests<br/>wrong package · wrong version<br/>1.0 = 1.0.0"]
    X --> M["merge.md<br/>Package B"]
    M --> E["EVIDENCE.md<br/>AC-02"]
```

Every line of code points back to a requirement, and every requirement to its source.

---

## Scene 5 — The cut: independence over equal size

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

## Scene 6 — AC-03: source concurrency

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

## Scene 7 — Who owns concurrency and the cache

| Concern | Single owner |
| --- | --- |
| package limit | one semaphore per scanner (process-wide) |
| identical misses | SingleFlight: one load per key → `miss` / `coalesced` |
| 3 sources of a package | TaskGroup inside that load |
| cache writes | only the load, **only complete results** |
| cancellation | TaskGroups cancel *and await*; last waiter cancels the load |

---

## Scene 8 — Cache reuse and a partial failure

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

## Scene 9 — Quality gate and one diff

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

## Scene 10 — Acceptance decision

### ✔ Accept with stated limitation

- AC-01 … AC-10: each has a deterministic test, plus runtime evidence
- 422 before any upstream call · 503 when all fail · 504 at the deadline
- agent tool rejects `../`, absolute paths, other filenames

**Remaining production risk:** only deterministic fixtures were tested. Real
services have rate limits and may spell versions differently than our strict
identity check expects.
