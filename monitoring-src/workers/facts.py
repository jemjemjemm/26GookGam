import argparse
import hashlib
import json
from pathlib import Path
from datetime import datetime
from backend.store import connect
from backend.demo import KST

STAGES={'examiner_opinion','commission_decision','prosecution_allegation','court_judgment','company_response','official_announcement'}

def approve(db,record,source_text_path,reviewer):
    required={'id','statement','procedural_status','source_uri','source_hash','locator','evidence_quote','version','valid_from'}
    if set(record)!=required:raise ValueError('기준선 키 불일치')
    if record['procedural_status'] not in STAGES:raise ValueError('절차 단계 불일치')
    if not reviewer.strip() or not record['locator'] or not record['statement']:raise ValueError('승인자/위치/문장 필요')
    path=Path(source_text_path)
    raw=path.read_bytes();text=raw.decode('utf-8-sig')
    if hashlib.sha256(raw).hexdigest()!=record['source_hash']:raise ValueError('원문 hash 불일치')
    if not record['evidence_quote'] or record['evidence_quote'] not in text:raise ValueError('원문 인용 불일치')
    if datetime.fromisoformat(record['valid_from']).tzinfo is None:raise ValueError('오프셋 필요')
    if type(record['version'])!=int or record['version']<1:raise ValueError('양수 version 필요')
    if db.execute('SELECT 1 FROM fact_baselines WHERE id=?',(record['id'],)).fetchone():raise ValueError('기존 사실을 덮지 않습니다. 새 id/version 필요')
    now=datetime.now(KST).isoformat()
    db.execute('INSERT INTO fact_baselines VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(record['id'],record['statement'],record['procedural_status'],record['source_uri'],record['source_hash'],record['locator'],record['evidence_quote'],'verified',record['version'],reviewer,now,record['valid_from'],None))
    db.execute('INSERT INTO audit_log(actor,action,object_id,payload_json,created_at) VALUES(?,?,?,?,?)',(reviewer,'fact_approve',record['id'],json.dumps(record,ensure_ascii=False),now))

def main():
    p=argparse.ArgumentParser(description='공식 원문 대조 후 사람 승인자 전용 기준선 등록. PDF는 페이지 대조한 UTF-8 전사와 원본을 함께 보존하세요.')
    p.add_argument('record');p.add_argument('source_text');p.add_argument('--db',default='data/live.sqlite3');p.add_argument('--reviewer',required=True);a=p.parse_args()
    with connect(a.db) as db:approve(db,json.loads(Path(a.record).read_text(encoding='utf-8-sig')),a.source_text,a.reviewer)
    print('공식 기준선 등록 및 승인 감사 이력 저장')

if __name__=='__main__':main()
