// Browser self-check records the engine that actually ran it, never simulated UA.
$('browser-check').addEventListener('click',()=>{
 const ua=navigator.userAgent;
 const safari=/Safari/.test(ua)&&/Version\//.test(ua)&&!/Chrome|Chromium|CriOS|Edg|FxiOS|SamsungBrowser/.test(ua);
 const results={at:new Date().toISOString(),userAgent:ua,safariDetected:safari,url:location.protocol==='file:'?'local file':location.origin,
 viewport:{width:innerWidth,height:innerHeight,scale:window.visualViewport?.scale??null},tab:active,
 overflow:document.documentElement.scrollWidth>document.documentElement.clientWidth,
 whiteBackground:getComputedStyle(document.body).backgroundColor==='rgb(255, 255, 255)',
 visibleLogicBlocks:document.querySelectorAll('.logic').length,
 navTargets:Array.from(document.querySelectorAll('.nav')).map(x=>({label:x.innerText,width:x.getBoundingClientRect().width,height:x.getBoundingClientRect().height})),
 capabilities:{dialog:typeof HTMLDialogElement!=='undefined'&&typeof HTMLDialogElement.prototype.showModal==='function',dvh:CSS.supports('height','100dvh'),safeArea:CSS.supports('padding','env(safe-area-inset-bottom)')},
 manualChecks:{sixTabs:'pending',detailScrollAndClose:'pending',rotation:'pending',pinchZoom:'pending',bottomSafeArea:'pending'},status:'manual_checks_pending'};
 $('detail-title').textContent='브라우저 점검';
 $('detail-body').innerHTML=`<div class="detail-row">${safari?'Safari에서 실행한 점검':'현재 브라우저 점검 · Safari 검수 결과 아님'}<br>화면 ${innerWidth}×${innerHeight} · 가로 넘침 ${results.overflow?'있음':'없음'} · 흰 배경 ${results.whiteBackground?'확인':'미확인'}<br>판단 기준 표시 ${results.visibleLogicBlocks}개</div><div class="detail-row">아래 항목은 직접 조작해 확인해 주세요. 자동 점검만으로 통과 처리하지 않습니다.</div>`+
 [['sixTabs','6개 탭 이동'],['detailScrollAndClose','상세창 내부 스크롤·닫기'],['rotation','세로·가로 회전 후 화면'],['pinchZoom','확대·축소와 글자 읽기'],['bottomSafeArea','하단 탭과 홈 표시줄 겹침 없음']].map(([key,label])=>`<label class="qa-row">${label}<select data-check="${key}"><option value="pending">미확인</option><option value="pass">확인</option><option value="fail">문제 있음</option></select></label>`).join('')+`<p class="logic">판단 기준: 자동 검사는 가로 넘침·흰 배경·탭 크기만 측정합니다. 기능·회전·안전 영역은 실제 조작 확인이 필요합니다.</p><button id="download-check">점검 결과 저장</button>`;
 $('download-check').addEventListener('click',()=>{
   const checks=Array.from(document.querySelectorAll('[data-check]'));
   checks.forEach(x=>results.manualChecks[x.dataset.check]=x.value);
   const manualPassed=checks.every(x=>x.value==='pass');
   const autoPassed=!results.overflow&&results.whiteBackground&&results.navTargets.every(x=>x.width>=44&&x.height>=44);
   results.status=manualPassed&&autoPassed?'checked_current_view':'needs_review';
   const blob=new Blob([JSON.stringify(results,null,2)],{type:'application/json'}),url=URL.createObjectURL(blob),link=document.createElement('a');
   link.href=url;link.download=`browser-check-${safari?'safari':'other'}-${active}.json`;document.body.appendChild(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),1000);
 });showDialog();
});
