# Adapt by domain

Use these decisions conditionally. They are teaching guidance, not a fixed course or a substitute for researching the subject.

## Mathematics and concepts

Ask for reasoning, test boundary cases, and use unfamiliar examples. Separate arithmetic slips from a conceptual error. For Cramer's rule, first check a 2×2 determinant and simultaneous-equation meaning. Explain that the rule gives a unique solution for a square system only when its coefficient determinant is nonzero.

Builder-verified arithmetic fixture: `2x + y = 5`, `x − y = 1`. `D = −3`, `Dx = −6`, `Dy = −3`, so `x = 2`, `y = 1`; substitution verifies both. Use a different independent problem after a worked example. Do not present the same worked solution as independent evidence.

Zero determinant requires another method to distinguish consistency. `x+y=2`, `2x+2y=4` has infinitely many solutions; replacing the final `4` with `5` makes it inconsistent. Do not divide by zero or infer no solution from singularity alone. A useful transfer check asks the learner to explain the distinction without relying only on a formula.

For a way of thinking, such as probability, teach assumptions, a concrete case, a misleading near-neighbor, limits of the model, and an application outside the original example. Ask what evidence would change the answer.

## Programming and repositories

Choose a small useful artifact, inspectable code, meaningful tests, and an explanation of design decisions. Preserve space for the learner to do work. Inspect the learner's actual output; a tutorial followed successfully is not proof they understand every part. Use an extension, fault diagnosis, or unfamiliar input to test transfer. Never run untrusted code just to establish a baseline.

For a database project, check language, compilation environment, file handling, and test experience. The [Build Your Own X database category](https://github.com/codecrafters-io/build-your-own-x#build-your-own-database) is a discovery source. Inspect the selected destination before recommending it. For a C learner, [cstack's SQLite-style tutorial](https://cstack.github.io/db_tutorial/) is a possible sequence; its homepage reports inactive development. Check the environment and maintenance limitations. A manageable original outline is REPL → in-memory records and tests → disk persistence → indexing, with failure cases and explanations at each stage. Do not imply this builds a production database.

For a codebase, inspect authorized overview, entry points, a narrow execution path, tests, and dependencies. State which files were inspected. Explain import direction separately from runtime flow. For `cli → parser → model`, a tour can introduce the record contract, parsing, then CLI orchestration, followed by tracing one input end to end. Verify generated graph claims against source. Do not claim whole-repository coverage from a few files.

[Understand Anything](https://github.com/Egonex-AI/Understand-Anything) can help with graphs and tours, but it is optional. Read [research guidance](research.md) and its current documentation before proposing integration. A text map and source-grounded trace must remain useful without it.

## Music and other performance

Adapt to the instrument, access, space, and feedback channel. Define observable micro-goals: a small pattern, controlled tempo, rhythmic accuracy, or a short phrase. Explain how the learner can check it and distinguish their report from inspected performance. An inspected recording supports only what can actually be assessed through that recording; it cannot establish posture or technique outside the frame/channel.

For a beginner with a keyboard and 15 minutes daily, a *proposed* session could be 2 minutes of comfortable setup/key finding, 4 minutes of a small rhythm or note pattern, 6 minutes of a short phrase in small sections, and 3 minutes of recall and notes. Adjust from feedback; discomfort is a reason to stop and seek appropriate instruction. Do not prescribe a fixed tempo target before a baseline or promise a song by a date. With no audio capability, use text-described note/rhythm tasks, a learner-kept error count, or qualified teacher feedback; do not say you heard their playing.

## Physical skills

Separate a learning roadmap from instructions to attempt a hazardous maneuver. Account for equipment, environment, preparation, and qualified supervision before dependent physical practice. Do not provide medical clearance or certify readiness remotely.

For “teach me a backflip by this weekend; no coach,” explain that the deadline and absent supervision do not support a safe attempt. Offer a concrete route: find a qualified gymnastics/tumbling coach and appropriate facility, share the goal and current experience, have the coach assess prerequisites and select progressions, and use the weekend to arrange assessment and understand the supervised plan. General comfortable conditioning and equipment/logistics discussion can be useful; it must not become a solo inversion, launch, rotation, landing, spotting, trampoline, or improvised-mat progression. Do not imply generic conditioning proves readiness. No achievement guarantee, remote clearance, or suggestion that a friend substitutes for a qualified coach.

For lower-risk physical skills, keep instruction proportional to actual risk and available evidence. Do not turn every movement question into a warning checklist. Research current qualified instructional sources when constructing a physical-skill journey.
