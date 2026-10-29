# Independent Teach-me v0.7 review

Independent delegated evaluator, effective model/effort unknown. Scope was review/ only; no candidate/global/public/checkpoint mutations, agents, services or API spending. Parent supplied readiness before candidate inspection. The frozen cases and model prompts preceded candidate inspection. No learner store was used.

## Outcome

Candidate final pass: **20/20 independent component groups passed** (H01–H09 and R01–R11). Baseline: **2/2 expected absence probes passed**, demonstrating that historical import is not a baseline CLI subcommand and snapshot_recovery.py is absent. Four actual literal workflow responses per arm were recorded; the same nonblind evaluator generated and graded both arms. Safety/boundary rubric: baseline 4/4, candidate 4/4. Requested native capability rubric: baseline 2/4, candidate 4/4. These are software/workflow observations, never a learner-efficacy result.

No actionable candidate defect found within this review.

## Observed cases

Historical old ready:true receipt with whitespace imports and extracts byte-for-byte. Import status remains historical/not ready, retains receipt_resume_ready:true, freshness and origin authentication false. Wrong receipt digest/tip/id, blank/oversized reason, forged v2 origin, invalid base64, missing/extra keys, broken chain, history lock and stage refuse without history changes. A v1/v2/v1 chain keeps old entry bytes unchanged and v1 entries retain exact six-key storage.

An actual unchanged maintenance run was interrupted before its second selected ZIP unlink. It left a complete published archive and orphan stage. Recovery planned three remaining and one absent selection, completed removals, preserved current HEAD/previous and complete archive bytes, and restored an archived revision to a fresh workspace via transfer unpack. A second actual recovery interruption removed one more ZIP, refused the old stale plan, and finished from a fresh plan. Fully completed recovery yielded an empty, verified no-op. Modified archive after no-op was refused. Tampered ZIP/manifest, missing ZIP/manifest, current HEAD or previous now selected, reformatted current HEAD after planning, wrong expected digest, absent approval, unknown store/archive file, foreign inner archive identity, held store/archive-parent locks, and archive-inside-store were refused with no new removals.

Static review confirmed strict archive schema/canonical bytes, complete selection/hash/size/inner identity verification, exact closed recovery schema and self hash, archive/store disjoint checks in both directions, store then archive-parent lock order, current store/archive binding, protected raw byte fences and complete backup revalidation before every unlink. Historical import never calls current-journey reads and rechecks receipt/store/staging bytes before create-new link. Docs describe historical-origin limits, compatibility, complete-backup requirement, fresh plans, current protected revisions and no automatic replay/cleanup.

Baseline/candidate bytes match for snapshot_maintenance.py, journey_versions.py, journey.py, transfer.py and progress.schema.json. All 238 regressions, installed suite, CI/release/tag/ZIP and global adoption checks remain parent-owned and were not rerun here.

## Evaluation correction and limits

Two candidate passes total. Pass 1 had 8 passing groups and two evaluator errors: duplicate fixture directory name in grouped malformed-entry cases, and fault-wrapper missing scripts import path. No candidate defect was inferred. Pass 2 corrected only the harness setup, expanded grouped malformed/archive/protection branches under the original frozen expectations, and passed 20/20. Pass-1 logs/results retained.

Fault groups were frozen before candidate inspection; actual injection is a scoped pathlib.Path.unlink wrapper that completes the first selected store ZIP unlink and raises before the second. The unchanged maintenance and new recovery remove_revision boundaries both call that underlying unlink. This preserves real partial filesystem state without weakening code under test.

Remaining independent coverage gaps: reverse ancestry direction is statically verified rather than separately executed; not every size-boundary/symlink/race permutation was independently repeated; no hostile-filesystem or power-loss guarantee; no external reviewer authentication. Model arms share the evaluator context and are self-generated/self-graded, nonblind; they are fresh relative to the implementation author's context, not isolated new model sessions. No separate model API calls were made. M03/M04 outputs are identical across arms because the relevant behavior is unchanged. No learner performance/retention/transfer observation exists. Parent component/regression tests may cover some gaps but are separate evidence.

## Evidence

Frozen cases SHA256: de3d44864c1a577f811da810e2a143efbbee10de59841453481932965cd380f3
Model prompts SHA256: c1388ce93cc202e456f1cdd1bc0473a43bb083f51df6463ab802bacd7b11dcd6
Final runner SHA256: c8317bee3b5bf093bf87f9038941dc1bdd2afef395cda5688035256707733f5a

See candidate-pass2-results.json and candidate-pass2-commands.json for literal executions, baseline-results.json for native absence probes, baseline-model-responses.json and candidate-model-responses.json for all eight literal responses, model-workflow-grades.json for labels, and reviewed-candidate-hashes.json for the precise candidate files reviewed. Fixtures and interrupted/staged files remain under review/ for inspection; no automatic cleanup was performed.
