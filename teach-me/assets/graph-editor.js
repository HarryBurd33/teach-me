(function () {
  'use strict';
  const LIMIT = 2097152;
  const MAX_RECORDS = 256;
  const HISTORY_STEPS = 20;
  const HISTORY_BYTES = 8388608;
  const encodedBytes = (text) => new TextEncoder().encode(text).length;
  const $ = (id) => document.getElementById(id);
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const make = (tag, text, className) => {
    const element = document.createElement(tag);
    if (text !== undefined) element.textContent = text;
    if (className) element.className = className;
    return element;
  };
  let source;
  try {
    source = JSON.parse($('editor-data').textContent);
    if (source.version !== 1 || !/^[a-f0-9]{64}$/.test(source.base_sha256) ||
        !Array.isArray(source.graph.nodes) || !Array.isArray(source.graph.chains)) {
      throw new Error('Unsupported embedded graph data.');
    }
  } catch (error) {
    $('action-status').textContent = 'Unable to open the embedded graph: ' + error.message;
    document.querySelectorAll('button, input, select, textarea').forEach((element) => { element.disabled = true; });
    return;
  }
  const base = clone(source.graph);
  let graph = clone(base);
  let selectedNode = '';
  let selectedChain = '';
  const say = (message) => { $('action-status').textContent = message; };
  const focus = (id) => { const element = $(id); if (element) element.focus(); };
  const fail = (message, field) => { const error = new Error(message); error.field = field; throw error; };
  let undo = [];
  let redo = [];
  let evicted = 0;
  const historyBytes = () => undo.concat(redo).reduce((sum, text) => sum + encodedBytes(text), 0);
  const trimHistory = () => {
    const before = evicted;
    while (undo.length + redo.length > HISTORY_STEPS || historyBytes() > HISTORY_BYTES) {
      if (undo.length) undo.shift(); else redo.shift();
      evicted++;
    }
    return evicted > before;
  };
  const showHistory = () => {
    $('undo-draft').disabled = !undo.length;
    $('redo-draft').disabled = !redo.length;
    $('history-summary').textContent = 'Undo: ' + undo.length + ' · Redo: ' + redo.length +
      ' · History: ' + historyBytes() + ' / ' + HISTORY_BYTES + ' bytes; ' + HISTORY_STEPS +
      ' steps maximum. ' + (evicted ? evicted + ' oldest snapshot(s) discarded to keep history bounded. ' : '') +
      'Staged graph only; unsaved form text is not included. Export before closing.';
  };
  const equal = (left, right) => {
    if (left === right) return true;
    if (!left || !right || typeof left !== 'object' || typeof right !== 'object' || Array.isArray(left) !== Array.isArray(right)) return false;
    const a = Object.keys(left).sort(), b = Object.keys(right).sort();
    return a.length === b.length && a.every((key, i) => key === b[i] && equal(left[key], right[key]));
  };
  // This small JSON reader rejects duplicate decoded member names before values can overwrite them.
  // It uses no executable parsing path and bounds nesting independently of the byte limit.
  const strictJSON = (text) => {
    if (encodedBytes(text) > LIMIT) throw new Error('Draft exceeds the 2 MiB import limit.');
    let at = 0;
    const space = () => { while (at < text.length && /[ \t\r\n]/.test(text[at])) at++; };
    const invalid = () => { throw new Error('Malformed JSON near character ' + at + '.'); };
    const string = () => {
      const start = at++;
      while (at < text.length) {
        const c = text[at++];
        if (c === '"') return JSON.parse(text.slice(start, at));
        if (c === '\\') at++;
      }
      return invalid();
    };
    const value = (depth) => {
      if (depth > 64) throw new Error('Draft JSON exceeds the 64-level nesting limit.');
      space(); const c = text[at];
      if (c === '"') return string();
      if (c === '{') {
        at++; space(); const result = Object.create(null), keys = new Set();
        if (text[at] === '}') { at++; return result; }
        while (at < text.length) {
          if (text[at] !== '"') return invalid();
          const key = string();
          if (keys.has(key)) throw new Error('Duplicate JSON member: ' + key);
          keys.add(key); space(); if (text[at++] !== ':') return invalid();
          space(); const valueStart = at; result[key] = value(depth + 1);
          if (key === 'version' && result[key] === 1 && text.slice(valueStart, at) !== '1') throw new Error('Version must use the integer JSON token 1.');
          space();
          const end = text[at++]; if (end === '}') return result;
          if (end !== ',') return invalid(); space();
        }
        return invalid();
      }
      if (c === '[') {
        at++; space(); const result = [];
        if (text[at] === ']') { at++; return result; }
        while (at < text.length) {
          result.push(value(depth + 1)); space();
          const end = text[at++]; if (end === ']') return result;
          if (end !== ',') return invalid();
        }
        return invalid();
      }
      for (const [token, parsed] of [['true', true], ['false', false], ['null', null]]) {
        if (text.slice(at, at + token.length) === token) { at += token.length; return parsed; }
      }
      const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(text.slice(at));
      if (!match) return invalid();
      at += match[0].length; const number = Number(match[0]);
      if (!Number.isFinite(number)) throw new Error('Nonfinite JSON number.');
      return number;
    };
    const result = value(0); space(); if (at !== text.length) invalid(); return result;
  };
  const exact = (value, keys, label) => {
    if (!value || Array.isArray(value) || typeof value !== 'object' ||
        Object.keys(value).length !== keys.length || keys.some((key) => !Object.prototype.hasOwnProperty.call(value, key))) {
      throw new Error(label + ' has unsupported or missing fields.');
    }
  };
  const importedGraph = (text) => {
    const draft = strictJSON(text);
    exact(draft, ['version', 'base_sha256', 'patch'], 'Draft');
    if (draft.version !== 1) throw new Error('Draft version must be 1.');
    if (draft.base_sha256 !== source.base_sha256) throw new Error('Draft base SHA256 does not match this editor. Keep your current work and open the exact original base.');
    const patch = draft.patch;
    exact(patch, ['version', 'delete_nodes', 'delete_chains', 'upsert_nodes', 'upsert_chains'], 'Patch');
    if (patch.version !== 1) throw new Error('Patch version must be 1.');
    for (const field of ['delete_nodes', 'delete_chains', 'upsert_nodes', 'upsert_chains']) {
      if (!Array.isArray(patch[field]) || patch[field].length > MAX_RECORDS) throw new Error(field + ' must be an array of at most 256 records.');
    }
    const result = clone(base);
    for (const [field, deleted, upserted] of [['nodes', 'delete_nodes', 'upsert_nodes'], ['chains', 'delete_chains', 'upsert_chains']]) {
      const originals = new Map(base[field].map((record) => [record.id, record]));
      const current = new Map(base[field].map((record) => [record.id, clone(record)]));
      const removed = new Set();
      for (const id of patch[deleted]) {
        requireId(id, deleted);
        if (removed.has(id)) throw new Error('Duplicate deletion ID in ' + deleted + '.');
        if (!originals.has(id)) throw new Error('Cannot delete unknown ' + field + ' ID: ' + id);
        removed.add(id); current.delete(id);
      }
      const seen = new Set();
      for (const record of patch[upserted]) {
        exact(record, field === 'nodes' ? ['id', 'name', 'statement', 'aliases', 'createdAt', 'provenance'] :
          ['id', 'premises', 'conclusion', 'createdAt', 'provenance'], 'Imported ' + field + ' record');
        requireId(record.id, 'Record ID');
        if (seen.has(record.id) || removed.has(record.id)) throw new Error('Duplicate or overlapping patch ID: ' + record.id);
        seen.add(record.id);
        if (typeof record.createdAt !== 'string' || !Array.isArray(record.provenance)) throw new Error('Malformed record metadata.');
        for (const point of record.provenance) {
          exact(point, ['chatId', 'messageId'], 'Provenance');
          if (typeof point.chatId !== 'string' || !point.chatId.trim() || typeof point.messageId !== 'string') throw new Error('Malformed provenance text.');
        }
        if (field === 'nodes') {
          if (typeof record.name !== 'string' || typeof record.statement !== 'string' || !Array.isArray(record.aliases) ||
              record.aliases.some((alias) => typeof alias !== 'string' || !alias.trim())) throw new Error('Malformed claim text or aliases.');
        } else {
          if (!Array.isArray(record.premises) || !record.premises.length || record.premises.length > MAX_RECORDS ||
              record.premises.some((id) => !validId(id)) || new Set(record.premises).size !== record.premises.length) throw new Error('Argument premises must contain unique valid IDs.');
          requireId(record.conclusion, 'Conclusion ID');
        }
        const prior = originals.get(record.id);
        for (const key of field === 'nodes' ? ['aliases', 'createdAt', 'provenance'] : ['createdAt', 'provenance']) {
          const expected = prior ? prior[key] : (key === 'createdAt' ? '' : []);
          if (!equal(record[key], expected)) throw new Error('Import may not change or invent ' + key + ' metadata for ' + record.id + '.');
        }
        // Retain original field ordering as well as values, making export/re-import a stable no-op.
        const kept = prior ? clone(prior) : clone(record);
        for (const key of field === 'nodes' ? ['name', 'statement'] : ['premises', 'conclusion']) kept[key] = clone(record[key]);
        current.set(record.id, kept);
      }
      result[field] = [...current.values()];
    }
    const before = graph;
    let errors;
    try { graph = result; errors = validation(getPatch()); } finally { graph = before; }
    if (errors.length) throw new Error(errors[0]);
    return result;
  };
  const validId = (value) => typeof value === 'string' && value.trim().length > 0 &&
    value === value.trim() && Array.from(value).length <= 128 && !/[\x00-\x1f\x7f]/.test(value);
  const requireId = (value, label) => {
    if (!validId(value)) throw new Error(label + ' must be 1–128 characters, without surrounding whitespace or control characters.');
  };
  const getPatch = () => {
    const patch = {version: 1, delete_nodes: [], delete_chains: [], upsert_nodes: [], upsert_chains: []};
    for (const [field, deleted, upserted] of [['nodes', 'delete_nodes', 'upsert_nodes'], ['chains', 'delete_chains', 'upsert_chains']]) {
      const before = new Map(base[field].map((record) => [record.id, record]));
      const after = new Map(graph[field].map((record) => [record.id, record]));
      for (const record of base[field]) if (!after.has(record.id)) patch[deleted].push(record.id);
      for (const record of graph[field]) {
        if (!before.has(record.id) || JSON.stringify(before.get(record.id)) !== JSON.stringify(record)) patch[upserted].push(clone(record));
      }
    }
    return patch;
  };
  const draftText = (patch) => JSON.stringify({version: 1, base_sha256: source.base_sha256, patch: patch}, null, 2) + '\n';
  const validation = (patch) => {
    const errors = [];
    if (graph.nodes.length > MAX_RECORDS || graph.chains.length > MAX_RECORDS) errors.push('The final graph may contain at most 256 claims and 256 arguments.');
    const known = new Set(graph.nodes.map((node) => node.id));
    const logical = new Set();
    for (const node of graph.nodes) if (!validId(node.id)) errors.push('Invalid claim ID: ' + node.id);
    for (const chain of graph.chains) {
      if (!validId(chain.id) || !validId(chain.conclusion) || !chain.premises.length ||
          chain.premises.some((id) => !validId(id)) || new Set(chain.premises).size !== chain.premises.length) errors.push('Argument ' + chain.id + ' requires valid, unique premise IDs and a conclusion ID.');
      const missing = [...new Set(chain.premises.concat([chain.conclusion]).filter((id) => !known.has(id)))];
      if (missing.length) errors.push('Argument ' + chain.id + ' has unresolved endpoints: ' + missing.join(', ') + '. Add claims or edit/delete this argument.');
      const signature = JSON.stringify([chain.premises.slice().sort(), chain.conclusion]);
      if (logical.has(signature)) errors.push('Argument ' + chain.id + ' duplicates another argument with the same joint premises and conclusion.');
      logical.add(signature);
    }
    for (const field of ['delete_nodes', 'delete_chains', 'upsert_nodes', 'upsert_chains']) {
      if (patch[field].length > MAX_RECORDS) errors.push('Draft exceeds 256 records in ' + field + '.');
    }
    if (new TextEncoder().encode(draftText(patch)).length > LIMIT) errors.push('The draft exceeds the 2 MiB export limit. Reduce the staged changes.');
    return errors;
  };
  const option = (value, text) => { const item = make('option', text); item.value = value; return item; };
  const editNode = (id) => {
    selectedNode = id;
    const node = graph.nodes.find((item) => item.id === id);
    $('node-select').value = id;
    $('node-id').value = node ? node.id : '';
    $('node-id').readOnly = !!node;
    $('node-name').value = node ? node.name : '';
    $('node-statement').value = node ? node.statement : '';
    $('node-delete').disabled = !node;
    $('node-save').textContent = node ? 'Stage claim update' : 'Stage new claim';
  };
  const editChain = (id) => {
    selectedChain = id;
    const chain = graph.chains.find((item) => item.id === id);
    $('chain-select').value = id;
    $('chain-id').value = chain ? chain.id : '';
    $('chain-id').readOnly = !!chain;
    $('chain-premises').value = chain ? chain.premises.join('\n') : '';
    $('chain-conclusion').value = chain ? chain.conclusion : '';
    $('chain-delete').disabled = !chain;
    $('chain-save').textContent = chain ? 'Stage argument update' : 'Stage new argument';
  };
  const updateSelects = () => {
    $('node-select').replaceChildren(option('', 'Add a new claim'));
    $('chain-select').replaceChildren(option('', 'Add a new argument'));
    $('known-node-ids').replaceChildren();
    for (const node of graph.nodes) {
      $('node-select').append(option(node.id, node.id + (node.name ? ' — ' + node.name : '')));
      $('known-node-ids').append(option(node.id, node.name || node.id));
    }
    for (const chain of graph.chains) $('chain-select').append(option(chain.id, chain.id));
    $('node-select').value = selectedNode;
    $('chain-select').value = selectedChain;
  };
  const drawCards = () => {
    const target = $('graph-cards');
    target.replaceChildren();
    const query = $('graph-search').value.toLowerCase();
    const names = new Map(graph.nodes.map((node) => [node.id, node.name || node.id]));
    const endpoint = (id) => (names.has(id) ? names.get(id) : '[missing claim]') + ' (' + id + ')';
    let count = 0;
    for (const node of graph.nodes) {
      if (query && !JSON.stringify(node).toLowerCase().includes(query)) continue;
      const card = make('article', undefined, 'card');
      card.append(make('h3', node.name || node.id), make('p', node.statement), make('small', 'Claim ID: ' + node.id, 'metadata'),
        make('small', 'Aliases: ' + (node.aliases.join('; ') || '(none)'), 'metadata'),
        make('small', 'Created: ' + (node.createdAt || '(unspecified)') + '\nRetained provenance: ' + JSON.stringify(node.provenance), 'metadata'));
      const button = make('button', 'Edit claim ' + node.id, 'secondary');
      button.type = 'button';
      button.addEventListener('click', () => { editNode(node.id); focus('node-name'); });
      card.append(button); target.append(card); count++;
    }
    for (const chain of graph.chains) {
      const searchable = JSON.stringify(chain) + ' ' + chain.premises.concat([chain.conclusion]).map(endpoint).join(' ');
      if (query && !searchable.toLowerCase().includes(query)) continue;
      const card = make('article', undefined, 'card argument');
      card.append(make('h3', 'Argument ' + chain.id));
      const line = make('p', undefined, 'argument-line');
      chain.premises.forEach((id, index) => {
        if (index) line.append(make('span', ' AND ', 'and'));
        line.append(make('span', endpoint(id), names.has(id) ? '' : 'missing'));
      });
      line.append(make('span', ' ⇒ ', 'and'), make('strong', endpoint(chain.conclusion), names.has(chain.conclusion) ? '' : 'missing'));
      card.append(line, make('small', 'Created: ' + (chain.createdAt || '(unspecified)') + '\nRetained provenance: ' + JSON.stringify(chain.provenance), 'metadata'));
      const button = make('button', 'Edit argument ' + chain.id, 'secondary');
      button.type = 'button';
      button.addEventListener('click', () => { editChain(chain.id); focus('chain-premises'); });
      card.append(button); target.append(card); count++;
    }
    $('search-empty').hidden = count !== 0;
    $('graph-summary').textContent = graph.nodes.length + ' claims · ' + graph.chains.length + ' arguments · ' + count + ' visible cards';
  };
  const refresh = () => {
    updateSelects(); drawCards();
    const patch = getPatch();
    const pending = $('pending-changes'); pending.replaceChildren();
    for (const [field, label] of [['delete_nodes', 'Delete claim'], ['delete_chains', 'Delete argument'], ['upsert_nodes', 'Add/update claim'], ['upsert_chains', 'Add/update argument']]) {
      for (const item of patch[field]) pending.append(make('li', label + ': ' + (typeof item === 'string' ? item : item.id)));
    }
    const count = patch.delete_nodes.length + patch.delete_chains.length + patch.upsert_nodes.length + patch.upsert_chains.length;
    $('pending-summary').textContent = count ? count + ' record change(s) staged. Nothing has been written to the base file.' : 'No changes staged. The graph matches the base.';
    const errors = validation(patch);
    $('validation-messages').replaceChildren();
    if (errors.length) for (const error of errors) $('validation-messages').append(make('li', error));
    else $('validation-messages').append(make('li', 'Structure is ready to export. Semantic correctness and evidence are not verified.', 'valid'));
    $('export-draft').disabled = errors.length > 0;
    showHistory();
  };
  const changed = (message) => { $('exported-draft').value = ''; refresh(); say(message); };
  const handle = (action, fallback = 'graph-search') => (event) => {
    event.preventDefault();
    const before = JSON.stringify(graph), savedExport = $('exported-draft').value;
    const nodeSelection = selectedNode, chainSelection = selectedChain;
    try {
      action();
      if (JSON.stringify(graph) !== before) {
        undo.push(before); redo = [];
        const discarded = trimHistory();
        showHistory();
        if (discarded) say($('action-status').textContent + ' Oldest history discarded to keep the 20-step / 8 MiB bound.');
      }
    } catch (error) {
      graph = JSON.parse(before); selectedNode = nodeSelection; selectedChain = chainSelection;
      $('exported-draft').value = savedExport;
      say('Cannot stage this change: ' + error.message); focus(error.field || fallback);
    }
  };
  $('node-form').addEventListener('submit', handle(() => {
    const id = $('node-id').value;
    if (!validId(id)) fail('Claim ID must be 1–128 characters, without surrounding whitespace or control characters.', 'node-id');
    if (selectedNode && id !== selectedNode) throw new Error('Existing IDs cannot be changed while editing.');
    const index = graph.nodes.findIndex((node) => node.id === id);
    if (!selectedNode && index !== -1) throw new Error('That claim ID already exists. Select it to edit.');
    const prior = index === -1 ? base.nodes.find((node) => node.id === id) : graph.nodes[index];
    const record = prior ? clone(prior) : {id: id, name: '', statement: '', aliases: [], createdAt: '', provenance: []};
    record.name = $('node-name').value;
    record.statement = $('node-statement').value;
    if (index === -1) graph.nodes.push(record); else graph.nodes[index] = record;
    selectedNode = id; changed('Claim ' + id + ' staged in memory.'); editNode(id);
  }, 'node-id'));
  $('chain-form').addEventListener('submit', handle(() => {
    const id = $('chain-id').value;
    if (!validId(id)) fail('Argument ID must be 1–128 characters, without surrounding whitespace or control characters.', 'chain-id');
    if (selectedChain && id !== selectedChain) throw new Error('Existing IDs cannot be changed while editing.');
    const premises = $('chain-premises').value.split(/\r?\n/);
    if (!premises.length || premises.some((item) => !validId(item))) fail('Enter one valid premise ID per line; blank lines are not IDs.', 'chain-premises');
    if (new Set(premises).size !== premises.length) fail('Premise IDs must be unique.', 'chain-premises');
    const conclusion = $('chain-conclusion').value;
    if (!validId(conclusion)) fail('Conclusion ID must be 1–128 characters, without surrounding whitespace or control characters.', 'chain-conclusion');
    const index = graph.chains.findIndex((chain) => chain.id === id);
    if (!selectedChain && index !== -1) throw new Error('That argument ID already exists. Select it to edit.');
    const prior = index === -1 ? base.chains.find((chain) => chain.id === id) : graph.chains[index];
    const record = prior ? clone(prior) : {id: id, premises: [], conclusion: '', createdAt: '', provenance: []};
    record.premises = premises; record.conclusion = conclusion;
    if (index === -1) graph.chains.push(record); else graph.chains[index] = record;
    selectedChain = id; changed('Argument ' + id + ' staged in memory.'); editChain(id);
  }, 'chain-id'));
  $('node-delete').addEventListener('click', handle(() => {
    if (!selectedNode) throw new Error('Select a claim first.');
    const references = graph.chains.filter((chain) => chain.premises.includes(selectedNode) || chain.conclusion === selectedNode);
    if (references.length) throw new Error('Claim ' + selectedNode + ' is referenced by argument(s): ' + references.map((chain) => chain.id).join(', ') + '. Edit or delete those arguments first; no cascade is performed.');
    graph.nodes = graph.nodes.filter((node) => node.id !== selectedNode);
    editNode(''); changed('Claim deletion staged in memory.'); focus('node-id');
  }, 'node-name'));
  $('chain-delete').addEventListener('click', handle(() => {
    if (!selectedChain) throw new Error('Select an argument first.');
    graph.chains = graph.chains.filter((chain) => chain.id !== selectedChain);
    editChain(''); changed('Argument deletion staged in memory.'); focus('chain-id');
  }, 'chain-premises'));
  $('node-select').addEventListener('change', () => { editNode($('node-select').value); focus(selectedNode ? 'node-name' : 'node-id'); });
  $('chain-select').addEventListener('change', () => { editChain($('chain-select').value); focus(selectedChain ? 'chain-premises' : 'chain-id'); });
  $('node-new').addEventListener('click', () => { editNode(''); $('node-id').focus(); });
  $('chain-new').addEventListener('click', () => { editChain(''); $('chain-id').focus(); });
  $('graph-search').addEventListener('input', drawCards);
  $('reset-all').addEventListener('click', handle(() => {
    graph = clone(base); editNode(''); editChain(''); changed('All staged changes reset to the base graph.'); focus('reset-all');
  }));
  const travel = (from, to, label) => {
    if (!from.length) return;
    to.push(JSON.stringify(graph)); graph = JSON.parse(from.pop());
    const discarded = trimHistory();
    editNode(''); editChain(''); changed(label + ' restored a staged graph. Unsaved form text is not restored.');
    if (discarded) say($('action-status').textContent + ' Oldest history discarded to keep the 20-step / 8 MiB bound.');
    focus('graph-search');
  };
  $('undo-draft').addEventListener('click', () => travel(undo, redo, 'Undo'));
  $('redo-draft').addEventListener('click', () => travel(redo, undo, 'Redo'));
  $('import-draft').addEventListener('click', handle(() => {
    const incoming = importedGraph($('import-draft-text').value);
    if (equal(graph, incoming)) { say('Draft already matches the staged graph; no history added.'); return; }
    graph = incoming; editNode(''); editChain('');
    changed('Draft imported into memory against the exact original base. Review it before exporting or applying.'); focus('graph-search');
  }, 'import-draft-text'));
  $('export-draft').addEventListener('click', () => {
    const patch = getPatch();
    const errors = validation(patch);
    if (errors.length) { refresh(); say('Cannot export: ' + errors[0]); return; }
    const text = draftText(patch);
    $('exported-draft').value = text;
    let url;
    let link;
    try {
      const blob = new Blob([text], {type: 'application/json;charset=utf-8'});
      if (blob.size > LIMIT) throw new Error('Draft exceeds the 2 MiB limit.');
      url = URL.createObjectURL(blob);
      link = make('a'); link.href = url; link.download = 'teach-me-graph-draft.json';
      document.body.append(link); link.click();
      say('Draft exported. A copy is available below. Review and check it before applying to a new file.');
    } catch (error) {
      say('The browser could not start the download. Copy the exported draft below into teach-me-graph-draft.json. ' + error.message);
    } finally {
      if (link) link.remove();
      if (url) setTimeout(() => URL.revokeObjectURL(url), 1000);
    }
  });
  $('base-digest').textContent = 'Base SHA256: ' + source.base_sha256;
  for (const warning of base.warnings) $('base-warnings').append(make('li', warning));
  if (!base.warnings.length) $('base-warnings').append(make('li', 'No warnings stored in the base document.'));
  editNode(''); editChain(''); refresh();
}());
