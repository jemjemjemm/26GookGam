/* Provisional title observations. These never approve analyses or assert case facts. */
(function(root){
 const start='2026-10-07T12:00:00+09:00';
 const companyRules={SK:/SK(?:\s*에너지)?|에스케이\s*에너지/i,HYUNDAI:/(?:HD\s*)?현대(?:\s*오일뱅크)?/i,GS:/GS\s*칼텍스|지에스\s*칼텍스/i,SOIL:/S[\s-]*OIL|에쓰\s*오일|에스\s*오일/i};
 const rules=[
  ['F06',/면죄부|처벌\s*회피|제재\s*회피|특혜/],
  ['F12',/손해배상|집단소송|불매/],['F07',/소비자|서민|부담|피해/],
  ['F08',/폭리|부당\s*이익/],['F11',/전쟁\s*(?:틈|타)|고유가\s*(?:악용|이용)/],
  ['F05',/리니언시|자진\s*신고/],['F14',/반론|최종\s*판단|미확정/],
  ['F13',/국감|국정감사|국회의원|시민단체/]
 ];
 function classify(title){
  for(const [code,re] of rules){const m=title.match(re);if(m)return {code,evidence:m[0]};}
  const sk=title.match(companyRules.SK),hy=title.match(companyRules.HYUNDAI);
  if(sk&&hy)return {code:'F02',evidence:sk[0]+' / '+hy[0]};
  const industry=title.match(/정유\s*(?:4사|업계|사)|정유/);
  if(industry)return {code:'F01',evidence:industry[0]};
  return {code:'F00',evidence:'사전의 제목 단서 없음'};
 }
 function observe(documents,at){
  const media=documents.filter(r=>r.channel==='media'),companies={};
  for(const [code,re] of Object.entries(companyRules)){
   const hits=media.filter(r=>re.test(r.title));
   companies[code]={count:hits.length,total:media.length,share:media.length?Math.round(hits.length/media.length*1000)/10:null};
  }
  const first=Date.parse(start),last=Date.parse(at),hours=[];
  for(let from=first;from<last;from+=3600000){
   const until=Math.min(from+3600000,last),rows=media.filter(r=>{const t=Date.parse(r.published_at);return t>=from&&t<until;});
   const counts={},shares={};for(const r of rows){const c=classify(r.title).code;counts[c]=(counts[c]||0)+1;}
   for(const [c,n] of Object.entries(counts))shares[c]=n/rows.length;
   hours.push({at:new Date(from).toISOString(),end:new Date(until).toISOString(),n:rows.length,shares,counts,partial:until<from+3600000});
  }
  return {start,companies,hours,total:media.length};
 }
 root.HeadlineObservation={classify,observe};
 if(typeof module!=='undefined')module.exports=root.HeadlineObservation;
})(typeof window!=='undefined'?window:globalThis);
