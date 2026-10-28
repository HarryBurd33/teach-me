# Current v0.5.0 validation

See [the current release report](V0.5.0.md): 178 candidate/installed checks, independent failure review and scoped simulated responses. The following sections retain historical results and limitations.

# Current v0.4.0 validation

See [the current release report](V0.4.0.md). Prior sections preserve historical v0.3.0 and older results, partials and limits.

# Current v0.3.0 validation

See [the current release report](V0.3.0.md). The following record preserves earlier v0.2.0/v0.1.0 evidence and limits.

# Validation and limits

Current v0.2.0 evidence and limitations are in [the release report](V0.2.0.md). The sections below preserve **historical v0.1.0** trials and their original limits; they do not describe a new full trial of v0.2.0.

## Deterministic checks

The actual journey helper has 16 executed tests covering create/save/read/resume, byte-preserving backup, stale and corrupt state, zero versus unknown and missing time, strict schema/version/type checks, duplicate JSON members, evidence references and observed-versus-reported rules, immutable IDs, traversal, symlinks, and missing files. Run `python3 -m unittest discover -s tests -v` from the repository root. `scripts/check_release.py` independently checks required assets, local Markdown links, JSON syntax, and consistent root/skill MIT licenses.

## Actual model trials

The original build used a separate executor context with manually loaded instructions and synthetic learner prompts. All 19 exact inputs matched a frozen case table. Independent non-blind grading found 18 meet criteria, one partial, and no critical failures. The first Cramer's-rule response used different valid examples than the specified fixture; its partial score is preserved. A supplemental trial explicitly requested `2x+y=5`, `x-y=1` and passed with `D=-3`, `Dx=-6`, `Dy=-3`, `(x,y)=(2,1)`, both substitution checks, and a separate practice problem.

The three shared direct-prompt baseline cases yielded two ties and stronger provisional/export handling for the skill in the no-browsing/no-files scenario. This tiny comparison is descriptive, not causal evidence. The two nominal heldout cases were visible to the parent before authoring and count only as author-known supplemental checks. Exact model slug/effort and task cost were unavailable. Candidate cases share one executor context; A1→A2 is a staged pair. Historical tool notes summarize retained context rather than authenticated raw logs. Selected claims and fixture validator outcomes were independently corroborated.

See the [frozen cases](../validation/cases.json), [baseline](../validation/baseline-responses.json), [candidate](../validation/candidate-responses.json), [exact fixture](../validation/exact-fixture-response.json), [grades](../validation/model-grades.json), [review](../validation/model-review.md), [executor notes](../validation/execution-notes.md), and [independent artifact review](../validation/independent-review.md). Older hashes and statements in these files describe their original review snapshot; current release structure is checked by CI. No teaching instructions or helper behavior changed for publication; installation documentation and the schema identifier were clarified.

## Local installation and public CI

Global installation, exact file integrity, native user-scope discovery from two directories, installed-helper tests, and four public CI jobs were verified separately after publication. See [release verification](INSTALLATION-VERIFICATION.md). These new checks do not retroactively alter the original model-trial grades.

## What is not established

No real learner outcome, longitudinal retention, physical or musical execution/readiness, cross-device synchronization, full Understand Anything integration, or model-driven state-saving behavior was validated. Actual helper saving/resuming is tested separately. Explicitly loaded response boundaries do not prove automatic host selection. Native discovery/installation is host-specific and should be checked on the target machine. Python and tests cannot certify instructional quality, citation truth, evidence sufficiency, or mastery.

Piano source attempts in the model trial were inaccessible; the response disclosed that and used a provisional sequence. Upstream immutable revisions, full integration costs/compatibility, and future URL availability were unverified. Optional resources are inspected again when selected for an actual journey. State writing requires one writer and an authorized workspace. The public repository contains only source and synthetic validation fixtures, never real learner records.
