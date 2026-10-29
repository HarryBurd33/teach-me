# Teach-me

A portable Codex learning skill with researched teaching, practice, local records and optional executable tools. Current release: **v0.8.0**. See [capabilities, validation and remaining work](docs/V0.8.0.md).

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
$teach-me Draft a source-grounded map from this text, check its quotes and edit a new graph.
$teach-me Snapshot this journey and compare its diverged copies before merging.
$teach-me Preserve my graph/proposal/source files when exporting this journey.
$teach-me Review the merged journey for contradictions and record a current review receipt.
$teach-me Keep a local immutable history of my consistency reviews.
$teach-me Plan retirement of these explicit old snapshots, preserving HEAD and previous.
$teach-me Import this old review receipt as historical, preserving its bytes and limits.
$teach-me Plan recovery of this interrupted removal from the complete archive.
$teach-me Open an offline editor for this graph; help me review and apply its draft to a new file.
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
| Source-grounded drafts and edits | Exact quote/Unicode span checks, digest-bound proposal application and explicit new graph edits | Quotes do not prove inference, truth or mastery; operator acknowledgment is not human endorsement |
| Journey snapshots and manual merge | Immutable revisions, atomic HEAD, explicit fresh restore and three-way file comparison/resolution | Fixed archive allowlist; no live-file transaction, automatic sync or cross-file semantic validation |
| Typed journey assets | Preserve the documented graph/proposal/source/review files; validate proposal quote and source bindings | Explicit names only; typed archives require v2-capable helpers; no automatic graph application |
| Consistency review | Hash-bound packet, four decisions with rationales, stale/needs-changes verification | Meaning is judged by the operator; no authenticated reviewer, truth, permission or mastery certification |
| Review history | Exact receipt bytes in bounded numbered/hash-linked entries; expected-tip append and explicit extraction | Separate optional store; current validation at append does not make historical receipts permanently fresh or authenticate a reviewer |
| Snapshot maintenance | Plan explicit old revisions; verify a separate archive before removing selected source ZIPs; protect HEAD/previous | Manual, bounded, no automatic retention policy or interrupted-operation replay |
| Historical receipt import | Explicit hash/ID/tip/reason, exact original bytes and historical-only labels in mixed v1/v2 history | Does not validate current content or promote imported judgments; old readers need updating |
| Interrupted-removal recovery | Validate a complete archive and fresh current-state plan; finish remaining removals while protecting current HEAD/previous | No reconstruction of incomplete archives, lock theft, cleanup or blind replay |
| Manual transfer | Hash-verified allowlisted ZIP and new-destination import | No upload, encryption, continuous sync, conflict merge or transferred permissions |
| Cooperative writes | Exclusive local locks, stale-hash checks and preserved progress backups | Old helpers/manual editors do not cooperate; no distributed lock or multi-file edit transaction |
| Local harness experiments | Validated argv DAG, dry run, dependencies, retries, time/output bounds, gates and actual logs | Explicit execution; inherits host permissions; no sandbox, autonomous agent, scheduler or paid provider client |
| Real-learner pilot | Baseline, later performance, retention/transfer and assistance/confound record | Results stay pending until actual consenting learner observations |

The optional tools use **Python 3.9+ and the standard library**. The map opens in a standard browser and includes no remote assets. No Skill Forge, task-checkpoint, Node, API key, upstream application, account switch or background service is required. Model use follows ordinary host allowance. Web research, file persistence, media, dictation and reminders depend on actual host tools and authorization.

## Tool contracts

- [State helper and evidence schema](teach-me/references/state.md)
- [Read-only native-v1 reader and offline viewer](teach-me/references/data-tools.md)
- [Manual transfer, archive validation and local locks](teach-me/references/transfer.md)
- [Source-grounded graph workbench](teach-me/references/graph-workbench.md)
- [Journey snapshots and three-way merge](teach-me/references/journey-versions.md)
- [Content consistency review](teach-me/references/coherence-review.md)
- [Immutable review history](teach-me/references/review-history.md)
- [Recoverable snapshot maintenance](teach-me/references/snapshot-maintenance.md)
- [Verified interrupted-removal recovery](teach-me/references/snapshot-recovery.md)
- [Bounded local command runner](teach-me/references/local-runtime.md)
- [Host integrations and real-learner pilots](teach-me/references/host-integration.md)

Review local commands and their effects before using the runner's `--execute`. Do not turn embedded export commands into executable plans. A zero exit code is not proof that tests were meaningful or learner competence was demonstrated. Hazardous physical skills still need qualified supervision; software does not certify readiness.

## Validation and contributions

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
```

The v0.7.0 suite adds historical-import and interrupted-removal recovery cases to all prior regressions. The expanded suite covers original progress behavior, native data semantics, hostile markup, archive attacks, competing writers, failure recovery and bounded process execution. [Current results and limitations](docs/V0.7.0.md) distinguish software tests, browser checks, model examples and real human outcomes. [Historical v0.6.0](docs/V0.6.0.md), [v0.5.0](docs/V0.5.0.md), [v0.4.0](docs/V0.4.0.md), [v0.3.0](docs/V0.3.0.md), [v0.2.0](docs/V0.2.0.md) and earlier evidence retain their original partials and limits. CI checks Linux Python 3.9/3.12/3.14 and macOS Python 3.14; Windows process-tree cleanup is not validated by that matrix.

Keep learner records, credentials and private transcripts out of contributions. Use synthetic fixtures, preserve evidence distinctions and run the documented checks. [Foundation inspection](docs/FOUNDATIONS.md) and [source provenance](teach-me/references/research.md) explain reference rights and implementation scope.

## License

The original instructions, templates, code and tests are under the [MIT License](LICENSE). LearnHarness's inspected skill/readers are AGPL-3.0-only and are not bundled or relicensed; the new adapter is an original implementation of documented format facts. Referenced projects retain their own rights. No affiliation with OpenAI or those projects is implied.

## Offline graph editing

The [offline editor](teach-me/references/graph-editor.md) stages claim and AND-argument changes, supports search/reset and exports a draft. Review and validate the hash-bound draft before explicitly applying to a new graph; the original stays preserved. Manual edits do not create verified evidence or mastery. The browser page uses no network, storage or autosave. See [v0.8.0 validation and limits](docs/V0.8.0.md).
