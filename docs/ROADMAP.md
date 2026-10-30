# Teach-me limitations roadmap

## v0.11: validate choices before writing
Implement a read-only merge preflight using existing strict validators, exact reviewed hashes and final source rechecks. Report prospective draft hash/size/counts/changed IDs. Freeze independent and construction checks; compare with v0.10; preserve all prior tests and helper/editor bytes. Exercise the preflight/apply/import/export path in the browser matrix. Adopt only after tests and review pass, preserve rollback, verify global discovery and release downloads.

## Subsequent engineering gates
1. Different-base or field-level merging: define ancestry, identity, metadata and conflict rules first; demonstrate refusal for ambiguous lineage and independent provenance. Current preflight handles same-base choices only.
2. Editing and recovery: prototype an explicit export/recovery journal with clear file origin, quota and privacy controls; test interrupted writes, corrupted exports and stale tabs before adding autosave or native writeback. Never-exported work is currently unrecoverable.
3. Accessibility and platforms: retain actual browser matrices; add keyboard/semantic checks as features change, then conduct consenting screen-reader user studies and qualify installed Safari/Edge and the complete Windows filesystem stack. Playwright WebKit is not Safari.
4. Learning evidence: run consenting baseline, delayed retention and unfamiliar transfer pilots with predefined outcomes, assistance and confounds recorded. Software tests are not learner-gain evidence.
5. Trust/storage: settle reviewer identity, key rotation/revocation/recovery and private transport/conflict contracts before signing, encryption or distributed sync. Test compromised/stale keys and uncertain effects.
6. Archive reconstruction/isolation: define partial recovery outcomes for incomplete archives, preserve ambiguous locks/artifacts, and test platform crash/power-loss behavior. Hostile writers need a separately reviewed isolation design.

Each phase needs its own observable acceptance and scope; this release does not claim those future capabilities. Prior notices and MIT license are retained; no new runtime dependency or data service is introduced.
