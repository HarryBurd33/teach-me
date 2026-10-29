#!/usr/bin/env python3
"""Focused asset contract checks and DOM-adapter interaction tests (not browser QA)."""
import json
from pathlib import Path
import re
import subprocess
import unittest
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'candidate' / 'teach-me' / 'assets'


class Markup(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class AssetTests(unittest.TestCase):
    def test_template_security_and_accessibility_contract(self):
        html = (ASSETS / 'graph-editor.html').read_text()
        css = (ASSETS / 'graph-editor.css').read_text()
        js = (ASSETS / 'graph-editor.js').read_text()
        for marker in ['EDITOR_DATA', 'EDITOR_SCRIPT', 'EDITOR_STYLE', 'SCRIPT_HASH', 'STYLE_HASH']:
            self.assertEqual(html.count('{{' + marker + '}}'), 1)
        self.assertIn('<script>{{EDITOR_SCRIPT}}</script>', html)
        self.assertIn('<style>{{EDITOR_STYLE}}</style>', html)
        self.assertIn('default-src \'none\'; script-src \'sha256-{{SCRIPT_HASH}}\'; style-src \'sha256-{{STYLE_HASH}}\'; object-src \'none\'; base-uri \'none\'', html)
        parsed = Markup(html)
        ids = [attrs['id'] for _, attrs in parsed.elements if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        labels = {attrs['for'] for tag, attrs in parsed.elements if tag == 'label'}
        for tag, attrs in parsed.elements:
            self.assertFalse(any(key.startswith('on') for key in attrs))
            self.assertFalse('src' in attrs)
            if tag in ['input', 'select', 'textarea']:
                self.assertIn(attrs['id'], labels)
        self.assertIn(('script', {'type': 'application/json', 'id': 'editor-data'}), parsed.elements)
        self.assertIn('readonly', dict(next(attrs for tag, attrs in parsed.elements if attrs.get('id') == 'exported-draft')))
        for forbidden in ['innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'Function(', 'fetch(', 'XMLHttpRequest', 'WebSocket', 'localStorage', 'sessionStorage', 'serviceWorker', 'document.write', '@import', 'url(']:
            self.assertNotIn(forbidden, js + css)
        self.assertNotRegex(js, r'https?://')
        self.assertIn('@media(max-width:', css)
        self.assertIn('No mastery score', html)
        self.assertIn('new source provenance', html)

    def test_javascript_syntax(self):
        result = subprocess.run(['node', '--check', str(ASSETS / 'graph-editor.js')], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_dom_adapter_interactions(self):
        # The adapter implements only the used DOM API. Actual browser/CSP/download QA is a separate parent gate.
        runner = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const script = fs.readFileSync(process.argv[1], 'utf8');
const ids = [...fs.readFileSync(process.argv[2], 'utf8').matchAll(/id="([^"]+)"/g)].map(m => m[1]);
class Element {
  constructor(tag='div') { this.tagName=tag; this.children=[]; this.events={}; this.value=''; this.textContent=''; this.disabled=false; this.readOnly=false; }
  append(...items) { this.children.push(...items); }
  replaceChildren(...items) { this.children=[...items]; }
  addEventListener(type, callback) { this.events[type]=callback; }
  focus() {}
  remove() { this.removed=true; }
  click() { if(this.tagName==='a') this.clicked=true; else this.fire('click'); }
  fire(type) { if(this.disabled) return; if(this.events[type]) this.events[type]({preventDefault(){}}); }
}
const node = (id, extra={}) => ({id,name:id,statement:'Statement '+id,aliases:[],createdAt:'',provenance:[],...extra});
const chain = (id,premises,conclusion,extra={}) => ({id,premises,conclusion,createdAt:'',provenance:[],...extra});
const base = () => ({format:'teach-me-learning-v1',source_files:[],sessions:[],nodes:[node('a',{aliases:['older'],createdAt:'2020',provenance:[{chatId:'source',messageId:'m'}]}),node('b'),node('c')],chains:[chain('ab',['a','b'],'c',{createdAt:'2021',provenance:[{chatId:'s',messageId:'x'}]})],warnings:['Manual source history']});
function open(graph=base()) {
  const elements = new Map(ids.map(id=>[id,new Element()]));
  elements.get('editor-data').textContent=JSON.stringify({version:1,base_sha256:'a'.repeat(64),graph});
  const urls=[]; const blobs=[]; const body=new Element('body');
  const context={document:{getElementById:id=>elements.get(id),createElement:tag=>new Element(tag),querySelectorAll:()=>[],body},TextEncoder,Blob:class extends Blob { constructor(...args){super(...args);blobs.push(this);} },URL:{createObjectURL(blob){urls.push(blob);return 'blob:local';},revokeObjectURL(){}},setTimeout:fn=>fn()};
  vm.runInNewContext(script,context);
  const el=id=>elements.get(id);
  const fire=(id,type='click')=>el(id).fire(type);
  const select=(kind,id)=>{el(kind+'-select').value=id;fire(kind+'-select','change');};
  const addNode=(id,name=id)=>{fire('node-new');el('node-id').value=id;el('node-name').value=name;el('node-statement').value='Statement '+id;fire('node-form','submit');};
  const addChain=(id,premises,conclusion)=>{fire('chain-new');el('chain-id').value=id;el('chain-premises').value=premises.join('\n');el('chain-conclusion').value=conclusion;fire('chain-form','submit');};
  const exportDraft=()=>{fire('export-draft');return el('exported-draft').value?JSON.parse(el('exported-draft').value):null;};
  return {el,fire,select,addNode,addChain,exportDraft,urls,blobs,body};
}
const text = e => e.textContent + e.children.map(text).join(' ');
let ui=open();
assert.equal(ui.urls.length,0,'no automatic download');
assert.equal(ui.el('export-draft').disabled,false);
ui.select('node','a'); assert.equal(ui.el('node-id').readOnly,true);
ui.el('node-name').value='Changed claim';ui.fire('node-form','submit');
let draft=ui.exportDraft();
assert.deepEqual(Object.keys(draft),['version','base_sha256','patch']);
assert.deepEqual(Object.keys(draft.patch),['version','delete_nodes','delete_chains','upsert_nodes','upsert_chains']);
assert.deepEqual(draft.patch.upsert_nodes[0],node('a',{name:'Changed claim',aliases:['older'],createdAt:'2020',provenance:[{chatId:'source',messageId:'m'}]}));
assert.equal(ui.body.children.at(-1).download,'teach-me-graph-draft.json');
assert.equal(ui.body.children.at(-1).clicked,true);
assert.equal(ui.blobs[0].type,'application/json;charset=utf-8');
ui.fire('node-delete'); assert.match(ui.el('action-status').textContent,/referenced by argument/);
assert.equal(ui.exportDraft().patch.delete_nodes.length,0);
ui.select('chain','ab');ui.el('chain-premises').value='b\na';ui.fire('chain-form','submit');
draft=ui.exportDraft();assert.deepEqual(draft.patch.upsert_chains[0],chain('ab',['b','a'],'c',{createdAt:'2021',provenance:[{chatId:'s',messageId:'x'}]}));
ui.addNode('x','<img src=x onerror=alert(1)>');
assert.equal(ui.el('exported-draft').value,'','editing invalidates exported copy');
draft=ui.exportDraft();assert.deepEqual(draft.patch.upsert_nodes.at(-1),node('x',{name:'<img src=x onerror=alert(1)>'}));
assert.match(text(ui.el('graph-cards')),/<img src=x onerror=alert\(1\)>/);
assert.equal(ui.el('graph-cards').children.flatMap(c=>c.children).some(c=>c.tagName==='img'),false);
ui.addChain('joint',['a','b','x'],'x');
draft=ui.exportDraft();assert.deepEqual(draft.patch.upsert_chains.at(-1),chain('joint',['a','b','x'],'x'));
assert.match(text(ui.el('graph-cards')),/AND/);
ui.el('graph-search').value='zzzz';ui.fire('graph-search','input');assert.equal(ui.el('search-empty').hidden,false);
ui.el('graph-search').value='older';ui.fire('graph-search','input');assert.equal(ui.el('graph-cards').children.length,1);
ui.fire('reset-all');assert.equal(ui.el('exported-draft').value,'');
draft=ui.exportDraft();assert.deepEqual(draft.patch,{version:1,delete_nodes:[],delete_chains:[],upsert_nodes:[],upsert_chains:[]});
ui.select('chain','ab');ui.fire('chain-delete');ui.select('node','a');ui.fire('node-delete');
draft=ui.exportDraft();assert.deepEqual(draft.patch.delete_chains,['ab']);assert.deepEqual(draft.patch.delete_nodes,['a']);
ui.addNode('a','Restored');draft=ui.exportDraft();assert.deepEqual(draft.patch.upsert_nodes[0],node('a',{name:'Restored',aliases:['older'],createdAt:'2020',provenance:[{chatId:'source',messageId:'m'}]}));
ui.addChain('ab',['a','b'],'c');draft=ui.exportDraft();assert.deepEqual(draft.patch.upsert_chains,[],'restored base chain retains metadata');
ui=open();ui.addChain('bad',['a','a'],'c');assert.match(ui.el('action-status').textContent,/unique/);assert.equal(ui.exportDraft().patch.upsert_chains.length,0);
ui.addNode(' a ');assert.match(ui.el('action-status').textContent,/without surrounding/);
ui.select('node','a');ui.el('node-id').value='renamed';ui.fire('node-form','submit');assert.match(ui.el('action-status').textContent,/cannot be changed/);
ui=open({...base(),nodes:[node('a')],chains:[chain('gap',['a','missing1'],'missing2')]});
assert.equal(ui.el('export-draft').disabled,true);
ui.addNode('missing1');assert.equal(ui.el('export-draft').disabled,true);
ui.addNode('missing2');assert.equal(ui.el('export-draft').disabled,false);
assert.equal(ui.exportDraft().patch.upsert_nodes.length,2);
ui=open();ui.addChain('same',['b','a'],'c');assert.equal(ui.el('export-draft').disabled,true);assert.match(text(ui.el('validation-messages')),/duplicates/);
ui=open({...base(),nodes:Array.from({length:256},(_,i)=>node('n'+i)),chains:[]});
ui.addNode('over');assert.equal(ui.el('export-draft').disabled,true);
ui=open();ui.addNode('huge','\u2603'.repeat(750000));assert.equal(ui.el('export-draft').disabled,true);assert.match(text(ui.el('validation-messages')),/2 MiB/);assert.equal(ui.urls.length,0);
ui=open();ui.addNode('😀'.repeat(128));assert.equal(ui.exportDraft().patch.upsert_nodes[0].id.length,256);
ui=open();ui.addNode('😀'.repeat(129));assert.match(ui.el('action-status').textContent,/128/);
console.log(JSON.stringify({passed:true,assertions:'metadata, AND, reference refusal, explicit export, reset, repair, inert DOM text, search, schema, ID immutability, duplicates, UTF8 bytes, graph limits'}));
'''
        result = subprocess.run(['node', '-e', runner, str(ASSETS / 'graph-editor.js'), str(ASSETS / 'graph-editor.html')], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)['passed'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
