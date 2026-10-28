# teach-me

Version **0.5.0**. A portable, text-first learning skill for researched curricula, adaptive tutoring, and local save/resume. Start with a topic; receive a proportionate plan and a first useful lesson or diagnostic. It supports concepts, mental models, programming, music, and coach-supported physical-skill planning.

## Use

The examples below describe independent learners; their equipment and availability do not carry into another request.

- “Teach me Cramer's rule; I know basic algebra.”
- “Help me learn piano. I have a keyboard and 15 minutes daily.”
- “Help me learn how databases work by building one.”
- “Resume the algebra journey in this workspace.”

“What is a determinant?” remains a short factual answer. “Build a website” remains a work request unless learning intent is added.

## Installation and use

Copy the entire `teach-me/` directory into `~/.agents/skills/teach-me/` for user-wide Codex use on this machine. Preserve an existing customized copy instead of overwriting it. Codex detects skill changes automatically; if it does not appear on your next turn, restart Codex. Invoke it explicitly with `$teach-me`, followed by your learning goal. This local installation does not install it on other computers or cloud executors. See the [official skill guide](https://learn.chatgpt.com/docs/build-skills) for discovery and scope. The skill does not require Skill Forge, task-checkpoint, Understand Anything, or Build Your Own X to be installed.

Full experience: web search/page retrieval and an authorized writable workspace. Python 3.9+ is optional for the bundled state helper and uses only the standard library. Without browsing, curricula are provisional; without files, export state explicitly; without media tools, use text/self-reports and explain limits.

For example: `$teach-me Teach me probability. I know basic algebra and have 20 minutes per session.` To resume, provide the saved journey folder, for example `$teach-me Resume the probability journey in /path/to/workspace/learning/probability.`

## New learning-harness workflows

- `$teach-me Teach me gradient descent. I know algebra but not calculus.`
- `$teach-me Give me mixed practice without naming the method first. Record help used.`
- `$teach-me Map the prerequisites and jointly required premises for this topic, with sources.`
- `$teach-me Teach me harness engineering with a tiny parser project. Save one feature, its check, and tomorrow’s handoff in this workspace.`
- `$teach-me Review this selected LearnHarness export read-only and suggest a fresh diagnostic.`

The tutor can switch among diagnostic, teaching, practice and review modes. Optional knowledge, practice and project records sit beside existing progress files. Read [learning-harness guidance](references/learning-harness.md) and [engineering guidance](references/harness-engineering.md).

The optional tools use original Python 3.9+ standard-library code:

- [Native-v1 data adapter and searchable offline map](references/data-tools.md): selected session/graph files, chronological learner answers, provenance and grouped premises. Supported subset only; source unchanged, no inferred mastery or automatic extraction from prose.
- [Manual journey transfer and writer locks](references/transfer.md): allowlisted hash-verified archive, fresh-destination import, cooperative local save/init coordination. Existing progress schema v1 stays compatible; the helper now locks its writes.
- [Bounded local harness runner](references/local-runtime.md): explicit argv plans, dry run, dependencies, retries, time/output limits and human-gated nodes. Commands inherit host access; this is not a sandbox, autonomous agent, scheduler or provider service.
- [Host integration and real-learner pilot](references/host-integration.md): capability-aware dictation/media/reminder/provider workflow and a pending baseline/retention/transfer record. Real outcomes require actual learner participation.

Version 0.4.0 adds [source-grounded graph proposals and edits](references/graph-workbench.md), [immutable journey snapshots and conflict-aware manual merging](references/journey-versions.md), and atomic JSON/HTML report publication. The tutor drafts a proposal; exact quotes and input hashes are validated, while semantic correctness remains a review judgment. Snapshots activate a stored generation through HEAD, and merges preserve originals and bind conflict choices to a report hash. Even a clean file-level merge needs review for meaning across plan/progress/source records. Current snapshots preserve the eleven documented files when present, including the typed graph/proposal/source/review records. Arbitrary attachments still need separate handling. These are optional workflows, not a prerequisite questionnaire for ordinary lessons.

Facts remain scoped to the current learner/journey. Equipment, software or time in an example is not supplied information about another learner. Unknown resources stay unknown unless a reasonable assumption is explicitly labeled.

No continuous sync, distributed lock, automatic stale-lock recovery, multi-file edit transaction, native upstream writeback, bundled speech engine or guaranteed learning gain is supplied. Inspect the linked contracts before using a tool; model judgments and saved confidence never certify competence.

## Files and privacy

`SKILL.md` is the entry point. `references/` contains domain/research guidance and the state contract/schema; `templates/` contains editable scaffolds; `scripts/journey.py` manages progress files. Learner records belong in an approved workspace under `learning/<id>/`, never in this installable folder. Do not upload, install dependencies, or schedule reminders merely because they might help.

See [state usage and recovery](references/state.md). Validation evidence is delivered separately beside the package; example material is illustrative, not an actual learner result. A schema-valid state does not prove competence. This skill cannot certify physical readiness or infer uninspected performance.

## License

Original material is MIT licensed; see [LICENSE](LICENSE). External references keep their own rights; see [provenance](references/research.md).

## Typed records and consistency review

Transfers and snapshots now preserve explicit `knowledge-graph.json`, `knowledge-proposal.json`, `knowledge-source.txt` and `journey-review.json` alongside the original records. Proposals must match the selected source hash and exact quotes; draft references remain drafts. See [transfer rules](references/transfer.md).

After reconciling divergent journeys, ask: `$teach-me Review this journey for contradictions, record concrete decisions and verify that the review matches the current files.` The [review helper](references/coherence-review.md) binds four operator decisions to exact file bytes and detects stale receipts. It cannot judge meaning, authenticate the reviewer, certify mastery or supply authorization. Typed archives use format v2; v0.4.0 and older helpers cannot read them. The new helper still reads valid legacy format v1 archives.
