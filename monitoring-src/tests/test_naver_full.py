import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch
from backend.store import connect
from collectors.naver_full import collect

NOW=datetime.fromisoformat('2026-10-07T13:00:00+09:00')
CFG={'since':'2026-10-07T00:00:00+09:00','queries':['test'],'request_budget':200}
def item(i,date='Wed, 07 Oct 2026 02:00:00 GMT'):
    return {'originallink':f'https://example.com/article/{i}','link':f'https://example.com/article/{i}','title':f'<b>title</b> {i}','description':'not full article','pubDate':date}
class NaverFullTests(unittest.TestCase):
    def test_hub_credentials_switch_endpoint_after_legacy_401(self):
        from urllib.error import HTTPError
        calls=[]
        def fetch(req):
            calls.append(req)
            if 'openapi.naver.com' in req.full_url:raise HTTPError(req.full_url,401,'Unauthorized',None,None)
            self.assertEqual(req.get_header('X-ncp-apigw-api-key-id'),'test')
            self.assertEqual(req.get_header('X-ncp-apigw-api-key'),'test')
            return {'total':1,'items':[item(1)]}
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'NAVER_CLIENT_ID':' test ','NAVER_CLIENT_SECRET':'test'}):
            r=collect(Path(t)/'a.db',fetch,NOW,CFG)
            self.assertEqual(r['status'],'ok');self.assertEqual(r['added'],1)
            self.assertEqual(r['endpoint'],'api_hub');self.assertEqual(r['requests'],2)
            self.assertIn('/search/v1/news?',calls[1].full_url)
    def test_missing_keys_never_calls(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{},clear=True):
            r=collect(Path(t)/'a.db',fetch=lambda req:(_ for _ in ()).throw(AssertionError('network')),now=NOW,config=CFG)
            self.assertEqual(r['status'],'not_configured')
            self.assertEqual(r['missing_credentials'],['NAVER_CLIENT_ID','NAVER_CLIENT_SECRET'])
    def test_auth_error_reports_status_without_credentials(self):
        from urllib.error import HTTPError
        def fail(req):raise HTTPError(req.full_url,401,'Unauthorized',None,None)
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'NAVER_CLIENT_ID':'private-id','NAVER_CLIENT_SECRET':'private-secret'}):
            r=collect(Path(t)/'a.db',fail,NOW,CFG)
            self.assertEqual(r['queries'][0]['error_code'],'HTTP_401')
            self.assertEqual(r['status'],'failed')
            self.assertNotIn('private-secret',str(r))
    def test_overlapping_pages_end_and_duplicates(self):
        starts=[]
        def fetch(req):
            from urllib.parse import urlsplit,parse_qs
            start=int(parse_qs(urlsplit(req.full_url).query)['start'][0]);starts.append(start)
            return {'total':230,'items':[item(i) for i in range(start,min(start+100,231))]}
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'NAVER_CLIENT_ID':'test','NAVER_CLIENT_SECRET':'test'}):
            path=Path(t)/'a.db';r=collect(path,fetch,NOW,CFG)
            self.assertEqual(starts,[1,76,151]);self.assertEqual(r['status'],'ok');self.assertEqual(r['added'],230)
            self.assertEqual(r['queries'][0]['unique_urls'],230)
            self.assertEqual(r['queries'][0]['status'],'results_end_reached')
            with connect(path) as db:self.assertEqual(db.execute("SELECT COUNT(*) FROM analyses WHERE status='approved'").fetchone()[0],0)
    def test_limit_is_not_complete(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'NAVER_CLIENT_ID':'test','NAVER_CLIENT_SECRET':'test'}):
            r=collect(Path(t)/'a.db',lambda req:{'total':5000,'items':[item(i) for i in range(100)]},NOW,CFG)
            self.assertEqual(r['queries'][0]['status'],'api_limit');self.assertEqual(r['status'],'failed')
            self.assertEqual(r['requests'],13)
    def test_old_scope_boundary_not_global_completion(self):
        with tempfile.TemporaryDirectory() as t,patch.dict(os.environ,{'NAVER_CLIENT_ID':'test','NAVER_CLIENT_SECRET':'test'}):
            r=collect(Path(t)/'a.db',lambda req:{'total':5000,'items':[item(1),item(2,'Tue, 06 Oct 2026 02:00:00 GMT')]},NOW,CFG)
            self.assertEqual(r['queries'][0]['status'],'scope_boundary_reached');self.assertEqual(r['added'],1)
