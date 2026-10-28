# Harness learning project

## Learning goal and first probe

- Goal: Explain how a failed check controls the next action in a small parser harness, and demonstrate one regression check.
- Exercise location and authorized scope: This scratch journey only. No parser repository was supplied or inspected; source edits are blocked pending selection of the actual repository.
- First probe: If a parser test fails, should the harness repeat the same change, mark the feature complete, or inspect the failure before choosing another action? Explain your choice.
- Observed response: pending; no learner answer or assistance yet.

## Five subsystems

| Subsystem | Current design | Missing information / next check |
| --- | --- | --- |
| Instructions | Target one parser behavior and require actual verification before completion. Read repository instructions before exercise edits. | Inspect real entry point and existing instructions. |
| Tools/environment | Python 3 and file tools are available for this scratch record; no new dependencies or services. | Actual parser language, runtime, grammar and test runner unknown. |
| State | This record owns the feature/handoff; progress.json retains schema v1 and no new keys. One writer. | Link real assessment/evidence IDs after actual work; none invented. |
| Verification/feedback | Proposed exact command below; record command, working directory, test count, exit code and output. Zero tests is not a pass. | Confirm interface, runner and named test after source inspection. |
| Scope/lifecycle | One active feature, current scratch files only; stop before unapproved installs, external effects or uncertain jobs. | Resume by checking current files and authorization; context is not a permission grant. |

## One active feature

| ID | Task | Dependencies | Done check | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | Reject trailing operator `1+` as malformed input, if actual grammar confirms this requirement | Inspect parser API and existing test runner; confirm error contract | Proposed command in selected parser repository: `python3 -m unittest tests.test_parser.TestParser.test_rejects_trailing_operator -v`; named test must execute and assert the confirmed error behavior. Change the command before implementation if the actual runner differs. | blocked | No parser source or test supplied; command not run; no pass claimed |

## Comparison protocol

- Freeze F1, its confirmed behavior, named check and review criteria before comparison.
- Start both arms from the same clean parser snapshot and fixtures, with empty generated evidence/pass flags; reset symmetrically.
- Change only the chosen harness component. Do not provide a completed reference implementation or answer key to one arm.
- Keep task, model/effort where inspectable, tools, environment, time/usage bounds and assistance policy equal. Exact current model/effort and cost are unknown.
- Independent review and held-out task: after actual check, try a new malformed expression not used while designing F1. Not run yet.
- Actual comparison result: none. A project record and a proposed command are not reliability evidence.

## Permissions and budgets

- Allowed paths/actions: initialize and write this candidate scratch journey only.
- Preserve: existing source and global instructions; there are no exercise source files in this scratch.
- Limits and stop conditions: one feature; stop for missing interface, actual host resource stop, uncertain job or action outside scope.
- External services, new dependencies, recurring work, deployment, paid use: none authorized by this lesson.
- Enforcement: manual scope in this record; no runtime or budget enforcement is implemented here.

## Session handoff

- Current files/revision: initialized plan.md, progress.json and sources.md; authored this harness-project.md. No parser application revision is available.
- Checks actually run: journey initialization succeeded; parser check unexecuted.
- Unfinished work and uncertainties: parser location, grammar, API, runtime and test command.
- Active/uncertain jobs and ownership: no exercise jobs started; one current record writer. Recheck before resuming.
- Next exact action: select the authorized tiny parser repository, read its instructions, parser entry point and one existing test; confirm F1 and replace the proposed command with its real equivalent if needed.
- Verification of that action: record inspected paths, actual API/error contract and an exact runnable named check; keep F1 unverified until execution.
- Learner's next task: answer the first probe, then predict behavior for `1+` and one nearby valid expression before editing code.
