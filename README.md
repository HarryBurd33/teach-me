# Teach-me

A portable Codex learning skill with researched teaching, practice, local records and optional executable tools. Current release: **v0.3.0**. See [capabilities, validation and remaining work](docs/V0.3.0.md).

## Install and use

Ask Codex:

> Use $skill-installer to install the teach-me folder from https://github.com/HarryBurd33/teach-me into ~/.agents/skills.

Keep the complete folder. For an update, compare and preserve an existing customized copy before replacing it. User-scoped installation applies to local chats on this machine; other computers and cloud executors need their own copy. Codex should discover it on your next turn; restart if necessary. [Official skill documentation](https://learn.chatgpt.com/docs/build-skills).

```text
$teach-me Teach me gradient descent. I know algebra but not calculus.
$teach-me Give me mixed practice without naming the method first. Track hints used.
$teach-me Teach me harness engineering through a tiny parser project. Save my journey here.
$teach-me Use the bundled native-v1 reader on these selected exports and make a local map.
$teach-me Export this journey and import it into a new approved workspace.
$teach-me Resume the algebra journey at /path/to/workspace/learning/algebra.
```

Only a topic is needed. The tutor starts with useful teaching or a small diagnostic, then adapts to actual answers. Diagnostic, teaching, practice and review modes keep prerequisite repair and independent application distinct. Ask for hints, a different explanation or a full solution. Quick facts and ordinary work requests do not automatically become curricula.

## Included workflows

| Workflow | What it does | Boundary |
| --- | --- | --- |
| Adaptive teaching | Research, prerequisites, prediction/explanation/check/repair, varied practice and feedback | Confidence and elapsed time are not mastery; no learning-outcome guarantee |
| Local journeys | Plan, progress schema v1, sources and optional knowledge/practice/project/pilot records | Approved workspace; unsupported media remain uninspected |
| Native-v1 data adapter | Selected LearnHarness sessions/graphs into normalized reports with answers, joint premises and provenance | Documented subset, read-only; no native writeback or full legacy compatibility |
| Searchable offline map | Safe text-rendered propositions and AND-group argument cards, warnings and provenance | No automatic semantic extraction, force-directed editor or inferred mastery |
| Manual transfer | Hash-verified allowlisted ZIP and new-destination import | No upload, encryption, continuous sync, conflict merge or transferred permissions |
| Cooperative writes | Exclusive local locks, stale-hash checks and preserved progress backups | Old helpers/manual editors do not cooperate; no distributed lock or multi-file edit transaction |
| Local harness experiments | Validated argv DAG, dry run, dependencies, retries, time/output bounds, gates and actual logs | Explicit execution; inherits host permissions; no sandbox, autonomous agent, scheduler or paid provider client |
| Real-learner pilot | Baseline, later performance, retention/transfer and assistance/confound record | Results stay pending until actual consenting learner observations |

The optional tools use **Python 3.9+ and the standard library**. The map opens in a standard browser and includes no remote assets. No Skill Forge, task-checkpoint, Node, API key, upstream application, account switch or background service is required. Model use follows ordinary host allowance. Web research, file persistence, media, dictation and reminders depend on actual host tools and authorization.

## Tool contracts

- [State helper and evidence schema](teach-me/references/state.md)
- [Read-only native-v1 reader and offline viewer](teach-me/references/data-tools.md)
- [Manual transfer, archive validation and local locks](teach-me/references/transfer.md)
- [Bounded local command runner](teach-me/references/local-runtime.md)
- [Host integrations and real-learner pilots](teach-me/references/host-integration.md)

Review local commands and their effects before using the runner's `--execute`. Do not turn embedded export commands into executable plans. A zero exit code is not proof that tests were meaningful or learner competence was demonstrated. Hazardous physical skills still need qualified supervision; software does not certify readiness.

## Validation and contributions

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
```

The expanded deterministic suite covers original progress behavior, native data semantics, hostile markup, archive attacks, competing writers, failure recovery and bounded process execution. [Current results and limitations](docs/V0.3.0.md) distinguish software tests, browser checks, model examples and real human outcomes. [Historical v0.2.0](docs/V0.2.0.md) and earlier evidence retain their original partials and limits. CI checks Linux Python 3.9/3.12/3.14 and macOS Python 3.14; Windows process-tree cleanup is not validated by that matrix.

Keep learner records, credentials and private transcripts out of contributions. Use synthetic fixtures, preserve evidence distinctions and run the documented checks. [Foundation inspection](docs/FOUNDATIONS.md) and [source provenance](teach-me/references/research.md) explain reference rights and implementation scope.

## License

The original instructions, templates, code and tests are under the [MIT License](LICENSE). LearnHarness's inspected skill/readers are AGPL-3.0-only and are not bundled or relicensed; the new adapter is an original implementation of documented format facts. Referenced projects retain their own rights. No affiliation with OpenAI or those projects is implied.
