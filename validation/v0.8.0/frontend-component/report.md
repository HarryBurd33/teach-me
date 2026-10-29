# Frontend component report

Implemented the three offline graph editor assets. Parent acceptance criteria and its timestamp correction are controlling: new records use `createdAt: ''`, not null, to preserve the normalized schema. This worker changed no backend, global installation, public delivery, checkpoint or frozen criteria files.

The editor stages claim and argument edits in memory, retains complete existing record metadata, preserves metadata even when a deleted base ID is restored, refuses referenced claim deletion, preserves AND premise lists, and renders searchable cards through `textContent`. Forms expose only the requested fields, with IDs read only during selection. Missing endpoints may be repaired incrementally. Duplicate logical arguments, unresolved endpoints, graph/patch record limits and UTF-8 draft byte limits block export.

Export is explicit, populates the read-only `exported-draft` textarea, and starts a Blob download named `teach-me-graph-draft.json`. Changes after export clear the prior copy. Reset returns all staged records to the base. No persistence, network, external assets, service worker, dynamic evaluation, or browser source writeback is used. CSP hashes bind the exact inline script/style file bytes. All five template markers occur once.

## Actual validation

Command: `python3 .forge/teach-me-v0.8.0/frontend-component/test_editor_assets.py`

Two bounded passes completed. First pass: three checks passed. Second pass: review identified possible metadata loss when restoring a deleted base ID; fixed the constructors to clone the original record, added regression assertions, and all three checks passed again. The checks cover template/CSP/static DOM safety/labels/responsiveness, Node syntax, and interaction execution in a minimal DOM adapter. Interaction assertions include full-record metadata, added-record defaults, AND premise retention, reference refusal, immutable selected IDs, duplicate ID/premise/logical handling, search, inert hostile text, gradual unresolved-endpoint repair, explicit Blob export/schema, reset, 256-record cap, UTF-8 2 MiB cap, and Unicode ID length.

The adapter is not an actual browser. This worker makes no browser/CSP-enforcement/download-availability/visual-layout acceptance claim. Parent actual browser QA and CLI check/apply are remaining integration gates.

## Stable controls and browser QA

- Claim: `node-select`, `node-new`, `node-form`, `node-id`, `node-name`, `node-statement`, `node-save`, `node-delete`.
- Argument: `chain-select`, `chain-new`, `chain-form`, `chain-id`, `chain-premises`, `chain-conclusion`, `chain-save`, `chain-delete`.
- State: `graph-search`, `graph-cards`, `graph-summary`, `action-status`, `pending-summary`, `pending-changes`, `validation-messages`, `base-warnings`.
- Output: `reset-all`, `export-draft`, `exported-draft`, `base-digest`.

Suggested actual browser flow:

1. Render a graph with claims `a`, `b`, `c` and argument `ab` (`a AND b ⇒ c`). Confirm initial cards and no download.
2. Select `a`, verify its ID is read only, edit its name/statement and stage. Confirm pending state.
3. Click delete for `a`. Confirm status reports the reference and the record remains.
4. Click New argument; enter a new ID, premise IDs `a` and `b` on separate lines, and a distinct conclusion (add a new claim first if necessary). Confirm every premise appears with AND.
5. Enter a hostile name/statement such as `</script><img src=x onerror=alert(1)>`; confirm it displays as text without new markup or alert.
6. Export. Read `exported-draft.value` if the browser tool cannot retrieve the download. Confirm exact schema, retained metadata and new-record defaults; pass those exact UTF-8 bytes to CLI `check` and digest-bound `apply`.
7. Stage another edit; confirm exported copy clears. Reset; confirm no pending changes and base values return.
8. Render a graph with missing endpoints. Confirm export is disabled; add missing claims one at a time and confirm export enables only after all endpoints resolve.
9. Narrow the viewport and inspect labeled form/card flow and keyboard focus visibility. Verify source base remains unchanged after applying to a new output.
