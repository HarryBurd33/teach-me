# Consistent snapshots and conflict-aware manual merging

`journey_versions.py` is an optional Python 3.9+ standard-library helper. It reuses
the existing [transfer archive validation](transfer.md), progress schema v1 and
cooperative locks. It does not install a service, upload data, synchronize devices,
resume a learner or execute commands from records.

## Snapshot a complete journey

Create a dedicated, empty approved store directory **outside the journey**. Each
store belongs to one journey ID. Substitute actual approved paths:

```sh
python3 /path/to/teach-me/scripts/journey_versions.py status --store /approved/snapshots
python3 /path/to/teach-me/scripts/journey_versions.py snapshot --journey /approved/workspace/learning/algebra --store /approved/snapshots --expected-head none
python3 /path/to/teach-me/scripts/journey_versions.py snapshot --journey /approved/workspace/learning/algebra --store /approved/snapshots --expected-head HASH-FROM-STATUS
python3 /path/to/teach-me/scripts/journey_versions.py restore --store /approved/snapshots --revision EXPLICIT-REVISION-HASH --root /approved/new-workspace --id algebra
```

`none` is the literal initial expectation, valid only when no HEAD exists. Later
snapshots require the current revision hash. A stale expectation fails rather
than replacing newer state. An unchanged journey produces an idempotent no-op.
The source uses the same local writer lock as updated progress saves and packing;
the store has its own `.teach-me-store.lock`. Status also briefly takes that lock.
Locks have no expiry or automatic theft. Old/manual editors do not cooperate.

Each immutable `<sha256>.zip` contains exactly the transfer allowlist when present:
required `plan.md`, `progress.json`, `sources.md`, and optional `knowledge.md`,
`practice.md`, `harness-project.md`, `learning-pilot.md`. Every archive and progress
record is validated. Optional typed `knowledge-graph.json`, `knowledge-proposal.json`,
`knowledge-source.txt` and `journey-review.json` are also preserved when present.
A proposal requires its matching UTF-8 source and exact quotes; graphs remain
structured assertions, not truth or learner evidence. These archives use transfer
format v2; legacy-only journeys still write v1. New helpers read both, while older
helpers refuse v2. No arbitrary attachment, raw export, source code, credential,
lock or command log enters the snapshot automatically. Media and arbitrary
attachments need separate reviewed handling.
The finite allowlist is not
a secret scanner; review selected prose and use an authorized private transport.

`HEAD.json` has exactly `version: 1`, `journey_id`, `revision` and `previous`.
`previous` is null for the first activation or the prior revision hash. Publication
creates a complete immutable archive, then atomically publishes this one pointer.
Cooperating readers therefore see an old or new complete revision. Snapshots do
**not** make arbitrary edits of the live journey's separate files transactional.

Restore validates an explicitly named revision and imports into a fresh
`ROOT/learning/ID`, using the existing destination lock and staging procedure. It
refuses any existing destination and never changes HEAD. An inactive revision may
be explicitly inspected/restored into a new workspace; no revision is selected by
timestamp, directory order or an invented “latest” rule.

## Interruption, limits and preservation

An activation failure leaves the previous valid HEAD unchanged and can retain a
new inactive archive. A first activation failure can leave an uninitialized store
with a valid inactive archive. Status reports `initialized`, `head`, `journey_id`,
`available_revisions`, `staging_entries` and `automatic_recovery: false`. Revision
lists are digest-sorted, not chronological. Temporary `.teach-me-snapshot-*` or
`.teach-me-head-*` entries can survive hard termination and are reported without
following their contents, automatically activating them, or deleting them.

Unknown store entries, symlinks, malformed/foreign HEAD records and corrupt
revisions fail closed and remain for review. Do not remove a lock merely because
its PID looks old. Reconcile the original process and file effects before a human
handles verified abandoned artifacts. Use [explicit snapshot maintenance](snapshot-maintenance.md) to archive selected old
revisions before removal, preserving HEAD and its previous revision. There is no
automatic pruning, source rollback or universal power-loss guarantee. Store updates are fenced for cooperating
local writers, not hostile filesystem races, distributed writers or old helpers.

Bounds: at most 64 immutable revisions and 192 total store entries; each archive
uses the transfer limits (17 MiB compressed input, 16 MiB uncompressed journey
bytes, 2 MiB per journey file). HEAD, compare reports and resolution records are
small bounded JSON objects (64 KiB for read metadata). Journey IDs must fit a
single local filesystem leaf (at most 255 ASCII characters). Store commands validate
known revision archives, so large stores cost more I/O. Use the maintenance plan/apply workflow to copy and verify explicitly selected
old revisions into a separate archive before retiring them. Do this before
reaching the limit; it does not repair an already invalid oversized store. Never
silently delete history or a revision still referenced by HEAD/previous.

## Three-way comparison

Pack the common base and the two changed journeys separately with `transfer.py`.
All three verified archives must contain the same journey ID. Then:

```sh
python3 /path/to/teach-me/scripts/journey_versions.py compare --base /approved/base.zip --local /approved/local.zip --incoming /approved/incoming.zip --output /approved/comparison.json
python3 /path/to/teach-me/scripts/journey_versions.py merge --base /approved/base.zip --local /approved/local.zip --incoming /approved/incoming.zip --output /approved/merged.zip
```

Comparison returns a stable JSON report containing `version: 1`, `journey_id`,
`source_archives` (base/local/incoming archive SHA256 values), `files`, `conflicts`
and `report_sha256`. Each file entry has base/local/incoming content hashes or null,
`status` and `selected`. The report hash is SHA256 of its canonical JSON excluding
the hash field itself (sorted keys, UTF-8, compact separators and a final newline).
Reports expose hashes and filenames, not archive paths or file contents.

File-level decisions are:

| State | Outcome |
| --- | --- |
| Neither side changed | `unchanged`; keep base |
| Both sides have identical changed bytes, including the same deletion | `identical`; keep their shared result |
| Only local changed | `local-only`; keep local |
| Only incoming changed | `incoming-only`; keep incoming |
| Both changed differently, including delete versus edit | `conflict`; no automatic choice |

`progress.json` is deliberately one whole-file decision. The tool never invents or
semantically combines evidence IDs, assessments, mastery or next actions. Review
the actual learner history before choosing one conflicting progress record.
Even a conflict-free byte/file merge can contain semantic contradictions across
plan, progress, sources or other records. Inspect the combined content before
resuming teaching or changing evidence; this tool does not validate cross-file
meaning or domain truth. Use the [consistency review packet](coherence-review.md)
to record a review of the resulting live files and detect later changes. Valid stale
receipts may be retained in archives as history; they cannot establish current
review status. A file-clean merge still validates typed source/proposal bindings
and refuses mismatched combinations.

## Resolve conflicts explicitly

Unresolved conflicts prevent merged output. Write a separate resolution record
only after inspecting the current comparison and the relevant source bytes:

```json
{
  "version": 1,
  "report_sha256": "COPY-EXACT-HASH-FROM-CURRENT-COMPARISON",
  "choices": {"progress.json": "local", "practice.md": "incoming"}
}
```

`choices` must name every and only the conflicted filename. Values are `base`,
`local` or `incoming`. Supply the resolution with `merge --resolutions PATH`.
Changing any source archive invalidates the saved report hash. Unknown choices,
missing choices, stale hashes, unsupported versions and duplicate JSON members are
refused. A chosen optional deletion removes that file from the new archive; required
files and the final progress schema/ID must remain valid.

Merge publishes a new validated archive, never changes the three inputs or an
existing output, and reports its digest and actual choices. Use ordinary transfer
unpack to inspect it in another new workspace. Choosing a file is an operator
decision, not proof that its claims are true or the learner has mastered them.
There is no line-level conflict marker insertion, silent “last writer wins”,
continuous sync, encryption, authenticated signature or transferred permission.

Commands return JSON on success and exit 2 with an error on rejected input or I/O
failure. Atomic create-if-absent publication uses local hard-link support and fails
closed when unavailable. Keep the whole installed skill folder together because
this script imports its bundled helper modules.
