"""Portable synthetic UI fixture; no keys, live records or server required."""
import json
from pathlib import Path
from backend.store import ROOT,connect
from backend.demo import DEMO_AT
from backend.metrics import snapshot
from workers.report import render

def build(output):
    with connect(ROOT/'data/demo.sqlite3') as db:
        s=snapshot(db,DEMO_AT)
        if s['mode']!='demo':raise ValueError('검수 패키지는 합성 예시만 허용')
    data={'snapshot':s,'/api/frames':json.loads((ROOT/'config/frames.json').read_text(encoding='utf-8-sig')),
          '/api/health':{'mode':'demo'},'/api/reports':[{'body':render(s)}],
          '/api/readiness':{'steps':[],'documents':0,'approved':0,'pending':0,'next_action':'검수용 예시에는 실제 수집·분석 기능이 연결되지 않습니다.'}}
    embed=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    html=(ROOT/'frontend/index.html').read_text(encoding='utf-8')
    html=html.replace('<link rel="stylesheet" href="/style.css">','<style>'+(ROOT/'frontend/style.css').read_text(encoding='utf-8')+'</style>')
    html=html.replace('<script src="/app.js"></script>','<script>window.RADAR_PREVIEW='+embed+';</script><script>'+(ROOT/'frontend/app.js').read_text(encoding='utf-8')+'</script>')
    html=html.replace('<script src="/browser-check.js"></script>','<script>'+(ROOT/'frontend/browser-check.js').read_text(encoding='utf-8')+'</script>')
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(html,encoding='utf-8')
    return output

if __name__=='__main__':print(build(ROOT/'preview/safari-preview.html'))
