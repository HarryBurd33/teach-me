# Offline graph editor

Use this optional editor for an explicit concept-map edit during a learning journey or a requested graph-editing task. It stages full-record changes in browser memory and downloads a draft. It makes no requests and does not write the source graph. Opening HTML does not apply any change.

The editor accepts a graph-only `teach-me-learning-v1` JSON document, at most 2 MiB with at most 256 nodes and 256 chains. Session data is refused rather than discarded. Existing metadata, source-file records, and warnings remain in the graph. Initial unresolved endpoints can be rendered for repair; a checked draft must resolve all endpoints. Each chain's premises are jointly required, not alternatives.

```sh
python3 scripts/graph_editor.py render --input graph.json --output editor.html
```

Open `editor.html` locally. Search and select a record; stage additions, updates, and deletions. Existing IDs are immutable through editing: delete/add is explicit. Referenced-node deletion is refused; repair or remove the chain explicitly. Reset restores the loaded base. Export is enabled only when the final staged graph passes structural validation and bounds. Export downloads `teach-me-graph-draft.json`; move that file to your chosen working directory. Existing aliases, creation times, and provenance are preserved by field edits. New nodes use `aliases: []`, `createdAt: ""`, and `provenance: []`; new chains use the same unknown creation time and empty provenance.

Review the staged claims and the downloaded file, then check it against the exact selected base bytes:

```sh
python3 scripts/graph_editor.py check --base graph.json --draft teach-me-graph-draft.json
```

`check` writes nothing. It returns the SHA256 of the exact draft bytes, base SHA256, structural counts, and `semantic_correctness_verified: false`. Use its `draft_sha256` in an explicit apply:

```sh
python3 scripts/graph_editor.py apply --base graph.json --draft teach-me-graph-draft.json --expected-draft-sha256 SHA_FROM_CHECK --output edited-graph.json --approve
```

`--approve` acknowledges operator review. It does not authenticate human consent. Apply requires both the exact reviewed draft digest and its embedded base digest; formatting-only file changes also change these digests. Output is create-new, never an overwrite. Source files are rechecked during publication, and an existing output or a changed source causes refusal. To revise a draft, check its new bytes again and choose a new output path. Keep the original base for inspection.

The draft has exactly `version`, `base_sha256`, and `patch` keys. Version is integer `1`; the digest is lowercase SHA256. The patch has exactly `version`, `delete_nodes`, `delete_chains`, `upsert_nodes`, and `upsert_chains` keys and uses the workbench full-record contract. Unknown fields, duplicate JSON members or IDs, overlapping delete/upsert IDs, unknown deletes, malformed IDs, duplicate logical arguments, empty/duplicate premises, and unresolved final endpoints are refused. Both input files are limited to 2 MiB. Rendered HTML is limited to 32 MiB.

Manual edits are operator assertions, not new source provenance. Structural checks do not verify semantic truth, inference, source support, endorsement, or learner mastery. Existing provenance remains historical metadata when a claim changes; examine whether it still supports the claim. Apply retains existing warnings and adds explicit edit/evidence-limit notices.

The generated HTML bundles its JavaScript and CSS with exact SHA256 CSP hashes and escaped JSON. Its content security policy denies external resources, network requests, object embeds, and base URL changes. Staging uses no local storage, autosave, service worker, provider calls, or direct graph writeback. Reopening the HTML begins from its embedded base, so export work you intend to retain. This is a searchable form/card editor; it makes no semantic-search or force-layout claim.
