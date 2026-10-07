import argparse
import json
import time
from datetime import datetime,timedelta
from pathlib import Path
from backend.store import ROOT,connect
from backend.demo import KST
from collectors.naver import collect
from workers.report import tick

# 마지막 실행 시각을 DB에 보존해 재기동 직후 중복 수집을 방지한다.
def prepare(db):
    db.execute('CREATE TABLE IF NOT EXISTS pipeline_state (job TEXT PRIMARY KEY, last_attempt TEXT, last_result_json TEXT NOT NULL)')

def export_pending(db,out):
    rows=[dict(r) for r in db.execute("SELECT d.* FROM documents d JOIN analyses a ON a.document_id=d.id WHERE d.is_demo=0 AND a.status='pending'")]
    facts=[dict(r) for r in db.execute("SELECT * FROM fact_baselines WHERE verification='verified' AND valid_to IS NULL")]
    out=Path(out);out.parent.mkdir(parents=True,exist_ok=True)
    payload={'prompt_version':'1.0.0','dictionary':json.loads((ROOT/'config/frames.json').read_text(encoding='utf-8-sig')),'prompts':(ROOT/'docs/prompts.md').read_text(encoding='utf-8-sig'),'verified_facts':facts,'documents':rows,'review_required':True}
    temp=out.with_suffix('.tmp');temp.write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8');temp.replace(out)
    return len(rows)

def step(db_path,interval=300,now=None,collector=collect):
    if interval<120:raise ValueError('수집 간격은 120초 이상')
    now=now or datetime.now(KST)
    with connect(db_path) as db:
        prepare(db)
        if db.execute('SELECT COUNT(*) FROM documents WHERE is_demo=1').fetchone()[0]:raise ValueError('작업기는 합성 데모 DB를 사용하지 않습니다')
        row=db.execute("SELECT last_attempt FROM pipeline_state WHERE job='news'").fetchone()
        due=not row or (now-datetime.fromisoformat(row['last_attempt'])).total_seconds()>=interval
        if due:
            db.execute('INSERT OR REPLACE INTO pipeline_state VALUES(?,?,?)',('news',now.isoformat(),'{}'))
    collected={'status':'not_due'}
    if due:collected=collector(db_path,now=now)
    with connect(db_path) as db:
        if due:db.execute('UPDATE pipeline_state SET last_result_json=? WHERE job=?',(json.dumps(collected),'news'))
        tick(db,now)
        pending=export_pending(db,Path(db_path).parent/'analysis_jobs.json')
    return {'collection':collected,'analysis_pending':pending,'reports':'draft_only','model_calls':0}

def main():
    p=argparse.ArgumentParser();p.add_argument('--db',default=str(ROOT/'data/live.sqlite3'));p.add_argument('--interval',type=int,default=300);p.add_argument('--once',action='store_true');a=p.parse_args()
    while True:
        result=step(a.db,a.interval)
        print(json.dumps(result,ensure_ascii=False),flush=True)
        if a.once:break
        time.sleep(15)
if __name__=='__main__':main()
