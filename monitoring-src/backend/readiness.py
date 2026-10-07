import os
from pathlib import Path

def readiness(db):
    creds=all(os.environ.get(k) for k in ['NAVER_CLIENT_ID','NAVER_CLIENT_SECRET'])
    documents=db.execute('SELECT COUNT(*) FROM documents WHERE is_demo=0').fetchone()[0]
    approved=db.execute("SELECT COUNT(*) FROM analyses a JOIN documents d ON d.id=a.document_id WHERE d.is_demo=0 AND a.status='approved'").fetchone()[0]
    pending=db.execute("SELECT COUNT(*) FROM analyses a JOIN documents d ON d.id=a.document_id WHERE d.is_demo=0 AND a.status='pending'").fetchone()[0]
    facts=db.execute("SELECT COUNT(*) FROM fact_baselines WHERE verification='verified'").fetchone()[0]
    sources=[dict(r) for r in db.execute('SELECT id,name,status,last_success FROM sources')]
    successes=db.execute("SELECT COUNT(*) FROM collection_runs WHERE status IN ('ok','truncated')").fetchone()[0]
    steps=[
        {'label':'공식 브리핑 확인','ready':bool(facts),'note':f'승인된 공식 기준선 {facts}건. 원문·문단 증거와 담당자 승인 필요.'},
        {'label':'뉴스 검색 인증','ready':creds,'note':'서버 환경변수 설정 여부만 확인합니다. 비밀키 값은 화면에 보내지 않습니다.'},
        {'label':'실제 자료 수집','ready':bool(successes or documents),'note':f'수집 문서 {documents}건, 성공한 API 수집 실행 {successes}회.'},
        {'label':'AI 분석·검토','ready':bool(approved),'note':f'승인 {approved}건, 대기 {pending}건. 현재 분석 작업파일과 수동 승인 경로를 사용합니다.'},
        {'label':'휴대폰 접속 주소','ready':False,'note':'현재는 PC 안의 로컬 주소입니다. 실제 휴대폰 접속에는 별도 HTTPS 호스팅과 접근 권한 설정이 필요합니다.'}
    ]
    next_action='공식 브리핑 원문 확인' if not facts else '서버에 뉴스 검색 인증 설정' if not creds else '수집 작업기를 실행하고 본문 확보·분석 검수'
    return {'steps':steps,'documents':documents,'approved':approved,'pending':pending,'sources':sources,'next_action':next_action}
