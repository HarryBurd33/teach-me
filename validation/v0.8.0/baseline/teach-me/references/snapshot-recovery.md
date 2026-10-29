# Finish an interrupted snapshot removal

Use this optional tool only after inspecting an interrupted explicit snapshot
retirement. It requires the **complete** archive published by
`snapshot_maintenance.py`: the directory named by the original maintenance plan
SHA256, containing canonical `archive-manifest.json` and every originally
selected revision ZIP. Keep the archive unchanged.

```sh
python3 scripts/snapshot_recovery.py plan --store /path/to/store \
  --archive /path/to/archives/ORIGINAL_PLAN_SHA256 --output /path/to/new-recovery.json
```

Review the new plan's current `head`, `protected`, `remaining`, `already_absent`,
and `plan_sha256`. `already_absent` means only that an originally selected
revision is currently absent; it does not establish who removed it or why.
The plan binds the original plan digest and exact current store/archive bytes.
Current HEAD and previous revisions are protected, including references changed
since the original retirement. New unselected snapshots are allowed when the
current store remains valid.

```sh
python3 scripts/snapshot_recovery.py apply --store /path/to/store \
  --archive /path/to/archives/ORIGINAL_PLAN_SHA256 --plan /path/to/new-recovery.json \
  --expected-plan-sha256 REVIEWED_RECOVERY_PLAN_SHA256 --approve
```

The output plan must be new, with an existing parent, outside both store and
archive. Apply requires its exact internal digest and explicit approval. Under
the existing store lock followed by the archive parent's maintenance lock, it
recomputes the plan before any removal and rechecks the entire complete backup
and protected bytes before each removal. The archive is always preserved. An
empty `remaining` list is a verified no-op.

After another partial failure, inspect actual files and create a **fresh** plan
at a new path. The prior plan becomes stale after a successful removal; there
is no automatic replay. Restore a selected backup with the existing
`transfer.py unpack --archive BACKUP.zip --root NEW_WORKSPACE --id JOURNEY` tool.

Incomplete, corrupt, noncanonical, foreign-identity, unexpected-member or symlink
archives are refused. Current store stages, unknown files, corrupt revisions or
foreign identities are refused. This tool never repairs an incomplete archive,
rebuilds metadata, cleans stages, steals locks, or infers absence is safe without
a verified complete backup. Unrelated archive-parent stages remain untouched;
reconcile those and abandoned locks separately after checking their owner.
Cooperative local locks do not provide a sandbox against hostile filesystem
writers. Journey formats and progress data are unchanged.
