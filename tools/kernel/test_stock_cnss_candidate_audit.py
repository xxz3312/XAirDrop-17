"""Reject substituted CI metadata, archives and incomplete ELF records."""
import copy
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile
from stock_cnss_candidate_audit import ROOT, verify_ci, verify_archive, verify_record, members

class CandidateAuditTests(unittest.TestCase):
    def setUp(self):
        self.e=json.loads((ROOT/'docs/research/popsicle-candidate-0188-ci.json').read_text())
        self.head=self.e['run']['head_sha']

    def test_ci_required_jobs_and_source(self):
        verify_ci(self.e,self.head)
        changes=[lambda e:e['run'].update(head_sha='0'*40),
                 lambda e:e['run'].update(path='.github/workflows/other.yml'),
                 lambda e:e['run'].update(conclusion='failure'),
                 lambda e:e['jobs'].pop(0),
                 lambda e:e['jobs'].append(copy.deepcopy(e['jobs'][0])),
                 lambda e:e['jobs'][0].update(conclusion='skipped')]
        for change in changes:
            e=copy.deepcopy(self.e);change(e)
            with self.subTest(change=change),self.assertRaises(ValueError):verify_ci(e,self.head)

    def test_archive_digest_and_origin(self):
        # Synthetic bytes exercise the integrity gate, not an ELF/ABI certification.
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'sample.zip';p.write_bytes(b'archive fixture')
            e=copy.deepcopy(self.e)
            a=next(a for a in e['artifacts'] if 'diagnostics' in a['name'])
            a.update(size_in_bytes=p.stat().st_size,digest='sha256:'+hashlib.sha256(p.read_bytes()).hexdigest())
            verify_archive(p,e,'diagnostics')
            for field,value in [('expired',True),('size_in_bytes',0),('digest','sha256:'+'0'*64)]:
                bad=copy.deepcopy(e);next(x for x in bad['artifacts'] if x['id']==a['id'])[field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):verify_archive(p,bad,'diagnostics')
            bad=copy.deepcopy(e)
            next(x for x in bad['artifacts'] if x['id']==a['id'])['workflow_run']['head_sha']='0'*40
            with self.assertRaises(ValueError):verify_archive(p,bad,'diagnostics')
            p.write_bytes(b'substituted bytes')
            with self.assertRaises(ValueError):verify_archive(p,e,'diagnostics')

    def test_zip_ambiguity_and_traversal(self):
        for names in [['../escape'],['/absolute'],['a\\b'],['same','same']]:
            b=io.BytesIO()
            with warnings.catch_warnings():
                warnings.simplefilter('ignore',UserWarning)
                with zipfile.ZipFile(b,'w') as z:
                    for n in names:z.writestr(n,b'x')
            with zipfile.ZipFile(b) as z,self.assertRaises(ValueError):members(z)

    def test_elf_record_rejects_unversioned_or_substituted_symbols(self):
        actual={'sha256':'fixture','modinfo':{'name':['wonder'],'vermagic':['fixture']},
                'versions':{'symbol':'0x123'},'undefined':['symbol']}
        claim={'status':'RECORDED_LOADER_CHECKS_MATCH_ONLY','sha256':'fixture','vermagic':['fixture'],
               'version_records':1,'version_record_mismatches':[],'undefined_without_version':[],
               'vermagic_stock_loader_match':True}
        verify_record(actual,claim,'wonder')
        for mutate in [lambda a:a.update(sha256='substitute'),
                       lambda a:a['undefined'].append('unversioned'),
                       lambda a:a['modinfo'].update(name=['wrong']),
                       lambda a:a['modinfo'].update(vermagic=['wrong'])]:
            bad=copy.deepcopy(actual);mutate(bad)
            with self.assertRaises(ValueError):verify_record(bad,claim,'wonder')
        bad=copy.deepcopy(claim);bad['vermagic_stock_loader_match']=False
        with self.assertRaises(ValueError):verify_record(actual,bad,'wonder')

    def test_recorded_result_grants_no_deployment_authority(self):
        r=json.loads((ROOT/'docs/research/popsicle-candidate-0188-validation.json').read_text())
        self.assertEqual(r['source_commit'],self.head)
        self.assertEqual(r['status'],'CANDIDATE_RECORDS_VERIFIED_NOT_FOR_INSTALL')
        self.assertEqual(len(r['actual_module_records']),5)
        for key in ['runtime_certified','phone_executed','load_authorized','deployment_bundle_created','old_0135_bundle_retargeted']:
            self.assertIs(r[key],False,key)

if __name__=='__main__':unittest.main()
