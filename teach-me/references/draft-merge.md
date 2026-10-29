# Merge divergent offline graph drafts

Use this helper when two exported graph drafts were edited from the exact same complete base graph. It creates a reviewable three-way merge plan, then produces a new ordinary v1 draft after explicit decisions. Import that draft into the [offline editor](graph-editor.md), inspect it, export it and use the normal check/apply workflow.

The base must be graph-only teach-me-learning-v1 with resolved endpoints. Each branch must be a structurally valid v1 editor draft against the base's exact byte SHA256. Different whitespace in the base changes that digest. This helper does not reconcile unrelated bases, session data or native application stores.

## Plan before choosing

Keep the original base and both exported drafts. Run from the installed skill folder, using explicit paths to the selected files:

~~~sh
python3 scripts/draft_merge.py plan --base graph.json --left left-draft.json --right right-draft.json --output merge-plan.json
~~~

The output path must be new. Inspect merge-plan.json and the command's plan_sha256. The plan contains exactly version, format, base_sha256, left_sha256, right_sha256, automatic, conflicts and notice. Format is teach-me-draft-merge-plan-v1 and version is integer 1. It includes no source paths or timestamps.

Automatic changes compare whole records against the base. A change made by only one branch, or the same change made by both branches, can combine. Independent claim and argument edits preserve complete records and every jointly required premise. The helper does not infer a semantic or field-level merge: if left changes a statement while right changes the name of the same claim, that is a conflict.

Each conflict contains kind (node or chain), id, reason, and the complete nullable base, left and right records:

| Reason | Why a choice is required |
| --- | --- |
| both-edited | Divergent edits, delete versus edit, or different new records under the same ID |
| dependency | Combining branches would leave a missing claim endpoint; the affected claim and referring argument need deliberate choices |
| capacity | Combining changes would exceed count or draft-byte bounds; affected changed records are exposed for review |

A null record means that branch has no record under the ID. Choosing that side deliberately deletes or drops the record. Do not select it merely because it looks like an empty value.

## Record exact choices

Copy the [decisions template](../templates/draft-merge-decisions.json) into a separate working file. Replace its all-zero plan_sha256 with the SHA256 of the exact current merge-plan.json bytes. An empty choices array is correct only when the plan has no conflicts. Otherwise include exactly one choice for every conflict and no others. Each choice has exactly kind, id and choose; choose is left, right or base. Arbitrary replacement record contents are not accepted.

For a plan with exactly one conflict for claim a, a left-side decision has this shape. Replace PLAN_SHA256_FROM_PLAN with the actual 64-character digest:

~~~json
{
  "version": 1,
  "plan_sha256": "PLAN_SHA256_FROM_PLAN",
  "choices": [
    {"kind": "node", "id": "a", "choose": "left"}
  ]
}
~~~

Choosing left retains the full left claim, including its name and statement. It does not combine a left statement with a right name. Preserve aliases, creation time and provenance from existing base records. New records use blank metadata: aliases [] for nodes, createdAt "" and provenance [].

Review the decision file, then obtain its exact SHA256:

~~~sh
python3 -c "import hashlib; print(hashlib.sha256(open('merge-decisions.json','rb').read()).hexdigest())"
~~~

## Produce a new draft

Use the exact current plan and decision digests:

~~~sh
python3 scripts/draft_merge.py apply --base graph.json --left left-draft.json --right right-draft.json --plan merge-plan.json --expected-plan-sha256 PLAN_SHA256_FROM_PLAN --decisions merge-decisions.json --expected-decisions-sha256 DECISIONS_SHA256_FROM_REVIEW --output merged-draft.json --approve
~~~

The helper re-reads the base, both branches, plan and decisions. The raw hashes must match, the decisions must bind the raw plan, and the parsed plan must equal a newly computed deterministic plan for the current sources. The approval flag records operator review; it does not authenticate identity or consent.

A successful result is an ordinary v1 draft with exactly version, base_sha256 and patch. It is not an applied graph. All final editor validations must pass: valid IDs, immutable historical metadata, resolved endpoints, nonempty unique joint premises, no duplicate logical argument, size/count limits and exact schemas. Incompatible choices are refused instead of silently repairing records. Independent branches can also add the same logical argument under different IDs: the plan can be record-conflict-free, but final apply still refuses duplicate arguments. Revise one branch and regenerate the plan; the helper does not silently deduplicate equivalent premises and conclusions. Revisit the source drafts or choices, make a fresh plan when sources change, and review new hashes.

The output is create-new. Existing files and foreign files created during publication are preserved. Source bytes are rechecked before publication. A refused operation must not replace inputs or the selected output. Do not remove a source, output or lock to force acceptance.

## Import, inspect and apply

Render or reopen an editor for the exact original base:

~~~sh
python3 scripts/graph_editor.py render --input graph.json --output editor.html
~~~

In that page, paste the entire merged-draft.json into Draft JSON to import and select Import draft JSON. Import replaces the staged graph rather than merging into current page edits. Export current page work first if you want to keep both versions. A valid import is one undoable staged action; history remains bounded and in memory. See [editor recovery](editor-recovery.md).

Inspect claims, argument premises, metadata, warnings and the staged change list. Export the inspected draft; it may have different formatting or ordering from the merger's file, so check the actual exported bytes:

~~~sh
python3 scripts/graph_editor.py check --base graph.json --draft exported-reviewed-draft.json
python3 scripts/graph_editor.py apply --base graph.json --draft exported-reviewed-draft.json --expected-draft-sha256 DRAFT_SHA256_FROM_CHECK --output edited-graph.json --approve
~~~

Choose a new output graph filename. Preserve the original base, both branch drafts, reviewed plan, decisions and exported final draft when an audit trail is useful.

## Refusals, bounds and evidence limits

Each base and branch input is limited to 2 MiB; decisions to 2 MiB; plans to 8 MiB; and the output draft to 2 MiB. Branch and final graphs may contain at most 256 nodes and 256 chains. Duplicate JSON members, unknown keys, boolean or floating version values, malformed choices, unknown IDs, changed metadata, wrong-base digests, stale hashes and sensitive/symlink/traversal paths are refused. Formatting changes affect raw hashes. If a reviewed source changes, preserve both versions and make a new plan instead of editing digests to bypass the mismatch.

Manual choices are assertions. Structural acceptance does not verify truth, inference, source support, learner mastery or authenticated reviewer identity. Retained provenance is historical metadata; it does not automatically support a changed claim. The helper offers no autosave, continuous sync, encryption, native source writeback, arbitrary attachment support or hostile-writer fencing. An interrupted operation can leave a private staging artifact; preserve uncertain artifacts and establish actual owner/process outcomes before any cleanup. Existing publisher safeguards are cooperative and do not guarantee universal power-loss durability.
