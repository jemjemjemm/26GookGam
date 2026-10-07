import argparse
import json
from datetime import datetime
from pathlib import Path
from backend.store import ROOT,connect
from backend.demo import KST
from backend.metrics import exposure

CODES={f['code'] for f in json.loads((ROOT/'config/frames.json').read_text(encoding='utf-8-sig'))['frames']}
FLAGS={'body','central','headline','first','negative_link','leniency_link','consumer_link','moral_link'}
COMPANIES={'SK','HYUNDAI','GS','SOIL'}

def validate(result,doc,has_facts):
    required={'document_id','primary_frame','secondary','frames','targets','tone','emotion','argument','evidence','exposure','fact_gap','confidence','model','prompt_version','fact_version'}
    if set(result)!=required: raise ValueError('응답 키 불일치')
    if result['document_id']!=doc['id']: raise ValueError('문서 ID 불일치')
    if result['primary_frame'] not in CODES: raise ValueError('알 수 없는 primary')
    if not isinstance(result['secondary'],list) or len(result['secondary'])>3 or any(f not in CODES or f==result['primary_frame'] for f in result['secondary']): raise ValueError('secondary 불일치')
    if len(set(result['secondary']))!=len(result['secondary']): raise ValueError('secondary 중복')
    if not isinstance(result['frames'],dict) or result['primary_frame'] not in result['frames']: raise ValueError('프레임 강도 누락')
    if set(result['frames'])!={result['primary_frame'],*result['secondary']}: raise ValueError('태그/강도 불일치')
    for value in [result['confidence'],*result['frames'].values()]:
        if type(value) not in [float,int] or not 0<=value<=1: raise ValueError('0~1 수치 필요')
    if result['emotion'] not in ['anger','distrust','mockery','concern','neutral','unknown']: raise ValueError('emotion 불일치')
    if result['tone'] not in ['negative','neutral','positive','unknown']: raise ValueError('tone 불일치')
    if result['fact_gap'] not in ['none','scope','stage','amount','unverifiable']: raise ValueError('fact_gap 불일치')
    if not has_facts and result['fact_gap']!='unverifiable': raise ValueError('공식 사실 미승인: fact gap 판정 금지')
    if not isinstance(result['targets'],list) or any(t not in COMPANIES for t in result['targets']): raise ValueError('target 불일치')
    if not isinstance(result['evidence'],list) or not result['evidence']: raise ValueError('증거 필요')
    for e in result['evidence']:
        if set(e)!={'quote','field'} or e['field'] not in ['title','body'] or not isinstance(e['quote'],str) or not e['quote'] or e['quote'] not in doc[e['field']]: raise ValueError('원문에 없는 인용')
    if not isinstance(result['exposure'],dict) or not set(result['exposure'])<=set(result['targets']): raise ValueError('exposure target 불일치')
    for flags in result['exposure'].values():
        if set(flags)!=FLAGS or any(type(v)!=int or v not in [0,1] for v in flags.values()): raise ValueError('노출 플래그 불일치')
        if flags['first']>flags['headline'] or flags['central']>flags['body']: raise ValueError('노출 플래그 모순')
    if type(result['fact_version'])!=int or result['fact_version']<0: raise ValueError('fact version 필요')
    if not has_facts and result['fact_version']!=0: raise ValueError('미검증 fact version')
    for k in ['model','prompt_version','emotion','argument']:
        if not isinstance(result[k],str) or len(result[k])>500: raise ValueError('문자열 불일치')
    if result['prompt_version']!='1.0.0': raise ValueError('지원하지 않는 prompt 버전')
    # 모델 자유 요약·사실 문장은 저장하지 않는다. 화면은 원문과 검증된 구조 필드만 쓴다.
    return result

def accept(db,result,reviewer):
    doc=db.execute('SELECT * FROM documents WHERE id=?',(result.get('document_id'),)).fetchone()
    if not doc: raise ValueError('문서 없음')
    facts=db.execute("SELECT * FROM fact_baselines WHERE verification='verified' AND valid_to IS NULL").fetchall()
    validate(result,doc,bool(facts))
    if facts and result['fact_version']!=max(f['version'] for f in facts): raise ValueError('fact version 불일치')
    if not reviewer.strip(): raise ValueError('승인자 필요')
    previous=db.execute('SELECT * FROM analyses WHERE document_id=?',(doc['id'],)).fetchone()
    now=datetime.now(KST).isoformat()
    values=(doc['id'],'approved',result['primary_frame'],json.dumps(result['secondary']),json.dumps(result['frames']),json.dumps(result['targets']),result['tone'],result['emotion'],result['argument'],json.dumps(result['evidence'],ensure_ascii=False),json.dumps(result['exposure']),result['fact_gap'],result['confidence'],result['model'],result['prompt_version'],result['fact_version'],reviewer,now)
    db.execute('INSERT OR REPLACE INTO analyses VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',values)
    db.execute('INSERT INTO audit_log(actor,action,object_id,payload_json,created_at) VALUES(?,?,?,?,?)',(reviewer,'analysis_approve',doc['id'],json.dumps({'previous':dict(previous) if previous else None,'new':result},ensure_ascii=False),now))

def check(db,result):
    doc=db.execute('SELECT * FROM documents WHERE id=?',(result.get('document_id'),)).fetchone()
    if not doc:raise ValueError('문서 없음')
    facts=db.execute("SELECT * FROM fact_baselines WHERE verification='verified' AND valid_to IS NULL").fetchall()
    validate(result,doc,bool(facts))
    if facts and result['fact_version']!=max(f['version'] for f in facts):raise ValueError('fact version 불일치')
    return {'status':'validated_not_approved','document_id':doc['id'],'title':doc['title'],
            'primary_frame':result['primary_frame'],'evidence':result['evidence'],
            'exposure':{company:round(exposure(flags),1) for company,flags in result['exposure'].items()},
            'logic':'원문 일치 인용·사전 코드·수치 범위·공식 기준선 버전 검증. 의미 분류의 타당성은 담당자 확인 필요.',
            'fact_gap':result['fact_gap'],'writes':0}

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['jobs','check','accept']);p.add_argument('file',nargs='?');p.add_argument('--db',default='data/live.sqlite3');p.add_argument('--reviewer');a=p.parse_args()
    with connect(a.db) as db:
        if a.action=='check':
            if not a.file:p.error('check에는 응답 JSON file 필요')
            print(json.dumps(check(db,json.loads(Path(a.file).read_text(encoding='utf-8-sig'))),ensure_ascii=False,indent=2))
        elif a.action=='accept':
            if not a.file or not a.reviewer: p.error('accept에는 file과 --reviewer 필요')
            accept(db,json.loads(Path(a.file).read_text(encoding='utf-8-sig')),a.reviewer)
            print('approved')
        else:
            rows=[dict(r) for r in db.execute("SELECT d.* FROM documents d JOIN analyses a ON a.document_id=d.id WHERE a.status='pending'")]
            out=ROOT/'data/analysis_jobs.json'
            out.write_text(json.dumps({'prompt_version':'1.0.0','prompts':str(ROOT/'docs/prompts.md'),'dictionary':json.loads((ROOT/'config/frames.json').read_text(encoding='utf-8-sig')),'verified_facts':[dict(r) for r in db.execute("SELECT * FROM fact_baselines WHERE verification='verified' AND valid_to IS NULL")],'documents':rows},ensure_ascii=False,indent=2),encoding='utf-8')
            print(str(out),len(rows))

if __name__=='__main__':main()
