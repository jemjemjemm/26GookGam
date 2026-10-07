const assert=require('node:assert/strict'),{judge}=require('../frontend/sk-impact.js');
assert.equal(judge({title:'SK 무혐의',url:'https://example.com'}).label,'본문 미 확인 판단 보류');
assert.equal(judge({body_observation:{confirmed:false,label:'긍정'}}).label,'본문 미 확인 판단 보류');
assert.equal(judge({body_observation:{confirmed:true,label:'부정',basis:'본문 근거'}}).label,'부정');
console.log('Body confirmation gate checks passed');
