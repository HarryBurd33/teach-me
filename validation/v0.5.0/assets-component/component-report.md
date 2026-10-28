# Typed asset transport component

Constructed original MIT code in the isolated candidate:

- `scripts/journey_assets.py`: closed 11-name asset contract, bounded bytes,
  exact proposal/source binding, graph-only normalized validation, historical
  receipt schema and identity checks, and content fingerprints excluding the receipt.
- `scripts/transfer.py`: selects all 11 names; writes version 1 for legacy-only
  journeys and version 2 for any typed asset; accepts both, refuses typed files
  smuggled under version 1, and retains existing publication/path/size safeguards.
- `references/transfer.md`: current filename/format/validation/freshness contract.

`journey_versions.py` required no edit: snapshot, restore, compare and merge
already use transfer packing/inspection. The new tests execute these paths.
Legacy `transfer.ALLOWED` and `OPTIONAL` remain seven-name/Markdown-only
compatibility constants; the complete current contract is
`journey_assets.ALLOWED`, also selected internally as `transfer.ASSET_ALLOWED`.
Manual callers that enumerate the legacy constant must explicitly adopt the
current contract to enumerate typed files.

Executed checks: 13 new synthetic cases, 14 unchanged legacy transfer cases and
17 unchanged legacy versions cases; all 44 pass. Exact commands, counts and
candidate hashes are in `results.json`; full logs are alongside it.

The tests preserve exact UTF-8/CRLF bytes for ten-file and eleven-file transfer,
snapshot and restore; verify valid typed merge; reject a byte-clean merge that
would combine a changed source with a newly added proposal bound to the old
source; preserve stale and needs-changes receipts while warning, and reject
their use as a current completed consistency review. Existing outputs and
symlink paths remain protected. A second bounded pass additionally checks the
receipt's packet digest against the current generated packet, so a matching
file manifest with an altered packet digest warns stale just as explicit review
verification does. The tests use synthetic data and local temporary
directories, not real learner outcomes or external services.

Remaining boundaries: no automatic semantic truth or learning verification,
arbitrary attachments, encrypted transport, remote synchronization, provider
integration or hostile-filesystem sandbox. Prior releases refuse version 2;
update the receiving skill first. Valid stale receipts remain historical data,
so callers must use explicit review verification before relying on a judgment.
