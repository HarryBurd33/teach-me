# Review consistency across journey files

Use this after a merge, restore or substantial edit when a journey's files may
disagree. A file-level merge can be clean while the plan asks for one task and
the saved next action names another. The review helper records explicit judgments
about the current content and detects when those judgments become stale. It does
not automatically interpret meaning, certify truth or mastery, authenticate a
human reviewer, or authorize execution of another task.

Use Python 3.9+ and paths approved for this journey. Commands below are run from
the installed skill folder; replace the example paths with your selected journey
and an existing directory for review files.

## Prepare and inspect

```sh
python3 scripts/coherence_review.py prepare --journey /workspace/learning/logic --output /workspace/logic-review-packet.json
```

The packet has exactly `version`, `journey_id`, `files`, `checks`, `summary` and
`packet_sha256`. `files` binds the SHA256 and byte size of every present content
file in the transfer allowlist, including graph, proposal and source files. The
receipt itself is excluded from its own fingerprint. The summary quotes the
current goal, stage and next action, counts assessments and evidence, and reports
typed files and graph warnings. It is navigation help, not a substitute for reading
the files.

Inspect the actual plan, progress, source notes, evidence and relevant knowledge
files. Check all four questions in `checks`:

- `goal-stage-next-action`: goal, constraints, plan, stage and next action agree.
- `evidence-scope`: claimed assessments fit recorded attempts, evidence and help.
- `sources-and-claims`: claims fit sources and provenance; uncertainty is visible.
- `merge-consistency`: combined files agree after any merge, restore or edit.

Missing evidence, unresolved contradictions or uncertainty that prevents review
requires `needs_changes` with a concrete rationale. A structurally valid proposal
may remain a draft; transport never applies it or certifies its reasoning. Do not
mark all questions consistent merely because the utility accepted the files.

## Record judgments

Copy [the decisions template](../templates/coherence-decisions.json) to a new file.
Set `packet_sha256` to the packet's value. Keep `version` as integer `1`; set
`reviewer_role` to `tutor`, `learner` or `other`. This is a claimed role, not verified
identity. Supply the exact four unique decision records with `check_id`, `result`
and a nonempty `rationale`. Each `result` is `consistent` or `needs_changes`.

```sh
python3 scripts/coherence_review.py record --journey /workspace/learning/logic --packet /workspace/logic-review-packet.json --decisions /workspace/logic-review-decisions.json --output /workspace/learning/logic/journey-review.json
python3 scripts/coherence_review.py verify --journey /workspace/learning/logic --receipt /workspace/learning/logic/journey-review.json
```

`record` rejects a stale or altered packet and decisions for a different packet.
It writes a new receipt even when a decision is `needs_changes`, so the unresolved
review is preserved. A receipt has exactly `version`, `journey_id`, `files`,
`packet_sha256`, `reviewer_role`, `decisions`, `recorded_at`, `resume_ready` and
`semantic_correctness_verified`. `resume_ready` means only that all four recorded
consistency decisions are `consistent`. `semantic_correctness_verified` is always
false. Neither field proves learning readiness, grants permission or overrides
checkpoint/usage guards.

`verify` exits `0` for a current receipt with four consistent judgments, `1` for a
current receipt containing `needs_changes`, and `2` for stale or invalid data. Any
edited, added or removed content file invalidates freshness. Inspect and correct
the actual content before preparing a new packet; the helper cannot repair a
semantic contradiction on its own.

## Replace a canonical receipt safely

Outputs are create-new by default, including packets and receipts. To replace
only the canonical `journey-review.json`, provide the SHA256 of its exact current
bytes after reviewing a fresh packet:

```sh
python3 scripts/coherence_review.py record --journey /workspace/learning/logic --packet /workspace/fresh-packet.json --decisions /workspace/fresh-decisions.json --output /workspace/learning/logic/journey-review.json --expected-output-sha256 CURRENT_RECEIPT_SHA256
```

The old receipt must have a valid schema for the same journey. Its exact bytes
are preserved as `journey-review.previous.json`; an existing previous receipt
must also be valid for that journey. The last previous receipt can be replaced
on a later update. Use immutable journey snapshots for a longer history.
Replacing other files with this flag is refused. Source content is never edited.

## Limits and transport

The helper reads only ten explicit content files: the legacy seven and
`knowledge-graph.json`, `knowledge-proposal.json`, `knowledge-source.txt`. It
never follows graph provenance paths or arbitrary attachments. Each input/output
is limited to 2 MiB and total journey content to 16 MiB; strict JSON rejects
duplicate keys, nonfinite values and invalid receipts. Symlink paths and
nonregular files are refused. Writers cooperate through the journey lock; an
uncooperative or hostile filesystem can still race outside that contract.

Publication stages complete bytes before an atomic new-file link or replacement.
A forced termination may leave an unused stage file or a writer lock requiring
owner reconciliation. This is not a universal power-loss durability guarantee.

[Transfer](transfer.md), snapshots and merges preserve a schema-valid receipt
as historical data even if stale. Restoring or transporting it never silently
marks it current. Run `verify` against the selected restored/merged journey and
perform a new review if needed. The previous receipt backup is not transferred.
