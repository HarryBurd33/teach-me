# Research and optional resources

At a journey's start, research the actual subject: what prerequisites matter, what sequence fits the target performance, which practice gives useful feedback, and which sources the learner can use. For a narrow stable concept, a small authoritative source check is enough. Do not browse extensively on every tutoring turn. Recheck changing tooling, selected links, stale claims, or a changed goal.

Use primary research, official technical documentation, authoritative educational institutions, or qualified instructional organizations. Inspect a selected page rather than citing a search snippet. Explain the source's fit and limitations. Label practical teaching choices as choices, not proven universal rules. If a source is inaccessible, say so and choose an accessible substitute; do not claim inspection.

Keep a small annotated source list in `sources.md`: title/URL, role in this curriculum, prerequisite or limitation, verified date and exact scope. Unverified supplied links stay unverified. A retrieval date is not a publication date. Local dates should use the learner's timezone when known.

## Learning-method foundations

These inform original instructions; no source text is bundled:

- [IES: Organizing Instruction and Study to Improve Student Learning](https://ies.ed.gov/ncee/wwc/PracticeGuide/1): reference for spacing, alternating examples with problems, retrieval, and explanatory questions. Its recommendations have different evidence ratings and a content-learning scope. Do not infer a universal schedule or physical-skill readiness rule from it.
- [Dunlosky et al. (2013), Improving Students' Learning With Effective Learning Techniques](https://doi.org/10.1177/1529100612453266): review comparing learning techniques across conditions. Use as research background for retrieval and distributed practice, while checking subject-specific suitability. No guaranteed transfer to every skill is implied.

## Required project references, used conditionally

### Build Your Own X

[Repository](https://github.com/codecrafters-io/build-your-own-x). For related programming goals, inspect the current relevant category, then inspect the chosen tutorial itself. Explain its prerequisites, language/toolchain, maintenance, scope, and why it fits. Link directly to the tutorial in the learner's plan. Do not force it into math, music, or physical learning. The collection's copyright waiver covers its list, not all linked material. Check each destination's reuse rights before copying anything.

The builder inspected the Database category and [cstack tutorial](https://cstack.github.io/db_tutorial/) on 2026-10-26. The tutorial is MIT, copyright Connor Stack 2019, and reports that development stopped. It can be a scoped C learning project, subject to a current environment/source check. No tutorial code or text is copied here; retain its notice if incorporating code later.

### Understand Anything

[Repository](https://github.com/Egonex-AI/Understand-Anything). Potentially useful for codebase maps, dependency relationships, guided tours, and contextual explanations. It is not assumed to be a general tutoring engine. The builder inspected `README.md`, `LICENSE`, package metadata, and `understand-anything-plugin/skills/understand/SKILL.md` on 2026-10-26. The project is MIT; no component is copied here.

The inspected workflow required Node ≥22 and pnpm ≥10, model-assisted analysis, possible package build/install, and local graph files (`.ua/` or a legacy location). Worktree output may target the main checkout. These are observations of inspected documentation, not a compatibility guarantee. Immutable upstream revisions and end-to-end cost were unverified.

Before proposing integration, inspect current documentation and the actual available installation; check supported host/runtime, destinations, privacy of analysis, tool access, model allowance or other costs, and relevant reuse rights. Explain expected benefit and setup. Installation, new dependencies, remote upload, and paid execution require applicable user authorization. Do not run installers or analysis automatically. Default to authorized source inspection and a small text map when integration is absent or unsuitable.

## Provenance and rights

All packaged instructions, templates, schema, and helper code are original to this skill. External projects and research are references, not bundled dependencies. No upstream source was adopted, so the package's MIT license applies only to original material. Verify current root and file-level terms before future component reuse. Do not treat public availability, a repository summary, or this dated note as sufficient evidence of current licensing.

## Learning-harness references (v0.2.0)

Inspected on 2026-10-28 through connected GitHub source reads; no upstream application was executed or bundled.

- [LearnHarness, revision 3dc8847](https://github.com/amosblomqvist/learnharness/tree/3dc88472eea41eed0d5e5f29c2f16f8d063c415b): inspected root and skill licenses, `skills/learnharness/SKILL.md` and `references/data-format.md`. Both license files are AGPLv3; the skill declares AGPL-3.0-only. Its own reader requires Python 3.10+, which is not a Teach-me dependency. Used as a reference for general diagnostic/teaching/practice methods and evidence-aware reading of selected exports. No upstream prompt, code or reader is copied or relicensed. See [our original learning guide](learning-harness.md) for format limits and privacy.
- [WalkingLab course, revision a9342ff](https://github.com/walkinglabs/learn-harness-engineering/tree/a9342ff471f2c0e60be0c08b9f4a7c502df4e442): inspected MIT root license (copyright 2025 WalkingLab), harness-creator skill, P01/P03 project READMEs, lecture 02, P07/P08 project documentation, feature-list/evaluator templates and project tree. Used as a reference for small experiments, verification and handoff; no upstream code or substantial text is copied. P01 includes a finished reference app; P07/P08 documentation links to implementations absent at that revision. Neither a fair comparison nor a running loop follows from copying those artifacts. See [our original engineering guide](harness-engineering.md).

These source observations establish the inspected workflows, not teaching effectiveness, full data compatibility or runtime support. Verify current source and rights before future component reuse. Original MIT material here remains independent of both upstream applications.
