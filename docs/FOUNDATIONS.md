# Teach-me foundation research

Build evidence; contains no learner records. Retrieved 2026-10-26 (America/Denver). Bounded search: approximately five minutes; four candidate resources, with three repository candidates inspected. No downloaded code executed or dependencies installed.

## Brief and method

Brief identifier: `teach-me/original-researched-adaptive-local-v1`. A portable tutoring skill must combine proportionate curricula, teaching, performance evidence, local save/resume, and honest tool limits across conceptual, programming, musical and physical learning. Required reference projects are optional resources, never mandatory installations.

Capabilities used: web search, page retrieval, local report writing. Actual search queries:

- `site:github.com "tutor" "SKILL.md" adaptive learning`
- `site:huggingface.co adaptive tutoring learning skill`
- `retrieval practice learning Dunlosky 2013 distributed practice primary paper`

GitHub repository pages and raw files were opened directly. Hugging Face search produced no useful candidate; deeper model/dataset inspection was skipped because the skill needs no model dependency and adding one would add privacy/setup cost without solving its central workflow. Search is targeted, not exhaustive.

Immutable revisions: GitHub commit API retrieval was attempted for all three repository candidates and cstack. The web tool rejected those API URLs; local urllib fallback failed DNS. Commit SHAs are **unverified**. Inspected URLs below track current branches and must be rechecked before component reuse. No source copying is proposed.

## Candidates and adoption

### 1. Build Your Own X — reference

Source: https://github.com/codecrafters-io/build-your-own-x

Inspected: repository `README.md`, specifically Database and Origins & License sections. The README includes a copyright waiver for the list; a standalone `master/LICENSE` request returned 404. That waiver does not establish licenses for linked tutorials. Keep attribution and direct links even when only referencing.

Fit: programming-project selection and prerequisite-aware database learning. The database category links C, Go, Python, Rust and other tutorials. Select by learner language and goal, then inspect the destination; do not present the whole category as a vetted curriculum.

Selected destination inspected: https://cstack.github.io/db_tutorial/; actual `_parts/part1.md` at https://raw.githubusercontent.com/cstack/db_tutorial/master/_parts/part1.md; `LICENSE` at https://github.com/cstack/db_tutorial/blob/master/LICENSE. The license is MIT, copyright Connor Stack 2019. The homepage explicitly says development has stopped. Part 1 assumes C, compilation and a POSIX-style `getline` interface; the sequence proceeds from REPL through memory, tests, disk persistence and B-trees. Reference as a scoped learning project with environment checks and a maintenance caveat; do not claim a complete production database course or imply every platform is supported. No tutorial code/text is copied, so no bundled upstream notice is needed. Code reuse later would require its MIT notice.

### 2. Understand Anything — optional reference/integration

Source: https://github.com/Egonex-AI/Understand-Anything

Inspected files: `README.md`, `LICENSE`, root `package.json`, `understand-anything-plugin/package.json`, and `understand-anything-plugin/skills/understand/SKILL.md` via raw main URLs. MIT license names Yuxiang Lin and Infinite Universe, Inc. Plugin package reports version 2.9.8; immutable revision remains unverified.

Fit: codebase relationships, graph exploration, guided tours and contextual explanation. Its actual skill requires Node ≥22 and pnpm ≥10, may install/build packages, invokes model-assisted analysis, and writes `.ua/` (or legacy `.understand-anything/`). Worktree output may redirect to the main checkout. Thus availability/support in README is not proof of a working integration in this host. No fixed end-to-end price was established; host model usage, analysis size and setup create possible cost. Before proposing execution, verify current install, tools, destinations, privacy and model allowance. Default teach-me behavior should inspect authorized files directly and offer a small textual dependency map. Do not run its installer, auto-update hooks or pipeline just to teach. No upstream component copied; if components are later incorporated, retain MIT notices and inspect file-level rights.

### 3. TuTor — reject as implementation base; reference contrast

Source: https://github.com/kevinnio/tutor

Inspected actual `SKILL.md`, `references/tool-gate.md`, and `LICENSE` through raw master URLs. MIT license, copyright Kevin Perez 2026; skill metadata version 0.6. Its tool gate requires read-only verification and forbids delivering the learner's work, including a complete solution on request. These constraints conflict with teach-me's explicit direct-explanation option and local progress-file writes. Its learn-by-doing and command explanation ideas are useful general practices, but original instructions avoid importing this rigid contract. No files adopted; no copied material or attribution requirement beyond this provenance record.

### 4. Learning research — conceptual reference

Inspected primary review: https://doi.org/10.1177/1529100612453266 — Dunlosky et al. (2013), *Improving Students' Learning With Effective Learning Techniques*. The review compares techniques across learning conditions and supports retrieval and distributed practice without establishing one universal mastery threshold or schedule. Use original, cautious instructions: retrieve, explain, apply, revisit, and adapt by domain and evidence. Do not copy article prose or infer physical-skill readiness from verbal quizzes. The article is copyrighted scholarly material; reference/citation only.

Parent independently inspected the authoritative IES practice guide: https://ies.ed.gov/ncee/wwc/PracticeGuide/1. Search query: `site:ies.ed.gov organizing instruction learning improve student learning spacing quizzing worked examples practice guide`. Parent reports guidance for spacing, worked-example/problem interleaving and quizzing, with distinct evidence levels. Mark this as parent evidence rather than a second independent inspection. Do not flatten evidence ratings into universal prescriptions.

## Integration plan and checks

Adopt **no third-party code or skill text**. Author an original concise skill, domain guidance, source-selection instructions, documented local state and deterministic state helper. This is smaller and more portable than either existing project. Original material may use proposed MIT licensing without relicensing reference resources.

1. Preserve named reference links and maintenance/setup caveats in a conditional resource guide.
2. For database acceptance, verify the list category and selected tutorial, assess language/environment prerequisites, then stage a modest REPL → records → tests → persistence → indexing project. Assess explanation as well as execution.
3. For repository acceptance, inspect only authorized repository content. Use graph/tour ideas without requiring Understand Anything; independently check existing graph claims against source files before teaching them.
4. For learning research, distinguish supported general methods from practical teaching choices; research subject-specific pedagogy when a journey begins and recheck only when needed.
5. Confirm the delivered skill functions without these repositories, Node, pnpm, Skill Forge, a paid service or a media tool. Verify that absence produces disclosed limitations, never invented access or observations.

No material blocker or additional user decision was found. External installation/runtime compatibility, exact current model cost and immutable upstream SHAs remain unverified. These limits do not block an original skill using references rather than bundled integrations.


## v0.2.0 harness references

See the [pinned file-level inspection and adoption decisions](../validation/v0.2.0/foundation-report.md). Both new guides and all companion templates are original MIT material; upstream applications and readers are not bundled.


## v0.3.0 original local tools

The [targeted source-format inspection](../validation/v0.3.0/foundation-update.md) and [independent source review](../validation/v0.3.0/source-review.json) record the pinned native-v1 data facts and scope. The bundled readers/viewer, local locks, manual transfer and bounded runner are original MIT code; no upstream AGPL reader or prompt is copied. Their contracts and limits are in [the v0.3.0 report](V0.3.0.md).


## v0.4.0 original local extensions

The graph workbench and journey versions reuse this project’s MIT normalized data, safe publishing, archive and lock helpers. [Graph foundation inspection](../validation/v0.4.0/graph-component/component-report.md) and [versions foundation inspection](../validation/v0.4.0/versions-component/component-report.md) record actual reused files and scope. No new upstream dependency, model/dataset license, copied AGPL reader or paid runtime is introduced. Exact source spans do not establish semantic truth.

## v0.5.0 original extension

Typed asset transport and hash-bound consistency review extend this repository’s MIT modules. The prior pinned foundation inspection remains applicable. No new upstream code, reader or prompt is bundled; proposal validation reuses this skill’s original quote/hash checks. Recorded judgments do not automate semantic truth or learning efficacy.

## v0.6.0 original extension

The review-history and snapshot-maintenance tools extend this repository’s MIT receipt, storage and snapshot validators using Python standard-library code. Prior pinned foundation findings remain applicable. No upstream prompt, reader or AGPL implementation is bundled. Hash chains record local integrity, not authenticated identity or semantic truth.
