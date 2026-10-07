import argparse
import html
import json
import os
import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from backend.store import connect, ROOT
from backend.demo import KST
from collectors.import_json import ingest

QUERIES=['정유 담합','SK에너지 현대오일뱅크 가격정보','정유 리니언시','정유 소비자 피해']
def clean(s):return html.unescape(re.sub('<[^>]*>','',s))
def fetch_json(request):
    with urlopen(request,timeout=20) as response:return json.load(response)

def collect(db_path,queries=None,pages=2,fetch=fetch_json,now=None):
    if not 1<=pages<=10:raise ValueError('pages는 1~10')
    credentials={k:os.environ.get(k) for k in ['NAVER_CLIENT_ID','NAVER_CLIENT_SECRET']}
    timestamp=(now or datetime.now(KST)).isoformat()
    with connect(db_path) as db:
        db.execute('INSERT OR IGNORE INTO sources(id,channel,name,access_mode,expected_minutes,status,rights_note) VALUES(?,?,?,?,?,?,?)',('naver-search','media','뉴스 검색','api',5,'not_connected','검색 메타데이터만 확보; 원문·댓글은 별도 연결'))
        if not all(credentials.values()):
            db.execute("UPDATE sources SET status='not_configured' WHERE id='naver-search'")
            return {'status':'not_configured','added':0,'runs':0,'truncated':0,'failed':0}
    summary={'status':'ok','added':0,'runs':0,'truncated':0,'failed':0}
    for query in queries or QUERIES:
        with connect(db_path) as db:
            run=db.execute('INSERT INTO collection_runs(source_id,started_at,status,cursor) VALUES(?,?,?,?)',('naver-search',timestamp,'running',query)).lastrowid
        added=0;status='ok'
        try:
            for page in range(pages):
                url='https://openapi.naver.com/v1/search/news.json?'+urlencode({'query':query,'sort':'date','display':100,'start':page*100+1})
                req=Request(url,headers={'X-Naver-Client-Id':credentials['NAVER_CLIENT_ID'],'X-Naver-Client-Secret':credentials['NAVER_CLIENT_SECRET']})
                data=fetch(req);items=[]
                for r in data['items']:
                    original=r.get('originallink') or r['link']
                    pub=parsedate_to_datetime(r['pubDate'])
                    if pub.tzinfo is None:raise ValueError('게시 시각 시간대 누락')
                    items.append({'source_id':'naver-search','source_name':'뉴스 검색','external_id':original,'channel':'media','url':original,'title':clean(r['title']),'body':clean(r['description']),'published_at':pub.isoformat(),'collected_at':timestamp,'content_scope':'snippet','time_basis':'naver_provided_time','rights_note':'검색 API 메타데이터. 원문 저장권 별도 확보 필요'})
                with connect(db_path) as db:added+=ingest(db,items)
                if len(items)<100:break
                if page==pages-1:status='truncated'
            with connect(db_path) as db:
                db.execute('UPDATE collection_runs SET finished_at=?,status=?,items=? WHERE id=?',(timestamp,status,added,run))
                db.execute('UPDATE sources SET last_success=?,status=? WHERE id=?',(timestamp,'connected','naver-search'))
            summary['added']+=added;summary['runs']+=1;summary['truncated']+=status=='truncated'
        except Exception as exc:
            with connect(db_path) as db:
                db.execute('UPDATE collection_runs SET finished_at=?,status=?,items=?,error_code=? WHERE id=?',(timestamp,'failed',added,type(exc).__name__,run))
                db.execute("UPDATE sources SET status='failed' WHERE id='naver-search'")
            summary['failed']+=1
    if summary['failed']:summary['status']='partial' if summary['runs'] else 'failed'
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default=str(ROOT/'data/live.sqlite3'));p.add_argument('--pages',type=int,default=2);a=p.parse_args()
    print(json.dumps(collect(a.db,pages=a.pages),ensure_ascii=False))
if __name__=='__main__':main()
