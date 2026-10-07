import json
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime,timedelta
from pathlib import Path
from urllib.parse import urlsplit,parse_qs
from unittest.mock import patch
from backend.store import connect
from backend.readiness import readiness
from backend.demo import DEMO_AT
from collectors.naver import collect
from workers.pipeline import step

class ConnectionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'live.sqlite3'
    def tearDown(self):self.temp.cleanup()
    def test_missing_credentials_no_network(self):
        with patch.dict(os.environ,{'NAVER_CLIENT_ID':'','NAVER_CLIENT_SECRET':''}):
            result=collect(self.path,fetch=lambda _:self.fail('네트워크 호출하면 안 됨'))
        self.assertEqual(result['status'],'not_configured')
        with connect(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM documents').fetchone()[0],0)
    def test_pagination_idempotency_and_scope(self):
        def fake(req):
            start=int(parse_qs(urlsplit(req.full_url).query)['start'][0]);count=100 if start==1 else 1
            return {'items':[{'title':'<b>검증</b> 제목','description':'검색 요약','originallink':f'https://example.com/{start+i}','link':'https://example.com','pubDate':'Wed, 07 Oct 2026 21:30:00 +0900'} for i in range(count)]}
        with patch.dict(os.environ,{'NAVER_CLIENT_ID':'test-id','NAVER_CLIENT_SECRET':'test-secret'}):
            one=collect(self.path,queries=['검증'],fetch=fake);two=collect(self.path,queries=['검증'],fetch=fake)
        self.assertEqual(one['added'],101);self.assertEqual(two['added'],0);self.assertEqual(one['truncated'],0)
        with connect(self.path) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM documents WHERE content_scope='snippet'").fetchone()[0],101)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM analyses WHERE status='pending'").fetchone()[0],101)
    def test_readiness_does_not_return_secrets(self):
        with patch.dict(os.environ,{'NAVER_CLIENT_ID':'PRIVATE-ID','NAVER_CLIENT_SECRET':'PRIVATE-SECRET'}),connect(self.path) as db:
            text=json.dumps(readiness(db))
        self.assertNotIn('PRIVATE-ID',text);self.assertNotIn('PRIVATE-SECRET',text)
    def test_pipeline_checkpoint_and_catchup(self):
        calls=[]
        def fake(path,now):calls.append(now);return {'status':'not_configured'}
        now=datetime.fromisoformat(DEMO_AT)
        step(self.path,now=now,collector=fake);step(self.path,now=now+timedelta(seconds=60),collector=fake)
        self.assertEqual(len(calls),1)
        step(self.path,now=now+timedelta(seconds=300),collector=fake);self.assertEqual(len(calls),2)
        with connect(self.path) as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM reports').fetchone()[0],4)
        self.assertTrue((self.path.parent/'analysis_jobs.json').exists())
    def test_pipeline_rejects_demo_db(self):
        from backend.demo import seed
        with connect(self.path) as db:seed(db)
        with self.assertRaises(ValueError):step(self.path,collector=lambda *a,**k:self.fail('합성 데이터 수집 호출 금지'))

    def test_connection_closes_after_transaction(self):
        with connect(self.path) as db:db.execute('SELECT 1')
        with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')

if __name__=='__main__':unittest.main()
