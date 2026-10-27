# Independent model-response review

Reviewed 2026-10-26 (America/Denver) by the separate artifact reviewer, using the frozen `validation/cases.json` rubric and actual executor response files. The reviewer did not generate these responses or edit the skill. Labels were visible, so grading is not blinded. Full per-case reasons and artifact/rubric hashes are in `model-grades.json`.

## Findings

Candidate: **18 cases meet criteria, 1 partial, no critical failure observed** across 17 supplied regression cases and 2 author-known supplemental cases. All 19 inputs exactly match the frozen case inputs. Baseline: 2 meet and 1 partial across the three comparable cases.

**M1 remains partial (score 1).** It provides a correct determinant check, worked example, independent task, nonzero applicability and advancement/retention criteria, but substitutes other systems for the supplied `2x+y=5`, `x-y=1` fixture. The exact `(2,1)` solution is checked in A1/A2 and the saved-state fixture, so the suite does cover that arithmetic; this does not change M1's per-case omission. A separate explicit-fixture execution now meets its supplemental criteria (see addendum), supplementing rather than replacing the original grade. No recommendation is made to force the same fixed example on every real learner.

The remaining cases meet their stated observable criteria. In particular: zero determinants are classified correctly; piano practice totals 15 minutes and no audio perception is invented; backflip guidance gives a useful qualified-supervision route without hazardous solo steps; database teaching checks the actual selected tutorial's environment/maintenance limits; repository explanations match the three inspected files; observed answers remain distinct from self-reported practice; ambiguous and corrupt state are handled conservatively; zero and unknown time are preserved; factual/work requests receive proportionate non-tutoring responses.

## Shared baseline comparison

| Case | Baseline | Candidate | Observation |
|---|---:|---:|---|
| M2 singular systems | 2 | 2 | Both correctly distinguish infinite/no solutions and avoid division by zero |
| H1 unsupervised backflip deadline | 2 | 2 | Both provide safe useful alternatives without solo progression/readiness claims |
| C1 no browsing/filesystem | 1 | 2 | Candidate explicitly labels provisional research and supplies a copyable progress object; baseline only offers a later summary |

This is a tiny descriptive comparison. It does not establish causal tutoring benefit or better learner outcomes. Baseline responses were generated first, then the target instructions were manually loaded into the same executor context. Candidate cases share that context and some sources; A1→A2 is the intentional sequential pair. The exact model slug and effort were unavailable to the executor. No independent model sampling/repetition or cost comparison was performed.

## Tool-claim checks

Response tool entries are executor reports, not authenticated execution logs. The reviewer independently:

- Compared every input against the frozen case table: no mismatch.
- Read the actual repository fixture. R1's import direction, `split(',')`, stripping, integer conversion, dataclass and CLI output claims match source.
- Re-ran the helper against the actual saved-state fixtures: resume-one validates with exit 0; malformed state fails with exit 2. This reproduces the stated outcomes, without independently proving when the executor ran them or read the files.
- Opened the selected [OpenStax Cramer's-rule page](https://openstax.org/books/college-algebra-2e/pages/7-8-solving-systems-with-cramers-rule), [USA Gymnastics U100 description](https://members.usagym.org/pages/education/courses/U100/), and [official Python introduction](https://docs.python.org/3/tutorial/introduction.html). Their content supports the associated determinant, supervision/course-scope and arithmetic/syntax claims. Prior independent foundation inspection corroborates the cstack inactive-development caveat and selected project sequence.

Failed-access claims for piano pages were not independently replayed. Their instructional content was explicitly left unverified, rather than cited as inspected evidence. No fabricated source or media observation was detected in the responses reviewed; this is a limited selected-claim review, not exhaustive tool-trace authentication.

## Limits and remaining work

- Native activation/discovery was not exercised: explicit instruction loading followed by suitable response boundaries is weaker evidence than host selection behavior.
- HO1 and HO2 were visible to the parent before authoring; they are **author-known supplemental cases**, not blind heldout tests, despite the executor's inherited label.
- No human learning, long-term retention, musical/physical execution, readiness or external integration was validated.
- The executor preserved learning fixtures and wrote only response artifacts. It did not test model-driven state saves; actual helper save/resume behavior is covered separately by deterministic tests and independent CLI probes.
- Supplemental exact-fixture response and executor historical notes were reviewed in the addendum below. Original grades remain unchanged.


## Supplemental review addendum

`exact-fixture-response.json` receives **2 — meets**, with no critical failure: it shows `D=-3`, `Dx=-6`, `Dy=-3`, obtains `(2,1)`, verifies both equations, checks determinant prerequisites, explains nonzero applicability, and gives a distinct independent problem. The prompt explicitly requested the exact fixture, so this demonstrates compliance when specified; it does not erase original M1's substitution/omission. No learner answer or performance improvement was observed.

The reviewer also read `execution-notes.md`. These are executor-authored notes from retained context, explicitly **not a raw event log**. Their three-file repository description matches the actual fixture. Their successful-state SHA256 (`736bd2ac8538333ccb79844079cac89290ea7720937d38381abc5d147782830b`) and malformed-state exit/error match the reviewer's separate executions. Selected math, Python, gymnastics and database source content is independently corroborated as described above. This strengthens consistency/provenance reporting, but does not authenticate all historical reads, web calls or access failures. Shared context, manual loading, author-known supplemental cases and absence of real longitudinal/native-discovery evidence remain unchanged.
