# 운영 게시판

운영 주소: https://jemjemjemm.github.io/26GookGam/issue-monitoring/

흰 배경·스마트폰 우선 6개 탭. 뉴스 제목/발행 시각/매체 링크를 공개 RSS에서 수집하고, 판단 기준을 지표·분류·알림 바로 아래 표시합니다.

## 운영 구성

- `monitoring-src/collectors`: 공개 뉴스 수집기. 본문·댓글을 수집했다고 간주하지 않습니다.
- `monitoring-src/backend` / `db`: SQLite DB와 지표 계산. 실행 DB는 저장소에 게시하지 않습니다.
- `monitoring-state`: 공개 제목 메타데이터·보고 초안의 지속 장부. 실행마다 DB 복구.
- `issue-monitoring/data.json`: 시간창·채널별 읽기 API. 공개 제목 자료만 내보내며 승인 없는 본문/실제 댓글/합성 자료를 거부합니다.
- `issue-monitoring/`: GitHub Pages 프론트. 비밀키·PC 로컬 주소를 사용하지 않습니다.
- `.github/workflows/issue-monitoring.yml`: 15분 목표 수집·테스트·게시. 기존 root 게시판의 HTML을 수정하지 않습니다.

자동 갱신은 GitHub Actions의 예약 실행이며 지연될 수 있습니다. 45분 이상 오래된 화면에는 지연 신호를 표시합니다. 실패 시 이전 기사를 보존하고 수집 상태를 표시합니다. 예약 작업은 활동이 없는 공개 저장소에서 60일 뒤 비활성화될 수 있습니다. [GitHub 예약 실행 문서](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows)

기존 Pages는 main/root 기반입니다. GitHub 토큰 커밋은 Pages 자동 빌드를 유발하지 않으므로 작업 마지막에 Pages 빌드를 명시적으로 요청합니다. [Pages 빌드 API](https://docs.github.com/en/rest/pages/pages?apiVersion=2022-11-28#request-a-github-pages-build)

## 연결 상태

뉴스 제목 자동 수집은 실제 RSS 자료입니다. 본문·댓글·방송·포털 메인, 공식 브리핑, 모델 자동 분석은 연결 대기입니다. 승인 독립 기사·온라인 표본이 없으면 노출/부정/위험/프레임 변화 지수는 판단 보류입니다. 기사 제목의 주장이나 심사 단계 내용을 최종 판단으로 확정하지 않습니다.

공개 게시 범위는 제목·매체·링크 메타데이터로 제한합니다. 실제 본문과 검토 자료를 운영 DB에 연결하는 단계에서는 별도 비공개 DB/API와 접근 제어가 필요합니다. 현재 Pages 장부에 넣으면 게시를 거부합니다.

## 보고 / 점검

KST 12/15/18/21:30에 대응하는 고정 시각의 초안을 다음 작업 실행에서 생성합니다. 늦게 수집한 자료를 과거 보고에 소급 반영하지 않습니다. 외부 발송은 없습니다.

하단 '브라우저 점검'에서 실제 Safari 환경의 실행 정보·수동 점검을 JSON으로 저장할 수 있습니다. Chromium 모바일 폭 검사와 실제 Safari 실행 결과를 구분합니다.
