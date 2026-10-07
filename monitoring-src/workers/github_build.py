"""Build GitHub Pages data from public RSS metadata, with a durable JSON ledger."""
import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from backend.store import ROOT,connect
from backend.demo import KST
from backend.metrics import snapshot
from collectors.import_json import ingest
from collectors.rss import collect
from collectors.naver_full import collect as collect_naver
from workers.report import render,tick
from workers.public_report import connected,render_current
from collectors.article_body import collect as collect_bodies

def build(db_path,out,state,run_collection=True,now=None):
    now=now or datetime.now(KST);out=Path(out);out.mkdir(parents=True,exist_ok=True);state=Path(state)
    if state.exists():
        items=json.loads(state.read_text(encoding='utf-8'))
        # Public ledger is title-only and cannot smuggle approval/fact/body fields into publication.
        for x in items:
            if x.get('source_id') not in ['google-news-rss','naver-search'] or x.get('content_scope')!='title' or x.get('body')!='':raise ValueError('비공개 자료 또는 본문 장부 거부')
        with connect(db_path) as db:ingest(db,items)
    rss=collect(db_path,now=now) if run_collection else {'status':'not_run'}
    naver=collect_naver(db_path,now=now) if run_collection else {'status':'not_run','queries':[]}
    result={'status':'ok' if naver['status']=='ok' else 'partial' if rss['status']=='ok' else rss['status'],'rss':rss,'naver':naver}
    channels=['all','media','portal','community','sns','broadcast','official']
    with connect(db_path) as db:
        if db.execute('SELECT COUNT(*) FROM documents WHERE is_demo=1').fetchone()[0]:raise ValueError('데모 DB 게시 금지')
        # Dedicated publication DB must contain public RSS title metadata only.
        if db.execute("SELECT COUNT(*) FROM documents WHERE source_id NOT IN ('google-news-rss','naver-search') OR content_scope!='title' OR body!=''").fetchone()[0]:raise ValueError('공개 승인 없는 자료 게시 금지')
        report_state=state.with_name('reports.json')
        if report_state.exists():
            for r in json.loads(report_state.read_text(encoding='utf-8')):
                db.execute('INSERT OR IGNORE INTO reports VALUES(?,?,?,?,?,?,?)',tuple(r[k] for k in ['id','scheduled_at','cutoff_at','status','body','snapshot_json','generated_at']))
        tick(db,now)
        saved_reports=[dict(r) for r in db.execute('SELECT * FROM reports ORDER BY scheduled_at DESC LIMIT 100')]
        report_state.parent.mkdir(parents=True,exist_ok=True);report_state.write_text(json.dumps(saved_reports,ensure_ascii=False),encoding='utf-8')
        snapshots={f'{hours}:{channel}':snapshot(db,now.isoformat(),hours,channel) for hours in [1,3,6,12,24] for channel in channels}
        rows=[dict(r) for r in db.execute('SELECT * FROM documents ORDER BY published_at DESC')]
        archive_hours=max(24,(now-min(datetime.fromisoformat(r['published_at']) for r in rows)).total_seconds()/3600+1) if rows else 24
        snapshots.update({f'archive:{channel}':snapshot(db,now.isoformat(),archive_hours,channel) for channel in channels})
        keys=['source_id','external_id','url','title','body','published_at','collected_at','time_basis','content_scope']
        ledger=[{**{k:r[k] for k in keys},'channel':'media','source_name':'네이버 뉴스 API' if r['source_id']=='naver-search' else 'Google 뉴스 RSS'} for r in rows]
        state.parent.mkdir(parents=True,exist_ok=True);state.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
        total=len(rows);s=snapshots['24:all']
        reports=[{'body':r['body']} for r in saved_reports[:20]]
        if connected(naver):
            current=render_current(rows,result,now.isoformat())
            (out/'report.md').write_text(current,encoding='utf-8')
            reports.insert(0,{'body':current})
        # Store documents once; all time/channel snapshots reference the same catalog.
        catalog={r['id']:r for entry in snapshots.values() for r in entry['documents']}
        observations,body_summary=collect_bodies(rows,state.with_name('article-observations.json'),now)
        for doc_id,doc in catalog.items():doc['body_observation']=observations.get(doc_id,{'confirmed':False})
        result['article_body']=body_summary
        for entry in snapshots.values():entry['documents']=[r['id'] for r in entry['documents']]
        payload={'schema_version':1,'generated_at':now.isoformat(),'collection':result,'total_documents':total,
                 'snapshots':snapshots,'documents':catalog,'frames':json.loads((ROOT/'config/frames.json').read_text(encoding='utf-8-sig')),
                 'readiness':{'documents':total,'approved':0,'pending':total,'body_confirmed':body_summary['confirmed'],'body_unconfirmed':body_summary['unconfirmed'],'steps':[
                    {'label':'네이버 뉴스 API','ready':naver['status']=='ok','note':f'네이버: {naver["status"]}. 검색별 수집 결과는 보고서에서 확인.'},
                    {'label':'보조 뉴스 RSS','ready':rss['status']=='ok','note':f'누적 제목·매체·링크 {total}건. RSS: {rss["status"]}.'},
                    {'label':'공식 브리핑 확인','ready':True,'note':'대한민국 정책브리핑 공식 보도자료','url':'https://www.korea.kr/briefing/pressReleaseView.do?newsId=156784497&pageIndex=1&repCodeType=&repCode=&startDate=2025-10-07&endDate=2026-10-07&srchWord=&period='},
                    ],'next_action':'공식 브리핑과 기사 원문을 대조해 확인'},
                 'reports':reports}
    (out/'data.json').write_text(json.dumps(payload,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    html=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
    html=html.replace('href="/style.css"','href="./style.css"').replace('src="/app.js"','src="./app.js"').replace('src="/browser-check.js"','src="./browser-check.js"')
    html=html.replace('src="/impact-reference.js"','src="./impact-reference.js"').replace('src="/sk-impact.js"','src="./sk-impact.js"')
    html=html.replace('src="/headline-observation.js"','src="./headline-observation.js"')
    html=html.replace('<script src="./app.js">','<script src="./pages-api.js"></script><script src="./app.js">')
    html=html.replace('<option value="1">','<option value="1">').replace('<option value="24">','<option value="24" selected>')
    html=html.replace('기준 시각 · 한국시간','최근 수집 시각 · 한국시간')
    html=html.replace('<option value="24" selected>최근 24시간</option>','<option value="24">최근 24시간</option><option value="archive" selected>전체 수집 기사</option>')
    # Browsers may retain old scripts after Pages deploys new HTML.
    for name in ['app.js','style.css','browser-check.js','pages-api.js','headline-observation.js','impact-reference.js','sk-impact.js']:
        version=hashlib.sha256((ROOT/'frontend'/name).read_bytes()).hexdigest()[:12]
        html=html.replace(f'./{name}"',f'./{name}?v={version}"')
    (out/'index.html').write_text(html,encoding='utf-8')
    for name in ['app.js','style.css','browser-check.js','pages-api.js','headline-observation.js','impact-reference.js','sk-impact.js']:(out/name).write_bytes((ROOT/'frontend'/name).read_bytes())
    (out/'.nojekyll').touch()
    return {'collection':result,'documents':total,'output':str(out)}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--db',default='data/github-live.sqlite3');p.add_argument('--out',default='site');p.add_argument('--state',default='state/news.json');p.add_argument('--no-collect',action='store_true');a=p.parse_args()
    print(json.dumps(build(a.db,a.out,a.state,not a.no_collect),ensure_ascii=False))
