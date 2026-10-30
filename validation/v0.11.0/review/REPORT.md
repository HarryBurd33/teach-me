# Independent v0.11 review

Accepted within the frozen contract. Candidate checker SHA256: `e632a2ddc812ee5f31641ea39d2b6a16d64e6e59e417351cd714bff2f93661a7`.

The tests and baseline-helper hash inventory were frozen before opening the candidate. The frozen test SHA256 is `a70b95de7b999c8b74f344aa0226a8433d8e53aef77773d699890ce9c693fc42`; frozen.json SHA256 is `07dc1dbc24c3ddab908ca3be251426bf56c3f79bd7b58d0f932a50d981a9cafd`. Both remain unchanged. The frozen metadata's count of 16 was a counting error: unittest discovered and ran 15 methods. No case was removed or weakened.

Candidate: 15 methods passed in 3.171 seconds, with subcases for all whole-record choices, malformed/missing/extra/duplicate choices, reviewed-hash/source changes, all five final source rereads, byte bounds, capacity, and CLI refusals. The successful Unicode/metadata/AND-premise case produced exactly the same prospective draft digest and byte count as the existing apply command; repeated previews were deterministic. Every normal check compared the fixture tree before/after; injected race cases allowed only the injected one-byte source mutation.

Baseline: 15 methods produced 35 feature-absence failure instances. They are explicitly classified as missing read-only merge-check capability, not passing negative validations or security regressions. The observed benefit is a successful read-only digest/summary of the resolved prospective merge, where the baseline exposes only plan and output-producing apply. Existing apply still produced the matching final bytes for the candidate's positive scenarios.

Source review confirms reuse of existing source/plan/decision/graph/patch validators, merge resolver and encoder; final bounded rereads of all five sources; deterministic sorted change IDs; no graph or source paths in successful output; no publisher invocation; and strict command-line option handling. All existing baseline Python helpers were byte-identical in the candidate. No actionable defect was found in this pass.

One of two permitted candidate review passes used. No candidate files, task ownership, global state, model selection, GitHub state, or other task files were changed. Fresh intake account allowance was 37% remaining. Evidence is in `candidate-pass1.log`, `baseline-tests.log`, `results.json`, `frozen.json`, and `test_v11_contract.py` in this directory.

Parent integration remains responsible for the complete prior 475 tests and actual browser matrix. These tests establish bounded structural behavior, not semantic truth, authenticated authorization, or hostile-writer fencing. Run copied tests with `TEACH_ME_SKILL=/absolute/skill/path python3 -B test_v11_contract.py`.
