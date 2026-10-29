"""Focused v0.9 construction checks; DOM adapter, not actual browser evidence."""
import ast
import json
import os
from pathlib import Path
import subprocess
import unittest

RUN = Path(__file__).resolve().parents[1]
ASSETS = Path(os.environ.get('TEACH_ME_SKILL', RUN / 'teach-me')) / 'assets'
# Preserve the prior adapter's implementation/API; add focus observation only.
source = (Path(__file__).resolve().parent/'test_v8_editor_assets.py').read_text()
tree = ast.parse(source)
RUNNER = next(n.value.value for n in ast.walk(tree) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'runner' for t in n.targets))
RUNNER = RUNNER[:RUNNER.index('let ui=open();')]
RUNNER = RUNNER.replace('class Element {', 'let active;\nclass Element {').replace('  focus() {}', '  focus() { active=this; }')
RUNNER = RUNNER.replace("ids.map(id=>[id,new Element()])", "ids.map(id=>{const e=new Element();e.id=id;return [id,e];})")
RUNNER = RUNNER.replace('return {el,fire,select,addNode,addChain,exportDraft,urls,blobs,body};', 'return {el,fire,select,addNode,addChain,exportDraft,urls,blobs,body,focused:()=>active};')
RUNNER += "\nconst importText=(ui,text)=>{ui.el('import-draft-text').value=text;ui.fire('import-draft');};\n"

CASES = {
 'undo_redo_metadata_and': r"""
let ui=open(); ui.select('node','a');ui.el('node-statement').value='Changed';ui.fire('node-form','submit');const changed=ui.exportDraft();
ui.fire('undo-draft');assert.equal(ui.exportDraft().patch.upsert_nodes.length,0);assert.equal(ui.el('redo-draft').disabled,false);
ui.fire('redo-draft');assert.deepEqual(ui.exportDraft(),changed);assert.deepEqual(changed.patch.upsert_nodes[0].provenance,[{chatId:'source',messageId:'m'}]);
ui.select('chain','ab');ui.el('chain-conclusion').value='b';ui.fire('chain-form','submit');const joint=ui.exportDraft();ui.fire('undo-draft');ui.fire('redo-draft');assert.deepEqual(ui.exportDraft(),joint);assert.deepEqual(joint.patch.upsert_chains[0].premises,['a','b']);
""",
 'branch_and_noop': r"""
let ui=open();ui.addNode('x');ui.fire('undo-draft');ui.addNode('y');assert.equal(ui.el('redo-draft').disabled,true);assert.match(ui.el('history-summary').textContent,/Undo: 1/);
ui.select('node','y');ui.fire('node-form','submit');assert.match(ui.el('history-summary').textContent,/Undo: 1/);
""",
 'import_reset_undo_redo': r"""
let ui=open();ui.addNode('x');ui.addChain('xx',['a','b'],'x');const draft=ui.exportDraft(),text=ui.el('exported-draft').value;
ui.fire('reset-all');assert.equal(ui.exportDraft().patch.upsert_nodes.length,0);importText(ui,text);assert.deepEqual(ui.exportDraft(),draft);
ui.fire('undo-draft');assert.equal(ui.exportDraft().patch.upsert_nodes.length,0);ui.fire('redo-draft');assert.deepEqual(ui.exportDraft(),draft);
const before=ui.el('history-summary').textContent;importText(ui,text);assert.equal(ui.el('history-summary').textContent,before);
""",
 'refusals_preserve_export_history_graph': r"""
let ui=open();ui.addNode('x');const saved=ui.exportDraft(),text=ui.el('exported-draft').value,history=ui.el('history-summary').textContent;
for(const bad of ['{',text.replace('"version": 1','"version": 1,"version": 1'),text.replace('a'.repeat(64),'b'.repeat(64)),text.replace('"name": "x"','"name": 3'),text+' trailing',text.replace('"version": 1','"version": true')]){
importText(ui,bad);assert.equal(ui.el('exported-draft').value,text);assert.equal(ui.el('history-summary').textContent,history);assert.equal(ui.focused().id,'import-draft-text');assert.deepEqual(ui.exportDraft(),saved);
}
""",
 'metadata_forgery_and_unknown_delete': r"""
let ui=open();ui.select('node','a');ui.el('node-name').value='Changed';ui.fire('node-form','submit');const saved=ui.exportDraft(),text=ui.el('exported-draft').value;
for(const mutate of [d=>d.patch.upsert_nodes[0].aliases.push('fake'),d=>d.patch.upsert_nodes[0].createdAt='now',d=>d.patch.upsert_nodes[0].provenance=[],d=>d.patch.delete_nodes=['unknown'],d=>d.patch.upsert_nodes[0].unknown=1]){
let d=JSON.parse(text);mutate(d);importText(ui,JSON.stringify(d));assert.match(ui.el('action-status').textContent,/Cannot stage/);assert.deepEqual(ui.exportDraft(),saved);
}
""",
 'blank_newmetadata_and_fullschema': r"""
let ui=open();ui.addNode('x');let d=ui.exportDraft();ui.fire('reset-all');
for(const mutate of [d=>d.patch.upsert_nodes[0].createdAt=null,d=>d.patch.upsert_nodes[0].aliases=['fake'],d=>d.patch.upsert_nodes[0].provenance=[{chatId:'a',messageId:'b'}],d=>delete d.patch.upsert_nodes[0].statement,d=>d.extra=1,d=>d.patch.upsert_nodes.push(d.patch.upsert_nodes[0])]){
const bad=JSON.parse(JSON.stringify(d));mutate(bad);importText(ui,JSON.stringify(bad));assert.match(ui.el('action-status').textContent,/Cannot stage/);assert.equal(ui.exportDraft().patch.upsert_nodes.length,0);
}
importText(ui,JSON.stringify(d));assert.equal(ui.exportDraft().patch.upsert_nodes[0].createdAt,'');
""",
 'size_depth_duplicate_decoded_key': r"""
let ui=open();ui.addNode('x');const before=ui.exportDraft();
for(const text of [' '.repeat(2097153),'['.repeat(66)+'0'+']'.repeat(66),'{{"version":1}}','{"version":1,"\\u0076ersion":1}','{"version":1e999}']){
importText(ui,text);assert.match(ui.el('action-status').textContent,/Cannot stage/);assert.deepEqual(ui.exportDraft(),before);
}
""",
 'version_lexical_integer': r"""
let ui=open();ui.addNode('x');const before=ui.exportDraft(),raw=ui.el('exported-draft').value;for(const token of ['1.0','1e0','1E+0']){importText(ui,raw.replace(/\"version\": 1/g,'\"version\": '+token));assert.match(ui.el('action-status').textContent,/integer JSON token/);assert.deepEqual(ui.exportDraft(),before);}
""",
 'history_twenty_steps': r"""
let ui=open();for(let i=0;i<26;i++)ui.addNode('n'+i);assert.match(ui.el('history-summary').textContent,/Undo: 20/);assert.match(ui.el('history-summary').textContent,/discarded/);assert.match(ui.el('action-status').textContent,/discarded/);
for(let i=0;i<20;i++)ui.fire('undo-draft');assert.equal(ui.el('undo-draft').disabled,true);assert.equal(ui.exportDraft().patch.upsert_nodes.length,6);assert.match(ui.el('history-summary').textContent,/Redo: 20/);
""",
 'history_byte_bound': r"""
let g=base();g.nodes[0].statement='x'.repeat(1048576);let ui=open(g);for(let i=0;i<12;i++){ui.select('node','a');ui.el('node-name').value='v'+i;ui.fire('node-form','submit');}
const summary=ui.el('history-summary').textContent;const bytes=Number(/History: (\d+)/.exec(summary)[1]);const steps=Number(/Undo: (\d+)/.exec(summary)[1]);assert.ok(bytes<=8388608);assert.ok(steps<8);assert.match(summary,/discarded/);
""",
 'focus_error_delete_selection': r"""
let ui=open();ui.select('node','a');assert.equal(ui.focused().id,'node-name');ui.select('chain','ab');assert.equal(ui.focused().id,'chain-premises');
ui.fire('node-new');ui.el('node-id').value=' bad ';ui.fire('node-form','submit');assert.equal(ui.focused().id,'node-id');
ui.addNode('x');ui.fire('node-delete');assert.equal(ui.focused().id,'node-id');ui.select('chain','ab');ui.el('chain-premises').value='a\na';ui.fire('chain-form','submit');assert.equal(ui.focused().id,'chain-premises');
""",
 'dangling_and_duplicate_logical_import': r"""
let ui=open();ui.addNode('x');let d=ui.exportDraft();ui.fire('reset-all');
for(const mutate of [d=>d.patch.upsert_chains=[chain('new',['a'],'missing')],d=>d.patch.upsert_chains=[chain('same',['b','a'],'c')],d=>{d.patch.delete_nodes=['a'];d.patch.upsert_nodes.push(node('a'));},d=>d.patch.upsert_chains=[chain('same',['a','a'],'c')]]){
let bad=JSON.parse(JSON.stringify(d));mutate(bad);importText(ui,JSON.stringify(bad));assert.match(ui.el('action-status').textContent,/Cannot stage/);assert.equal(ui.exportDraft().patch.upsert_nodes.length,0);
}
""",
 'import_uses_original_base_and_inert_text': r"""
let ui=open();ui.addNode('x','<img src=x onerror=alert(1)>');const d=ui.exportDraft();ui.addNode('unrelated');importText(ui,JSON.stringify(d));const actual=ui.exportDraft();assert.deepEqual(actual,d);assert.equal(actual.patch.upsert_nodes.some(n=>n.id==='unrelated'),false);assert.match(text(ui.el('graph-cards')),/<img src=x/);assert.equal(ui.el('graph-cards').children.flatMap(c=>c.children).some(c=>c.tagName==='img'),false);
"""
}

class HistoryTests(unittest.TestCase):
    pass

def case_method(code):
    def run(self):
        result=subprocess.run(['node','-e',RUNNER+'\n{\n'+code+'\n}\n',str(ASSETS/'graph-editor.js'),str(ASSETS/'graph-editor.html')],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+'\n'+result.stderr)
    return run
for name,code in CASES.items():setattr(HistoryTests,'test_'+name,case_method(code))
if __name__=='__main__':unittest.main(verbosity=2)
