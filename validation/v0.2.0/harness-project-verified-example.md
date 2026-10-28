# Harness learning project

## Learning goal and first probe

- Goal: explain and repair one parser behavior, using actual test output to choose the next action.
- Exercise location and authorized scope: supplied supplement-candidate-repo, read and test only; learner owns application repair. This scratch journey is the record destination.
- First probe: why does the empty part after the trailing + disappear in parse, and which requirement should prevent that?
- Observed response: pending; no learner answer or help yet.

## Five subsystems

| Subsystem | Current design | Missing information / next check |
| --- | --- | --- |
| Instructions | Reject a trailing operator; preserve valid integer addition; tutor leaves source unchanged for learner repair. | Learner explains intended invariant before editing. |
| Tools/environment | Existing parser_demo.py and test_parser.py; Python 3 stdlib unittest; no installs/services. | Runtime exact patch version unmeasured; not needed for this observed check. |
| State | One feature F1 and captured verification.txt; progress.json v1 unchanged; one record writer. | Link learner assessment/evidence IDs only after actual response; currently pending. |
| Verification/feedback | Exact existing two-test command below; inspect actual test names/count/output, not pass flags. | Rerun after learner repair and try a held-out malformed input. |
| Scope/lifecycle | One feature; tutor read/test only; learner makes source repair; no background work. | Resume from current source, output and scope; do not assume prior result persists. |

## One active feature

| ID | Task | Dependencies | Done check | Status | Evidence |
| --- | --- | --- | --- | --- | --- |
| F1 | Reject parse('1+') with ValueError and preserve parse('1+2') == 3 | Learner diagnoses and repairs current parse | `python3 -B -m unittest -v` in supplied supplement-candidate-repo; both named tests must run and pass, zero tests is failure | active | Baseline check ran: 2 tests; valid addition passed, trailing-operator check failed; exit 1; verification.txt. No repair or pass yet |

## Comparison protocol

- Frozen task/check: F1 and the supplied test_parser.py, same for both arms.
- Baseline/candidate start: identical parser/test bytes; no finished repair or pre-filled pass. Application files are unchanged.
- Controlled difference: learning instructions and companion project record only.
- Model/tools/environment/budget: same executor/tools; exact model/effort/cost unknown; shared sequential context means this is not a fresh isolated baseline or causal reliability experiment.
- Reset: retain identical source and independent evidence files; clear any generated pass flags symmetrically before another comparison.
- Independent review and held-out task: pending. Later ask learner to classify a new malformed input and justify the check.
- Actual result: existing app has one passing and one failing test; this says nothing about learning gain or general harness reliability.

## Permissions and budgets

- Allowed: inspect/run supplied stdlib tests and write this scratch journey; do not change application source.
- Preserve: parser_demo.py and test_parser.py; hashes checked unchanged.
- Stop: after bounded first check/record; do not start uncertain duplicate jobs or exceed host resource stop.
- External services, installs, recurring jobs, deployment, paid use: none.
- Enforcement: manual record scope only; this is no agent runtime or budget guard.

## Session handoff

- Current files: plan.md, progress.json, sources.md, harness-project.md, verification.txt in scratch journey; application unchanged.
- Checks actually run: `python3 -B -m unittest -v`, two tests, exit 1. Valid addition passes; trailing-operator check fails with ValueError not raised.
- Unfinished: learner explanation and repair; passing regression and transfer remain untested.
- Jobs/ownership: no active exercise job; one record writer; recheck before resume.
- Next exact action: learner explains why the filter removes the missing operand, then makes their own bounded repair.
- Verification: rerun the same command from the current repo; inspect both named test results, then choose a new malformed case.
- Learner next task: explain how an input ending in + differs from a valid sum, without assuming any test pass proves broad understanding.
