'use strict';
// Independent graph editor contract runner. DOM adapter, not a browser.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const [scriptPath, htmlPath, testName] = process.argv.slice(2);
const script = fs.readFileSync(scriptPath,'utf8');
const html = fs.readFileSync(htmlPath,'utf8');
const clone = x => JSON.parse(JSON.stringify(x));
const node = (id, extra={}) => ({id,name:id,statement:'Claim '+id,aliases:[],createdAt:'',provenance:[],...extra});
const chain = (id='joint',extra={}) => ({id,premises:['a','b'],conclusion:'c',createdAt:'2025-01-01',provenance:[{chatId:'old',messageId:'m'}],...extra});
const base = () => ({format:'teach-me-learning-v1',source_files:[],sessions:[],nodes:[node('a',{aliases:['historical'],createdAt:'2024-01-01',provenance:[{chatId:'old',messageId:'p'}]}),node('b'),node('c')],chains:[chain()],warnings:['Historical warning']});
class Element {
 constructor(tag='div',id=''){this.tagName=tag.toUpperCase();this.id=id;this.children=[];this.events={};this.value='';this.textContent='';this.disabled=false;this.readOnly=false;this.attributes={};this.hidden=false;}
 append(...items){this.children.push(...items);}
 replaceChildren(...items){this.children=[...items];}
 addEventListener(type,fn){this.events[type]=fn;}
 setAttribute(k,v){this.attributes[k]=String(v);}
 getAttribute(k){return this.attributes[k]??null;}
 removeAttribute(k){delete this.attributes[k];}
 focus(){this.doc.activeElement=this;}
 remove(){this.removed=true;}
 click(){if(this.tagName==='A')this.clicked=true;else this.fire('click');}
 fire(type){if(!this.disabled&&this.events[type])this.events[type]({preventDefault(){},target:this,currentTarget:this});}
}
function open(graph=base()){
 const ids=[...html.matchAll(/id="([^"]+)"/g)].map(x=>x[1]);
 const elements=new Map(ids.map(id=>[id,new Element('div',id)]));
 const body=new Element('body');
 const doc={activeElement:null,body,getElementById:id=>elements.get(id),createElement:tag=>{const e=new Element(tag);e.doc=doc;return e;},querySelectorAll:()=>[],addEventListener(){}};
 body.doc=doc;for(const e of elements.values())e.doc=doc;
 elements.get('editor-data').textContent=JSON.stringify({version:1,base_sha256:'a'.repeat(64),graph});
 const context={document:doc,TextEncoder,TextDecoder,Blob,console,URL:{createObjectURL(){return 'blob:synthetic';},revokeObjectURL(){}},setTimeout:fn=>fn(),requestAnimationFrame:fn=>fn()};
 vm.runInNewContext(script,context,{timeout:3000});
 const el=id=>{assert.ok(elements.has(id),'Missing control '+id);return elements.get(id);};
 const fire=(id,type='click')=>el(id).fire(type);
 const select=(kind,id)=>{el(kind+'-select').value=id;fire(kind+'-select','change');};
 const editName=(value,id='a')=>{select('node',id);el('node-name').value=value;fire('node-form','submit');};
 const addNode=(id,name=id)=>{fire('node-new');el('node-id').value=id;el('node-name').value=name;el('node-statement').value='Claim '+id;fire('node-form','submit');};
 const exported=()=>{fire('export-draft');assert.ok(el('exported-draft').value,'No exported draft');return JSON.parse(el('exported-draft').value);};
 const importRaw=raw=>{el('import-draft-text').value=raw;fire('import-draft');};
 const importDraft=d=>importRaw(JSON.stringify(d));
 const graphNow=()=>{
  const d=exported(),g=clone(graph);
  for(const [field,del,up] of [['nodes','delete_nodes','upsert_nodes'],['chains','delete_chains','upsert_chains']]){
   g[field]=g[field].filter(x=>!d.patch[del].includes(x.id));
   for(const v of d.patch[up]){const i=g[field].findIndex(x=>x.id===v.id);if(i<0)g[field].push(v);else g[field][i]=v;}
  }
  return g;
 };
 return {el,fire,select,editName,addNode,exported,importRaw,importDraft,graphNow,doc};
}
const emptyDraft=()=>({version:1,base_sha256:'a'.repeat(64),patch:{version:1,delete_nodes:[],delete_chains:[],upsert_nodes:[],upsert_chains:[]}});
const draftNode=(name='Imported')=>{const d=emptyDraft();d.patch.upsert_nodes=[node('a',{name,aliases:['historical'],createdAt:'2024-01-01',provenance:[{chatId:'old',messageId:'p'}]})];return d;};
const currentName=ui=>ui.graphNow().nodes.find(x=>x.id==='a').name;
function refusal(raw){
 const ui=open();ui.editName('Current work');ui.exported();const before=ui.el('exported-draft').value;const history=ui.el('history-summary').textContent;
 ui.importRaw(raw);assert.equal(ui.el('exported-draft').value,before,'Refusal changed exported copy');assert.equal(ui.el('history-summary').textContent,history,'Refusal changed history');assert.equal(currentName(ui),'Current work','Refusal changed graph');assert.equal(ui.doc.activeElement.id,'import-draft-text','Import error must focus pasted draft');
 ui.fire('undo-draft');assert.equal(currentName(ui),'a');assert.equal(ui.el('undo-draft').disabled,true,'Refusal created extra undo entry');
}
const cases={
 history_exact_metadata(){const ui=open();const initial=ui.graphNow();ui.editName('Changed');const changed=ui.graphNow();assert.deepEqual(changed.nodes[0].aliases,initial.nodes[0].aliases);assert.deepEqual(changed.nodes[0].provenance,initial.nodes[0].provenance);assert.deepEqual(changed.chains,initial.chains);ui.fire('undo-draft');assert.deepEqual(ui.graphNow(),initial);ui.fire('redo-draft');assert.deepEqual(ui.graphNow(),changed);},
 redo_branch_and_noop(){const ui=open();ui.editName('One');ui.editName('Two');ui.fire('undo-draft');ui.editName('Branch');assert.equal(ui.el('redo-draft').disabled,true);ui.fire('undo-draft');assert.equal(currentName(ui),'One');const history=ui.el('history-summary').textContent;ui.editName('One');assert.equal(ui.el('history-summary').textContent,history,'No-op mutated history/redo');assert.equal(ui.el('redo-draft').disabled,false);},
 failed_mutation_preserves(){const ui=open();ui.editName('Keep');ui.exported();const out=ui.el('exported-draft').value,hist=ui.el('history-summary').textContent;ui.select('node','a');ui.fire('node-delete');assert.equal(ui.el('exported-draft').value,out);assert.equal(ui.el('history-summary').textContent,hist);assert.equal(currentName(ui),'Keep');},
 reset_undo_redo(){const ui=open();ui.editName('Saved');const before=ui.graphNow();ui.fire('reset-all');assert.equal(currentName(ui),'a');ui.fire('undo-draft');assert.deepEqual(ui.graphNow(),before);ui.fire('redo-draft');assert.equal(currentName(ui),'a');},
 import_replaces_from_base_and_undo(){const ui=open();ui.addNode('x');ui.importDraft(draftNode());let g=ui.graphNow();assert.equal(g.nodes.some(x=>x.id==='x'),false,'Import incorrectly merged into staged graph');assert.equal(g.nodes[0].name,'Imported');ui.fire('undo-draft');assert.equal(ui.graphNow().nodes.some(x=>x.id==='x'),true);ui.fire('redo-draft');assert.equal(currentName(ui),'Imported');},
 import_roundtrip_and_joint(){const ui=open();ui.editName('Restored');ui.select('chain','joint');ui.el('chain-premises').value='b\na';ui.fire('chain-form','submit');const d=ui.exported();const g=ui.graphNow();ui.fire('reset-all');ui.importDraft(d);assert.deepEqual(ui.graphNow(),g);assert.deepEqual(ui.graphNow().chains[0].premises,['b','a']);},
 reject_malformed(){refusal('{"version":');},
 reject_duplicate_members(){refusal('{"version":1,"version":1,"base_sha256":"'+'a'.repeat(64)+'","patch":'+JSON.stringify(emptyDraft().patch)+'}');},
 reject_nested_duplicate_members(){const d=draftNode();refusal(JSON.stringify(d).replace('"name":"Imported"','"name":"Ignored","name":"Imported"'));},
 reject_wrong_base(){const d=draftNode();d.base_sha256='b'.repeat(64);refusal(JSON.stringify(d));},
 reject_unknown_and_bool(){for(const f of [d=>d.extra=1,d=>d.version=true,d=>d.patch.extra=[],d=>d.patch.version=true]){const d=draftNode();f(d);refusal(JSON.stringify(d));}},
 reject_metadata(){for(const f of [n=>n.aliases=[],n=>n.createdAt='',n=>n.provenance=[]]){const d=draftNode();f(d.patch.upsert_nodes[0]);refusal(JSON.stringify(d));}const d=emptyDraft();d.patch.upsert_nodes=[node('new',{provenance:[{chatId:'fake',messageId:'fake'}]})];refusal(JSON.stringify(d));},
 reject_bad_shapes_ids_endpoints(){for(const f of [d=>d.patch.upsert_nodes[0].id=' bad ',d=>d.patch.upsert_nodes[0].name=9,d=>d.patch.upsert_nodes.push(clone(d.patch.upsert_nodes[0])),d=>d.patch.delete_nodes=['a'],d=>d.patch.delete_nodes=['unknown'],d=>d.patch.upsert_chains=[chain('new',{premises:['a','missing']})],d=>d.patch.upsert_chains=[chain('new',{premises:['a','a']})]]){const d=draftNode();f(d);refusal(JSON.stringify(d));}},
 reject_size_and_depth(){refusal(' '.repeat(2097153));refusal('['.repeat(80)+'0'+']'.repeat(80));},
 history_step_bound(){const ui=open();for(let n=1;n<=25;n++)ui.editName('Name '+n);let undos=0;while(!ui.el('undo-draft').disabled&&undos<30){ui.fire('undo-draft');undos++;}assert.equal(undos,20);assert.equal(currentName(ui),'Name 5');assert.match(ui.el('history-summary').textContent,/evict|discard|drop|oldest|removed/i,'Eviction not disclosed');},
 history_byte_bound(){const graph=base();graph.nodes[0].statement='x'.repeat(1048576);const ui=open(graph);for(let n=1;n<=12;n++)ui.editName('Large '+n);let undos=0;while(!ui.el('undo-draft').disabled&&undos<25){ui.fire('undo-draft');undos++;}assert.ok(undos>0&&undos<=7,'Expected <=7 >1MiB snapshots in8MiB, got '+undos);const summary=ui.el('history-summary').textContent;assert.match(summary,/8388608|8\s*MiB/);},
 focus_controls_and_hostile_text(){const ui=open();ui.select('node','a');assert.equal(ui.doc.activeElement.id,'node-name');ui.fire('node-new');assert.equal(ui.doc.activeElement.id,'node-id');ui.el('node-id').value=' bad ';ui.fire('node-form','submit');assert.equal(ui.doc.activeElement.id,'node-id');ui.addNode('unreferenced','<img src=x onerror=alert(1)>');ui.fire('node-delete');assert.equal(ui.doc.activeElement.id,'node-id');assert.equal(ui.el('node-id').readOnly,false);assert.ok(!script.includes('innerHTML'));assert.ok(!script.includes('localStorage'));assert.ok(!script.includes('fetch('));assert.match(html,/aria-live="polite"/);},
};
assert.ok(cases[testName],'Unknown case '+testName);cases[testName]();console.log(JSON.stringify({case:testName,passed:true,evidence:'executed independent DOM adapter, not browser'}));
