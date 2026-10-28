# Snapshot maintenance component return

Constructed only the assigned candidate script, reference guide and this component
test/results/report directory. No global skill, canonical repository, versions
module, checkpoint, frozen criteria or actual learner store was edited. Synthetic
fixtures live in temporary directories and are cleaned by the tests.

The helper implements the frozen explicit plan/apply CLI and closed plan schema.
Its store fingerprint hashes a canonical filename-to-SHA256 map for exact HEAD
bytes plus every revision ZIP; the guide documents that algorithm. Plan output is
create-new. Apply locks store then archive root, validates an exact current plan,
refuses protected/duplicate/unknown selections and orphan staging, and caps selected
ZIP bytes at 64 MiB.

All original ZIP bytes are copied and verified in staging. Publication exclusively
reserves the new plan-hash child directory, links staged copies create-new and puts
the manifest last, then validates the entire published backup. No directory rename
can overwrite a racing empty foreign destination. No source unlink occurs before
that complete verified backup. Failure preserves stages and any published backup;
the error directs inspection of the actual archive/store and a fresh plan.

Two bounded component passes ran with no failures: initially 19 tests (1.258s),
then 21 final tests (1.392s), both process exit 0. The second pass also checks final
backup verification failure and malformed ZIP CLI exit 2. Results are recorded in
`results.json` and `results.txt`, including exact source SHA256 values and command.
Module and test source parse with Python 3.9 grammar; execution used the available
`python3`, not a separate verified Python 3.9 runtime. Test default paths point to
the candidate; `TEACH_ME_SKILL` supports a parent port with no implementation edits.

Executed cases cover two explicit retired revisions with exact archive bytes and
unpack, unchanged HEAD/previous bytes, independent fingerprint and plan-hash
calculations, selections, initialized-store requirement, stale raw HEAD and added
snapshot, strict JSON/closed fields/hash/version/path validation, approval and
create-new output, unknown/orphan entries, both locks, symlink paths, archive
ancestry, existing empty and racing foreign destination preservation, copy failure,
copy corruption, failed final-backup verification, partial publication, and second
unlink failure. The latter leaves a complete verified backup; both retired ZIPs
unpack into fresh workspaces after the partial deletion. An archive orphan also
blocks apply without deleting it.

The selected-total refusal branch uses an injected smaller bound; this worker did
not execute an actual 64 MiB payload boundary fixture. This is cooperative local
filesystem safety, with no hostile-filesystem or universal power-loss claim.
Manifest-last directory publication is not an atomic rename. Interrupted
publication may leave an incomplete destination and staging while sources remain.
Operators must inspect/reconcile such artifacts before fresh planning; there is no
automatic replay, lock stealing or cleanup on failure.

Independent frozen checks/static review, the full prior regression suite,
actual-model workflow checks, installation/discovery, CI and release download
verification remain the parent's integration gates. No causal learning efficacy or
authenticated semantic-truth claim is made.

Routing retained the inherited current context (effective model/effort unknown),
with no new worker, service or paid API route. Existing owner-check verified
`codex-teach-me-harness-upgrade`. Latest inspected checkpoint signal reported 25%
remaining against the existing 20% reserve; there were no guard denials. An initial
owner-check invocation incorrectly supplied `--owner`, received argparse exit 2,
then the documented no-argument owner-check succeeded; no state mutation occurred.
