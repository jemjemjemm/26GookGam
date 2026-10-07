"""Read public article bodies on the worker; publish judgments, never full text."""
import hashlib
import ipaddress
import json
import re
import socket
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta
from urllib.parse import urlsplit
from urllib.request import Request,build_opener,HTTPRedirectHandler
from bs4 import BeautifulSoup

PENDING='본문 미 확인 판단 보류'
SELECTORS=['#dic_area','#articleBodyContents','#articleBody','#article_body','#textBody','#newsct_article','#article_content','.story-news','.article-body','.article_body','.article-body-content','[itemprop="articleBody"]','.article-view-content','article']

def safe_url(url):
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.port not in (None,80,443):raise ValueError('unsafe_url')
    if p.hostname in ('localhost','news.google.com'):raise ValueError('original_article_unresolved')
    for row in socket.getaddrinfo(p.hostname,p.port or (443 if p.scheme=='https' else 80),type=socket.SOCK_STREAM):
        if not ipaddress.ip_address(row[4][0]).is_global:raise ValueError('unsafe_url')
    return url

class PublicRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        safe_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def fetch_html(url):
    req=Request(safe_url(url),headers={'User-Agent':'D-Issue/1.0 public-article-reader','Accept':'text/html'})
    with build_opener(PublicRedirect()).open(req,timeout=8) as response:
        if 'html' not in response.headers.get('Content-Type',''):raise ValueError('not_html')
        raw=response.read(2_000_001)
        if len(raw)>2_000_000:raise ValueError('document_too_large')
        return raw,response.geturl()

def extract(raw):
    soup=BeautifulSoup(raw,'html.parser')
    if soup.select_one('[class*="paywall"], [id*="paywall"]'):raise ValueError('paywall')
    candidates=[]
    def structured(value):
        if isinstance(value,dict):
            if isinstance(value.get('articleBody'),str):candidates.append((value['articleBody'],'structured_articleBody'))
            for v in value.values():structured(v)
        elif isinstance(value,list):
            for v in value:structured(v)
    for script in soup.select('script[type="application/ld+json"]'):
        try:structured(json.loads(script.string or script.get_text()))
        except (ValueError,TypeError):pass
    for node in soup.select('script,style,nav,header,footer,aside,form,.related-news,.advertisement'):node.decompose()
    for selector in SELECTORS:
        for node in soup.select(selector):candidates.append((node.get_text('\n',strip=True),selector))
    for text,method in candidates:
        text=re.sub(r'[ \t]+',' ',text).strip()
        if len(text)<600 or len(re.findall('[가-힣]',text))<150:continue
        if re.search('유료회원 전용|이 기사는 유료|로그인 후 전문|구독 후 전문',text):continue
        return text,method
    raise ValueError('article_body_not_confirmed')

def judge_body(text):
    # Evaluate article paragraphs, not headlines or supplied title classifications.
    paragraphs=re.split(r'\n|(?<=[.!?])\s+',text)
    relevant=[p for p in paragraphs if re.search(r'SK|에스케이|정유|기름값|유가.*담합',p,re.I)]
    if not relevant:return '중립','확인한 본문에서 SK에너지·정유업계에 대한 평가 단서를 찾지 못했습니다.'
    negative=[];positive=[]
    for p in relevant:
        n=re.search(r'면죄부|봐주기|꼼수|폭리|특혜|제재\s*회피|처벌\s*회피|불매|집단소송|소비자.{0,30}(?:분노|피해.*비판)',p)
        if n and not re.search(re.escape(n[0])+r'.{0,15}(?:아니|없|부인)',p):negative.append(n[0])
        m=re.search(r'사실과\s*다르|담합.{0,12}(?:부인|없)|정상적인?\s*(?:거래|영업)|법.{0,10}위반.{0,10}없|무혐의|기소\s*대상에서\s*제외|성실히.{0,15}소명',p)
        if m:positive.append(m[0])
    if negative:
        return '부정',f'본문에서 ‘{negative[0]}’라는 추가 비판·피해 논리가 SK에너지·정유업계와 연결됩니다.'+(' 방어·반론도 있으나 비판 신호를 우선한 규칙 판정입니다.' if positive else ' 단순 심의·과징금 추정 보도와 구분한 규칙 판정입니다.')
    if positive:return '긍정',f'본문에서 ‘{positive[0]}’라는 방어·완화 논리가 함께 전달됩니다. 대응 논리 노출의 상대적 효과이며 주장 진위·무혐의 확정 판단이 아닙니다.'
    return '중립','확인한 본문은 심의 절차·혐의·당국 발표를 전달하며 별도의 비판 또는 방어 단서가 확인되지 않았습니다. 과징금 추정액만으로 부정 분류하지 않습니다.'

def read(row,at,fetch=fetch_html):
    result={'confirmed':False,'label':PENDING,'basis':PENDING,'checked_at':at,'version':2}
    try:
        raw,url=fetch(row['url']);body,method=extract(raw)
        label,basis=judge_body(body)
        result.update(confirmed=True,label=label,basis=basis+' 본문 추출 내용 기준 자동 규칙 판정.',characters=len(body),method=method,body_sha256=hashlib.sha256(body.encode()).hexdigest(),original_url=url)
    except Exception as exc:result['error_code']=f'HTTP_{exc.code}' if hasattr(exc,'code') else str(exc) if isinstance(exc,ValueError) else type(exc).__name__
    return result

def collect(rows,cache_file,now,fetch=fetch_html):
    cache_file.parent.mkdir(parents=True,exist_ok=True)
    cached=json.loads(cache_file.read_text(encoding='utf-8')) if cache_file.exists() else {}
    pending=[]
    for row in rows:
        old=cached.get(row['url'])
        ttl=timedelta(hours=6) if old and old.get('confirmed') else timedelta(minutes=15)
        if not old or old.get('version')!=2 or now-datetime.fromisoformat(old['checked_at'])>=ttl:pending.append(row)
    # Worker timeout remains bounded; all unvisited URLs explicitly remain unconfirmed.
    with ThreadPoolExecutor(max_workers=6) as pool:
        for row,result in zip(pending[:300],pool.map(lambda r:read(r,now.isoformat(),fetch),pending[:300])):cached[row['url']]=result
    cache_file.write_text(json.dumps(cached,ensure_ascii=False),encoding='utf-8')
    result={r['id']:cached.get(r['url'],{'confirmed':False,'label':PENDING,'basis':PENDING}) for r in rows}
    return result,{'attempted':min(300,len(pending)),'confirmed':sum(bool(v.get('confirmed')) for v in result.values()),'unconfirmed':sum(not v.get('confirmed') for v in result.values()),'scope':'언론사 공개 본문 추출. 접근 차단·유료·추출 실패는 판단 보류. 본문 전문은 게시하지 않음.'}
