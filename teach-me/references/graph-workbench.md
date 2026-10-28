# Source-grounded graph proposals and explicit edits

`graph_workbench.py` is an original Python 3.9+ standard-library tool. It checks
exact source spans and graph structure, then creates a new normalized graph for
the existing [offline viewer](data-tools.md). It does not call a model, extract
meaning automatically, prove an inference, write back to LearnHarness, or infer
learner mastery. A tutor may draft a proposal from selected text through the
host's normal model tools; inspect that draft before applying it.

The source is a selected UTF-8 file, not a directory to crawl. The proposal and
patch are JSON. All inputs use the existing reader's 8 MiB, strict-JSON,
sensitive-name and symlink-path guards. No stored path, URL, command, HTML or SVG
is followed or executed. Generated graphs remain local unless a separate upload
is authorized. Local file processing does not promise offline model inference.

## Draft, check, then apply

Use [graph-proposal.json](../templates/graph-proposal.json) as a shape template.
Its placeholders are illustrative and are not a validated proposal. Required
top-level keys are exactly `version` (integer 1), `source_sha256`, `nodes` and
`chains`.

- A node has exactly `id`, `name`, `statement` and `evidence`.
- A chain has exactly `id`, `premises`, `conclusion` and `evidence`. Its premise
  IDs are nonempty, distinct and **jointly required**. Separate arguments to one
  conclusion stay separate; duplicate logical arguments are refused.
- Every evidence object has exactly `start`, `end` and `quote`. Offsets count
  Unicode characters in the decoded UTF-8 source, starting at zero; `end` is
  exclusive. No newline normalization occurs. The nonempty quote must match that
  exact slice. Boolean, negative, missing or out-of-range offsets are rejected.
- `source_sha256` hashes the original source bytes, including their exact line
  endings. Node/chain IDs are bounded nonempty text (at most 128 characters),
  without surrounding whitespace or control characters. A proposal permits up
  to 256 nodes and 256 chains; an edited result permits up to 4096 of each.

```sh
python3 /path/to/teach-me/scripts/graph_workbench.py check --source /selected/notes.txt --proposal /approved/proposal.json
python3 /path/to/teach-me/scripts/graph_workbench.py apply --source /selected/notes.txt --proposal /approved/proposal.json --expected-proposal-sha256 HASH-FROM-CHECK --output /approved/new-graph.json --approve
python3 /path/to/teach-me/scripts/learning_data.py view --input /approved/new-graph.json --output /approved/map.html
```

`check` writes nothing. It reports source/proposal hashes, counts, unresolved
endpoint IDs and `ready_without_base`. Exact spans can pass while a proposal
requires existing nodes from a base graph. A missing endpoint is never invented.
`semantic_correctness_verified` is always false: a correct quote does not prove
the proposed statement paraphrases it fairly or that a chain's inference follows.

`apply` requires `--approve` and the exact proposal hash. This acknowledges the
operator's review for this invocation; it is not authentication, independent
human consent, learner endorsement or a verified learning outcome. Existing
session authorization still governs the write. A reversible graph request need
not become an additional user approval ceremony when authorization already covers
it; never claim an actual human reviewed a draft unless that occurred.

To add a proposal to an existing normalized graph, supply `--base PATH` and
`--expected-base-sha256 HASH`. Proposals can reference existing base nodes, but
cannot overwrite any existing node or chain ID; use explicit edits for that.
All final endpoints must resolve. Base source metadata/provenance is retained;
new records use a source-hash identifier and `chars:start:end` provenance anchors.
The helper adds draft/semantic-limit warnings, not mastery scores.

## Explicit graph edits

The patch's top-level keys are exactly `version: 1`, `delete_nodes`,
`delete_chains`, `upsert_nodes` and `upsert_chains`. Delete lists contain distinct
existing IDs. Upsert lists contain complete records in the normalized graph
schema: nodes have `id`, `name`, `statement`, `aliases`, `createdAt`, `provenance`;
chains have `id`, `premises`, `conclusion`, `createdAt`, `provenance`. Each patch
list is limited to 256 entries. The same ID cannot be deleted and upserted in
one patch. Upserts explicitly replace that record, including its provenance;
preserve correct source anchors when preparing the patch.

```sh
python3 /path/to/teach-me/scripts/graph_workbench.py edit --base /approved/graph.json --patch /approved/patch.json --expected-base-sha256 REVIEWED-BASE-HASH --expected-patch-sha256 REVIEWED-PATCH-HASH --output /approved/edited-graph.json --approve
```

Both hashes must match the reviewed bytes. Use an available SHA256 tool or a
read-only file-hash calculation to obtain them. A changed file requires fresh
inspection. Unknown deletions, duplicate/ambiguous IDs, duplicate logical
arguments and dangling final chains are refused. A pre-existing missing endpoint
must be repaired or its chain removed in the resulting patch; it is not silently
reinterpreted. Once final endpoints pass, earlier missing-endpoint warnings are
retained with an `Input history:` prefix rather than presented as current gaps.
Graphs with nonempty session records are refused rather than
discarding learner history.

Every output is create-new; sources and an existing output are never replaced.
Success prints the result path/hash and counts. Invalid inputs, stale hashes,
missing review acknowledgement or I/O errors exit 2 with an explanation. The
shared data publisher checks selected sources again before publication. Those
checks coordinate ordinary stable reads, not hostile concurrent filesystem
replacement or a multi-source transaction.

These tools make source-grounded drafting and explicit editing executable. They
do not supply automatic semantic extraction, a force-directed editor, semantic
search, full native/legacy import support or automatic synchronization. Use the
existing viewer for literal, searchable proposition/AND-group cards. Scientific
truth, useful teaching, valid source interpretation and learner understanding
still need appropriate review and observed evidence.
