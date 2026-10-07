"""Current public metadata report; never convert titles into verified case facts."""
import re

def connected(naver):
    return any(q.get('pages',0)>0 for q in naver.get('queries',[]))

def render_current(rows,collection,at):
    naver=collection['naver'];queries=naver.get('queries',[])
    aliases={'SK':r'SK(?:\s*에너지)?|에스케이\s*에너지','현대오일뱅크':r'(?:HD\s*)?현대(?:\s*오일뱅크)?','GS':r'GS\s*칼텍스|지에스\s*칼텍스','S-OIL':r'S[\s-]*OIL|에쓰\s*오일|에스\s*오일'}
    lines=[f'# D-Issue 최신 수집 보고 | {at}', '', '검토 대기 초안 · 제목·링크 관측 기준 · 사건의 확정 사실이나 본문 AI 분석이 아닙니다.', '',
           f"수집 기사: {len(rows)}건 / 네이버 누적: {sum(r['source_id']=='naver-search' for r in rows)}건 / 이번 네이버 신규: {naver.get('added',0)}건.",
           '판단 기준: 보관 장부의 기사 URL 단위 집계. RSS와 네이버의 전재·중복 보도가 포함될 수 있습니다.', '',
           f"네이버 연결: 실제 응답 확인 / 검색 조회: {naver.get('requests',0)}회 / 수집 범위 상태: {naver['status']}.",
           '판단 기준: 페이지 응답 성공으로 연결을 확인합니다. 검색 상한·오류가 있으면 전체 수집 완료로 해석하지 않습니다.', '', '## 회사별 제목 노출']
    for name,pattern in aliases.items():
        count=sum(bool(re.search(pattern,r['title'],re.I)) for r in rows)
        lines.append(f'- {name}: {count}/{len(rows)}건 ({count/len(rows)*100:.1f}%)' if rows else f'- {name}: 표본 없음')
    lines+=['판단 기준: 회사명 제목 언급 기사 ÷ 수집 기사 ×100. 복수 회사 언급 가능. 책임·부정·실제 도달률이 아닙니다.', '',
            '## 검색별 수집 범위']
    for q in queries:
        lines.append(f"- {q['query']}: {q.get('pages',0)}페이지, 기준일 이후 {q.get('in_scope',0)}건, 상태 {q['status']}"+(f", 오류 {q['error_code']}" if q.get('error_code') else ''))
    lines+=['판단 기준: 검색 결과 끝/기준일 이전 도달은 지정 범위 조회 완료. API·호출 예산 상한과 실패는 미완료입니다.', '',
            '## 온라인·공식 자료', '댓글·SNS·방송 실제 수집 및 공식 브리핑 원문 연결 대기. 미관측을 무반응으로 해석하지 않습니다. 법 위반·대상·수치의 확정 서술은 보류합니다.', '', '## 최근 수집 기사 30건']
    for r in sorted(rows,key=lambda x:x['published_at'],reverse=True)[:30]:
        # Markdown escaping prevents titles from replacing the public source link.
        title=r['title'].replace('\\','\\\\').replace('[','\\[').replace(']','\\]').replace('\n',' ')
        url=r['url'].replace('>','%3E').replace('<','%3C')
        lines.append(f"- {r['published_at']}: [{title}](<{url}>)")
    lines+=['', '기사 제목은 언론의 표현입니다. 분류·판단의 확정 근거로 사용하기 전 원문과 담당자 검토가 필요합니다.']
    return '\n'.join(lines)+'\n'
