#!/usr/bin/env python3
"""Original, read-only native-v1 learning-data adapter. Python 3.9+, stdlib."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import sys

FORMAT = 'teach-me-learning-v1'
LIMIT = 8 * 1024 * 1024
OUTPUT_LIMIT = 32 * 1024 * 1024
SENSITIVE = {'auth.json', 'settings.json', 'credentials.json', 'credentials', '.git'}
QUESTIONS = {'ask_user_question', 'probe', 'quiz', 'recall', 'explain', 'problem'}


class DataError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise DataError(message)


def text(value, where, empty=False):
    require(isinstance(value, str) and (empty or bool(value.strip())), where + ': expected text')
    return value


def members(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'Duplicate JSON member: ' + key)
        result[key] = value
    return result


def nonfinite(value):
    raise DataError('Nonfinite JSON number: ' + value)


def finite_float(value):
    result = float(value)
    require(math.isfinite(result), 'Nonfinite JSON number: ' + value)
    return result


def decode(raw, where):
    try:
        return json.loads(raw, object_pairs_hook=members, parse_constant=nonfinite, parse_float=finite_float)
    except (ValueError, UnicodeError) as exc:
        raise DataError(where + ': invalid JSON: ' + str(exc))


def path_checked(value):
    path = Path(value).absolute()
    require('..' not in path.parts, 'Parent traversal is not accepted; use an explicit absolute path')
    cursor = Path(path.anchor)
    for part in path.parts[1:]:
        cursor = cursor / part
        low = part.lower()
        require(low not in SENSITIVE and not low.startswith('.env') and
                'provider-debug' not in low and 'provider_debug' not in low,
                'Sensitive data path is excluded')
        require(not cursor.is_symlink(), 'Symlinked paths are excluded')
    return path


def read_bytes(value):
    path = path_checked(value)
    require(path.is_file(), 'Source must be a regular file: ' + path.name)
    before = path.stat()
    require(before.st_size <= LIMIT, 'Source exceeds 8 MiB limit')
    with path.open('rb') as handle:
        raw = handle.read(LIMIT + 1)
    after = path.stat()
    require(len(raw) <= LIMIT, 'Source exceeds 8 MiB limit')
    require((before.st_ino, before.st_size, before.st_mtime_ns) ==
            (after.st_ino, after.st_size, after.st_mtime_ns), 'Source changed while reading')
    return path, raw


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def source(value, jsonl=False):
    path, raw = read_bytes(value)
    if jsonl:
        try:
            lines = raw.decode('utf-8').splitlines()
        except UnicodeError as exc:
            raise DataError('Source is not UTF-8: ' + str(exc))
        data = [decode(line, path.name + ':' + str(n))
                for n, line in enumerate(lines, 1) if line.strip()]
    else:
        data = decode(raw, path.name)
    return path, raw, data


def envelope(sources):
    return {'format': FORMAT,
            'source_files': [{'name': p.name, 'sha256': sha(raw)} for p, raw in sources],
            'sessions': [], 'nodes': [], 'chains': [], 'warnings': []}


def stamp(value, where):
    require(isinstance(value, dict), where + ': expected an object')
    version = value.get('version', 1)
    require(type(version) is int and version == 1, where + ': supported native version is 1')
    require('parts' not in value, where + ': pre-native parts dialect is unsupported')


def strings(value, where):
    require(isinstance(value, list), where + ': expected a list')
    for item in value:
        text(item, where + ' item')
    return value


def visible_content(value, where):
    if isinstance(value, str):
        return value
    require(isinstance(value, list), where + ': content must be text or blocks')
    parts = []
    for block in value:
        require(isinstance(block, dict), where + ': malformed block')
        kind = block.get('type')
        if kind == 'text':
            parts.append(text(block.get('text'), where + '.text', empty=True))
        elif kind in ('image', 'image_url', 'file', 'audio'):
            parts.append('[media omitted; not inspected]')
        elif kind == 'thinking':
            continue
        else:
            raise DataError(where + ': unsupported content block ' + str(kind))
    return '\n'.join(parts)


def object_field(value, where):
    if isinstance(value, str):
        value = decode(value, where + ' encoded JSON')
    require(isinstance(value, dict), where + ': expected an object')
    return value


def answer_fields(details):
    if 'kind' in details:
        require(details['kind'] in ('quiz', 'ask', 'explain'), 'Unsupported answer kind')
    for key in ('questionText', 'text', 'other', 'thinking', 'note', 'readingThinking', 'answeredAt'):
        if key in details and details[key] is not None:
            text(details[key], 'answer.' + key, empty=True)
    for key in ('answers', 'options'):
        if key in details:
            require(isinstance(details[key], list), 'answer.' + key + ': expected list')
            for option in details[key]:
                require(isinstance(option, dict), 'answer option: expected object')
                text(option.get('label'), 'answer option.label', empty=True)
                text(option.get('value'), 'answer option.value', empty=True)
                if key == 'answers':
                    require(type(option.get('index')) is int and option['index'] >= 1,
                            'answer index: expected positive displayed-order integer')
    if 'correct' in details:
        require(type(details['correct']) is bool, 'answer.correct: expected boolean')
    if 'correctIndices' in details:
        require(isinstance(details['correctIndices'], list) and
                all(type(i) is int and i >= 1 for i in details['correctIndices']),
                'answer.correctIndices: expected displayed-order positive integers')


def normalize_session(data, document):
    stamp(data, 'session')
    text(data.get('id'), 'session.id')
    text(data.get('title', ''), 'session.title', empty=True)
    kind = data.get('kind', 'teach')
    require(kind in ('teach', 'practice'), 'session.kind: unsupported kind')
    messages = data.get('messages')
    require(isinstance(messages, list), 'session.messages: expected a list')
    session = {'id': data['id'], 'title': data.get('title', ''), 'kind': kind, 'events': []}
    events = session['events']
    preceding = {}
    ids = set()
    for index, message in enumerate(messages):
        require(isinstance(message, dict) and 'parts' not in message,
                'message: malformed or pre-native dialect')
        mid = text(message.get('id'), 'message.id')
        require(mid not in ids, 'Duplicate message ID is ambiguous: ' + mid)
        ids.add(mid)
        role = message.get('role')
        anchor = {'message_id': mid, 'sequence': index}
        if role == 'user':
            events.append(dict(anchor, type='learner_text', text=visible_content(message.get('content', ''), mid)))
        elif role == 'assistant':
            content = message.get('content')
            require(isinstance(content, list), mid + ': native assistant content must be blocks')
            for block_index, block in enumerate(content):
                require(isinstance(block, dict), mid + ': malformed assistant block')
                if block.get('type') == 'thinking':
                    continue
                if block.get('type') == 'text':
                    events.append(dict(anchor, type='teacher_text', text=text(block.get('text'), mid, empty=True)))
                elif block.get('type') == 'toolCall':
                    call_id = text(block.get('id'), 'call.id')
                    tool = text(block.get('name'), 'call.name')
                    args = object_field(block.get('arguments', {}), 'call.arguments')
                    event_id = mid + ':' + str(block_index)
                    event = dict(anchor, type='question' if tool in QUESTIONS else 'operation',
                                 event_id=event_id, call_id=call_id, tool=tool,
                                 status='pending', question=args.get('question', args.get('statement')),
                                 teacher_committed={k: args[k] for k in
                                     ('correctAnswer', 'committed', 'explanation', 'modelSolution') if k in args})
                    if tool not in QUESTIONS:
                        document['warnings'].append('Unsupported operation retained as metadata: ' + tool)
                    events.append(event)
                    preceding[call_id] = event
                else:
                    raise DataError(mid + ': unsupported assistant block ' + str(block.get('type')))
        elif role == 'toolResult':
            call_id = text(message.get('toolCallId'), 'result.toolCallId')
            call = preceding.get(call_id)
            require(call is not None, 'Result lacks a matching preceding call: ' + call_id)
            if message.get('toolName') is not None:
                require(message['toolName'] == call['tool'], 'Result toolName conflicts with nearest preceding call')
            compact = visible_content(message.get('content', ''), mid)
            require('isError' not in message or type(message['isError']) is bool, 'isError: expected boolean')
            if message.get('isError') is True:
                call['status'] = 'failed'
                events.append(dict(anchor, type='failed_tool', question_event_id=call['event_id'],
                                   call_id=call_id, compact_content=compact))
                continue
            if call['tool'] not in QUESTIONS or call['tool'] == 'problem':
                call['status'] = 'returned'
                events.append(dict(anchor, type='operation_result', question_event_id=call['event_id'],
                                   call_id=call_id, compact_content=compact))
                continue
            details = message.get('details')
            if details is None:
                call['status'] = 'returned_without_details'
                document['warnings'].append('Result has no structured learner snapshot: ' + mid)
                events.append(dict(anchor, type='unstructured_result', question_event_id=call['event_id'],
                                   call_id=call_id, compact_content=compact))
                continue
            details = object_field(details, 'result.details')
            answer_fields(details)
            confidence = details.get('confidence')
            if confidence is not None:
                require(type(confidence) in (int, float) and math.isfinite(confidence) and 0 <= confidence <= 100,
                        'confidence must be 0..100 or absent/null')
            for flag in ('dontKnow', 'dismissed'):
                require(flag not in details or type(details[flag]) is bool, flag + ': expected a boolean')
            learner = {k: details[k] for k in ('answers', 'text', 'other', 'dontKnow', 'dismissed',
                       'readingThinking', 'answeredAt') if k in details}
            learner['confidence'] = confidence
            learner['thinking'] = details.get('thinking') if details.get('thinking') is not None else details.get('note')
            snapshot = {k: details[k] for k in ('kind', 'tool', 'questionType', 'questionText', 'options',
                        'correct', 'correctIndices') if k in details}
            if 'options' in details and 'answers' in details:
                for selected in details['answers']:
                    position = selected['index'] - 1
                    if position >= len(details['options']) or any(
                            selected.get(k) != details['options'][position].get(k) for k in ('label', 'value')):
                        document['warnings'].append('Displayed option snapshot conflicts with answer tuple; retained without remapping: ' + mid)
            # Display-order answers remain exactly as stored; no index remapping.
            teacher = {k: details[k] for k in ('committed', 'explanation') if k in details}
            submitted = bool(details.get('answers')) or any(
                isinstance(details.get(k), str) and bool(details[k].strip())
                for k in ('text', 'other', 'thinking', 'note')) or details.get('dontKnow') is True or details.get('dismissed') is True
            if not submitted:
                call['status'] = 'returned_without_submission'
                document['warnings'].append('Structured result has no learner submission: ' + mid)
                events.append(dict(anchor, type='unstructured_result', question_event_id=call['event_id'],
                                   call_id=call_id, compact_content=compact, snapshot=snapshot, teacher_payload=teacher))
                continue
            call['status'] = 'dismissed' if details.get('dismissed') else 'dont_know' if details.get('dontKnow') else 'answered'
            events.append(dict(anchor, type='learner_response', question_event_id=call['event_id'],
                               call_id=call_id, snapshot=snapshot, learner=learner,
                               teacher_payload=teacher, compact_content=compact))
            if compact:
                document['warnings'].append('Compact content separately retained; not used to override details: ' + mid)
        elif role == 'custom':
            custom_type = text(message.get('customType'), 'customType')
            details = object_field(message.get('details', {}), 'custom.details')
            if custom_type == 'practice-thinking':
                call_id = text(details.get('problemCallId'), 'practice.problemCallId')
                call = preceding.get(call_id)
                require(call is not None and call['tool'] == 'problem', 'Practice attempt lacks preceding problem call')
                events.append(dict(anchor, type='practice_attempt', call_id=call_id,
                                   question_event_id=call['event_id'], text=text(details.get('text'), 'practice.text', empty=True)))
            elif custom_type == 'subagent-steer':
                payload = details.get('result', {})
                require(isinstance(payload, dict), 'artifact result: expected object')
                summary = {k: payload[k] for k in ('title', 'brief', 'notes', 'question', 'pagesRead', 'pagesConsulted') if k in payload}
                events.append(dict(anchor, type='delivered_artifact', artifact_kind=details.get('kind'), summary=summary,
                                   executable_markup_omitted=any(k in payload for k in ('html', 'svg'))))
            else:
                events.append(dict(anchor, type='application_marker', marker=custom_type))
                document['warnings'].append('Application marker is not learner speech: ' + custom_type)
        else:
            raise DataError(mid + ': unsupported native role ' + str(role))
    document['sessions'].append(session)


def provenance(value, where):
    require(isinstance(value, list), where + ': expected provenance list')
    result = []
    for point in value:
        require(isinstance(point, dict) and set(point) == {'chatId', 'messageId'}, where + ': unsupported provenance shape')
        text(point['chatId'], where + '.chatId')
        text(point['messageId'], where + '.messageId', empty=True)
        if point not in result:
            result.append(point)
    return result


def union(target, extra):
    for value in extra:
        if value not in target:
            target.append(value)


def normalize_graph(node_lines, chain_lines, document):
    nodes = {}
    for item in node_lines:
        stamp(item, 'node')
        ident = text(item.get('id'), 'node.id')
        name = text(item.get('name'), 'node.name', empty=True)
        statement = text(item.get('statement'), 'node.statement', empty=True)
        aliases = strings(item.get('aliases', []), 'node.aliases')
        created = text(item.get('createdAt'), 'node.createdAt', empty=True)
        points = provenance(item.get('provenance', []), 'node.provenance')
        if ident not in nodes:
            nodes[ident] = {'id': ident, 'name': name, 'statement': statement,
                            'aliases': list(dict.fromkeys(aliases)), 'createdAt': created, 'provenance': points}
        else:
            union(nodes[ident]['aliases'], ([statement] if statement else []) + aliases)
            union(nodes[ident]['provenance'], points)
    chains = {}
    for item in chain_lines:
        stamp(item, 'chain')
        ident = text(item.get('id'), 'chain.id')
        premises = strings(item.get('premises'), 'chain.premises')
        require(premises and len(premises) == len(set(premises)), 'chain.premises: nonempty unique IDs required')
        conclusion = text(item.get('conclusion'), 'chain.conclusion')
        created = text(item.get('createdAt'), 'chain.createdAt', empty=True)
        points = provenance(item.get('provenance', []), 'chain.provenance')
        key = (tuple(sorted(premises)), conclusion)
        if key not in chains:
            chains[key] = {'id': ident, 'premises': premises[:], 'conclusion': conclusion,
                           'createdAt': created, 'provenance': points}
        else:
            union(chains[key]['provenance'], points)
    for chain in chains.values():
        for endpoint in chain['premises'] + [chain['conclusion']]:
            if endpoint not in nodes:
                document['warnings'].append('Missing graph endpoint: ' + endpoint + ' in chain ' + chain['id'])
    document['nodes'] = list(nodes.values())
    document['chains'] = list(chains.values())


def validate_document(data):
    require(isinstance(data, dict) and set(data) == {'format', 'source_files', 'sessions', 'nodes', 'chains', 'warnings'},
            'Normalized document keys do not match teach-me-learning-v1')
    require(data['format'] == FORMAT, 'Unsupported normalized format')
    for field in ('source_files', 'sessions', 'nodes', 'chains', 'warnings'):
        require(isinstance(data[field], list), field + ': expected list')
    strings(data['warnings'], 'warnings')
    for source_file in data['source_files']:
        require(isinstance(source_file, dict) and set(source_file) == {'name', 'sha256'}, 'Malformed source file record')
        text(source_file['name'], 'source.name')
        digest = source_file['sha256']
        require(isinstance(digest, str) and len(digest) == 64 and all(c in '0123456789abcdef' for c in digest), 'Invalid source digest')
    ids = set()
    for node in data['nodes']:
        require(isinstance(node, dict) and set(node) == {'id','name','statement','aliases','createdAt','provenance'}, 'Malformed normalized node')
        ident = text(node['id'], 'node.id')
        require(ident not in ids, 'Duplicate normalized node ID')
        ids.add(ident)
        for field in ('name','statement','createdAt'):
            text(node[field], 'node.'+field, empty=True)
        strings(node['aliases'], 'aliases')
        provenance(node['provenance'], 'node.provenance')
    for chain in data['chains']:
        require(isinstance(chain, dict) and set(chain) == {'id','premises','conclusion','createdAt','provenance'}, 'Malformed normalized chain')
        text(chain['id'], 'chain.id'); text(chain['conclusion'], 'chain.conclusion')
        premises = strings(chain['premises'], 'chain.premises')
        require(premises and len(premises) == len(set(premises)), 'Malformed normalized premises')
        text(chain['createdAt'], 'chain.createdAt', empty=True)
        provenance(chain['provenance'], 'chain.provenance')
    # Sessions are not rendered as HTML/code; still reject an unknown container shape.
    for session in data['sessions']:
        require(isinstance(session, dict) and set(session) == {'id','title','kind','events'}, 'Malformed normalized session')
        text(session['id'], 'session.id'); text(session['title'], 'session.title', empty=True)
        require(session['kind'] in ('teach','practice') and isinstance(session['events'],list), 'Malformed normalized session')
    return data


def render(data):
    validate_document(data)
    # Escape '<' so even a hostile closing script tag cannot leave the JSON element.
    payload = json.dumps(data, ensure_ascii=True, allow_nan=False).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    return '''<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src 'none'; connect-src 'none'">
<title>Teach-me knowledge map</title>
<style>body{font:16px system-ui;margin:2rem;max-width:1000px;color:#192435;background:#f6f8fc}input{padding:.6rem;width:90%}.card{background:white;border:1px solid #bcc9dd;border-radius:.5rem;padding:1rem;margin:1rem 0}.chain{border-left:5px solid #6950a1}.warning{color:#8b2b1b}small{display:block;white-space:pre-wrap}h2{font-size:1.2rem}.and{font-weight:bold;color:#60399c}.arrow{font-size:1.4rem}#summary{margin-top:1rem}</style>
<h1>Knowledge and argument map</h1><p>Claims and provenance, not mastery. All premises in each AND group are jointly required. This local viewer sends no network requests.</p>
<label>Filter claims, IDs, aliases and provenance <input id="query" type="search"></label>
<p id="summary"></p><section id="warnings" aria-label="Warnings"></section><main id="map"></main>
<script id="data" type="application/json">''' + payload + '''</script>
<script>
'use strict';
const data=JSON.parse(document.getElementById('data').textContent);
const map=document.getElementById('map'), summary=document.getElementById('summary');
function el(tag,value,cls){const n=document.createElement(tag);if(value!==undefined)n.textContent=value;if(cls)n.className=cls;return n;}
for(const w of data.warnings)document.getElementById('warnings').appendChild(el('p',w,'warning'));
const names=new Map(data.nodes.map(n=>[n.id,n.name||n.id]));
function draw(){map.replaceChildren();const q=document.getElementById('query').value.toLowerCase();let count=0;
for(const n of data.nodes){if(q&&!JSON.stringify(n).toLowerCase().includes(q))continue;const c=el('article',undefined,'card');c.append(el('h2',n.name||n.id),el('p',n.statement),el('small','ID: '+n.id+' | Aliases: '+n.aliases.join('; ')),el('small','Sources: '+JSON.stringify(n.provenance)));map.append(c);count++;}
for(const chain of data.chains){const combined=JSON.stringify(chain)+' '+chain.premises.map(id=>names.get(id)||id).join(' ')+' '+(names.get(chain.conclusion)||chain.conclusion);if(q&&!combined.toLowerCase().includes(q))continue;const c=el('article',undefined,'card chain');c.append(el('h2','Argument '+chain.id));chain.premises.forEach((id,i)=>{if(i)c.append(el('span',' AND ','and'));c.append(el('span',(names.get(id)||'[missing]')+' ('+id+')'));});c.append(el('span',' ⇒ ','arrow'),el('strong',(names.get(chain.conclusion)||'[missing]')+' ('+chain.conclusion+')'),el('small','Sources: '+JSON.stringify(chain.provenance)));map.append(c);count++;}
summary.textContent=count+' visible cards; '+data.nodes.length+' propositions, '+data.chains.length+' separate arguments. No mastery score.';}
document.getElementById('query').addEventListener('input',draw);draw();
</script></html>'''


def publish(value, output, sources, as_html=False):
    path = path_checked(output)
    require(path.parent.is_dir(), 'Output parent must already exist')
    require(all(path != item[0] for item in sources), 'Output may not replace a source')
    for original, raw in sources:
        _, now = read_bytes(original)
        require(sha(raw) == sha(now), 'Source changed during analysis')
    raw = (value if as_html else json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + '\n').encode('utf-8')
    require(len(raw) <= (OUTPUT_LIMIT if as_html else LIMIT),
            'Output exceeds size limit (8 MiB JSON / 32 MiB HTML)')
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(str(path), flags, 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(raw); handle.flush(); os.fsync(handle.fileno())
    except BaseException:
        path.unlink()
        raise
    return {'output': str(path), 'sha256': sha(raw), 'source_files': len(sources)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('session'); p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    p = sub.add_parser('graph'); p.add_argument('--nodes', required=True); p.add_argument('--chains', required=True); p.add_argument('--format'); p.add_argument('--output', required=True)
    p = sub.add_parser('view'); p.add_argument('--input', required=True); p.add_argument('--output', required=True)
    a = parser.parse_args(argv)
    try:
        if a.command == 'session':
            path, raw, data = source(a.input); sources = [(path, raw)]; result = envelope(sources); normalize_session(data, result)
        elif a.command == 'graph':
            np, nr, nodes = source(a.nodes, True); cp, cr, chains = source(a.chains, True); sources = [(np,nr),(cp,cr)]
            if a.format:
                fp, fr, fmt = source(a.format); stamp(fmt, 'graph format'); sources.append((fp,fr))
            result = envelope(sources); normalize_graph(nodes, chains, result)
        else:
            path, raw, result = source(a.input); sources = [(path,raw)]; result = render(result)
        record = publish(result, a.output, sources, a.command == 'view')
        print(json.dumps(record)); return 0
    except (DataError, OSError, UnicodeError, RecursionError, OverflowError) as exc:
        print(str(exc), file=sys.stderr); return 2


if __name__ == '__main__':
    sys.exit(main())
