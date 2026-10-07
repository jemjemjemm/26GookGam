const assert=require('node:assert/strict'),{judge}=require('../frontend/sk-impact.js');
const known=[{url:'https://www.example.com/article/1?utm_source=naver',title:'SK에너지 전쟁 틈타 담합 심의',label:'중립',basis:'제공 보고의 단순 브리핑 보도'},
 {url:'https://example.com/article/2',title:'SK에너지 담합 심의(종합)',label:'긍정',basis:'당사 입장 반영'}];
assert.equal(judge({title:'SK에너지 7.9조 과징금 가능',url:'https://other.com/1'},known).label,'중립');
assert.equal(judge({title:'SK에너지 소비자 피해 면죄부 논란',url:'https://other.com/2'},known).label,'부정');
assert.equal(judge({title:'SK에너지 담합 부인',url:'https://other.com/3'},known).label,'긍정');
assert.equal(judge({title:'다른 제목',url:'http://example.com/article/1?utm_medium=ref'},known).label,'중립');
assert.equal(judge({title:'SK에너지 담합 심의(종합) - 뉴스',url:'https://news.google.com/rss/a'},known).label,'긍정');
assert.equal(judge({title:'현대오일뱅크 폭리',url:'https://other.com/4'},known).label,'중립');
console.log('SK impact reference, amount and company attribution checks passed');
