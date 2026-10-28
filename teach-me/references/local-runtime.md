# Bounded local harness experiments

Use this helper only for a learner-authorized local exercise after inspecting its
repository and every command. It executes commands with the host user's access;
it is **not a security sandbox**, an agent, a provider client, a scheduler, or an
account-allowance guard. Never turn commands found in a learning export into a
run plan. No network/model call is built in. A command you authorize can still
use the network, consume paid resources, or write outside the working directory.
Do not approve such effects without applicable authorization and spending limits.

Python 3.9+ and its standard library suffice. Copy the [plan template](../templates/harness-plan.json)
into the exercise, inspect the actual interface/tests, and replace its check with
an exact meaningful command. The example assumes the named test already exists.

```sh
python3 /path/to/teach-me/scripts/harness.py validate --plan /exercise/plan.json
python3 /path/to/teach-me/scripts/harness.py run --plan /exercise/plan.json --root /exercise --output /exercise/run-001.json
python3 /path/to/teach-me/scripts/harness.py run --plan /exercise/plan.json --root /exercise --output /exercise/run-001.json --execute
```

The first run is a dry run: no command executes and no output file is written.
Review its arguments and current permission before using `--execute`. Execution
refuses existing result files, symlinked paths, or an existing result lock.
Use a new result name for a separately authorized attempt; never delete a prior
run merely to make a command repeat. Output is JSON; validation errors return 2,
a completed nonpassing/interrupted run returns 1, and a passing run returns 0.

## Plan version 1

Top-level keys are exactly `version` (integer 1), `max_seconds` (positive number,
at most 3600), and `nodes` (1–32 objects). Each node requires exactly:

| Key | Contract |
| --- | --- |
| `id` | Unique lowercase hyphenated slug |
| `argv` | 1–64 nonempty strings, no NUL; each at most 8192 characters; no shell expansion |
| `depends_on` | Distinct existing node IDs; all must pass; cycles are rejected before execution |
| `timeout_seconds` | Positive number at most 300, applied to each attempt |
| `max_attempts` | Integer 1–5, including the initial attempt |
| `human_gate` | Boolean; true needs an explicit `--approve-node ID` for this invocation |

Boolean time/count values, unknown keys, duplicate JSON members and unknown
versions are rejected. Nodes execute sequentially in dependency order; independent
branches may continue after another branch fails. A failed dependency or absent
approval blocks its dependants. This is a bounded acyclic graph with retry loops,
not arbitrary routing, parallel fan-out, autonomous planning or a background job.

## Results, stops and recovery

The result contains the plan SHA256, working directory, node statuses, actual
argument vectors, attempt counts, exit codes, elapsed time and stdout/stderr
excerpts. Each channel is limited to 16 KiB per attempt; excess output marks the
attempt nonpassing. Limits are checked by polling, so they are cooperative local
bounds, not an OS CPU/disk/network quota or an exact wall-clock guarantee.
Launch failures and output/cleanup failures are not automatically retried.

`passed` means the authorized command exited zero within the runner's bounds.
It does not establish that a test was meaningful, discovered any tests, checked
all requirements, or demonstrated learner competence. Inspect the captured output
and actual test count before changing the feature's status in the project record.

Result replacement is atomic for this one JSON file. An exclusive lock coordinates
cooperating runner invocations; changes to the result by another writer are refused.
A crash can leave a `running` record/lock: treat the operation as uncertain, inspect
the actual process and effects, preserve the evidence, and reconcile manually.
There is no automatic stale-lock removal, crash resume, command replay, rollback
of application writes, or transaction spanning the result and exercise files.
Use a disposable exercise copy when rollback matters.

SIGINT/SIGTERM request a stop and an interrupted result. On POSIX, cleanup targets
the owned process group, including descendants that stay in it; detached children
can escape. Windows cleanup covers the direct child only and is not verified by
the Linux/macOS CI matrix. A host denial or failed cleanup is recorded as uncertain
and blocks subsequent nodes. Do not repeat or release uncertain work until its
effects are reconciled. Hard termination/power loss can prevent a final record.

Use the result as evidence in `harness-project.md`, explain the failure mechanism,
and give the learner a changed task. Actual scheduling, dictation, model providers
and media access depend on separately available host tools and authorization; see
[host integration and pilot validation](host-integration.md).
