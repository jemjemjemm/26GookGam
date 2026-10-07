"""Public title/link metadata only. RSS success never approves AI analysis."""
import argparse
import html
import json
import re
from datetime import datetime,timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode,urlsplit
from urllib.request import Request,urlopen
import xml.etree.ElementTree as ET
from backend.store import connect
from backend.demo import KST
from collectors.import_json import ingest

QUERIES=['정유 담합 when:7d','SK에너지 현대오일뱅크 가격정보 when:7d','정유 리니언시 when:7d']
def fetch(url):
    with urlopen(Request(url,headers={'User-Agent':'IssueMonitoring/1.0 (public news metadata)'}),timeout=25) as r:
        data=r.read(2_000_001)
        if len(data)>2_000_000:raise ValueError('RSS too large')
        return data

def parse(data,now):
    if b'<!DOCTYPE' in data.upper() or b'<!ENTITY' in data.upper():raise ValueError('XML entities not allowed')
    rows=[]
    for item in ET.fromstring(data).findall('./channel/item'):
        title=html.unescape(re.sub('<[^>]*>','',item.findtext('title',''))).strip()
        link=item.findtext('link','').strip();published=item.findtext('pubDate','')
        if not title or urlsplit(link).scheme!='https':continue
        try:dt=parsedate_to_datetime(published)
        except (ValueError,TypeError):continue
        if dt.tzinfo is None or not now-timedelta(days=7)<=dt<=now:continue
        rows.append({'source_id':'google-news-rss','source_name':'Google 뉴스 RSS','external_id':item.findtext('guid') or link,
                     'channel':'media','url':link,'title':title,'body':'','published_at':dt.isoformat(),
                     'collected_at':now.isoformat(),'content_scope':'title','time_basis':'rss_published',
                     'rights_note':'공개 RSS 제목·매체·링크만 저장. 본문·댓글·감정·법 위반 사실은 확인하지 않음.'})
    return rows

def collect(path,queries=None,fetcher=fetch,now=None):
    now=now or datetime.now(KST);stamp=now.isoformat();added=failed=0
    with connect(path) as db:
        db.execute('INSERT OR IGNORE INTO sources(id,channel,name,access_mode,expected_minutes,status,rights_note) VALUES(?,?,?,?,?,?,?)',
                   ('google-news-rss','media','Google 뉴스 RSS','public_rss',15,'not_connected','제목·매체·원문 링크만 관측'))
    for query in queries or QUERIES:
        with connect(path) as db:run=db.execute('INSERT INTO collection_runs(source_id,started_at,status,cursor) VALUES(?,?,?,?)',('google-news-rss',stamp,'running',query)).lastrowid
        try:
            url='https://news.google.com/rss/search?'+urlencode({'q':query,'hl':'ko','gl':'KR','ceid':'KR:ko'})
            rows=parse(fetcher(url),now)
            with connect(path) as db:
                n=ingest(db,rows);added+=n
                db.execute('UPDATE collection_runs SET finished_at=?,status=?,items=? WHERE id=?',(stamp,'ok',len(rows),run))
                db.execute("UPDATE sources SET last_success=?,expected_minutes=15,status='connected' WHERE id='google-news-rss'",(stamp,))
        except Exception as exc:
            failed+=1
            with connect(path) as db:db.execute('UPDATE collection_runs SET finished_at=?,status=?,error_code=? WHERE id=?',(stamp,'failed',type(exc).__name__,run))
    status='failed' if failed==len(queries or QUERIES) else 'partial' if failed else 'ok'
    with connect(path) as db:db.execute('UPDATE sources SET status=? WHERE id=?',('failed' if status=='failed' else 'connected','google-news-rss'))
    return {'status':status,'added':added,'failed':failed,'queries':len(queries or QUERIES)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',default='data/github-live.sqlite3');a=p.parse_args();print(json.dumps(collect(a.db),ensure_ascii=False))
