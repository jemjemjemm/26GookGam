// GitHub Pages serves a versioned read API as JSON; no keys or local endpoints.
window.RADAR_PAGES={cache:null};
window.radarPagesAPI=async function(path){
 const params=new URL(path,'https://local.invalid');
 let data=window.RADAR_PAGES.cache;
 if(!data||params.pathname==='/api/snapshot'||params.pathname==='/api/readiness'||params.pathname==='/api/reports'){
   try{let res;try{res=await fetch('https://raw.githubusercontent.com/jemjemjemm/daily-energy-dashboard/main/issue-monitoring-data/data.json?t='+Date.now(),{cache:'no-store'});}catch(e){}if(!res||!res.ok)res=await fetch('./data.json?t='+Date.now(),{cache:'no-store'});if(!res.ok)throw Error('수집 자료 조회 실패');data=await res.json();window.RADAR_PAGES.cache=data;}
   catch(e){if(!data)throw e;}
 }
 const at=data.generated_at,stale=Date.now()-Date.parse(at)>45*60000;
 if(params.pathname==='/api/health')return {mode:'live'};
 if(params.pathname==='/api/frames')return data.frames;
 if(params.pathname==='/api/readiness')return data.readiness;
 if(params.pathname==='/api/reports')return data.reports;
 if(params.pathname!=='/api/snapshot')throw Error('지원하지 않는 조회');
 const key=(params.searchParams.get('hours')||'archive')+':'+(params.searchParams.get('channel')||'all');
 const s=JSON.parse(JSON.stringify(data.snapshots[key]));
 if(!s)throw Error('지원하지 않는 시간창');
 s.documents=s.documents.map(id=>data.documents[id]);
 s.mode='live';s.collection_coverage=data.collection.naver;if(s.collection_coverage&&s.collection_coverage.status!=='ok'){s.alerts.unshift({rule:'COLLECTION_STALE',severity:'quality',text:'네이버 검색 전수 조회 미완료: '+s.collection_coverage.status,logic:'검색 실패·API 상한·인증 연결 상태를 검색별 수집 범위에서 확인.',evidence:[]});}if(data.collection.status==='failed'||data.collection.status==='partial'){s.alerts.unshift({rule:'COLLECTION_STALE',severity:'quality',text:'일부 또는 전체 뉴스 수집 실패. 이전 기사 목록을 유지합니다.',logic:'최근 RSS 수집 실행의 실패 건수가 1건 이상.',evidence:[]});}const q=(params.searchParams.get('q')||'').toLocaleLowerCase();
 if(q){s.documents=s.documents.filter(r=>(r.title+' '+r.body).toLocaleLowerCase().includes(q));s.metrics.published=s.documents.filter(r=>r.channel==='media').length;s.metrics.stories=0;s.metrics.public_sample=0;s.metrics.negative=null;s.metrics.risk=null;s.metrics.eligible=0;s.metrics.pending=s.documents.length;s.frames={};s.narratives=[];s.trend=[];s.shift={score:null,delta_pp:null,reason:'검색 표본 분석 대기'};Object.values(s.companies).forEach(x=>{x.score=null;x.mentions=0;x.negative_share=null;});s.logic.exposure_short='검색 결과는 제목 자료만 포함. 본문·승인 분석이 없어 노출 지수 보류.';s.logic.risk_short='검색 결과의 본문·온라인 승인 표본이 없어 위험 지수 보류.';s.logic.shift='제목 검색 결과의 승인 독립 기사가 없어 프레임 변화 판단 보류.';s.logic.negative='승인된 온라인 표본이 없어 부정 비율 판단 보류.';}
 if(stale){s.metrics.risk=null;s.metrics.risk_reason='최신 수집 시각이 45분 이상 경과';s.metrics.coverage=0;s.sources.forEach(x=>x.fresh=false);s.logic.risk_short+=' 최신 수집 45분 초과로 판단 보류.';s.alerts.unshift({rule:'COLLECTION_STALE',severity:'quality',text:'수집·배포 지연. 화면의 기준 시각과 GitHub Actions 실행 결과를 확인하세요.',logic:'페이지 실행 시각−마지막 데이터 생성 시각>45분.',evidence:[]});}
 $('cutoff').value=new Date(Date.parse(at)+9*3600000).toISOString().slice(0,16);$('cutoff').disabled=true;$('dataset').value='live';$('dataset').disabled=true;
 s.limitations.push('네이버 검색 API + 보조 RSS의 제목·매체·링크 관측. 본문·온라인 여론 분석은 연결 대기.','자동 갱신 목표 15분. GitHub 작업 지연 가능; 실제 수집 기준 시각을 확인하세요.');
 return s;
};
