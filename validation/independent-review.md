# Independent artifact contract review

Date: 2026-10-26 (America/Denver). Reviewer: separate subagent context, read-only candidate inspection; approximately five-minute bound. This reviewer previously performed foundation research but did not author the skill or state helper. This is independent contract/static review plus executed CLI probes, not model-response grading or learner-outcome evidence. `execution-inputs.json` and model outputs were not read.

Reviewed hashes:

- `teach-me/SKILL.md`: `5bd5f086aac22b69a11fdfba7248ef4e1760a870bd7ae6c21d0935a650e62765`
- `teach-me/scripts/journey.py`: `531a16724204482842eb79b0443440950d3608c2f819c1e24a73ab3af37fbc6f`
- `validation/cases.json`: `477953b2f1e8389fc4c87741d243ce7db19f9f7140a7e6388ade7514b53315ca`

## Result

No material blocking contract, safety or package-privacy finding. The original requirements are represented concretely, including proportional learning scope, first teaching activity, prerequisite diagnosis, researched sequencing, adaptation from actual evidence, multiple topics, direct explanations on request, domain-specific checks, persistence and honest capability fallbacks.

One optional robustness improvement was found and subsequently resolved as recorded below. The original finding and original reviewed hash are retained for traceability.

## Finding

**P3 — Reject duplicate JSON object members before validating imported state.** `teach-me/scripts/journey.py:114` calls `json.loads` without duplicate-member detection. An independent CLI probe supplied a full valid progress object containing two `goal` members with different strings; `validate` returned exit 0. Python silently keeps the final member. Duplicate `evidence` or `assessments` members could likewise make a hand-edited/imported file ambiguous before structural checks run. Consider an `object_pairs_hook` that rejects repeated member names at every nesting level. This is optional hardening: ordinary generated files have unique members, original bytes are preserved on a successful save, and the stated required malformed/stale checks pass.

**Resolved, independently re-probed:** the parent added `unique_members` and passes it as `object_pairs_hook` in `load`. New helper SHA256: `7c9c65b5f108bc2bddbc621cd33ff5b092abb3b32e8ac4865922d9abb963a358`. The same independently constructed duplicate-goal input now exits 2 with `Duplicate JSON member is ambiguous: goal`; current progress bytes remain unchanged. A matching-hash attempt to save over `{broken` also exits 2 and preserves the corrupt bytes. This confirms the reported defect is closed without weakening corrupt-state preservation. The parent separately reports 16 CLI tests passing; this review's evidence is the independent re-probe, not that unobserved report.

## Resource-by-resource inspection

- `SKILL.md`: activation includes established practice/resume and excludes concrete factual/work requests; intake asks one consequential question at a time; unknown and zero are distinguished. Initial and later output contracts are explicit. No stale requirement to install a reference project, force Socratic withholding, create reminders or upload materials was found.
- `references/domains.md`: Cramer's-rule arithmetic is internally correct; nonzero and singular cases distinguish consistency. Programming checks code and reasoning. Repository imports are separated from runtime flow (`:21`). Music guidance totals 15 minutes and discloses perception limits (`:29`). Physical guidance (`:33–37`) gives a useful qualified-supervision route and prohibits solo hazardous progressions/readiness certification without expanding all movement instruction into warnings.
- `references/research.md`: current subject/source inspection is required, with proportional rechecking. Named projects are conditional. Build Your Own X list rights are separated from tutorial rights (`:20–22`). Understand Anything's runtime, writes, model usage, unverified revision/cost and authorization boundaries are retained (`:26–30`). Learning-method citations do not claim universal mastery criteria or physical readiness.
- `references/state.md`: documented fields, unknown/zero distinctions, evidence scope and cross-field invariants match the helper. Save/show envelope distinction is explicit. Single-writer/hash limits and absence of an all-file transaction are disclosed. Recovery preserves corrupt state and requires independently validating backup; unknown versions do not silently migrate. Multiple plausible journeys require selection before writes.
- `references/progress.schema.json`: required/nested keys, types, enums, string constraints and date-time requirements were inspected directly. Extra properties are rejected. Semantic invariants absent from ordinary JSON Schema are accurately described as additional helper checks. A third-party JSON Schema engine was not available in the default Python environment, so independent schema-engine execution was not performed.
- `templates/plan.md`: fields cover observable goal, baseline assumptions, prerequisites, measurable stages, practice/resources, advancement/review, known constraints, final/retention/transfer checks and next action. It does not manufacture learner evidence.
- `templates/sources.md`: annotated direct-resource links, scope, limitations and actual verification status are required; inaccessible links cannot become claimed inspections.
- `scripts/journey.py`: inspected actual parsing, validation, read/hash, traversal/symlink checks, init, backup and atomic replacement implementation. A demonstrated assessment requires referenced observed evidence, while documentation correctly says the helper cannot judge truth or sufficiency.
- `README.md` and `LICENSE`: installation is optional and explicitly not performed; full folder copying and customization preservation are described. No mandatory Skill Forge, task-checkpoint or named-project dependency. Privacy instructions keep learner records outside the reusable package. Original MIT material is distinguished from external references.
- `tests/test_journey.py`: read actual tests; coverage includes create/save/resume, backup bytes, zero/null, missing fields, duplicate IDs, evidence references, self-report limits, immutable IDs, versions, booleans, corrupt state, stale saves, traversal, symlinks and missing progress. The probes below were independently authored rather than copies of the test implementation.
- `validation/cases.json`: original supplied math/piano/backflip/database/repository/resume cases and requested boundary/fallback cases are present; development/held-out labels and critical failures are explicit. Reading the rubric does not establish behavioral success; model grading remains separate.

## Executed independent CLI probes

All writes were isolated in a temporary directory outside the candidate. Python subprocesses invoked the actual helper. Results:

| Probe | Actual result |
|---|---|
| Init one new `review` journey, then show | Both exit 0; readable state |
| Save `minutes_per_day: 0`, `session_minutes: null` | Exit 0; exact values preserved on show |
| Reuse pre-save hash | Exit 2; current progress and backup bytes both unchanged |
| Validate duplicate `goal` JSON members | Exit 0; optional hardening finding above |
| Replace progress bytes with `{broken`, then show | Exit 2 |
| Save over corrupt current bytes even with matching corrupt-byte hash | Exit 2; corrupt original bytes unchanged |

No media perception, physical readiness, longitudinal retention, native skill installation/discovery or full external integration was executed by this review. No claim about those outcomes follows from static checks or the CLI probes.
