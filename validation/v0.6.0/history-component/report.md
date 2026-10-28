# Review history component

Implemented only `candidate/teach-me/scripts/review_history.py` and
`candidate/teach-me/references/review-history.md`, with component tests and evidence
in this directory. Existing `storage`, `coherence_review`, and `journey_versions`
helpers are reused without modification. No additional worker or API route used.

Construction contract: optional append/status/extract for a dedicated existing
directory outside an initialized journey; canonical six-key hash-chain entries;
receipt bytes retained exactly; store-then-journey locks and current packet/hash
verification on append; historical schema/hash validation on status/extract;
create-new output, bounded orphan reporting and no orphan cleanup or lock stealing.

The pre-build check groups were strict chain/receipt validation, exact two-entry
extraction, stale inputs and foreign outputs, locks/orphans, bounds, and publication
failure. The executed component command was:

```sh
python3 .forge/teach-me-v0.6.0/history-component/test_review_history.py -v
```

Second pass: **26 tests, 0 failures, 0 errors**. First pass stopped in every test's
setup because macOS supplied a `/var` symlink temporary root. The existing helper
correctly rejected it. Resolving the test-only root fixed the fixture; production
code needed no repair. Test files support `TEACH_ME_SKILL` and default to the sibling
candidate skill, so the parent can port only that default path for repository CI.

| Contract group | Concrete discriminating input | Observed result |
| --- | --- | --- |
| Exact receipts and readiness | Two differently whitespace-formatted receipts, second `needs_changes` | Both append; extraction byte-equal; second readiness false |
| Current append fence | Stale expected tip, changed plan, wrong packet digest, another journey's receipt | Refused with prior committed history unchanged |
| Strict full-chain validation | Canonical rehashed malformed keys/version/sequence/previous, noncanonical base64, changed receipt identity/hash, UTF-16 receipt, duplicate keys, raw whitespace corruption | Refused |
| Bounded storage | Real 64 entries, oversized receipt/stage, 192 stages; injected smaller total-byte limit | Read/append boundary refusals; constants asserted |
| Cooperative failure preservation | Existing store/journey locks, orphan stage, symlink store/output, foreign output injected before link | Preserved; append/output refused |
| Publication and raw change | Injected link failure; receipt/content changes during stage; history change during extract | No new valid entry/output; own temporary stage cleaned |

Limits: total-byte branch is tested using a smaller injected limit, not an actual
64 MiB fixture. This component is self-tested construction evidence; the parent's
independent frozen evaluator, full regressions, installed skill and release checks
remain separate. Cooperative locks and bounded rechecks do not authenticate the
operator, defend a malicious complete chain rewrite, or guarantee all power-loss
outcomes. Hashes are recorded separately in `hashes.json`.
