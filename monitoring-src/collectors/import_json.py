import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from backend.store import connect
from backend.demo import KST

CHANNELS={'media','portal','community','sns','broadcast','official'}

def ingest(db,items):
    added=0
    for item in items:
        if item['channel'] not in CHANNELS: raise ValueError('invalid channel')
        for key in ['published_at','collected_at']:
            if datetime.fromisoformat(item[key]).tzinfo is None: raise ValueError('시간대 필요: '+key)
        url=item.get('url','')
        if url and urlsplit(url).scheme not in ['http','https']: raise ValueError('http(s) URL 필요')
        normalized=urlunsplit((*urlsplit(url)[:3],'','')) if url else ''
        body=item['body']; digest=hashlib.sha256(body.encode()).hexdigest()
        identity=item['source_id']+'|'+(item.get('external_id') or normalized or digest)
        id=hashlib.sha256(identity.encode()).hexdigest()[:24]
        db.execute('INSERT OR IGNORE INTO sources(id,channel,name,access_mode,expected_minutes,status,rights_note) VALUES(?,?,?,?,?,?,?)',(item['source_id'],item['channel'],item.get('source_name',item['source_id']),'manual_import',5,'connected',item.get('rights_note','접근권 별도 확인 필요')))
        source=db.execute('SELECT channel FROM sources WHERE id=?',(item['source_id'],)).fetchone()
        if source['channel']!=item['channel']: raise ValueError('source channel mismatch')
        existing=db.execute('SELECT id FROM documents WHERE id=?',(id,)).fetchone()
        if existing: continue
        # MVP는 완전 일치 본문만 묶는다. 유사 전재 군집은 운영 단계에서 별도 검수.
        cluster=hashlib.sha256((item['channel']+'|'+digest).encode()).hexdigest()[:24]
        db.execute('INSERT INTO documents(id,source_id,external_id,url,title,body,published_at,collected_at,time_basis,content_scope,content_hash,cluster_id,parent_id,sample_method) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,item['source_id'],item.get('external_id') or id,url,item['title'],body,item['published_at'],item['collected_at'],item.get('time_basis','source'),item['content_scope'],digest,cluster,item.get('parent_id'),item.get('sample_method','manual')))
        db.execute('INSERT INTO analyses VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,'pending','F00','[]','{}','[]','unknown','unknown','','[]','{}','unverifiable',0,'not_analyzed','1.0.0',0,None,datetime.now(KST).isoformat()))
        db.execute('UPDATE sources SET last_success=?,status=? WHERE id=?',(item['collected_at'],'connected',item['source_id']))
        added+=1
    return added

def main():
    p=argparse.ArgumentParser();p.add_argument('file');p.add_argument('--db',default='data/live.sqlite3');a=p.parse_args()
    items=json.loads(Path(a.file).read_text(encoding='utf-8-sig'))
    with connect(a.db) as db: print('imported:',ingest(db,items))

if __name__=='__main__': main()
