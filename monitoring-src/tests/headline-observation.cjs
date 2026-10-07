const assert=require('node:assert/strict');
const {classify,observe}=require('../frontend/headline-observation.js');
const docs=[
 {channel:'media',title:'SK에너지·현대오일뱅크 담합 의혹',published_at:'2026-10-07T12:00:00+09:00'},
 {channel:'media',title:'소비자 피해 논란',published_at:'2026-10-07T13:00:00+09:00'},
 {channel:'media',title:'정유사 담합',published_at:'2026-10-07T11:59:59+09:00'},
 {channel:'sns',title:'SK에너지',published_at:'2026-10-07T12:05:00+09:00'}
];
const r=observe(docs,'2026-10-07T13:30:00+09:00');
assert.equal(r.hours.length,2);assert.equal(r.hours[0].counts.F02,1);
assert.equal(r.hours[1].counts.F07,1);assert.equal(r.hours[1].partial,true);
assert.equal(r.companies.SK.count,1);assert.equal(r.companies.SK.total,3);
assert.equal(classify('리니언시 면죄부 논란').code,'F06');
assert.equal(classify('공정위 발표').code,'F00');
assert.equal(observe(docs,'2026-10-07T11:00:00+09:00').hours.length,0);
assert.equal(observe([],'2026-10-07T13:00:00+09:00').companies.SK.share,null);
assert.equal(docs[0].status,undefined); // title observation never grants approval
console.log('Title observation boundary and guardrail checks passed');
