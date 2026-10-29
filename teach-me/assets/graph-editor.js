(function () {
  'use strict';
  const LIMIT = 2097152;
  const MAX_RECORDS = 256;
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
      button.addEventListener('click', () => { editNode(node.id); $('node-id').focus(); });
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
      button.addEventListener('click', () => { editChain(chain.id); $('chain-id').focus(); });
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
  };
  const changed = (message) => { $('exported-draft').value = ''; refresh(); say(message); };
  const handle = (action) => (event) => {
    event.preventDefault();
    try { action(); } catch (error) { say('Cannot stage this change: ' + error.message); }
  };
  $('node-form').addEventListener('submit', handle(() => {
    const id = $('node-id').value;
    requireId(id, 'Claim ID');
    if (selectedNode && id !== selectedNode) throw new Error('Existing IDs cannot be changed while editing.');
    const index = graph.nodes.findIndex((node) => node.id === id);
    if (!selectedNode && index !== -1) throw new Error('That claim ID already exists. Select it to edit.');
    const prior = index === -1 ? base.nodes.find((node) => node.id === id) : graph.nodes[index];
    const record = prior ? clone(prior) : {id: id, name: '', statement: '', aliases: [], createdAt: '', provenance: []};
    record.name = $('node-name').value;
    record.statement = $('node-statement').value;
    if (index === -1) graph.nodes.push(record); else graph.nodes[index] = record;
    selectedNode = id; changed('Claim ' + id + ' staged in memory.'); editNode(id);
  }));
  $('chain-form').addEventListener('submit', handle(() => {
    const id = $('chain-id').value;
    requireId(id, 'Argument ID');
    if (selectedChain && id !== selectedChain) throw new Error('Existing IDs cannot be changed while editing.');
    const premises = $('chain-premises').value.split(/\r?\n/);
    if (!premises.length || premises.some((item) => !validId(item))) throw new Error('Enter one valid premise ID per line; blank lines are not IDs.');
    if (new Set(premises).size !== premises.length) throw new Error('Premise IDs must be unique.');
    const conclusion = $('chain-conclusion').value;
    requireId(conclusion, 'Conclusion ID');
    const index = graph.chains.findIndex((chain) => chain.id === id);
    if (!selectedChain && index !== -1) throw new Error('That argument ID already exists. Select it to edit.');
    const prior = index === -1 ? base.chains.find((chain) => chain.id === id) : graph.chains[index];
    const record = prior ? clone(prior) : {id: id, premises: [], conclusion: '', createdAt: '', provenance: []};
    record.premises = premises; record.conclusion = conclusion;
    if (index === -1) graph.chains.push(record); else graph.chains[index] = record;
    selectedChain = id; changed('Argument ' + id + ' staged in memory.'); editChain(id);
  }));
  $('node-delete').addEventListener('click', handle(() => {
    if (!selectedNode) throw new Error('Select a claim first.');
    const references = graph.chains.filter((chain) => chain.premises.includes(selectedNode) || chain.conclusion === selectedNode);
    if (references.length) throw new Error('Claim ' + selectedNode + ' is referenced by argument(s): ' + references.map((chain) => chain.id).join(', ') + '. Edit or delete those arguments first; no cascade is performed.');
    graph.nodes = graph.nodes.filter((node) => node.id !== selectedNode);
    editNode(''); changed('Claim deletion staged in memory.');
  }));
  $('chain-delete').addEventListener('click', handle(() => {
    if (!selectedChain) throw new Error('Select an argument first.');
    graph.chains = graph.chains.filter((chain) => chain.id !== selectedChain);
    editChain(''); changed('Argument deletion staged in memory.');
  }));
  $('node-select').addEventListener('change', () => editNode($('node-select').value));
  $('chain-select').addEventListener('change', () => editChain($('chain-select').value));
  $('node-new').addEventListener('click', () => { editNode(''); $('node-id').focus(); });
  $('chain-new').addEventListener('click', () => { editChain(''); $('chain-id').focus(); });
  $('graph-search').addEventListener('input', drawCards);
  $('reset-all').addEventListener('click', () => {
    graph = clone(base); editNode(''); editChain(''); changed('All staged changes reset to the base graph.');
  });
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
