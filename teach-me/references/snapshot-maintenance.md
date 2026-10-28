# Recoverable snapshot retirement

Use this optional local helper only when an initialized [snapshot store](journey-versions.md)
needs explicit retirement of named revisions. It never chooses by date, edits a live
journey, activates an archive, or changes `HEAD.json`. HEAD's current and previous
revisions cannot be selected. Plan and apply both validate every ZIP and refuse
unknown entries, orphan store stages, symlink paths, malformed stores and busy locks.

```sh
python3 /path/to/teach-me/scripts/snapshot_maintenance.py plan --store /selected/store --revisions FIRST_SHA SECOND_SHA --output /selected/new-plan.json
python3 /path/to/teach-me/scripts/snapshot_maintenance.py apply --store /selected/store --plan /selected/new-plan.json --archive-root /selected/archive-root --expected-plan-sha256 PLAN_SHA --approve
```

Review the complete plan and selected revisions before applying. `--revisions` is a
nonempty list of unique, known lowercase SHA256 values; selection is sorted. Plan
output is create-new, outside the store, with an existing parent. `--approve` and the
reviewed plan's hash are required for apply. The existing archive root must be outside
the store, and cannot be its ancestor either. No existing archive directory is reused.
Successful commands return JSON; errors go to stderr with exit code 2. Python 3.9+
standard library is sufficient; no service or API call is involved.

The plan has exactly `version` (integer 1), `journey_id`, `store_sha256`, `head`,
`protected`, `revisions` and `plan_sha256`. `head` is the complete validated HEAD
object. `protected` is the sorted list of its current and non-null previous revision.
`store_sha256` is SHA256 of the canonical JSON filename-to-digest map containing
`"HEAD.json": SHA256(exact HEAD bytes)` and every `"REVISION.zip": SHA256(exact ZIP
bytes)`. The cooperative store lock is excluded; no other store entries are allowed
except recognized staging, which maintenance refuses. Canonical JSON uses sorted
keys, compact separators, UTF-8 without ASCII escaping, no non-finite values, and
one final newline. `plan_sha256` hashes the canonical plan object with only its own
`plan_sha256` field omitted. Duplicate JSON members and non-finite constants fail.
Formatting changes in the input plan are allowed; changed contents require the
matching new digest and must still exactly match the current computed plan.

Apply holds the existing `.teach-me-store.lock`, then the archive root's
`.teach-me-snapshot-maintenance.lock`. Locks use exclusive creation and are never
stolen or expired. It checks the entire current store against the plan while locked.
Selected ZIPs total at most 64 MiB. It copies original bytes into a new
`.teach-me-retirement-stage-*` directory, verifies every byte digest and complete
transfer archive, and writes `archive-manifest.json` with exactly:

```json
{"version":1,"plan":{"...":"complete reviewed plan"},"files":{"REVISION.zip":{"sha256":"REVISION","size":1234}}}
```

After rechecking the store, it exclusively creates `archive-root/PLAN_SHA/` and
publishes files create-new from the verified staging copies, with the manifest last.
It revalidates the complete published directory before removing any source ZIP.
This is a completion-marker publication, not an atomic directory rename. A
preexisting destination, including an empty foreign directory, is preserved. A
failure publishing files can leave an incomplete destination and stage, with all
source ZIPs intact. Later failures can leave some selected source ZIPs removed,
but always retain the complete verified backup. HEAD's raw bytes and its previous
revision remain preserved by this operation. Successful completion removes its
staging directory and retains the archive permanently.

After any failure, inspect the actual store, archive destination and stages.
Preserve them while reconciling the failure; do not replay an old plan automatically
or remove a lock without verifying its owner and uncertain operation. Once manually
reconciled, create and review a fresh plan for the actual remaining revisions. Apply
refuses orphan retirement stages in the archive root and never overwrites or deletes
a backup on failure. No automatic cleanup, retention policy or retry is provided.

To restore, first verify the ZIP's SHA256 and size against the complete manifest and
confirm the selected plan/revision. Then use `transfer.py unpack --archive
/selected/archive-root/PLAN_SHA/REVISION.zip --root /fresh/workspace --id JOURNEY_ID`.
The workspace must exist and the receiving journey must be new. A successful unpack
validates the transfer archive. This archive directory is a collection of retired
ZIPs, not a full snapshot store: it has no `HEAD.json` and does not carry execution
permission, ownership, active processes or an automatic resume instruction.

These are bounded cooperative local-filesystem safeguards. Uncooperative editors,
hostile path replacement and arbitrary interruption or power loss are outside the
guarantee. The helper does not provide authenticated history or prove learning,
semantic correctness or mastery.
