import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from backend.store import connect
from collectors.rss import parse,collect
from workers.github_build import build
from backend.demo import seed

NOW=datetime.fromisoformat('2026-10-07T12:10:00+09:00')
RSS=b'''<rss><channel><item><title>test headline - publisher</title><link>https://example.com/a</link><guid>a</guid><pubDate>Wed, 07 Oct 2026 02:00:00 GMT</pubDate></item><item><title>future</title><link>https://example.com/b</link><pubDate>Thu, 08 Oct 2026 02:00:00 GMT</pubDate></item><item><title>invalid URL</title><link>javascript:alert(1)</link><pubDate>Wed, 07 Oct 2026 02:00:00 GMT</pubDate></item></channel></rss>'''
class GitHubTests(unittest.TestCase):
    def test_rss_bounds_and_no_body(self):
        rows=parse(RSS,NOW)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['body'],'');self.assertEqual(rows[0]['content_scope'],'title')
        with self.assertRaises(ValueError):parse(b'<!DOCTYPE rss [<!ENTITY x "x">]><rss/>',NOW)
    def test_collection_duplicate_not_approval_and_live_export(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'live.sqlite3';out=Path(td)/'site';state=Path(td)/'state.json'
            self.assertEqual(collect(db,['q'],lambda url:RSS,NOW)['added'],1)
            self.assertEqual(collect(db,['q'],lambda url:RSS,NOW)['added'],0)
            with connect(db) as c:
                self.assertEqual(c.execute('SELECT status FROM analyses').fetchone()[0],'pending')
            build(db,out,state,False,NOW)
            data=json.loads((out/'data.json').read_text(encoding='utf-8'))
            self.assertEqual(data['snapshots']['24:all']['metrics']['published'],1)
            self.assertIsNone(data['snapshots']['24:all']['metrics']['risk'])
            self.assertNotIn('127.0.0.1',(out/'index.html').read_text(encoding='utf-8'))
    def test_demo_cannot_publish(self):
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/'demo.sqlite3'
            with connect(path) as db:seed(db)
            with self.assertRaises(ValueError):build(path,Path(td)/'site',Path(td)/'state.json',False,NOW)
    def test_ledger_cannot_inject_private_body(self):
        with tempfile.TemporaryDirectory() as td:
            rows=parse(RSS,NOW);rows[0]['body']='private';state=Path(td)/'state.json';state.write_text(json.dumps(rows),encoding='utf-8')
            with self.assertRaises(ValueError):build(Path(td)/'live.sqlite3',Path(td)/'site',state,False,NOW)
