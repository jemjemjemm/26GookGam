"""Overlapping pagination with explicit completeness accounting, never a zero-miss claim."""
import json
import os
from datetime import datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlencode
from urllib.request import Request
from backend.store import ROOT,connect
from backend.demo import KST
from collectors.import_json import ingest
from collectors.naver import clean,fetch_json

def collect(path,fetch=fetch_json,now=None,config=None):
    now=now or datetime.now(KST);stamp=now.isoformat()
    cfg=config or json.loads((ROOT/'config/collection.json').read_text(encoding='utf-8'))
    since=datetime.fromisoformat(cfg['since']);queries=cfg['queries'];budget=cfg.get('request_budget',200)
    creds=[os.environ.get('NAVER_CLIENT_ID'),os.environ.get('NAVER_CLIENT_SECRET')]
    result={'status':'not_configured','provider':'naver','since':since.isoformat(),'added':0,'requests':0,'failed':0,'queries':[],
            'scope':'네이버 검색에 색인되고 지정 검색어와 일치하는 기사. 미색인 기사·검색어 밖 기사는 포함 보장 불가.'}
    with connect(path) as db:
        db.execute('INSERT OR IGNORE INTO sources(id,channel,name,access_mode,expected_minutes,status,rights_note) VALUES(?,?,?,?,?,?,?)',('naver-search','media','네이버 뉴스 API','api',15,'not_configured','제목·매체·원문 링크만 관측. 요약은 본문으로 간주하지 않음.'))
    if not all(creds):
        result['missing_credentials']=[name for name,value in zip(['NAVER_CLIENT_ID','NAVER_CLIENT_SECRET'],creds) if not value]
        with connect(path) as db:db.execute("UPDATE sources SET status='not_configured' WHERE id='naver-search'")
        return result
    for query in queries:
        q={'query':query,'reported_total':None,'scanned':0,'unique_urls':0,'in_scope':0,'new':0,'pages':0,'status':'running','oldest':None}
        seen=set();relevant=set()
        with connect(path) as db:run=db.execute('INSERT INTO collection_runs(source_id,started_at,status,cursor) VALUES(?,?,?,?)',('naver-search',stamp,'running',query)).lastrowid
        try:
            for start in [*range(1,902,75)]:
                if result['requests']>=budget:q['status']='budget_limit';break
                req=Request('https://openapi.naver.com/v1/search/news.json?'+urlencode({'query':query,'sort':'date','display':100,'start':start}),headers={'X-Naver-Client-Id':creds[0],'X-Naver-Client-Secret':creds[1]})
                result['requests']+=1;data=fetch(req);q['pages']+=1
                total=int(data['total']);q['reported_total']=max(total,q['reported_total'] or 0)
                entries=data['items'];rows=[];old=False
                for r in entries:
                    pub=parsedate_to_datetime(r['pubDate'])
                    if pub.tzinfo is None:raise ValueError('시간대 누락')
                    url=r.get('originallink') or r['link'];seen.add(url);q['scanned']+=1
                    q['oldest']=min(pub.isoformat(),q['oldest']) if q['oldest'] else pub.isoformat()
                    if pub<since:old=True;continue
                    if pub>now:continue
                    relevant.add(url)
                    rows.append({'source_id':'naver-search','source_name':'네이버 뉴스 API','external_id':url,'channel':'media','url':url,'title':clean(r['title']),'body':'','published_at':pub.isoformat(),'collected_at':stamp,'content_scope':'title','time_basis':'naver_provided_time'})
                with connect(path) as db:q['new']+=ingest(db,rows)
                if old:q['status']='scope_boundary_reached';break
                if not entries or start+len(entries)-1>=total:q['status']='results_end_reached';break
                if start==901:q['status']='api_limit';break
            q['unique_urls']=len(seen);q['in_scope']=len(relevant)
            if q['status']=='running':q['status']='api_limit'
        except Exception as exc:
            q['status']='failed';q['error_code']=f'HTTP_{exc.code}' if hasattr(exc,'code') else type(exc).__name__;result['failed']+=1
        result['added']+=q['new'];result['queries'].append(q)
        with connect(path) as db:db.execute('UPDATE collection_runs SET finished_at=?,status=?,items=?,error_code=? WHERE id=?',(stamp,q['status'],q['new'],q.get('error_code'),run))
    good=sum(q['status'] in ['scope_boundary_reached','results_end_reached'] for q in result['queries'])
    result['status']='ok' if good==len(queries) else 'partial' if good else 'failed'
    result['limited_queries']=sum(q['status'] in ['api_limit','budget_limit'] for q in result['queries'])
    with connect(path) as db:
        db.execute('UPDATE sources SET status=?,last_success=CASE WHEN ? THEN ? ELSE last_success END,expected_minutes=15 WHERE id=?',('connected' if good else 'failed',bool(good),stamp,'naver-search'))
    return result
