# teach-me

A portable, text-first learning skill for researched curricula, adaptive tutoring, and local save/resume. Start with a topic; receive a proportionate plan and a first useful lesson or diagnostic. It supports concepts, mental models, programming, music, and coach-supported physical-skill planning.

## Use

- “Teach me Cramer's rule; I know basic algebra.”
- “Help me learn piano. I have a keyboard and 15 minutes daily.”
- “Help me learn how databases work by building one.”
- “Resume the algebra journey in this workspace.”

“What is a determinant?” remains a short factual answer. “Build a website” remains a work request unless learning intent is added.

## Installation and use

Copy the entire `teach-me/` directory into `~/.agents/skills/teach-me/` for user-wide Codex use on this machine. Preserve an existing customized copy instead of overwriting it. Codex detects skill changes automatically; if it does not appear on your next turn, restart Codex. Invoke it explicitly with `$teach-me`, followed by your learning goal. This local installation does not install it on other computers or cloud executors. See the [official skill guide](https://learn.chatgpt.com/docs/build-skills) for discovery and scope. The skill does not require Skill Forge, task-checkpoint, Understand Anything, or Build Your Own X to be installed.

Full experience: web search/page retrieval and an authorized writable workspace. Python 3.9+ is optional for the bundled state helper and uses only the standard library. Without browsing, curricula are provisional; without files, export state explicitly; without media tools, use text/self-reports and explain limits.

For example: `$teach-me Teach me probability. I know basic algebra and have 20 minutes per session.` To resume, provide the saved journey folder, for example `$teach-me Resume the probability journey in /path/to/workspace/learning/probability.`

## Files and privacy

`SKILL.md` is the entry point. `references/` contains domain/research guidance and the state contract/schema; `templates/` contains editable scaffolds; `scripts/journey.py` manages progress files. Learner records belong in an approved workspace under `learning/<id>/`, never in this installable folder. Do not upload, install dependencies, or schedule reminders merely because they might help.

See [state usage and recovery](references/state.md). Validation evidence is delivered separately beside the package; example material is illustrative, not an actual learner result. A schema-valid state does not prove competence. This skill cannot certify physical readiness or infer uninspected performance.

## License

Original material is MIT licensed; see [LICENSE](LICENSE). External references keep their own rights; see [provenance](references/research.md).
