# Repository working agreement

## Authority

- `SPEC.md` is the behavior contract. Do not edit it during implementation.
- Public tests are evidence, not the complete specification. Do not weaken,
  delete, skip, or rewrite an assertion to obtain a passing run.
- Record a necessary interpretation or deviation in `DECISIONS.md` before code
  depends on it.

## Team workflow

- Begin with a read-only request that splits the specification into independent
  tickets before authorizing edits.
- Give every ticket one goal, one owner, explicit file ownership, a focused test
  command, and a small imperative Git commit.
- Avoid two active tickets editing the same production file. If that is
  unavoidable, make the dependency and merge order explicit.
- Integrate one reviewed commit at a time. Run its focused checks before the
  next merge.

## Engineering rules

- Python 3.12 is required. Keep strict typing and the existing public interfaces.
- Preserve source attribution and the distinction between an empty successful
  result and a failed source.
- Only complete package assessments may enter the cache.
- Keep external I/O in adapters and orchestration in the application service.
- Do not add dependencies unless `DECISIONS.md` explains why the supplied stack
  is insufficient.
- Do not place credentials in files, prompts, commits, screenshots, or videos.
- Use deterministic fake services for acceptance evidence.

## Protected files

Do not modify:

- `SPEC.md`
- `tests/test_contract.py`
- `checks/readiness.py`

Documentation templates may be completed but their required headings must stay.
