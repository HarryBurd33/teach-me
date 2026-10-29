"""Post-inspection coverage additions; original40 frozen methods unchanged."""
import copy
import hashlib
import itertools
import json
from pathlib import Path
import unittest
import test_v10_contract as fixture

class AdditionalMergeCoverage(unittest.TestCase):
    def setUp(self):
        self.c=fixture.MergeContract('test_01_independent_node_chain_metadata_and');self.c.setUp();self.addCleanup(self.c.doCleanups)
    def test_independent_claim_edits_combine(self):
        c=self.c;c.l['patch']['upsert_nodes']=[c.edit('a',name='Left name')];c.r['patch']['upsert_nodes']=[c.edit('b',statement='Right statement')];c.save_drafts();c.planning();self.assertEqual(c.plan_data()['conflicts'],[]);c.choices([]);c.applying();g=c.final_graph();self.assertEqual(g['nodes'][0]['name'],'Left name');self.assertEqual(g['nodes'][1]['statement'],'Right statement');self.assertEqual(g['nodes'][0]['provenance'],c.g['nodes'][0]['provenance'])
    def test_different_fields_same_record_still_conflict(self):
        c=self.c;c.l['patch']['upsert_nodes']=[c.edit('a',name='Left name')];c.r['patch']['upsert_nodes']=[c.edit('a',statement='Right statement')];c.save_drafts();c.planning();self.assertEqual([(x['kind'],x['id'],x['reason']) for x in c.plan_data()['conflicts']],[('node','a','both-edited')]);c.choices([{'kind':'node','id':'a','choose':'left'}]);c.applying();g=c.final_graph();self.assertEqual(g['nodes'][0]['name'],'Left name');self.assertEqual(g['nodes'][0]['statement'],c.g['nodes'][0]['statement'])
    def test_draft_byte_capacity_promotes_and_rejects_combination(self):
        c=self.c;c.l['patch']['upsert_nodes']=[c.edit('a',statement='x'*1100000)];c.r['patch']['upsert_nodes']=[c.edit('b',statement='y'*1100000)];c.save_drafts();c.planning();cs=c.plan_data()['conflicts'];self.assertEqual({(x['kind'],x['id'],x['reason']) for x in cs},{('node','a','capacity'),('node','b','capacity')});c.choices([{'kind':'node','id':x['id'],'choose':'left' if x['id']=='a' else 'right'} for x in cs]);c.applying(ok=False);self.assertFalse(c.out.exists());c.choices([{'kind':'node','id':x['id'],'choose':'base'} for x in cs]);c.applying();self.assertEqual(c.final_graph()['nodes'],c.g['nodes'])
    def test_chain_count_capacity_promotes(self):
        c=self.c;ids=list('abcdef');possibilities=[(list(p),conclusion) for size in range(1,7) for p in itertools.combinations(ids,size) for conclusion in ids];c.g['nodes']=[fixture.node(x) for x in ids];c.g['chains']=[fixture.chain('c'+str(i),*possibilities[i]) for i in range(255)];c.write(c.base,c.g);c.l=c.draft();c.r=c.draft();c.l['patch']['upsert_chains']=[fixture.chain('left',*possibilities[255])];c.r['patch']['upsert_chains']=[fixture.chain('right',*possibilities[256])];c.save_drafts();c.planning();cs=c.plan_data()['conflicts'];self.assertEqual({(x['kind'],x['id'],x['reason']) for x in cs},{('chain','left','capacity'),('chain','right','capacity')});c.choices([{'kind':'chain','id':x['id'],'choose':'base'} for x in cs]);c.applying();self.assertEqual(len(c.final_graph()['chains']),255)
    def test_plan_byte_limit_refuses_even_rehashed(self):
        c=self.c;c.planning();c.plan.write_bytes(b' '*(8*1024*1024+1));c.write(c.decisions,{'version':1,'plan_sha256':fixture.sha(c.plan.read_bytes()),'choices':[]});c.applying(ok=False);self.assertFalse(c.out.exists())

if __name__=='__main__':unittest.main(verbosity=2)
