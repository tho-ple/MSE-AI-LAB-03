# Video narration script — Lab 03

Narration for `video/presentation.md`, written for **Kokoro TTS**.

How to use:

- Generate one audio file per scene: feed **only the text inside each
  ```text block``` ** to Kokoro, never the headings or these notes.
- Scroll to the matching `Scene N` in `presentation.md` while its audio plays
  (Scene 0 is the title block at the top of the page).
- Spelling is phonetic on purpose ("pie pea eye" = PyPI, "O S V" = OSV,
  "deps dot dev" = deps.dev, "my pie" = mypy). Numbers are written as spoken.
- Estimated length: about 11 minutes at roughly 140 words per minute (≈ 1,479 words). Kokoro's `speed` parameter can shorten it.
- The narration states that the voice is synthetic. Keep that sentence, so the
  video stays transparent about how it was made.

---

## Scene 0 — Title and team (≈ 40 s)

```text
Welcome to our group video for lab three, concurrent dependency intelligence.

A quick note first: this narration is generated with a text to speech model, and the video is a walkthrough of our documentation. The work, the decisions, and the evidence are ours.

We are a team of four roles. Johann built package A, the pie pea eye and O S V adapters. Michael built package B, the deps dot dev adapter. Thomas built package C, the cache and the scanner, and also acted as the merger who integrated everything into the main branch.
```

## Scene 1 — The mission (≈ 50 s)

```text
The task. Given exact Python dependencies, for example fast A P I at an exact version, our service asks three independent sources at once.

Pie pea eye tells us the latest version and the required Python version. O S V lists known vulnerabilities. And deps dot dev reports licenses, the publication date, and how many direct dependencies a package has.

The service combines all of this into one stable report. It has to run independent work concurrently, keep resource use bounded, reuse only complete results from a cache, and stay useful when one source is down. The same service powers an H T T P endpoint and a tool for A I agents.
```

## Scene 2 — How we worked (≈ 70 s)

```text
We did not start with code. We started with the specification.

First, we distilled the specification, the working rules, and the tests into one requirements document with about sixty requirements. Every requirement points back to its source, so we could always trace a line of code to a rule.

Where the specification left a question open, we wrote a decision before any code depended on it. We ended with twelve decisions. For example: when all three sources fail, the package has no assessment at all, so the report says failed instead of partial.

From the requirements we wrote a design, and from the design three tickets. Each ticket has one goal, one owner, its own files, a focused test command, and small commits. Each worker documented their result in a shared merge log, in their own section only. The merger then integrated one reviewed branch at a time, and only moved on when the focused checks were green.
```

## Scene 3 — Architecture and the cut (≈ 65 s)

```text
The starter code already used ports and adapters. The transports, the H T T P client, and the response schemas were supplied. Five files were missing: three source adapters, the cache, and the scanner.

The interesting decision was how to cut these into three packages. Our rule was: independence beats equal size.

The obvious cut, all adapters, then the cache, then the scanner, has a hidden link. One scanner test uses the real cache, so the scanner owner would have to wait for the cache owner.

So we chose a different cut. Package A takes pie pea eye and O S V. Package B takes deps dot dev. Package C takes the cache together with the scanner. Now no package imports code from another package. The scanner is built and tested only against fake sources. The result: all three branches started from the same commit, and the code merged without a single conflict.
```

## Scene 4 — Acceptance criterion three: source concurrency (≈ 70 s)

```text
Let us look at one acceptance criterion in detail: acceptance criterion three, source concurrency. All three source calls for one package must start before any of them is allowed to finish, and the two deps dot dev calls must overlap as well.

The scanner starts the three sources inside one task group. Inside the deps dot dev adapter, a second task group starts the metadata call and the dependency graph call together.

How do we prove it? In the tests, a start gate only opens once every expected call has started. If any call ran after another one, the gate would never open and the test would fail.

At runtime, we used the deterministic fixtures, where every single upstream call sleeps for two seconds. One package needs four calls. One after another, that would take eight seconds. We measured two point one seconds. That is only possible if all four calls were in flight at the same time.
```

## Scene 5 — Who owns concurrency and the cache (≈ 65 s)

```text
In the final design, every concurrency concern has exactly one owner.

The package limit is one semaphore per scanner. It is shared by all requests in the process, so many parallel requests cannot flood the upstream services.

Identical requests that arrive at the same time share one load through a single flight. The caller who started the load reports a cache miss. Everyone who joined it reports coalesced.

Inside that load, one task group runs the three sources. Each source result becomes either data or one attributed failure.

And the cache has exactly one writer: the load itself, and only when all three sources succeeded. A partial result is never stored.

Cancellation follows the same structure. Task groups cancel and await their children. When a deadline hits, the scan is cancelled, the waiters leave, and the last waiter cancels the shared load, which cancels the source calls.
```

## Scene 6 — Cache reuse and a partial failure (≈ 90 s)

```text
Now the cache, at runtime. We sent the same request twice.

The first response took a quarter of a second and reported a miss for both packages. The fixture counters showed two calls to each upstream endpoint. The second response took twenty two milliseconds, reported a hit for both packages, and the counters did not change at all. No new upstream call was made.

Next, a partial failure. For the package unavailable O S V demo, the O S V fixture returns error five oh three. The service retried once, as the H T T P policy allows, and then gave up on O S V only.

The response is still H T T P two hundred with status partial. The pie pea eye data and the deps dot dev data are there. The vulnerabilities field is null, and there is exactly one failure, attributed to O S V, marked as retryable. When we sent the same request again, it was a miss again, and O S V was called again. The partial result was not cached.

That null matters. An empty list means O S V answered and knows no advisory. Null means we do not know. Our report never claims that a package is safe just because O S V was unreachable.
```

## Scene 7 — Quality gate and one meaningful diff (≈ 80 s)

```text
The quality gate. Ruff lint and ruff format pass. My pie in strict mode reports no issues in thirty files. And the full test suite has fifty nine passing tests. The untouched starter had ten failing.

One diff we want to show came out of our own code review. The scanner wraps every source call. Originally, any cancellation error simply passed through. But what if a source raises a cancellation error by itself, while nobody cancelled the scan? Then one faulty adapter would abort the entire report.

We recorded decision twelve and changed the wrapper. Now a cancellation only passes through when the running task was really asked to cancel, for example by the deadline. A source that cancels itself becomes one attributed failure, and the rest of the report survives.

The same review produced a second fix: the scanner, not the adapter, now decides which source a failure belongs to.

We also tested our tests. We broke the scanner on purpose in several ways, for example by caching partial results or by leaking error text. Every broken version turned at least one test red.
```

## Scene 8 — Acceptance decision (≈ 80 s)

```text
Our acceptance decision is: accept, with a stated limitation.

Every one of the ten acceptance criteria has a deterministic test, and where it is observable, runtime evidence. Invalid input is rejected with four twenty two before any upstream call. Concurrency and the package limit are visible in the timing. The cache serves hits without new calls. A partial failure keeps the useful data. A complete failure returns five oh three. A deadline returns five oh four after one second. And the agent tool refuses to leave its workspace.

The remaining production risk is this: we only exercised deterministic fixtures, never the real pie pea eye, O S V, or deps dot dev services. Real services have rate limits, and deps dot dev might spell a version differently, which our strict identity check would reject. Before production, the next step would be a small, rate limited test against the real services.

We also documented three smaller limits in our evidence file: the single flight cancels a load but does not wait for it, the shared package limit can delay small requests, and the command line tool does not apply our connection limit.
```

## Scene 9 — What we take away (≈ 30 s)

```text
Three things we take away from this lab.

First, the specification trace made review possible. Every line of code points to a requirement or a decision.

Second, independence beat equal size. Our packages were uneven, but nobody waited for anybody.

And third, passing tests were not enough. Overlap, limits, and cache reuse only became convincing with real timing and real call counters.

Thank you for watching.
```
