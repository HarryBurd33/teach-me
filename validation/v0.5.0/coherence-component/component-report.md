# Coherence review component

Implemented `scripts/coherence_review.py`, `references/coherence-review.md` and
`templates/coherence-decisions.json` in the isolated v0.5.0 candidate. No global,
public checkout, canonical skill or checkpoint files were changed by this worker.

The helper prepares a packet for every present allowlisted content file, records
all four operator judgments against that exact packet and verifies freshness.
Literal goal/stage/next-action summaries and asset warnings support inspection;
actual contents still need a reviewer. `needs_changes` is preserved and yields
verify exit 1; stale/invalid data yields exit 2. Receipts keep the false semantic
verification flag. Claimed roles are not authenticated identities or permissions.

Publication is create-new through a staged atomic link. Expected-digest
replacement is limited to canonical `journey-review.json`, preserves exact old
bytes in the previous receipt, and refuses malformed/foreign-journey backups.
Output bytes are bounded before staging, including expansion from valid near-limit
inputs. Source, packet and decisions are rechecked before publication.

Validation: `python3 -B -m unittest discover -s
.forge/teach-me-v0.5.0/coherence-component -v`: 25 tests passed. Cases include
literal summaries and zero/null state, needs_changes/mixed decisions, stale edited/
added/deleted content, duplicate/unknown/missing decision IDs and blank rationale,
JSON duplicate/nonfinite values, tampered/rehashed packets, protected and existing
outputs, wrong replacement hashes and exact backups, malformed receipts, symlinks,
foreign locks, quoted source binding and unresolved proposal warnings, bounded
input -> oversized output rejection, source drift after staging and a foreign
output racing publication. The last two use local deterministic stage hooks;
they do not simulate hostile filesystems or power loss. A test-authoring patch
initially misplaced two lines, causing one NameError in the test itself; the lines
were restored without weakening assertions and all 25 tests then passed.

Remaining limits: judgments can be wrong, fabricated or unsupported despite
shape validation; no semantic truth/mastery/human identity/authorization proof.
Cooperative local locks are not an adversarial filesystem sandbox. Forced
termination can orphan a stage/lock; no universal power-loss guarantee. A previous
receipt keeps only one local predecessor; snapshots are needed for longer history.
No UI, provider or real-learner efficacy evaluation was performed by this worker.
