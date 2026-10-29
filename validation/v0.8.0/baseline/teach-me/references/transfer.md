# Manual journey transfer and local writer locks

Use Python 3.9+ and the standard library. Review the learner's chosen destination
and keep the whole installed skill folder together; transfer.py imports the
bundled validation, graph, review and storage modules. No account, API key, service, upload,
or third-party package is needed.

```sh
python3 /path/to/teach-me/scripts/transfer.py pack --journey /approved/workspace/learning/algebra --output /approved/exports/algebra.zip
python3 /path/to/teach-me/scripts/transfer.py unpack --archive /approved/exports/algebra.zip --root /approved/other-workspace --id algebra
```

The output parent and destination workspace must already exist. Substitute real
approved paths; these examples do not claim a transfer ran. A successful command
prints JSON; rejected input or an I/O failure prints an error and exits 2.

## Archive contract

Pack reads only these leaf files under the selected journey:

- Required: `plan.md`, `progress.json`, `sources.md`.
- Optional if present: `knowledge.md`, `practice.md`, `harness-project.md`, `learning-pilot.md`.
- Optional typed assets: `knowledge-graph.json`, `knowledge-proposal.json`,
  `knowledge-source.txt`, `journey-review.json`.

The current complete filename contract is `journey_assets.ALLOWED` (11 names).
The older Python constants `transfer.ALLOWED` and `transfer.OPTIONAL` retain
their seven-file/Markdown-only meanings for callers of earlier releases; they
do not enumerate the current pack operation. Use `journey_assets.ALLOWED` when
writing a new caller that must enumerate typed assets.

It ignores other files: backup progress, locks, credentials, raw imported exports,
media, project source, logs and arbitrary attachments are not transferred. The
allowlist is not a secret scanner; selected plans and records may themselves hold
private learner material. Review them and use an authorized private transport.
The helper does not upload or encrypt anything.

The ZIP contains the selected files and `manifest.json`. The manifest has exactly
`version` and `files`, an object keyed by each transferred filename. Pack writes
integer version 1 for a legacy-only journey and integer version 2 when any typed
asset is present. This version reads both; version 1 cannot contain typed files.
Older Teach-me releases refuse version 2, so update the receiving skill first.
Each file value
has exactly `sha256` and `size` (a nonnegative integer number of bytes). The
progress JSON must validate against the existing schema v1 and its `journey_id`
must equal the source folder or requested import `--id`. Transfer does not rename
journeys or silently migrate a newer schema.

Typed validation is deliberately limited. `knowledge-graph.json` must be a
graph-only `teach-me-learning-v1` document accepted by the bundled workbench;
unresolved endpoints remain visible draft warnings. `knowledge-proposal.json`
requires the selected UTF-8 `knowledge-source.txt`, an exact raw-byte source
SHA256 and matching Unicode quote spans. A proposal may contain unresolved draft
references; transfer never applies it. Graph provenance paths and URLs remain
inert data and are not followed. A graph need not share the proposal's source.
These checks establish shape and byte binding, not whether a claim is true.

`journey-review.json` must satisfy the [review receipt contract](coherence-review.md)
and have the same journey ID as progress. A valid stale receipt or a receipt with
`needs_changes` decisions is preserved as historical data; pack/unpack report
warnings instead of blocking its backup. Run the review tool's `verify` command
before relying on its recorded judgment. Edits, restores and merges can make a
receipt stale. The previous receipt backup is not in the transfer allowlist.

Limits: 2 MiB per journey file, 16 MiB total uncompressed journey bytes, 64 KiB
manifest and 17 MiB compressed input. Only stored/deflated ZIP members are
accepted. Duplicate names, unknown files, directories, nested/absolute/traversal
paths, backslashes, encrypted entries, symlink/device metadata, invalid manifests,
hash/size mismatches, unsupported versions and malformed progress are refused.
No archive paths or stored commands are executed or followed.

## Preservation and publication

Pack acquires the same `.teach-me.lock` as updated progress saves, validates
progress and typed assets, and reads the selected files twice to detect ordinary intervening
changes. It rejects symlinks in selected paths and their ancestors. The source
files remain unchanged; the temporary owned lock is released. Output must be
outside the source journey and must not exist. A temporary archive is published
with atomic create-if-absent hard-link semantics on the local filesystem. A
filesystem without that operation reports failure rather than replacing an
existing output.

Unpack first validates the entire bounded archive in memory, before creating a
journey. It writes verified bytes to a staging folder beside the intended
`ROOT/learning/ID`, then publishes the directory under the same per-destination
lock used by updated `journey.py init`. A pre-existing destination is refused,
including an empty one. Failed validation leaves no partial destination; failed
staging is cleaned up. Cooperative concurrent init/import attempts cannot both
publish one destination. The original archive remains unchanged.

Locks use exclusive file creation, random ownership bytes and file identity. They
have no expiry, auto-recovery or lock-stealing command. If a process is interrupted
and leaves a lock, preserve it, inspect the original process and current files,
and reconcile uncertain work before a human removes the verified abandoned lock.
Do not infer safety from elapsed time or a recycled PID. Progress replacement
failure leaves the original progress valid and its byte-preserving backup when
created; the separate plan and Markdown records are not part of that transaction.

These are cooperative safeguards on a local filesystem, not protection against a
hostile process racing filesystem replacements. Old helper versions and manual
editors do not participate. There is no distributed ownership, continuous sync,
authenticated archive signature or universal power-loss guarantee. The separate
[journey versions helper](journey-versions.md) provides explicit three-way
file-level merge; it reuses this typed validation, but cannot judge whether a
byte-clean merge is semantically consistent.
Hash verification detects accidental damage or mismatches; an attacker able to
replace both content and manifest can produce matching hashes.

## Resume after transfer

1. Make the approved archive available on the receiving machine through your
   chosen authorized channel; provision its Codex/other tool access separately.
2. Import into a fresh approved workspace. Preserve an existing journey and
   compare it separately; never use import to overwrite a conflict.
3. Ask the tutor to read the current plan, sources, progress and relevant optional
   records. Reconcile newer goals and evidence, and use a fresh retention check.

An import is data transfer. It neither grants permissions nor starts a lesson,
background job, account switch or external command. See [state and evidence
rules](state.md) for the unchanged progress schema and recovery procedure.
