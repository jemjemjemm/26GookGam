import argparse
import json
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlsplit, parse_qs
from datetime import datetime
from .store import connect, ROOT
from .demo import seed, DEMO_AT, KST
from .metrics import snapshot
from .readiness import readiness

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parts=urlsplit(self.path)
        if parts.path.startswith('/api/'):
            try:
                args=parse_qs(parts.query)
                dataset=args.get('dataset',['demo' if self.server.demo else 'live'])[0]
                if dataset not in ['demo','live']:raise ValueError('유효하지 않은 데이터셋')
                db_path=self.server.db_path if dataset=='demo' else self.server.live_db_path
                if parts.path=='/api/readiness':db_path=self.server.live_db_path
                at=args.get('at',[DEMO_AT if dataset=='demo' else datetime.now(KST).isoformat()])[0]
                hours=int(args.get('hours',['1'])[0])
                if hours not in [1,3,6,12,24]:
                    raise ValueError('지원 시간창: 1/3/6/12/24시간')
                channel=args.get('channel',['all'])[0]
                if channel not in ['all','media','portal','community','sns','broadcast','official']:
                    raise ValueError('유효하지 않은 채널')
                with connect(db_path) as db:
                    if parts.path=='/api/snapshot':
                        payload=snapshot(db,at,hours,channel,args.get('q',[''])[0][:200])
                    elif parts.path=='/api/frames':
                        payload=json.loads((ROOT/'config/frames.json').read_text(encoding='utf-8-sig'))
                    elif parts.path=='/api/reports':
                        payload=[dict(r) for r in db.execute('SELECT id,scheduled_at,status,body FROM reports ORDER BY scheduled_at DESC LIMIT 20')]
                    elif parts.path=='/api/readiness':
                        payload=readiness(db)
                    elif parts.path=='/api/health':
                        payload={'status':'ok','mode':'demo' if self.server.demo else 'live'}
                    else:
                        self.send_error(404); return
                self.json(payload)
            except (ValueError,KeyError) as exc:
                self.json({'error':str(exc)},400)
            return
        files={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css','/browser-check.js':'browser-check.js'}
        if parts.path not in files:
            self.send_error(404); return
        file=ROOT/'frontend'/files[parts.path]
        content=file.read_bytes()
        self.send_response(200)
        self.send_header('Content-Type',{'html':'text/html; charset=utf-8','js':'text/javascript; charset=utf-8','css':'text/css; charset=utf-8'}[file.suffix[1:]])
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'")
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Cache-Control','no-store')
        self.end_headers(); self.wfile.write(content)
    def json(self,payload,status=200):
        content=json.dumps(payload,ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json; charset=utf-8')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.end_headers(); self.wfile.write(content)
    def log_message(self,fmt,*args):
        pass

def main():
    p=argparse.ArgumentParser(); p.add_argument('--db'); p.add_argument('--live-db',default=str(ROOT/'data/live.sqlite3')); p.add_argument('--port',type=int,default=8765); args=p.parse_args()
    db_path=args.db or str(ROOT/'data/demo.sqlite3')
    demo=args.db is None
    with connect(db_path) as db:
        if demo: seed(db)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    server.db_path=db_path; server.live_db_path=args.db or args.live_db; server.demo=demo
    print(f'Dashboard: http://127.0.0.1:{args.port} | '+('DEMO' if demo else 'LIVE / awaiting collection'))
    try: server.serve_forever()
    except KeyboardInterrupt: server.server_close()

if __name__=='__main__': main()
