# v0.6.0 installation verification

The rollback-preserving update passed238 tests against the global skill. All38 files match the reviewed candidate; native enabled user-scope discovery passed from two directories without a model turn. Discovery does not establish automatic selection. Final immutable-source and release-download checks are recorded with the tagged release. Historical records below retain their original results and limits.

# v0.5.0 installation verification

The rollback-preserving local update passed all 178 tests against the installed skill. Native user-scope discovery succeeded from two directories; all 34 noncache files match the accepted candidate manifest. Discovery does not establish automatic instruction selection. Public immutable-source and release-download checks are recorded with the tagged release.

# Current v0.4.0 installation

All 30 global files match the accepted candidate. The installed 125-test suite and native enabled user-scope discovery from two directories passed on 2026-10-28. See [current release evidence](V0.4.0.md) and [hash record](../validation/v0.4.0/installation.json). Earlier records below remain historical.

# Current v0.3.0 installation

All 25 global files match the accepted candidate; native enabled user-scope discovery and final 70 tests passed on 2026-10-28. See [release evidence](V0.3.0.md) and [hash record](../validation/v0.3.0/installation.json). The initial macOS cleanup-test failure and independently reviewed test-only reconciliation are preserved there. Earlier records below remain historical.

# Current v0.2.0 installation

The fifteen-file update, native user-scope discovery and installed 16-test suite were verified on 2026-10-28. See [current release evidence](V0.2.0.md) and [installation hashes](../validation/v0.2.0/installation.json). The record below is the preserved v0.1.0 installation history.

# Release and installation verification

Checked 2026-10-26 (America/Denver).

- Initial public source revision: `f4fea83b2f8bad822d7ee4b82b411f4952dae954` on `main`.
- Installed the complete ten-file skill from that pinned GitHub revision into the user-scoped Codex directory `~/.agents/skills/teach-me`, using the built-in GitHub skill installer. All ten installed file hashes matched the reviewed source exactly. No existing skill was replaced.
- Codex CLI 0.164.0 native `skills/list` with `forceReload: true` returned `name: teach-me`, `scope: user`, `enabled: true`, with no matching parse/discovery errors, both from an unrelated temporary directory and from the project workspace. No model turn was started for this metadata check. This proves local discovery in those contexts, not automatic selection for every prompt or installation on remote/cloud machines.
- All 16 helper tests passed against the **installed** script on the author's local host, in addition to the source checks.
- [Initial public CI run](https://github.com/HarryBurd33/teach-me/actions/runs/40453028932) passed all four jobs: Linux Python 3.9, 3.12 and 3.14, and macOS Python 3.14. Each job ran the 16 tests and the self-contained release check. Future commits have their own [CI status](https://github.com/HarryBurd33/teach-me/actions).
- GitHub detected the root license as MIT. The skill-local license is byte-identical. Repository topics include `codex`, `codex-skill`, `agent-skills`, `adaptive-learning`, `tutoring`, `curriculum`, `education`, `learning`, and `python`.
- The public tree was reviewed to exclude private parent history, checkpoint/interview state, credentials, actual learner records, and compiled caches. The included learning fixtures are synthetic test data.

These release checks supplement the [original model evaluation](VALIDATION.md). They do not establish human learning outcomes, musical/physical readiness, automatic skill matching, or full external-integration behavior. After installing on another machine, check that machine's tools, permissions, and skill discovery separately.
