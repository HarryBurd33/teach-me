"""Closed journey asset contract. Validation checks structure, never truth or mastery."""
import hashlib
import json

import journey
from storage import StorageError

REQUIRED = {'plan.md', 'progress.json', 'sources.md'}
LEGACY_ALLOWED = REQUIRED | {'knowledge.md', 'practice.md', 'harness-project.md', 'learning-pilot.md'}
TYPED_ALLOWED = {'knowledge-graph.json', 'knowledge-proposal.json', 'knowledge-source.txt', 'journey-review.json'}
ALLOWED = LEGACY_ALLOWED | TYPED_ALLOWED
CONTENT_FILES = ALLOWED - {'journey-review.json'}
FILE_LIMIT = 2 * 1024 * 1024
TOTAL_LIMIT = 16 * 1024 * 1024


def strict_json(raw):
    return json.loads(raw, object_pairs_hook=journey.unique_members,
                      parse_constant=journey.reject_constant)


def content_manifest(files):
    """Bind all present allowlisted content bytes; omit the receipt's own bytes."""
    return {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
            for name, raw in sorted(files.items()) if name in CONTENT_FILES}


def validate_assets(files):
    """Validate a complete bounded file mapping, including typed links and identity.

    Returns diagnostic warnings. A proposal is a draft; unresolved graph references
    are preserved and reported. A schema-valid stale receipt is historical data,
    so freshness is reported rather than made a barrier to backing up that data.
    No provenance path, stored command or URL is opened or executed.
    """
    if (not isinstance(files, dict) or not REQUIRED <= set(files) or set(files) - ALLOWED or
            any(not isinstance(raw, bytes) or len(raw) > FILE_LIMIT for raw in files.values())):
        raise StorageError('Journey assets must be bounded bytes under the closed filename contract')
    if sum(map(len, files.values())) > TOTAL_LIMIT:
        raise StorageError('Journey exceeds transfer size limit')
    state = journey.validate(strict_json(files['progress.json']))
    warnings = []
    if 'knowledge-source.txt' in files:
        files['knowledge-source.txt'].decode('utf-8')
    if 'knowledge-graph.json' in files:
        import graph_workbench
        graph = graph_workbench.validate_graph(strict_json(files['knowledge-graph.json']), complete=False)
        warnings.extend(graph['warnings'])
        missing = graph_workbench.unresolved(graph)
        if missing:
            warnings.append('Unresolved graph endpoints: ' + ', '.join(missing))
    if 'knowledge-proposal.json' in files:
        if 'knowledge-source.txt' not in files:
            raise StorageError('knowledge-proposal.json requires knowledge-source.txt')
        import graph_workbench
        proposal = graph_workbench.validate_proposal(strict_json(files['knowledge-proposal.json']),
                                                     files['knowledge-source.txt'])
        known = {node['id'] for node in proposal['nodes']}
        if 'knowledge-graph.json' in files:
            known.update(node['id'] for node in graph['nodes'])
        missing = sorted({endpoint for chain in proposal['chains']
                          for endpoint in chain['premises'] + [chain['conclusion']]
                          if endpoint not in known})
        if missing:
            warnings.append('Unresolved draft proposal endpoints: ' + ', '.join(missing))
    if 'journey-review.json' in files:
        # Lazy import avoids a dependency cycle: review itself uses this contract.
        import coherence_review
        receipt = coherence_review.validate_receipt(strict_json(files['journey-review.json']))
        if receipt['journey_id'] != state['journey_id']:
            raise StorageError('Review receipt journey_id differs from progress')
        content = {name: raw for name, raw in files.items() if name in CONTENT_FILES}
        current_packet = coherence_review.packet_for(None, content, state)
        if (receipt['files'] != current_packet['files'] or
                receipt['packet_sha256'] != current_packet['packet_sha256']):
            warnings.append('Review receipt is stale; prepare and record a fresh review before relying on it')
        if not receipt['resume_ready']:
            warnings.append('Review records needs_changes; it is not a completed consistency review')
    return warnings
