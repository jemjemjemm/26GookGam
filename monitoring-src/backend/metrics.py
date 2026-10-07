import json
from datetime import datetime, timedelta

FRAME_LABELS = {}

def records(db):
    rows = db.execute('''SELECT d.*, s.channel, s.name as source_name, a.status, a.primary_frame, a.secondary_json,
        a.frames_json, a.targets_json, a.tone, a.emotion, a.argument, a.evidence_json, a.exposure_json,
        a.fact_gap, a.confidence, a.model, a.prompt_version, a.fact_version, a.reviewed_by, a.created_at as analyzed_at
        FROM documents d JOIN sources s ON s.id=d.source_id LEFT JOIN analyses a ON a.document_id=d.id
        ORDER BY d.published_at DESC''').fetchall()
    result=[]
    for row in rows:
        item=dict(row)
        for key in ['secondary','frames','targets','evidence','exposure']:
            raw=item.pop(key+'_json',None)
            item[key]=json.loads(raw) if raw else ({} if key in ['frames','exposure'] else [])
        result.append(item)
    return result

def exposure(flags):
    weights={'body':1,'central':2,'headline':3,'first':2,'negative_link':2,'leniency_link':2,'consumer_link':2,'moral_link':2}
    return 100 * sum(weights[k] * flags.get(k,0) for k in weights)/16

def unique(rows):
    seen={}
    for row in sorted(rows,key=lambda x:(x['published_at'],x['id'])):
        seen.setdefault(row['cluster_id'],row)
    return list(seen.values())

def eligible(rows):
    return [r for r in rows if r['status']=='approved' and r['confidence']>=0.7 and r['content_scope'] in ['full','transcript','comment']]

def frame_stats(rows):
    if not rows:
        return {}
    counts={}
    for r in rows:
        counts[r['primary_frame']]=counts.get(r['primary_frame'],0)+1
    return {k:round(v/len(rows),4) for k,v in counts.items()}

def shift(now,before):
    if len(now)<20 or len(before)<20:
        return {'score':None,'delta_pp':None,'reason':'현재·직전 동일 길이 창 각각 독립 기사 20개 이상 필요'}
    p,q=frame_stats(now),frame_stats(before)
    score=50*sum(abs(p.get(k,0)-q.get(k,0)) for k in p.keys()|q.keys())
    risk={'F03','F06','F07'}
    delta=100*sum(p.get(k,0)-q.get(k,0) for k in risk)
    return {'score':round(score,1),'delta_pp':round(delta,1),'reason':'동일 채널·동일 길이 창의 primary 분포'}

def snapshot(db,at,hours=1,channel='all',query=''):
    cutoff=datetime.fromisoformat(at)
    if cutoff.tzinfo is None:
        raise ValueError('시간대 오프셋이 필요합니다')
    start=cutoff-timedelta(hours=hours)
    prior=start-timedelta(hours=hours)
    all_rows=[r for r in records(db) if datetime.fromisoformat(r['collected_at'])<=cutoff]
    for r in all_rows:
        if r['analyzed_at'] and datetime.fromisoformat(r['analyzed_at'])>cutoff:
            r['status']='pending'
    def match(r):
        return (channel=='all' or r['channel']==channel) and (not query or query.casefold() in (r['title']+' '+r['body']).casefold())
    selected=[r for r in all_rows if match(r) and start<datetime.fromisoformat(r['published_at'])<=cutoff]
    prev=[r for r in all_rows if match(r) and prior<datetime.fromisoformat(r['published_at'])<=start]
    ok=eligible(selected)
    media=unique([r for r in ok if r['channel']=='media'])
    prev_media=unique([r for r in eligible(prev) if r['channel']=='media'])
    public=[r for r in ok if r['channel'] in ['portal','community','sns']]
    amp=[dict(r) for r in db.execute('SELECT * FROM amplifications WHERE verified=1') if start<datetime.fromisoformat(r['observed_at'])<=cutoff]
    ids={r['id'] for r in selected}
    amp=[a for a in amp if a['document_id'] in ids]
    by_cluster={r['id']:r['cluster_id'] for r in selected}
    multipliers={}
    for a in amp:
        cluster=by_cluster[a['document_id']]
        weight=2 if a['kind']=='broadcast_top' else 1.5 if a['kind']=='portal_main' else 1.2
        multipliers[cluster]=max(weight,multipliers.get(cluster,1))
    companies={}
    for company in ['SK','HYUNDAI','GS','SOIL']:
        denom=sum(multipliers.get(r['cluster_id'],1) for r in media)
        value=sum(exposure(r['exposure'].get(company,{}))*multipliers.get(r['cluster_id'],1) for r in media)/denom if denom else None
        neg=[r for r in media if r['tone']=='negative']
        companies[company]={'score':round(value,1) if value is not None else None,'mentions':sum(company in r['targets'] for r in media),'negative_share':round(sum(company in r['targets'] for r in neg)/len(neg)*100,1) if neg else None}
    # 관측 표본의 부정 비율이며 모집단 여론 추정이 아니다.
    negativity=round(100*sum(r['tone']=='negative' for r in public)/len(public),1) if len(public)>=30 else None
    velocity=min(100,max(0,50*(len(media)/len(prev_media)-1))) if len(prev_media)>=10 else None
    spread=100*len(set(a['kind'] for a in amp))/3
    e=companies['SK']['score']
    risk=round(.35*e+.25*negativity+.2*velocity+.2*spread,1) if len(media)>=20 and e is not None and negativity is not None and velocity is not None else None
    fs=shift(media,prev_media)
    source_rows=[dict(r) for r in db.execute('SELECT * FROM sources')]
    for s in source_rows:
        timestamp=s['last_success']
        s['fresh']=bool(timestamp and s['status'] in ['connected','demo'] and 0<=(cutoff-datetime.fromisoformat(timestamp)).total_seconds()<=max((s['expected_minutes'] or 5)*3*60,900))
    fresh_ratio=sum(s['fresh'] for s in source_rows)/len(source_rows) if source_rows else 0
    risk_reason='기본 표본 기준 충족' if risk is not None else '기사/온라인/비교창 표본 부족'
    if fresh_ratio<0.8:
        risk=None
        risk_reason='연결 소스 신선도 80% 미만'
    verified=[dict(r) for r in db.execute("SELECT * FROM fact_baselines WHERE verification='verified'") if datetime.fromisoformat(r['valid_from'])<=cutoff and datetime.fromisoformat(r['approved_at'])<=cutoff and (not r['valid_to'] or cutoff<datetime.fromisoformat(r['valid_to']))]
    narratives={}
    for r in public:
        k=r['argument'] or r['primary_frame']
        narratives.setdefault(k,[]).append(r)
    narrative=[{'code':k,'count':len(v),'share':round(len(v)/len(public)*100,1),'examples':[{'id':r['id'],'quote':r['title']} for r in v[:3]]} for k,v in sorted(narratives.items(),key=lambda x:len(x[1]),reverse=True)]
    # 추이는 동일 필터를 적용한 연속 1시간 구간별 값이다.
    trend=[]
    for h in range(6,0,-1):
        end=cutoff-timedelta(hours=h-1)
        begin=end-timedelta(hours=1)
        group=unique([r for r in eligible(all_rows) if match(r) and r['channel']=='media' and begin<datetime.fromisoformat(r['published_at'])<=end])
        trend.append({'at':end.isoformat(),'n':len(group),'shares':frame_stats(group)})
    alerts=[]
    if fs['score'] is not None and fs['score']>=20 and fs['delta_pp']>=15:
        alerts.append({'rule':'FRAME_SHIFT','severity':'high','text':'비판 프레임 비중 +15%p 이상, 분포 변화 20 이상','evidence':[r['id'] for r in media[:5]]})
    if risk is not None and risk>=65:
        alerts.append({'rule':'RISK_HIGH','severity':'high','text':'표본 기준 충족, Risk 65 이상','evidence':[r['id'] for r in media[:5]]})
    for a in amp:
        alerts.append({'rule':'AMPLIFICATION_'+a['kind'],'severity':'watch','text':'증빙된 '+a['kind']+' 관측','evidence':[a['document_id']]})
    if not verified:
        alerts.append({'rule':'FACT_UNVERIFIED','severity':'quality','text':'브리핑 원문·공식 사실 승인 대기. Fact Gap 판정 중단','evidence':[]})
    negative_count=sum(r['tone']=='negative' for r in public)
    logic={
        'published':'선택 시간창·채널·검색 조건의 기사 게시물 수. 전재·미승인도 포함.',
        'stories':'담당자 승인·신뢰도 0.7 이상·본문 확보 기사만 집계. 동일 cluster는 1건.',
        'exposure':f'본문 1·중심 대상 2·제목 3·제목 첫 언급 2·부정/리니언시/소비자/도덕성 연결 각 2점 → 합계÷16×100. 독립 기사 {len(media)}건의 노출 가중평균; 미언급은 0. 포털 메인 1.5·방송 주요 2·일반 1.2배, 중복 관측은 최댓값 적용. 표본이 없으면 보류.',
        'negative':f'부정 승인 댓글·게시물 {negative_count}건 ÷ 승인 온라인 표본 {len(public)}건 ×100. 30건 미만이면 보류. 전체 여론 비율이 아님.',
        'velocity':f'증가 지수 = 50×(현재 {len(media)}건÷직전 {len(prev_media)}건−1), 0~100으로 제한. 직전 10건 미만이면 보류.',
        'spread':f'확산 지수 = 증빙된 관측 종류 {len(set(a["kind"] for a in amp))}개÷3×100. 종류: 포털 메인·방송 주요·방송 일반. 관측 없는 종류는 0이며 미수집과 미노출을 구분할 수 없음.',
        'risk':f'위험 = SK 노출({e})×0.35 + 온라인 부정({negativity})×0.25 + 기사 증가({round(velocity,1) if velocity is not None else "보류"})×0.20 + 확산({round(spread,1)})×0.20. 현재 기사≥20·온라인≥30·직전 기사≥10·신선 소스≥80% 필요. 현재 {len(media)}/{len(public)}/{len(prev_media)}건·신선도 {fresh_ratio*100:.0f}%. {risk_reason}. 확정 사건 위험의 예측 확률이 아님.',
        'shift':f'변화 지수 = 50×Σ|현재 프레임 비율−직전 비율|. 비판 변화 = F03·F06·F07 합계 비율 차이×100(%p). 각 {hours}시간 창의 독립 기사 {len(media)}/{len(prev_media)}건, 각각 20건 이상 필요.',
        'frames':'각 60분 창의 대표 프레임 기사 수÷승인 독립 기사 수×100. 한 기사에 대표 프레임 1개. 20건 미만 구간은 숨김.',
        'narratives':f'해당 논리의 승인 표본 수÷온라인 승인 표본 {len(public)}건×100. 빈도 내림차순이며 논리 미지정 시 대표 프레임 사용.',
        'coverage':'성공 상태인 소스의 마지막 수집이 기준 시각 이전이며, 경과 시간이 수집 주기의 3배 또는 15분 중 큰 값 이내면 신선.',
    }
    for a in alerts:
        a['logic']=({'FRAME_SHIFT':'각 비교창 기사≥20, 변화 지수≥20, 비판 프레임 증가≥15%p를 모두 충족.', 'RISK_HIGH':'위험 산출 표본·신선도 조건을 충족하고 지수≥65.', 'FACT_UNVERIFIED':'기준 시각에 유효하고 담당자가 승인한 공식 사실이 0건.'}.get(a['rule'],'선택 시간창의 증빙된 포털·방송 관측 기록 1건 이상. 실제 도달 인원은 산출하지 않음.'))
    logic['exposure_short']=f'제목·본문·비판 연결 등 8항목 점수÷16×100의 가중평균. 기사 {len(media)}건, 미언급 0·표본 없으면 보류. 상세 배점은 아래 회사별 노출에 표시.'
    logic['risk_short']=f'SK 노출×35% + 부정×25% + 기사 증가×20% + 확산×20%. 표본 현재/온라인/직전 {len(media)}/{len(public)}/{len(prev_media)}건(최소 20/30/10), 신선도 {fresh_ratio*100:.0f}%(최소 80%). {risk_reason}. 예측 확률이 아님.'
    return {'logic':logic,'at':at,'window_hours':hours,'mode':'demo' if all_rows and all(r['is_demo'] for r in all_rows) else 'live','metrics':{'published':sum(r['channel']=='media' for r in selected),'stories':len(media),'public_sample':len(public),'negative':negativity,'risk':risk,'risk_reason':risk_reason,'velocity':velocity,'spread':round(spread,1),'coverage':sum(s['fresh'] for s in source_rows),'sources':len(source_rows),'eligible':len(ok),'pending':sum(r['status']!='approved' for r in selected)},'companies':companies,'shift':fs,'frames':frame_stats(media),'narratives':narrative,'trend':trend,'documents':selected,'amplifications':amp,'sources':source_rows,'facts':verified,'alerts':alerts,'limitations':['지표는 수집·승인된 표본 기준이며 전체 여론 추정이 아닙니다.','공식 사실 미검증 시 사건 관련 사실 문장을 생성하지 않습니다.','포털 관측은 개인화·시점 차이가 있으며 실제 도달 인원이 아닙니다.']}


