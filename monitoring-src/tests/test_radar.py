import json
import hashlib
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from backend.store import connect
from backend.demo import seed,DEMO_AT,KST
from backend.metrics import snapshot,shift,exposure
from collectors.import_json import ingest
from workers.analysis import validate,accept
from workers.report import tick,generate
from workers.facts import approve

class RadarTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.db=connect(Path(self.temp.name)/'test.sqlite3')
    def tearDown(self):
        self.db.close();self.temp.cleanup()
    def test_empty_not_zero(self):
        s=snapshot(self.db,DEMO_AT)
        self.assertIsNone(s['metrics']['risk'])
        self.assertIsNone(s['metrics']['negative'])
        self.assertIsNone(s['companies']['SK']['score'])
        self.assertEqual(s['facts'],[])
    def test_scores_bounded(self):
        seed(self.db);s=snapshot(self.db,DEMO_AT)
        self.assertEqual(s['metrics']['stories'],24)
        self.assertEqual(s['metrics']['published'],48)
        self.assertTrue(0<=s['metrics']['risk']<=100)
        self.assertEqual(exposure({}),0)
        self.assertEqual(exposure({k:1 for k in ['body','central','headline','first','negative_link','leniency_link','consumer_link','moral_link']}),100)
        self.assertAlmostEqual(sum(s['frames'].values()),1,places=3)
    def test_logic_tracks_filtered_sample_and_report(self):
        seed(self.db);s=snapshot(self.db,DEMO_AT,channel='broadcast')
        self.assertIn('기사 0건',s['logic']['exposure_short'])
        self.assertIn('0/0/0건',s['logic']['risk_short'])
        self.assertTrue(all(a['logic'] for a in s['alerts']))
        from workers.report import render
        self.assertIn(s['logic']['risk'],render(s))
        self.assertIn(s['logic']['shift'],render(s))
    def test_shift_gate_and_direction(self):
        a=[{'primary_frame':'F01'} for _ in range(20)]
        b=[{'primary_frame':'F06'} for _ in range(20)]
        self.assertIsNone(shift(a[:19],b)['score'])
        self.assertEqual(shift(b,a)['score'],100)
        self.assertEqual(shift(b,a)['delta_pp'],100)
    def test_zero_previous_velocity(self):
        seed(self.db)
        self.db.execute("DELETE FROM analyses WHERE document_id LIKE 'm9-%'")
        s=snapshot(self.db,DEMO_AT)
        self.assertIsNone(s['metrics']['velocity'])
        self.assertIsNone(s['metrics']['risk'])
    def test_filter_consistency(self):
        seed(self.db);s=snapshot(self.db,DEMO_AT,channel='broadcast')
        self.assertTrue(all(r['channel']=='broadcast' for r in s['documents']))
        self.assertEqual(s['metrics']['stories'],0)
        self.assertIsNone(s['metrics']['risk'])
    def test_partial_excluded(self):
        seed(self.db)
        self.db.execute("UPDATE documents SET content_scope='snippet' WHERE source_id='media'")
        s=snapshot(self.db,DEMO_AT)
        self.assertEqual(s['metrics']['published'],48)
        self.assertEqual(s['metrics']['stories'],0)
    def test_late_collection_and_analysis_excluded(self):
        seed(self.db)
        self.db.execute("UPDATE documents SET collected_at='2026-10-08T00:00:00+09:00' WHERE source_id='media'")
        self.assertEqual(snapshot(self.db,DEMO_AT)['metrics']['published'],0)
        self.db.execute("UPDATE documents SET collected_at=published_at")
        self.db.execute("UPDATE analyses SET created_at='2026-10-08T00:00:00+09:00' WHERE document_id LIKE 'm%'")
        self.assertEqual(snapshot(self.db,DEMO_AT)['metrics']['stories'],0)
    def test_stale_suppresses_risk(self):
        seed(self.db)
        self.db.execute("UPDATE sources SET last_success='2026-10-07T10:00:00+09:00'")
        self.assertIsNone(snapshot(self.db,DEMO_AT)['metrics']['risk'])
    def test_naive_timestamp_rejected(self):
        with self.assertRaises(ValueError):snapshot(self.db,'2026-10-07T21:30:00')
    def test_import_idempotent(self):
        item={'source_id':'manual','channel':'media','title':'검증 샘플','body':'본문','url':'https://example.com/a','published_at':DEMO_AT,'collected_at':DEMO_AT,'content_scope':'full'}
        self.assertEqual(ingest(self.db,[item]),1)
        self.assertEqual(ingest(self.db,[item]),0)
        self.assertEqual(self.db.execute('SELECT status FROM analyses').fetchone()[0],'pending')
    def example_result(self):
        seed(self.db);doc=self.db.execute("SELECT * FROM documents WHERE id='m10-0'").fetchone()
        return doc,{'document_id':doc['id'],'primary_frame':'F03','secondary':[],'frames':{'F03':0.9},'targets':['SK'],'tone':'negative','emotion':'anger','argument':'','evidence':[{'quote':doc['title'],'field':'title'}],'exposure':{'SK':{'body':1,'central':1,'headline':1,'first':1,'negative_link':1,'leniency_link':0,'consumer_link':0,'moral_link':0}},'fact_gap':'unverifiable','confidence':0.9,'model':'test','prompt_version':'1.0.0','fact_version':0}
    def test_fabricated_quote_rejected(self):
        doc,r=self.example_result();r['evidence'][0]['quote']='존재하지 않는 확정 판단'
        with self.assertRaises(ValueError):validate(r,doc,False)
    def test_unverified_fact_gap_rejected(self):
        doc,r=self.example_result();r['fact_gap']='stage'
        with self.assertRaises(ValueError):validate(r,doc,False)
        r['fact_gap']='unverifiable';r['fact_version']=1
        with self.assertRaises(ValueError):validate(r,doc,False)
    def test_injection_cannot_write_fact(self):
        doc,r=self.example_result();r['statement']='담합 확정'
        with self.assertRaises(ValueError):accept(self.db,r,'analyst')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM fact_baselines').fetchone()[0],0)
    def test_approval_audited(self):
        doc,r=self.example_result();accept(self.db,r,'analyst')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0],1)
        self.assertEqual(self.db.execute("SELECT reviewed_by FROM analyses WHERE document_id='m10-0'").fetchone()[0],'analyst')
    def test_report_idempotent_slots(self):
        seed(self.db);tick(self.db,datetime.fromisoformat(DEMO_AT));tick(self.db,datetime.fromisoformat(DEMO_AT))
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM reports').fetchone()[0],4)
        last=self.db.execute('SELECT * FROM reports ORDER BY scheduled_at DESC').fetchone()
        self.assertIn('21:30',last['scheduled_at'])
        self.assertEqual(json.loads(last['snapshot_json'])['window_hours'],3.5)
    def test_preflight_does_not_approve_or_write(self):
        from workers.analysis import check
        doc,r=self.example_result()
        before=self.db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]
        result=check(self.db,r)
        self.assertEqual(result['writes'],0)
        self.assertEqual(result['status'],'validated_not_approved')
        self.assertEqual(self.db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0],before)
        r['evidence'][0]['quote']='없는 인용'
        with self.assertRaises(ValueError):check(self.db,r)
    def test_fact_evidence_required(self):
        with self.assertRaises(Exception):
            self.db.execute("INSERT INTO fact_baselines VALUES('f','문장','심사','uri','hash','p1','','verified',1,NULL,NULL,?,NULL)",(DEMO_AT,))

    def test_fact_registration_hash_and_immutability(self):
        path=Path(self.temp.name)/'source.txt';path.write_text('공식 검수 전사 테스트',encoding='utf-8')
        r={'id':'f1','statement':'담당자가 대조한 출처의 문장','procedural_status':'examiner_opinion','source_uri':'official-source','source_hash':hashlib.sha256(path.read_bytes()).hexdigest(),'locator':'p1','evidence_quote':'공식 검수','version':1,'valid_from':DEMO_AT}
        approve(self.db,r,path,'fact-owner')
        self.assertEqual(self.db.execute('SELECT verification FROM fact_baselines').fetchone()[0],'verified')
        with self.assertRaises(ValueError):approve(self.db,r,path,'fact-owner')
        r['id']='f2';r['source_hash']='wrong'
        with self.assertRaises(ValueError):approve(self.db,r,path,'fact-owner')
    def test_fact_approval_cannot_be_backdated(self):
        self.db.execute("INSERT INTO fact_baselines VALUES('f','검수 문장','examiner_opinion','uri','hash','p1','인용','verified',1,'owner','2026-10-08T00:00:00+09:00','2026-10-07T10:00:00+09:00',NULL)")
        self.assertEqual(snapshot(self.db,DEMO_AT)['facts'],[])

if __name__=='__main__':unittest.main()
