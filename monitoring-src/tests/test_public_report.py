import unittest
from workers.public_report import connected,render_current

class PublicReportTests(unittest.TestCase):
    def test_missing_key_is_not_connected(self):
        self.assertFalse(connected({'status':'not_configured','queries':[]}))
    def test_auth_failure_is_not_connected(self):
        self.assertFalse(connected({'queries':[{'pages':0,'status':'failed'}]}))
    def test_partial_collection_keeps_limits_and_title_scope(self):
        n={'status':'partial','added':1,'requests':2,'queries':[{'query':'정유 담합','pages':1,'in_scope':1,'status':'api_limit'}]}
        self.assertTrue(connected(n))
        rows=[{'source_id':'naver-search','title':'SK에너지·현대오일뱅크 담합 의혹','url':'https://example.com/a','published_at':'2026-10-07T13:00:00+09:00'}]
        body=render_current(rows,{'naver':n},'2026-10-07T13:01:00+09:00')
        self.assertIn('SK: 1/1건 (100.0%)',body)
        self.assertIn('api_limit',body)
        self.assertIn('본문 AI 분석이 아닙니다',body)
        self.assertIn('검토 대기 초안',body)
