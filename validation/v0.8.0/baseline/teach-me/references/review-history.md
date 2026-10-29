# Immutable review history

Use this optional local tool to retain review receipts after an existing learning
journey changes. It records operator judgments and detects malformed or changed
history bytes. It does not authenticate a reviewer or certify semantic truth,
mastery, identity, authorization, or permission to resume an external task.

Create an empty history directory outside the journey, then append a receipt made
with [coherence review](coherence-review.md). The journey must already contain valid
progress and required content. Use a dedicated directory for one journey identity.
These examples use an existing `/workspace/review-history` directory:

```sh
python3 scripts/review_history.py append --store /workspace/review-history --journey /workspace/learning/probability --receipt /workspace/review.json --expected-tip none
python3 scripts/review_history.py status --store /workspace/review-history
python3 scripts/review_history.py append --store /workspace/review-history --journey /workspace/learning/probability --receipt /workspace/new-review.json --expected-tip ENTRY_SHA_FROM_STATUS
python3 scripts/review_history.py extract --store /workspace/review-history --entry EXPLICIT_ENTRY_SHA --output /workspace/old-review.json
```

`--expected-tip` is required: use literal `none` for an empty history or the exact
current tip SHA256 from `status`. Append holds `.teach-me-review-history.lock`, then
the selected journey's `.teach-me.lock`. While both are held, it validates the
receipt's closed schema, selected journey identity, exact content hashes, and
current review packet digest; it rechecks receipt bytes and content before atomic
create-new publication. A valid receipt with `needs_changes` can be recorded;
its `resume_ready` stays false. No journey content or existing entry is replaced.

To retain an older receipt after the journey has changed, use historical import.
It needs no current journey directory. Supply its explicit journey ID, exact raw
receipt SHA256, current history tip, and a nonblank reason of at most 4096 Unicode
characters. For example:

```sh
python3 scripts/review_history.py import --store /workspace/review-history --receipt /workspace/old-review.json --id probability --expected-tip ENTRY_SHA_FROM_STATUS --expected-receipt-sha256 EXACT_RECEIPT_SHA256 --reason "Retain review recorded before the plan changed"
```

Use `--expected-tip none` for an empty store. Import validates the receipt's closed
schema, exact digest, explicit ID, and existing store identity under the history
lock. It never reads the current journey or checks historical content freshness.
It rechecks the original receipt, history and stage bytes before create-new
publication. A valid older `needs_changes` receipt and a valid older receipt whose
original `resume_ready` is true are both historical: import always reports
`resume_ready: false`. Neither an ID match nor a hash authenticates anyone's
identity or the claimed origin of a receipt.

Append continues to write version 1 with exactly these six keys:

| Key | Meaning |
| --- | --- |
| `version` | Exact integer `1`, never boolean |
| `journey_id` | Same valid journey slug throughout the chain |
| `sequence` | Exact integer from 1, contiguous with no duplicates |
| `previous` | `null` for sequence 1, preceding entry SHA256 thereafter |
| `receipt_sha256` | SHA256 of the original receipt bytes |
| `receipt_base64` | Canonical standard base64 of those exact UTF-8 receipt bytes |

Historical import writes version 2 with those same six keys (`version` is exact
integer `2`) plus exactly `origin: "historical_import"` and `origin_note` containing
the supplied reason. No other origin or extra field is accepted. Version 1 entries
have no origin fields in their stored bytes. Existing version 1 entries are never
rewritten; a single chain can contain both versions, and current checked appends
can continue after historical imports using the same hash chain.

Entry bytes are `json.dumps(value, sort_keys=True, ensure_ascii=False,
allow_nan=False, separators=(',', ':'))` encoded as UTF-8 with one final newline.
The filename is `000001-SHA256.json` (six sequence digits), where the SHA256 covers
all canonical entry bytes including the final newline. There is no pointer file.
Receipt JSON may contain whitespace: extraction preserves every original byte.
Duplicate JSON keys, nonfinite values, foreign keys, noncanonical base64, receipt
digest/identity mismatches, noncanonical entry bytes, filename mismatches and chain
breaks are refused.

`status` verifies the entire bounded chain and all embedded historical receipt
schemas, hashes, and identities. It returns `tip` (`null` when empty), `sequence`,
`journey_id`, `entries`, and `staging_entries`. Every reported entry has an `origin`:
`current_checked_append` for version 1 or `historical_import` for version 2; the
latter includes its `origin_note`. Version 1 `resume_ready` retains the original
receipt judgment. Version 2 `resume_ready` is always false, even when its embedded
receipt originally said true. `receipt_resume_ready` preserves that original flag
for both versions. Status does not check any old receipt against today's journey:
`receipt_freshness_checked`, `semantic_correctness_verified`, and
`origin_authenticated` are false. The origin label describes the entry format and
recording operation; it does not authenticate the source or reviewer.
`extract` requires any explicit entry SHA256 and creates a new output outside the
history directory and its descendants. Existing outputs, including symlinks, are
preserved; missing output parents are refused.

Bounds are 64 committed entries, 2 MiB per original receipt, 3 MiB per entry or
stage file, 64 MiB total entry/stage bytes, and 192 directory entries including
the cooperative lock. Unknown directory entries and nonregular files are refused.
Append and import also reserve room for their stage and publication. A full history requires
an explicit new dedicated history directory; this tool never deletes old entries.

Staging uses `.teach-me-history-stage-` names. Status reports bounded regular orphan
stages; append and import refuse while any exists. Preserve and inspect the actual files and
reconcile interrupted operations explicitly. The tool never steals a lock or
automatically cleans up an orphan. It removes only its own identifiable temporary
stage during ordinary completion or failure. Existing foreign outputs and
replacement lock files are preserved by create-new publication and the shared
lock helper. Exit 0 means the requested operation completed, including appending
a valid `needs_changes` receipt or importing a valid historical receipt; malformed
or refused operations exit 2.

Version 0.6 history readers reject version 2 entries. Update the receiving skill
copy before reading a chain containing historical imports. Journey transfer ZIP
formats are unchanged; a review history is a separate local store.

The locks coordinate cooperating local writers. Staging, fsync and atomic link
publication do not promise universal power-loss durability or a hostile-filesystem
sandbox. Keep a trusted independent tip/hash if malicious complete chain rewriting
must be detectable: an attacker who rewrites every entry can construct another
internally valid chain. Historical bytes convey no external permission.
