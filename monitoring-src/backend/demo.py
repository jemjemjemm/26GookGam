import json
import hashlib
from datetime import datetime, timedelta, timezone
from .store import ROOT

KST = timezone(timedelta(hours=9))
DEMO_AT = '2026-10-07T21:30:00+09:00'

def seed(db):
    if db.execute('SELECT COUNT(*) FROM documents').fetchone()[0]:
        return
    channels = [('media','데모 언론'),('portal','데모 포털 댓글'),('community','데모 커뮤니티'),('sns','데모 SNS'),('broadcast','데모 방송')]
    for channel, name in channels:
        db.execute('INSERT OR IGNORE INTO sources(id,channel,name,access_mode,expected_minutes,last_success,status,rights_note) VALUES(?,?,?,?,?,?,?,?)', (channel,channel,name,'synthetic',5,DEMO_AT,'demo','실제 데이터 아님'))
    at = datetime.fromisoformat(DEMO_AT)
    for hour in range(11):
        start = at - timedelta(hours=10-hour, minutes=59)
        for i in range(28 + hour*2):
            frame = ['F01','F02','F05','F14'][(i//2) % 4] if hour < 7 else ['F03','F06','F07','F02'][(i//2) % 4]
            labels = {'F01':'정유업계 담합 의혹 보도','F02':'SK·현대 관련 심사절차 보도','F05':'자진신고 제도 소개','F14':'최종 판단 전, 절차 설명','F03':'SK 책임론을 제기하는 의견','F06':'SK·현대 리니언시 면죄부 논란','F07':'소비자 부담에 대한 주장'}
            title = '[가상] ' + labels[frame]
            body = title + f'. 합성 스토리 키 {hour}-{i//2}. 이 문장은 화면 검증용 합성 자료이며 실제 기사나 공식 발표가 아닙니다.'
            targets = ['SK','HYUNDAI'] if frame in ['F02','F03','F06'] else []
            flags = {k: {'body':1,'central':1,'headline':1,'first':int(frame=='F03'),'negative_link':int(frame in ['F03','F06']),'leniency_link':int(frame=='F06'),'consumer_link':0,'moral_link':int(frame=='F06')} for k in targets}
            add(db,f'm{hour}-{i}','media',title,body,(start+timedelta(minutes=i%59)).isoformat(),frame,targets,flags,'negative' if frame in ['F03','F06','F07'] else 'neutral',cluster=f'story-{hour}-{i//2}')
        for i in range(45):
            channel = ['portal','community','sns'][i%3]
            frame = ['F07','F06','F09','F10'][i%4]
            text = '[가상 댓글] ' + {'F07':'소비자 부담이 걱정된다','F06':'자진신고 제도에 대한 불만','F09':'제재 수준이 궁금하다','F10':'감독 책임을 묻고 싶다'}[frame]
            add(db,f'p{hour}-{i}',channel,text,text,(start+timedelta(minutes=i)).isoformat(),frame,['SK'] if i%4==0 else [],{},'negative' if i%5 else 'neutral',scope='comment',argument=frame)
        if hour >= 7:
            title='[가상 방송] 소비자 부담 논란 소개'
            add(db,f'b{hour}','broadcast',title,title+' / 앵커 멘트 합성 전사',(start+timedelta(minutes=20)).isoformat(),'F07',[],{},'negative',scope='transcript')
            db.execute('INSERT INTO amplifications VALUES(?,?,?,?,?,?,?,?)',(f'amp{hour}',f'b{hour}','broadcast_top',(start+timedelta(minutes=20)).isoformat(),None,'demo://broadcast',1,'point_observation'))
    db.execute('INSERT INTO amplifications VALUES(?,?,?,?,?,?,?,?)',('portal-amp','m10-0','portal_main',(at-timedelta(minutes=40)).isoformat(),None,'demo://portal',1,'point_observation'))
    db.commit()

def add(db, id, source, title, body, timestamp, frame, targets, flags, tone, cluster=None, scope='full', argument=''):
    db.execute('INSERT INTO documents(id,source_id,external_id,url,title,body,published_at,collected_at,content_scope,content_hash,cluster_id,is_demo,sample_method) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,source,id,'',title,body,timestamp,timestamp,scope,hashlib.sha256(body.encode()).hexdigest(),cluster or id,1,'synthetic'))
    db.execute('INSERT INTO analyses VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(id,'approved',frame,'[]',json.dumps({frame:0.9}),json.dumps(targets),tone,'anger' if tone=='negative' else 'neutral',argument,json.dumps([{'quote':title,'field':'body'}]),json.dumps(flags),'unverifiable',0.9,'demo-fixture','1.0.0',0,'demo-fixture',timestamp))

