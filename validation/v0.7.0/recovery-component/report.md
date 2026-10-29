# Snapshot recovery constructor report

Implemented `scripts/snapshot_recovery.py` and `references/snapshot-recovery.md`
in the v0.7 candidate only. The CLI offers the exact frozen `plan` and `apply`
arguments. Plans bind the original maintenance plan and canonical raw hash maps
of the current valid store and complete archive. The current HEAD/previous are
protected. Apply locks store then archive parent, rederives the reviewed plan
before removal, rechecks the entire backup and protected bytes before every
removal, and never cleans stages, steals locks, or changes the backup.

Component verification: **17 tests passed**, 2.099 seconds, Python 3.15.0.
The source uses Python 3.9-compatible standard-library syntax and interfaces;
Python 3.9 runtime execution was not available in this component run.
`results.json` contains exact artifact and unchanged-module hashes.

Executed checks include a real old-maintenance second-unlink failure followed
by recovery planning, apply, exact ZIP restore and completed no-op; independent
canonical store/archive/plan hashes; repeated partial failure requiring a new
plan; changed current unselected snapshots; current HEAD/previous protection;
raw HEAD staleness; corruption of every selected archive including already
absent revisions; incomplete and self-consistent foreign-identity archives;
strict manifest metadata/canonical encoding; output no-overwrite/ancestry;
unknown store members/stages/corrupt and foreign revisions; symlinks; preserved
foreign locks; missing approval/wrong SHA; malformed plans; CLI error handling;
and injected changes between removals proving whole-backup/protected-byte checks.
The actual maintenance failure's unrelated archive-parent stage remains present
through successful recovery and no-op.

Pass 1 had 16 successful tests and one test expectation error: existing
`journey_versions.read_store` propagates `zipfile.BadZipFile` for a corrupt ZIP.
The test now accepts that established exception alongside `StorageError`; no
source logic changed after the first run. Pass 2 passed all 17 tests.

Both `snapshot_maintenance.py` and `journey_versions.py` remain byte-identical
to the frozen baseline. Existing 238 regressions were not edited or run by this
worker. Independent frozen fault/static review, parent integration and release
checks remain parent-owned. No canonical/global/checkpoint/source-store writes,
services, paid calls, lease changes or guard changes were performed.
