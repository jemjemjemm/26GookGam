import tempfile
import unittest
from pathlib import Path
from datetime import datetime
from collectors.article_body import extract,read,collect,judge_body,PENDING

class ArticleBodyTests(unittest.TestCase):
    def test_summary_is_not_full_body(self):
        with self.assertRaises(ValueError):extract('<html><meta name="description" content="SK 무혐의"><p>뉴스 요약</p></html>')
    def test_read_body_not_title(self):
        text=('SK에너지와 현대오일뱅크에 대한 심의 절차가 시작됐다. 실제 과징금은 위원회에서 결정된다.\n'*20)+'SK에너지는 정상적인 거래라고 설명했다.'
        raw=('<html><article>'+text+'</article></html>').encode()
        result=read({'url':'https://example.com','title':'SK 폭리 면죄부'},'2026-10-07T14:00:00+09:00',lambda url:(raw,url))
        self.assertTrue(result['confirmed']);self.assertEqual(result['label'],'긍정')
        self.assertNotIn(text,str(result));self.assertIn('body_sha256',result)
    def test_paywall_and_failed_fetch_withhold(self):
        def fail(url):raise ValueError('article_body_not_confirmed')
        self.assertEqual(read({'url':'https://example.com'},'now',fail)['label'],PENDING)
        with self.assertRaises(ValueError):extract('<article class="paywall">'+('SK 기사 본문 '*200)+'</article>')
    def test_neutral_amount_and_mixed_critical_body(self):
        self.assertEqual(judge_body('SK에너지 과징금이 4.6조 또는 7.9조로 추정되며 심의에서 결정된다.')[0],'중립')
        self.assertEqual(judge_body('정유사에 대한 면죄부라는 비판이 제기됐다.\nSK에너지는 정상적인 거래라고 밝혔다.')[0],'부정')
    def test_cache_never_publishes_text(self):
        with tempfile.TemporaryDirectory() as t:
            rows=[{'id':'a','url':'https://example.com'}]
            observations,summary=collect(rows,Path(t)/'state.json',datetime.fromisoformat('2026-10-07T14:00:00+09:00'),lambda url:('<article>짧은 요약</article>',url))
            self.assertEqual(summary['unconfirmed'],1);self.assertEqual(observations['a']['label'],PENDING)
