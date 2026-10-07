import argparse
import hashlib
import json
import time
from datetime import datetime
from backend.store import ROOT,connect
from backend.demo import seed,KST,DEMO_AT
from backend.metrics import snapshot

SLOTS={'12:00','15:00','18:00','21:30'}

def render(s):
    m=s['metrics']; mode='합성 데모' if s['mode']=='demo' else '관측 자료'
    show=lambda x,suffix='':'판단 보류' if x is None else str(x)+suffix
    dictionary={f['code']:f['label'] for f in json.loads((ROOT/'config/frames.json').read_text(encoding='utf-8-sig'))['frames']}
    frames=', '.join(f'{dictionary.get(k,k)} {v*100:.1f}%' for k,v in sorted(s['frames'].items(),key=lambda x:x[1],reverse=True)[:4]) or '분석 표본 없음'
    return f'''# 상황보고 | {s['at']} | 검토 대기

자료 구분: {mode}. 보고 시간창: 직전 {s['window_hours']}시간. 외부 발송 없음.

1. 상황: 기사 게시 {m['published']}건 / 승인 독립 기사 {m['stories']}건. Risk {show(m['risk'])}. 사유: {m['risk_reason']}.
   판단 기준: {s['logic']['risk']}
2. 프레임: {frames}. Frame Shift {show(s['shift']['score'])}, 비판 프레임 변화 {show(s['shift']['delta_pp'],'%p')}.
   판단 기준: {s['logic']['shift']}
3. 회사 노출: SK {show(s['companies']['SK']['score'])}. 관측 부정기사 중 SK 언급 {show(s['companies']['SK']['negative_share'],'%')}.
   판단 기준: {s['logic']['exposure']} 부정기사 중 언급 비율은 SK 언급 부정기사÷전체 부정기사×100.
4. 온라인: 관측 표본 {m['public_sample']}건, 부정 {show(m['negative'],'%')}. 전체 국민 여론 추정 불가.
   판단 기준: {s['logic']['negative']}
5. 확산: 증빙 이벤트 {len(s['amplifications'])}건. 미연결 채널은 미관측.
   판단 기준: {s['logic']['spread']}
6. 공식 사실: 승인 기준선 {len(s['facts'])}건. 최종 판단 여부는 공식 원문 기준선으로만 확인. 미검증 시 사건 수치·행위 확정 서술 보류.
7. 확인 과제: 브리핑 원문 대조, 포털·방송 증빙 확인, 신규 프레임 담당자 검토.
8. 수집 품질: 신선한 소스 {m['coverage']}/{m['sources']}, 승인 대기 {m['pending']}건.
   판단 기준: {s['logic']['coverage']}

근거 문서: {', '.join(r['id'] for r in s['documents'][:10]) or '없음'}
기준선 버전: {max([f['version'] for f in s['facts']],default=0)}
산식 버전: 1.0.0 / 프롬프트 버전: 1.0.0
'''

def generate(db,at):
    old=db.execute('SELECT body FROM reports WHERE scheduled_at=?',(at,)).fetchone()
    if old: return old['body']
    hours=3.5 if datetime.fromisoformat(at).astimezone(KST).strftime('%H:%M')=='21:30' else 3
    s=snapshot(db,at,hours); body=render(s); now=datetime.now(KST).isoformat()
    id=hashlib.sha256(at.encode()).hexdigest()[:24]
    db.execute('INSERT INTO reports VALUES(?,?,?,?,?,?,?)',(id,at,at,'draft',body,json.dumps(s,ensure_ascii=False),now))
    for alert in s['alerts']:
        aid=hashlib.sha256((alert['rule']+at).encode()).hexdigest()[:24]
        db.execute('INSERT OR IGNORE INTO alerts(id,rule_id,window_end,severity,payload_json,created_at) VALUES(?,?,?,?,?,?)',(aid,alert['rule'],at,alert['severity'],json.dumps(alert,ensure_ascii=False),now))
    out=ROOT/'data/reports';out.mkdir(parents=True,exist_ok=True)
    (out/(id+'.md')).write_text(body,encoding='utf-8')
    return body

def tick(db,now):
    now=now.astimezone(KST)
    # 같은 날짜의 놓친 슬롯도 재기동 시 복구. 각 슬롯 cutoff는 그대로 고정.
    for slot in sorted(SLOTS):
        h,m=map(int,slot.split(':'));due=now.replace(hour=h,minute=m,second=0,microsecond=0)
        if due<=now:generate(db,due.isoformat())

def main():
    p=argparse.ArgumentParser();p.add_argument('--db');p.add_argument('--at',default=DEMO_AT);p.add_argument('--schedule',action='store_true');a=p.parse_args()
    path=a.db or str(ROOT/'data/demo.sqlite3')
    with connect(path) as db:
        if not a.db:seed(db)
    if a.schedule:
        print('KST 12/15/18/21:30 로컬 보고 스케줄러. Ctrl+C로 종료.')
        while True:
            with connect(path) as db:tick(db,datetime.now(KST))
            time.sleep(15)
    else:
        with connect(path) as db:print(generate(db,a.at))

if __name__=='__main__':main()
