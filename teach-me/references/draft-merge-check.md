# Check a merge before writing a draft

Use this optional local preflight after [planning and choosing conflict sides](draft-merge.md), before apply. It accepts the same exact base, left/right drafts, plan, decisions and reviewed hashes. Python 3.9+ standard library is sufficient.

```sh
python3 scripts/draft_merge_check.py check --base graph.json --left left-draft.json --right right-draft.json --plan merge-plan.json --expected-plan-sha256 PLAN_SHA256_FROM_REVIEW --decisions merge-decisions.json --expected-decisions-sha256 DECISIONS_SHA256_FROM_REVIEW
```

The command has no output-path or approval option. It reads files and prints a JSON report to stdout; it does not save a report, draft, graph or temporary output. Shell redirection, if chosen, is a separate filesystem operation by the caller. Run with Python's `-B` flag if you also want to suppress interpreter bytecode cache creation.

On success, exit status is 0. Report fields are `version` (1), `format` (`teach-me-draft-merge-check-v1`), `operation` (`check`), `applicable` (true), `plan_sha256`, `decisions_sha256`, `draft_sha256`, `draft_bytes`, `nodes`, `chains`, `conflicts_resolved`, `changes`, `semantic_correctness_verified` (false) and `notice`. Changes contain sorted ID arrays `delete_nodes`, `delete_chains`, `upsert_nodes`, `upsert_chains`. The report omits full records and source paths.

`draft_sha256` is the hash of the exact prospective ordinary v1 draft bytes serialized by the existing merge publisher, not a hash of the report. With unchanged inputs, a successful normal merge apply produces those bytes. Review changed IDs alongside the plan's complete records and decisions; the summary does not replace that review.

Malformed input, stale hashes, missing/extra/duplicate choices, incompatible final records, duplicate logical arguments, missing endpoints or exceeded limits return status 2 with a diagnostic on stderr and no successful report. Correct the source drafts or choices, regenerate the plan when sources changed and review new hashes. No automatic semantic repair or deduplication occurs.

All five sources are re-read before success is reported. A later change still invalidates the earlier check: normal apply independently rereads and validates them, requires `--approve`, and creates a new output. Preflight does not check destination availability, reserve storage, grant approval, authenticate reviewers or guarantee a future write. A hostile writer can race after the last observation; no locking or universal durability claim is made.

Existing bounds remain: 2 MiB base/branch/decision/draft bytes, 8 MiB plan and 256 claims/arguments. Same complete exact base and whole-record choices only. Retained aliases, timestamps, provenance and jointly required premises follow the existing validators. Structural acceptance does not establish semantic truth, source support or learning gains.
