# Learn to engineer a small harness

Use this track for explicit learning intent about agent harnesses. An ordinary
request to build an agent remains a work request. Teach through a tiny authorized
project with one observable feature, rather than beginning with an autonomous
production system.

## Begin with an experiment

Read the supplied repository's existing instructions, runtime/dependency files,
tests, and current state. Ask only for consequential missing context. State a
learning goal, such as explaining how a test result controls the next action.
Probe it with one prediction: what should happen after a verification failure?
Then choose one bounded task and an exact check before implementation. A tiny
parser might require an empty input to return an empty result and a malformed
token to raise a specified error; confirm the actual interface before writing a
command. Never mark this example or any check passed merely because it is written.

Use the optional [harness-project.md template](../templates/harness-project.md)
inside the approved learning journey. This scaffolds a project record, not an
agent runtime. Existing repository rules remain authoritative in their scope.
Do not replace real `AGENTS.md`, global configuration, or project files merely
to fill the template. Changes to the actual exercise need their own authorized
scope, existing-file inspection, and meaningful checks.

## Five subsystems, two useful views

Use five practical groups below. The upstream course separates instructions,
tools, environment, state, and feedback; its creator instead separates
instructions, state, verification, scope, and lifecycle. This teaching grouping
combines tools/environment and includes scope/lifecycle explicitly. These are
overlapping design views, not a universal taxonomy or reliability score.

| Subsystem | Question for the learner | Minimal record |
| --- | --- | --- |
| Instructions | What is the goal, working rule, and definition of done? | Short startup route and links to relevant facts |
| Tools/environment | Which operations and runtime are available and authorized? | Allowed operations, actual versions/dependencies/fixtures, setup commands, and unknowns |
| State | How will tomorrow's session know what happened? | One active feature, dependencies, status, and evidence |
| Verification/feedback | What result changes the next action? | Exact verification and review criteria, with observed outcomes |
| Scope/lifecycle | What may change, when must work stop, and how can it resume? | One active feature, permission/budget limits, ownership, and next-action handoff |

For each subsystem, ask the learner to predict a failure if it were missing.
Implement or revise the smallest useful part, inspect its result, and ask for a
changed-case explanation. A completed artifact does not prove the learner could
design it independently.

## One feature and an honest handoff

Define the feature's task, dependencies, done check, status, and evidence before
work. Keep it pending until the check actually runs. Record the exact command,
working directory, relevant environment, outcome, and limitation. A failed or
unavailable check stays failed or unexecuted. A structural checklist is evidence
of structure only; it cannot establish reliable agent behavior.

At a session boundary, record changed files, current evidence, unfinished work,
the next exact action and how to verify it, and any active or uncertain jobs.
Resume by reading current files and reconciling newer corrections. A written
handoff transfers context, not permission or ownership; an old process ID or
claimed pass must be checked again when it matters. Do not duplicate uncertain
work or invent completion history.

## Compare fairly

Freeze the task, success checks, environment, and intervention policy before the
comparison. Give baseline and candidate equivalent clean starting application
code, inputs, tools, model/effort where inspectable, and budget. Vary only the
harness component under test. Reset generated artifacts, saved pass flags, and
cached evidence symmetrically. Keep completed reference solutions and answer
keys away from both task executors. Giving only one arm a working app or passing
checks confounds the result; it cannot prove the harness caused the improvement.

Record actual outputs, failures, retries, human help, elapsed time and usage when
measured. Mark unknown costs unknown. Use independent checks on representative
tasks, include a new task not used to tune the change, and disclose any unequal
conditions or shared context. Repeated trials strengthen a narrow observation;
one successful demo or a structural score is not a general reliability claim.
Use failure evidence to locate a problem; a component-ablation score alone does
not establish its cause.

## Optional later projects

Only extend the project after a useful single-session baseline exists and the
learner wants the extension.

- A bounded maker/checker loop needs explicit input/output, current round,
  independent verification, retry/time/allowance limits, stop conditions, and
  an observable state transition. Design it on paper first, then use only a
  verified available execution mechanism within the user's authorization.
- A workflow graph needs node responsibilities, conditional routes, state
  readers/writers, ownership, fan-out/fan-in merge rules, failure/rollback
  routes, and any necessary human approval gate. Test each route, including
  failure and interruption. This graph describes execution; it is different
  from the proposition/argument map in `knowledge.md`.

Teach-me does not supply a scheduler, background worker, graph runner, paid
provider integration, or enforcement of a written budget. Do not translate
example `/goal` or `/loop` text into a claim that those commands work in this
host. Dependencies, recurring jobs, external writes, deployment, and paid use
require applicable authorization and actual tool support. Record a design as
unexecuted until an authorized implementation is tested.

## Foundation scope

The [WalkingLab course](https://github.com/walkinglabs/learn-harness-engineering/tree/a9342ff471f2c0e60be0c08b9f4a7c502df4e442)
is a reference for the project progression. At this pinned revision P01's
reference includes application implementation, so copying its full solution
into only the candidate is unsuitable for a controlled comparison. P07/P08
describe later loop/graph exercises, but their linked `projects/project-07/`
and `project-08/` implementations were absent from the inspected tree. Verify
current files and host capabilities before recommending execution. This guide
is original material; no upstream scripts, prompts, or app are bundled.
