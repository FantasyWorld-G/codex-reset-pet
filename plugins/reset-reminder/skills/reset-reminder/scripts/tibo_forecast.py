"""Public website estimates, kept separate from official account usage."""
from datetime import datetime, timezone
import math
from urllib.request import Request, urlopen
import json
import re

from check_reset import CN, epoch as parse_epoch

FORECAST_URL = 'https://codex-reset.com/api/forecast?tz=Asia%2FShanghai'
MAX_AGE = 3600
TIMELINE_URL = 'https://codex-reset.com/api/timeline?locale=zh'
REASON_TAGS = {'incident':'事故相关','compensation':'用量补偿','milestone':'里程碑',
               'launch':'产品发布','promo':'活动赠送','unlock':'额度提升'}


def public_json(url):
    request = Request(url,headers={'User-Agent':'CodexResetPet/0.4.6','Accept':'application/json'})
    with urlopen(request,timeout=10) as response:
        raw = response.read(1_000_001)
    if len(raw)>1_000_000:
        raise ValueError('网站响应过大')
    return json.loads(raw)


def source_url(value):
    # Only open ordinary source-post URLs, never execute website-provided schemes.
    return value if isinstance(value,str) and re.fullmatch(
        r'https://(?:x\.com|twitter\.com)/[A-Za-z0-9_]+/status/[0-9]+',value) else ''


def announcement_text(event):
    for key in ('localized_summary','summary','text'):
        value=event.get(key)
        if isinstance(value,str):
            value=' '.join(value.split())
            if value:return value[:4000]
    return ''


def latest_reset(events, now):
    candidates=[]
    for event in events:
        if (not isinstance(event,dict) or event.get('type')!='reset'
                or event.get('banked_grant') or event.get('preview')):
            continue
        observed=event.get('observation_result')=='reset_observed'
        if not observed and event.get('confirmed') is not True:
            continue
        at=next((value for key in ('effective_at','observed_at','announced_at')
                 if (value:=epoch(event.get(key))) is not None),None)
        if at is not None and at<=now:
            clean={key:event.get(key) for key in ('id','url','source','confirmed','reason_tags',
                   'observation_result','reset_verification_status')}
            clean['at']=at
            clean['announcement']=announcement_text(event)
            candidates.append(clean)
    return max(candidates,key=lambda e:e['at'],default=None)


def epoch(value):
    """Reject timestamps that cannot be rendered on the current platform."""
    try:
        result = parse_epoch(value)
        if result is not None:
            datetime.fromtimestamp(result,CN)
        return result
    except (ValueError,TypeError,OverflowError,OSError):
        return None


def fetch_forecast(cancel=None):
    if cancel is not None and cancel.is_set():
        raise ValueError('已取消')
    data = public_json(FORECAST_URL)
    if not isinstance(data,dict) or epoch(data.get('updated_at')) is None:
        raise ValueError('网站预估格式无效')
    if cancel is not None and cancel.is_set():
        raise ValueError('已取消')
    now = datetime.now(timezone.utc).timestamp()
    updated = epoch(data['updated_at'])
    if not -60 <= now-updated <= MAX_AGE:
        raise ValueError('网站返回过期预估')
    # No account identifiers, credentials, browser state or free-form instructions.
    selected = {key:data.get(key) for key in ('updated_at','mode','official_signal',
                'last_reset_at','latest_alert','probabilities')}
    result={'captured_at':datetime.now(timezone.utc).isoformat(),'forecast':selected}
    try:
        timeline=public_json(TIMELINE_URL)
        updated=epoch(timeline.get('updated_at')) if isinstance(timeline,dict) else None
        if (updated is None or not -60<=now-updated<=MAX_AGE
                or not isinstance(timeline.get('events'),list)):
            raise ValueError('网站历史格式无效或已过期')
        result['last_reset']=latest_reset(timeline['events'],now)
        result['history_updated_at']=updated
    except (OSError,ValueError,TypeError):
        # A history outage must not discard a successfully refreshed forecast.
        result['history_error']=True
    if cancel is not None and cancel.is_set():
        raise ValueError('已取消')
    return result


def clock_label(value):
    return datetime.fromtimestamp(value,CN).strftime('%m/%d %H:%M')


def history_view(snapshot, now, failed=False):
    view={'last_title':'上次 Tibo 重置','last_date':'等待网站记录',
          'last_reason':'网站暂无原因或公告说明','last_category':'网站分类：暂无',
          'last_status':'网站记录不代表本账户已到账','last_url':'','last_announcement':''}
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('forecast'),dict):
        return view
    data=snapshot['forecast']
    captured,updated=epoch(snapshot.get('captured_at')),epoch(data.get('updated_at'))
    if captured is None or updated is None or captured>now+60 or updated>now+60:
        return view
    at=epoch(data.get('last_reset_at'))
    event=snapshot.get('last_reset')
    event=event if isinstance(event,dict) else {}
    event_at=epoch(event.get('at'))
    if event_at is not None and event_at<=now and (at is None or event_at>=at):
        at=event_at
    elif event_at!=at:
        event={}  # Never attach a previous reset's reason to a newer reset.
    if at is None or at>now:return view
    view['last_date']=clock_label(at)
    view['last_url']=source_url(event.get('url'))
    tags=event.get('reason_tags')
    labels=[REASON_TAGS[t] for t in tags if isinstance(t,str) and t in REASON_TAGS] if isinstance(tags,list) else []
    if labels:
        labels=list(dict.fromkeys(labels))
        view['last_category']='网站分类：'+' / '.join(labels[:2])+(' 等' if len(labels)>2 else '')
    announcement=event.get('announcement')
    if isinstance(announcement,str) and announcement.strip():
        view['last_announcement']=' '.join(announcement.split())[:4000]
        view['last_reason']='网站说明：'+view['last_announcement']
    alert=data.get('latest_alert')
    if not event and isinstance(alert,dict) and alert.get('kind')=='reset':
        alert_at=epoch(alert.get('observed_at')) or epoch(alert.get('source_at'))
        if alert_at==at:
            view['last_url']=source_url(alert.get('confirmation_url')) or source_url(alert.get('url'))
            event={'source':alert.get('confirmation_source'),
                   'confirmed':alert.get('state')=='confirmed'}
    observed=event.get('source') in ('operator-observed','operator_observed')
    view['last_status']=('网站观测 · 待 Tibo 确认' if observed else
                         '社区已确认 · 非本账户到账确认' if event.get('confirmed') is True else
                         '网站历史记录 · 等待核实')
    captured=epoch(snapshot.get('captured_at'))
    updated=epoch(snapshot.get('history_updated_at')) or epoch(data.get('updated_at'))
    if failed or (captured is not None and updated is not None and now-min(captured,updated)>MAX_AGE):
        view['last_title']+=' · 缓存'
        view['last_status']='缓存待更新 · '+view['last_status']
    elif snapshot.get('history_error'):
        view['last_reason']='原因：待获取'
        view['last_category']='历史获取失败 · 可点击更新预估重试'
    return view


def forecast_view(snapshot, now, failed=False):
    view = {'title':'Tibo 预计重置','date':'等待网站预估','remaining':'尚未读取公开预告',
            'detail':'社区预估 · 不代表本账户已重置','status':'来源 codex-reset.com',
            'seconds':None,'deadline':None,'state':'unavailable'}
    view.update(history_view(snapshot,now,failed))
    if not isinstance(snapshot,dict) or not isinstance(snapshot.get('forecast'),dict):
        if failed:view['remaining']='获取失败 · 可点击更新预估'
        return view
    data=snapshot['forecast']
    captured,updated=epoch(snapshot.get('captured_at')),epoch(data.get('updated_at'))
    if captured is None or updated is None or captured>now+60 or updated>now+60:
        return view
    stale=now-min(captured,updated)>MAX_AGE
    if stale or failed:view['title']+=' · 缓存'
    view['status']=('获取失败 · ' if failed else '数据过期 · ' if stale else '')+'网站更新 '+clock_label(updated)
    view.update(date='暂无明确预告',remaining='等待网站公布目标时间',state='none')
    probabilities=data.get('probabilities')
    if isinstance(probabilities,dict):
        a,b=probabilities.get('model_24h'),probabilities.get('model_48h')
        valid=lambda p:isinstance(p,(int,float)) and not isinstance(p,bool) and math.isfinite(p) and 0<=p<=100
        if valid(a) and valid(b):view['detail']=f'网站模型概率 24h {a:g}% · 48h {b:g}%'
    signal=data.get('official_signal')
    reset=epoch(data.get('last_reset_at'))
    if isinstance(signal,dict):
        announced=epoch(signal.get('at'))
        window=signal.get('window')
        # Match the site's structured dated-commitment path. Never parse a
        # relative "tomorrow/PST" quote or derive dates from model probabilities.
        if (signal.get('signal_type')=='dated_commitment' and isinstance(window,dict)
                and announced is not None and announced<=now
                and not (reset is not None and reset>=announced)):
            start,end,target=(epoch(window.get(key)) for key in ('start_at','end_at','target_at'))
            kind=window.get('target_kind')
            if (None not in (start,end,target) and start<end and start<=target<=end
                    and kind in ('center','deadline') and (kind!='deadline' or target==end)):
                # The website rounds deadlines up to a minute for display.
                display_at=math.ceil(target/60)*60 if kind=='deadline' else target
                view.update(date=clock_label(display_at)+(' 前' if kind=='deadline' else ' 左右'),
                            deadline=target,seconds=target-now,state='scheduled',
                            detail='网站公告目标 · 预估，非账户到账')
                if now>=end:
                    view.update(remaining='预告窗口已过 · 等待确认',state='expired')
                elif now>=target:
                    view.update(remaining='已到预估目标 · 等待确认',state='reached')
                else:
                    minutes=math.ceil((target-now)/60)
                    days,minutes=divmod(minutes,1440)
                    hours,minutes=divmod(minutes,60)
                    view['remaining']='预估还剩 '+(f'{days}天 ' if days else '')+f'{hours}小时 {minutes}分钟'
                return view
    alert=data.get('latest_alert')
    if isinstance(alert,dict) and alert.get('kind')=='reset' and alert.get('state')=='confirmed':
        observed=epoch(alert.get('observed_at')) or epoch(alert.get('source_at'))
        if observed is not None and observed<=now:
            view.update(remaining='网站记录重置 '+clock_label(observed),state='observed',
                        detail='网站观测/确认 · 本账户以额度刷新为准')
    return view
