# Recover editing deliberately

The offline editor keeps staged graph changes in page memory. It never autosaves, writes the original graph, or sends graph data to a provider. Closing/reloading the page loses in-memory history and unstaged form text. Export deliberate checkpoints and preserve the original base graph and generated HTML together.

## Undo, redo and reset

Stage a claim/argument edit before using graph undo. Undo and redo restore staged graph records, including retained metadata and all jointly required premises. They do not undo keystrokes in an unsubmitted form; normal text-field undo remains the browser's responsibility. A successful new graph edit after undo clears redo. Failed operations preserve staged work and history. Reset to the embedded base is itself undoable.

History retains at most20 graph steps and8MiB of serialized snapshots across undo and redo. Older steps may be evicted; inspect the status message. History is a bounded convenience, not a durable backup, source history or review receipt.

## Reopen an exported draft

Open the same saved HTML whose displayed base SHA256 matches the draft. Paste the entire exported JSON into the labeled import field, then explicitly import it. Import replaces the staged graph using the original embedded base; it does not merge into current staged edits. Export current work first if you want both versions. A valid import is one undoable action.

Malformed JSON, duplicate keys, unknown fields, excessive nesting, wrong base digest, altered metadata, oversized records/drafts and unresolved final endpoints must be refused without replacing staged work. The draft remains version1 with exactly `version`, `base_sha256` and `patch`; no migration is needed. A differently formatted base file has a different digest even when its claims look the same. Keep both originals and render from the exact matching base; never edit the digest merely to force acceptance.

After importing, inspect the staged change list and warnings, export again, then use the [check/apply commands](graph-editor.md) with the exact downloaded draft hash and a new output path. Structural acceptance does not verify truth, valid inference, authorship, source support or learner mastery.

## Keyboard and failure recovery

Use native Tab/Shift-Tab navigation, Enter/Space on buttons, and the labeled forms. Select a claim or argument, move to its editable fields, then stage the change. Existing IDs stay fixed. Every premise line is jointly required. A referenced claim cannot be deleted until its referring arguments are deliberately repaired or removed. On a validation error, inspect the status and focused field, correct the input and stage again. No global shortcut intercepts normal text editing.

If the page closes unexpectedly, open the preserved HTML and explicitly import the most recent exported draft. Work never exported cannot be recovered. If an import fails, preserve both the pasted draft and current staged work; do not reset to make the error disappear. If check/apply refuses an existing output, choose a new filename. A stale source needs fresh inspection and a new reviewed draft, not a forced overwrite.

Journey progress, graph drafts, snapshots, review history and retirement archives are different records. For incomplete backups or uncertain locks, preserve every artifact, consult [snapshot recovery](snapshot-recovery.md), and establish actual ownership/process outcomes. Do not infer a safe reconstruction or remove locks automatically. Full skill rollback requires preserving learner files, restoring the entire prior skill folder, verifying its hashes and noting that older editors do not provide the newer UI features.

## Qualification limits

Automated browser results, exact versions and platforms belong in the release report. Playwright WebKit coverage is not a claim of Safari qualification. Keyboard automation is not a screen-reader or user accessibility study. Windows browser coverage is not universal Windows runner/filesystem qualification. Real learner retention/transfer, authenticated review identity, cloud sync/encryption and incomplete-archive reconstruction remain separate work.
