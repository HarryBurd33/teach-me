# Learning state and resume

The learner chooses or approves the workspace. Keep each journey in `WORKSPACE/learning/JOURNEY-ID/`; do not put personal records inside the installed skill. Required files are `plan.md`, `progress.json`, and `sources.md`. This is local persistence, not synchronization, automatic memory, or permission to write elsewhere.

Use the bundled Python 3.9+ standard-library helper when execution is available. Substitute actual absolute paths; commands shown here are examples, not claims that anything was saved:

```sh
python3 /path/to/teach-me/scripts/journey.py init --root /approved/workspace --id algebra --topic 'Linear systems' --goal 'Solve and explain small linear systems'
python3 /path/to/teach-me/scripts/journey.py show --journey /approved/workspace/learning/algebra
python3 /path/to/teach-me/scripts/journey.py validate --file /approved/workspace/learning/algebra/progress.json
python3 /path/to/teach-me/scripts/journey.py save --journey /approved/workspace/learning/algebra --input /approved/workspace/proposed-progress.json --expected-sha256 HASH-FROM-SHOW
```

`init` refuses existing journey folders, traversal IDs, and symlinks at or within the approved root. It copies the bundled plan/source templates; complete their placeholders with actual learner context. `show` returns a JSON object with `progress` and `sha256`. To save, edit a **full copy of the `progress` object**, not the `show` envelope. `save` validates both versions, checks the expected hash and immutable journey ID, saves the original bytes as `progress.previous.json`, then atomically replaces `progress.json`. Successful commands return JSON; errors go to stderr with exit code 2. Validate/show perform no writes. The helper does not edit `plan.md` or `sources.md`; preserve those separately when materially revising them.

Use one writer at a time. The hash catches stale sequential updates; it is not cross-process fencing. Atomic replacement reduces partial-file risk; this is not a transaction across all journey files or a guarantee against power loss. Writes refuse symlinked journey/nearby workspace paths, progress, backup, or `progress.lock`; no lock service is created. No networking or uploads occur.

## Schema version 1

The machine-readable structural contract is [progress.schema.json](progress.schema.json). Every listed key is required and unknown keys are rejected, including nested objects. The helper also rejects duplicate JSON members rather than silently taking the final value. Strings used as identifiers, goals, tasks, or summaries must contain a non-whitespace character. Arrays can be empty unless stated otherwise.

| Field | Value and meaning |
|---|---|
| `schema_version` | Integer `1`; unknown versions require reviewed migration, never silent reinterpretation |
| `journey_id` | Immutable lowercase letters/digits separated by single hyphens, matching the journey folder |
| `topics` | Nonempty array of nonempty strings |
| `goal` | Observable desired ability |
| `current_stage` | Current curriculum stage; not a global mastery claim |
| `availability` | Object with `minutes_per_day` and `session_minutes`; each nonnegative integer or `null`. Missing/unknown is `null`, confirmed zero stays `0`; booleans are invalid |
| `assessments` | Array of `{id, task, result, evidence_ids, feedback}`; `result` is `pending`, `needs_review`, or `demonstrated`; `feedback` may be empty |
| `evidence` | Array of `{id, kind, summary, recorded_at}`; `kind` is `observed` or `self_reported` |
| `difficulties`, `decisions` | Arrays of nonempty strings; record bottlenecks and material teaching decisions |
| `next_action` | Concrete next useful lesson, check, or practice task |
| `updated_at` | ISO timestamp with date, `T`, seconds, and timezone; optional fractional seconds |

The helper additionally checks cross-field invariants JSON Schema cannot express: assessment and evidence IDs are unique within their own arrays; every `evidence_ids` entry resolves; a `demonstrated` assessment references at least one `observed` evidence item. An evidence record is observed only when the assistant actually inspected the response/artifact through a supported channel. A learner saying they practised or completed a task is `self_reported`. Observing a written answer does not establish observed musical/physical performance or broad mastery. The helper cannot judge truth, sufficiency, or domain competence; the tutor must review that.

## Save and resume procedure

Save at a meaningful session boundary or material plan change, not after every message. Record actual attempts, scoped evidence, feedback, difficulties, changed decisions, and next action. Confirm saved paths only after successful writes. Keep sensitive learner material minimal and local; use short evidence summaries or authorized local references instead of transcripts.

On resume, identify the intended journey, read all three files, validate the state, summarize the last verified evidence and next action, reconcile newer learner instructions, and use a short retention/transfer check when helpful. If two journeys fit equally, ask which before writing either. Do not turn elapsed time, confidence, reading, or reported practice into demonstrated performance.

If progress is absent or malformed, preserve the original bytes and explain what is missing. Validate `progress.previous.json` independently before proposing recovery; preserve both versions and reconcile with `plan.md` and the learner. Do not call `save` to silently repair corrupt state; it intentionally refuses. Readable plans can support a provisional session, but they do not reconstruct lost assessment history. Unknown schema versions require a separate reviewed migration. Missing plan/source files can be recreated only from known context with their gaps stated.

Without execution, use equivalent careful filesystem reads/validation and replacement only if those tools are available. Without filesystem access, return the plan, sources, and a JSON progress object for the learner to save, explicitly stating that persistence has not been established. Never claim another chat or device will see unsaved state.

## Optional v0.2 companion records

Existing version-1 journeys need no migration. `journey.py init` still creates only the three required files, and `save` still changes only progress and its backup. Do not insert optional-record data or confidence keys into the closed progress schema.

For a difficult multi-session topic, create [knowledge.md](../templates/knowledge.md) for sourced propositions, prerequisite IDs and reasoning chains whose premise IDs are jointly required. It records what has been discussed and where it came from, never automatic mastery. Use [practice.md](../templates/practice.md) for attempt summaries, help used, feedback and the next retrieval task. Link real progress assessment/evidence IDs; write “not yet recorded” rather than inventing an ID. For an engineering learning project, use [harness-project.md](../templates/harness-project.md) for one feature, pending/executed checks, fair comparison and handoff.

The tutor creates/edits these Markdown files with ordinary authorized file tools; the helper does not manage them. Read existing contents first, preserve learner changes, use one writer, preserve the prior file when materially revising, and report only successful saves. There is no shared transaction or automatic synchronization with progress. If records disagree, preserve both and reconcile the evidence with the learner before advancing. On resume, read relevant existing companions as well as the required three files; missing companions do not invalidate a v1 journey. Without filesystem access, return explicit unsaved text.

LearnHarness data remains a separate external source. Follow the [selective read-only procedure](learning-harness.md); do not overwrite exports, reformat an unknown version into invented state, or assume local storage means model processing is offline.
