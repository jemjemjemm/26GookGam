/* SK impact is a communication judgment, never a legal finding. */
(function(root){
 const normalize=t=>String(t||'').split(' - ')[0].replace(/[^가-힣a-zA-Z0-9]/g,'').toLowerCase();
 function canonical(value){try{const u=new URL(value);const keys=['newsId','articleId','idxno','no','code','key'];return u.hostname.replace(/^www\./,'')+u.pathname+'?'+keys.filter(k=>u.searchParams.has(k)).sort().map(k=>k+'='+u.searchParams.get(k)).join('&');}catch{return value;}}
 function judge(row,references=[]){
  const byURL=references.find(x=>canonical(x.url)===canonical(row.url));
  const byTitle=references.find(x=>normalize(x.title)===normalize(row.title));
  const known=byURL||byTitle;
  if(known)return {label:known.label,basis:known.basis+' 기사 URL 또는 제목을 제공 목록과 대조. 본문 자동 검증 결과가 아님.'};
  const title=row.title||'',sk=/SK(?:\s*에너지)?|에스케이\s*에너지/i.test(title),industry=/정유\s*(?:4사|업계|사)|기름값.*담합|유가.*담합/.test(title);
  if(!sk&&!industry)return {label:'중립',basis:'제목에서 SK에너지 또는 정유업계의 명시적인 영향 단서를 확인하지 못함. 본문에 따른 판단 변경 가능.'};
  const negative=title.match(/면죄부|특혜|처벌\s*회피|제재\s*회피|소비자\s*(?:피해|분노)|서민\s*(?:피해|부담)|폭리|불매|집단소송|책임론|봐주기|꼼수|딱\s*걸렸다/);
  if(negative)return {label:'부정',basis:`제목 기준 잠정 판단: ‘${negative[0]}’가 단순 심의 보도보다 추가 비판·피해·제재 회피 논리를 강조. 법 위반 확정 판단이 아님.`};
  const positive=sk&&title.match(/무혐의|혐의\s*벗|담합\s*(?:아니다|아냐|부인)|반박|정당한\s*거래/);
  if(positive)return {label:'긍정',basis:`제목 기준 잠정 판단: ‘${positive[0]}’가 SK의 방어·완화 논리를 노출. 주장·반론의 진위를 확정하지 않음.`};
  return {label:'중립',basis:'제목 기준 잠정 판단: 혐의·조사·심의·제재 착수·관련 매출·예상 과징금은 브리핑 전달 범위로 처리. 4.6조/7.9조 등 추정액 차이만으로 부정 분류하지 않음. 본문 확인 전 판단.'};
 }
 root.SKImpact={judge};if(typeof module!=='undefined')module.exports=root.SKImpact;
})(typeof window!=='undefined'?window:globalThis);
