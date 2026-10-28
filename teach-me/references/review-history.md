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

Every entry has exactly these keys:

| Key | Meaning |
| --- | --- |
| `version` | Exact integer `1`, never boolean |
| `journey_id` | Same valid journey slug throughout the chain |
| `sequence` | Exact integer from 1, contiguous with no duplicates |
| `previous` | `null` for sequence 1, preceding entry SHA256 thereafter |
| `receipt_sha256` | SHA256 of the original receipt bytes |
| `receipt_base64` | Canonical standard base64 of those exact UTF-8 receipt bytes |

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
`journey_id`, `entries`, and `staging_entries`. Entry readiness is the recorded
receipt judgment; status does not check old receipts against today's journey.
`receipt_freshness_checked` and `semantic_correctness_verified` are false.
`extract` requires any explicit entry SHA256 and creates a new output outside the
history directory and its descendants. Existing outputs, including symlinks, are
preserved; missing output parents are refused.

Bounds are 64 committed entries, 2 MiB per original receipt, 3 MiB per entry or
stage file, 64 MiB total entry/stage bytes, and 192 directory entries including
the cooperative lock. Unknown directory entries and nonregular files are refused.
Append also reserves room for its stage and publication. A full history requires
an explicit new dedicated history directory; this tool never deletes old entries.

Staging uses `.teach-me-history-stage-` names. Status reports bounded regular orphan
stages; append refuses while any exists. Preserve and inspect the actual files and
reconcile interrupted operations explicitly. The tool never steals a lock or
automatically cleans up an orphan. It removes only its own identifiable temporary
stage during ordinary completion or failure. Existing foreign outputs and
replacement lock files are preserved by create-new publication and the shared
lock helper. Exit 0 means the requested operation completed, including appending
a valid `needs_changes` receipt; malformed or refused operations exit 2.

The locks coordinate cooperating local writers. Staging, fsync and atomic link
publication do not promise universal power-loss durability or a hostile-filesystem
sandbox. Keep a trusted independent tip/hash if malicious complete chain rewriting
must be detectable: an attacker who rewrites every entry can construct another
internally valid chain. Historical bytes convey no external permission.
