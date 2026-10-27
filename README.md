# teach-me

A Codex skill for researched curricula, adaptive tutoring, and local progress records. Learn a small concept in one lesson or work through a staged practical project. It combines teaching with practice and feedback, rather than stopping at a reading list.

## Install globally in Codex

Ask Codex:

> Use $skill-installer to install the teach-me folder from https://github.com/HarryBurd33/teach-me into ~/.agents/skills.

Or install manually after inspecting the source:

```sh
git clone https://github.com/HarryBurd33/teach-me.git teach-me-skill
mkdir -p ~/.agents/skills
if [ ! -e ~/.agents/skills/teach-me ] && [ ! -L ~/.agents/skills/teach-me ]; then
  cp -R teach-me-skill/teach-me ~/.agents/skills/teach-me
else
  echo 'An existing teach-me copy needs review; nothing was overwritten.'
fi
```

Copy the complete folder, including references, templates, and scripts. Codex detects skills automatically; it should be available on your next turn. Restart Codex if it does not appear. This user-scoped location applies across local Codex projects on that machine; other computers and cloud executors need their own installation. [Official OpenAI skill documentation](https://learn.chatgpt.com/docs/build-skills).

## Use it

Mention `$teach-me` explicitly, then describe the ability you want:

```text
$teach-me Teach me Cramer's rule. I know basic algebra.
$teach-me Help me learn piano. I have a keyboard and 15 minutes daily.
$teach-me Teach me how databases work by building one. I know basic C.
$teach-me Help me understand this repository, starting with one request path.
$teach-me Teach me probability, statistics, and Python, 30 minutes three days each week.
```

You can include your goal, current experience, available time, equipment, and constraints. Only a topic is required. The tutor checks prerequisites when useful, proposes a proportionate sequence, starts with a lesson or diagnostic, then adapts to your answers. Ask for hints, a different explanation, or a complete explanation when needed.

For an ongoing journey, give it an approved writable workspace:

```text
$teach-me Save this journey in the current workspace and continue teaching me probability.
$teach-me Resume the probability journey at /path/to/workspace/learning/probability.
```

Keep that folder available in the next chat. Resume is file-based; it is not automatic memory or cross-device synchronization. A quick definition or a request to build something does not automatically become a curriculum.

## What it supports

| Workflow | Behavior | Requirements and limits |
|---|---|---|
| Curriculum and first lesson | Target abilities, prerequisites, practice, advancement/review, final and retention/transfer checks | No guaranteed completion timeline or learning outcome |
| Adaptive tutoring | Feedback from submitted reasoning/artifacts; smaller steps or prerequisite review when needed | Confidence, reading, and elapsed time do not establish mastery |
| Researched resources | Subject-specific authoritative sources; annotated direct links | Web search/retrieval; without it, a provisional approach with no invented citations |
| Local save/resume | Separate `plan.md`, `progress.json`, `sources.md` per journey | Authorized files; without access, explicit unsaved export |
| Mathematics and programming | Reasoning checks, boundary cases, inspectable projects and meaningful tests | Execution tools useful; do not run untrusted code automatically |
| Music/performance feedback | Focused practice and scoped evidence | Only inspect media the host supports; reports remain self-reported |
| Physical-skill planning | Qualified-supervision roadmap and appropriate preparation | No hazardous solo progression, medical clearance, or remote readiness certification |
| Optional project resources | Build Your Own X and Understand Anything when they fit | No required installation or paid service; verify current prerequisites, rights, privacy and cost before integration |

Text is the baseline interface. Full researched/local experience needs web tools and a writable workspace. The optional state helper needs **Python 3.9+**, standard library only. The skill needs no API key, Skill Forge, task-checkpoint, Node, or external project installation. Model use remains subject to the host's ordinary account limits.

## State helper

```sh
python3 teach-me/scripts/journey.py --help
python3 teach-me/scripts/journey.py init --root /approved/workspace --id algebra --topic 'Linear systems' --goal 'Solve and explain 2x2 systems'
python3 teach-me/scripts/journey.py show --journey /approved/workspace/learning/algebra
```

For save commands, exact schema, backup/stale-write behavior, and malformed-state recovery, read [state.md](teach-me/references/state.md). One writer at a time; atomic progress replacement is not a multi-file transaction or concurrency fence. A schema-valid record does not prove competence.

## Validation and contributions

```sh
python3 -m unittest discover -s tests -v
python3 scripts/check_release.py
```

The deterministic helper suite has 16 tests. The initial model evaluation contains 19 simulated prompts: 18 meet their criteria, one is partial, and no critical failure was observed; an additional explicit math-fixture trial passes. This is limited manually loaded model evidence, not proof of real learning outcomes or automatic activation. See [release/installation verification](docs/INSTALLATION-VERIFICATION.md), [validation and limitations](docs/VALIDATION.md), [actual model outputs](validation/candidate-responses.json), and [independent grades](validation/model-review.md). The CI workflow runs deterministic checks across selected Python versions and operating systems; its status is evidence of those checks only.

Keep learner records, credentials, checkpoint state, and private transcripts out of contributions. Preserve the evidence distinction, capability fallbacks, and safety boundaries. Run both commands before proposing changes. [Foundation and rights inspection](docs/FOUNDATIONS.md) explains the external references and reuse limits.

## License

Original instructions, templates, schema, tests, and helper code are available under the [MIT License](LICENSE). Referenced projects and publications keep their own licenses and rights; none is a required bundled dependency. No affiliation with OpenAI or the referenced projects is implied.
