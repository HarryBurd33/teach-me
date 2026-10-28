# Read-only learning-data tools

`learning_data.py` is an original Python 3.9+ standard-library adapter for a
**documented subset of LearnHarness native format 1**, plus a local knowledge-map
viewer. It does not install LearnHarness, call a model, infer mastery, extract a
new graph from prose, migrate source data, or write back to the upstream app.
Missing version means native v1; future versions and pre-native `parts`/UIMessage
records are rejected. This is tested format handling, not complete application
compatibility or a native round-trip exporter.

## Select files, then create a separate report

Inspect only files relevant to the authorized learning question. Choose explicit
paths and put generated reports outside the original app/export directory. The
script never searches a profile or follows source paths, research URLs, media,
PDF references or embedded commands. It excludes sensitive names such as
`auth.json`, `settings.json`, `.env*`, credentials and provider-debug paths, plus
symlinked files or ancestors. Use the actual canonical path on systems where
`/tmp` or `/var` is a symlink; the tool does not silently resolve those aliases.
The caller still decides which non-secret learning files may be read.

```sh
python3 /path/to/teach-me/scripts/learning_data.py session --input /selected/export/chats/session.json --output /approved/reports/session.json
python3 /path/to/teach-me/scripts/learning_data.py graph --nodes /selected/export/graph/nodes.jsonl --chains /selected/export/graph/chains.jsonl --format /selected/export/graph/format.json --output /approved/reports/graph.json
python3 /path/to/teach-me/scripts/learning_data.py view --input /approved/reports/graph.json --output /approved/reports/map.html
```

The optional graph `--format` selects its explicit version-stamp file; without
it, unstamped native v1 is assumed. Output parents must exist. Outputs are
**create-new only**; existing reports, symlink destinations and source replacement
are refused. Success prints the output path/hash; an error prints a reason to
stderr and exits 2. No credentials, installs or network access are required.

Each input is limited to 8 MiB. JSON output is limited to 8 MiB and HTML to
32 MiB. Duplicate JSON members, nonfinite numbers, invalid required shapes and
unsupported roles/blocks fail rather than silently count as valid. Unknown
unneeded source metadata is ignored. Historical object fields encoded as JSON
strings are decoded in memory only. Source files are checked before/after reads
and again before publication; hashes identify the inspected bytes. This detects
ordinary concurrent changes, but is not an atomic multi-file snapshot, source
lock or defense against a hostile filesystem race. Close the source app or use a
stable export when consistency matters. A hard interruption may leave an
incomplete newly created report; validate or recreate that report rather than
altering the source.

## Report contract

All reports have exactly these top-level fields:

| Field | Meaning |
| --- | --- |
| `format` | Literal `teach-me-learning-v1` |
| `source_files` | Selected file basename and SHA-256; no absolute source path or automatic reference following |
| `sessions` | `{id, title, kind, events}`; `kind` is teach/practice, events retain source message ID and sequence |
| `nodes` | `{id, name, statement, aliases, createdAt, provenance}` |
| `chains` | `{id, premises, conclusion, createdAt, provenance}`; premises jointly required |
| `warnings` | Explicit incomplete/unsupported evidence distinctions and missing endpoints |

Session events distinguish learner text, teacher text, question/operation,
learner response, failed/unstructured/operation result, practice attempt,
delivered artifact and application marker. A question has an occurrence-specific
`event_id`, `call_id`, tool, question, `teacher_committed` payload and final status.
A response refers to its `question_event_id` and stores three separate objects:
`snapshot` (displayed question/options and recorded mechanical grading), `learner`
(actual selected answers/free text/confidence/short explanation), and
`teacher_payload` (committed answer/explanation). Compact result content is kept
separately with attribution rather than overriding the richer snapshot. No
numeric mastery field is generated.

Results join the nearest matching **preceding** call occurrence. A conflicting
tool name, orphan result, ambiguous duplicate message ID or malformed answer
shape is refused. Displayed answer labels/values/indices are retained as stored;
indices are never applied to the teacher's possibly different authored ordering. A conflicting displayed snapshot/answer tuple stays unchanged with a warning.
A pending key, teacher-only result, problem-delivery acknowledgement or failed call is not a learner response. Confirmed confidence zero
stays zero; missing/null stays unknown. It is self-reported confidence, not
competence. A stored 50 cannot establish whether a slider default was deliberate.

Learner `practice-thinking` attempts retain their order and problem occurrence;
agent `thinking` blocks are omitted. Other custom markers remain labeled as app
metadata, not learner speech. Delivered briefs/notes and citation page lists can
be retained, while executable HTML/SVG and encoded media are omitted, not run or
inspected. The adapter does not preserve every app field or operation, extract
session plans/usage/settings, or interpret every legacy custom payload. Retain
the original record if later analysis needs those fields.

Graph normalization follows the inspected format's exact merge rules: the first
assertion defines a node's name/statement/date; later nonempty statements and
aliases join aliases, and exact provenance pairs union in encounter order.
Different node IDs are not collapsed by similar labels. Chains merge by sorted
premise IDs plus conclusion, retaining the first ID, premise order and date.
Separate arguments to the same conclusion remain separate. This subset requires nonempty unique premise IDs and the documented node/chain date fields; unsupported shapes are refused. Missing endpoints
produce warnings; no replacement proposition is invented. Source metadata,
extraction coverage and session-index reconstruction are outside this adapter.
Graph presence, frequency and provenance never establish learner mastery.

## Local viewer and remaining limits

Open the generated HTML file in a supported browser. It has no external assets or
network requests, uses text-only DOM rendering for imported labels, and searches
claims, IDs, aliases and provenance. Each argument shows its jointly required
premises as an **AND** group leading to its conclusion. Missing nodes and warnings
remain visible. It is a searchable argument-card view, not a force-directed graph
editor, semantic search engine or automatic extraction service. Session-only
reports have no graph cards; inspect their JSON for event evidence.

The Python commands do not send data to a model. An agent or host may separately
send inspected records as model context; local storage is not a promise of offline
model processing. Minimize learner details and authorize any upload separately.
For tutoring interpretation and evidence boundaries, read
[the learning-harness guide](learning-harness.md).

## Source and rights

The builder inspected the [native format reference at revision
3dc8847](https://github.com/amosblomqvist/learnharness/blob/3dc88472eea41eed0d5e5f29c2f16f8d063c415b/skills/learnharness/references/data-format.md)
on 2026-10-28. The upstream skill/readers are AGPL-3.0-only and are not bundled or
relicensed. This adapter, tests and viewer are original MIT implementations of
observed data-format facts; no upstream reader or prompt code was copied.
