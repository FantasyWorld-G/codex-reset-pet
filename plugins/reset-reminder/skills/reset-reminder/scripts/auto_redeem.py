"""Opt-in, exact-credit redemption, bounded by a user-selected expiry window."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading
import time
import uuid
from functools import lru_cache

from check_reset import epoch
from refresh_usage import (RefreshError, account_operation, find_codex,
                           make_snapshot, save_snapshot)

TERMINAL={'reset','alreadyRedeemed','noCredit'}


def read_config(path):
    try:
        value=json.loads(Path(path).read_text('utf-8'))
        return value if isinstance(value,dict) else {}
    except (OSError,ValueError):
        return {}


def valid_policy(policy):
    start,stop=policy.get('start_before'),policy.get('stop_before')
    return (policy.get('enabled') is True and isinstance(policy.get('account_id'),str)
            and bool(policy['account_id']) and type(start) is int and type(stop) is int
            and 0<=stop<start<=3600)


def candidates():
    paths=[]
    # Prefer the desktop's recent bundled versions, without modifying PATH.
    local=os.environ.get('LOCALAPPDATA')
    if local:
        root=Path(local)/'OpenAI/Codex/bin'
        if root.exists():
            paths.extend(sorted(root.glob('*/codex.exe'),key=lambda p:p.stat().st_mtime,reverse=True))
    try:paths.append(Path(find_codex()))
    except RefreshError:pass
    return list(dict.fromkeys(str(p) for p in paths))


@lru_cache(maxsize=16)
def supports_exact_credit(path,modified,size):
    options={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    try:
        with tempfile.TemporaryDirectory(prefix='codex-pet-schema-') as folder:
            subprocess.run([path,'app-server','generate-json-schema','--out',folder],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=20,check=True,**options)
            schema=json.loads((Path(folder)/'v2/ConsumeAccountRateLimitResetCreditParams.json').read_text('utf-8'))
            return 'creditId' in schema.get('properties',{})
    except (OSError,ValueError,subprocess.SubprocessError):
        return False


def exact_credit_client():
    for path in candidates():
        stat=Path(path).stat()
        if supports_exact_credit(path,stat.st_mtime_ns,stat.st_size):return path
    raise RefreshError('Codex 版本不支持指定卡片，自动使用已暂停')


def card_rows(limits):
    raw=limits.get('rateLimitResetCredits') if isinstance(limits,dict) else None
    rows=raw.get('credits') if isinstance(raw,dict) else None
    if not isinstance(rows,list):
        raise RefreshError('缺少实时卡片明细，未使用任何卡')
    return [c for c in rows if isinstance(c,dict)]


def available(card):
    return (card.get('status')=='available' and card.get('resetType')=='codexRateLimits'
            and isinstance(card.get('id'),str) and bool(card['id'].strip())
            and epoch(card.get('expiresAt')) is not None)


def in_window(card,now,policy):
    if not available(card):return False
    left=epoch(card['expiresAt'])-now
    # stop_before is an exclusive boundary: no sends after the configured stop.
    return policy['stop_before']<left<=policy['start_before']


class CreditLock:
    """Nonblocking process lock; the OS releases it after a crash."""
    def __init__(self,path):self.path=path
    def __enter__(self):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        self.file=open(self.path,'a+b')
        try:
            if self.path.stat().st_size==0:self.file.write(b'0');self.file.flush()
            self.file.seek(0)
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(self.file,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:
            self.file.close()
            raise RefreshError('另一轮自动使用正在进行') from None
        return self
    def __exit__(self,*args):self.file.close()


def run_cycle(config_path,state_path,usage_path,cancel=None,*,client=None,clock=time.time,
              execute=account_operation):
    """One fresh check. Never derive permission or eligibility from cached usage."""
    cancel=cancel or threading.Event()
    config_path,state_path,usage_path=map(Path,(config_path,state_path,usage_path))
    policy=read_config(config_path)
    if not valid_policy(policy):return {'message':'自动使用：关闭','delay':60}
    with CreditLock(state_path.with_suffix('.lock')):
        if state_path.exists():
            try:
                state=json.loads(state_path.read_text('utf-8'))
                if not isinstance(state,dict) or not isinstance(state.get('attempts'),dict):raise ValueError()
            except (ValueError,OSError):
                raise RefreshError('自动使用记录损坏，已暂停；请保留记录检查') from None
        else:state={'attempts':{}}
        executable=client or exact_credit_client()

        def operation(account,limits,request):
            if not account.get('email'):raise RefreshError('无法核对当前账户，已暂停自动使用')
            snapshot=make_snapshot(account,limits)
            identity=snapshot['usage']['accountId']
            if identity!=policy['account_id']:raise RefreshError('账户已切换，自动使用已暂停')
            rows=card_rows(limits)
            save_snapshot(usage_path,snapshot)
            now=clock()
            pending=[e for e in state['attempts'].values() if e.get('outcome')=='pending']
            if pending:
                pending_ids={e['credit_id'] for e in pending}
                rows=[c for c in rows if c.get('id') in pending_ids]
                if not any(in_window(c,now,policy) for c in rows):
                    return {'message':'自动使用：上次兑换结果待核实','delay':60,'snapshot':snapshot}
            choices=sorted((c for c in rows if in_window(c,now,policy)),key=lambda c:epoch(c['expiresAt']))
            selected=None
            for card in choices:
                key=str(uuid.uuid5(uuid.NAMESPACE_URL,'codex-reset-pet:'+identity+':'+card['id']))
                entry=state['attempts'].get(key,{})
                if entry.get('outcome') not in TERMINAL:
                    selected=(card,key);break
            if selected is None:
                future=[epoch(c['expiresAt'])-policy['start_before']-now for c in rows
                        if available(c) and epoch(c['expiresAt'])-now>policy['start_before']]
                next_in=min(future,default=300)
                return {'message':'自动使用：等待临期窗口','delay':max(1,min(300,next_in)),
                        'snapshot':snapshot}
            card,key=selected
            # Persist intent before any irreversible RPC; retry this same key forever.
            previous=state['attempts'].get(key,{})
            initial_outcome='pending' if previous.get('outcome')=='pending' else 'prepared'
            state['attempts'][key]={'credit_id':card['id'],'expires_at':epoch(card['expiresAt']),
                'idempotency_key':key,'outcome':initial_outcome,'checked_at':clock(),
                'attempt_count':previous.get('attempt_count',0)+1}
            save_snapshot(state_path,state)
            # Revalidate both permission and current server state immediately before sending.
            current=request(4,'account/read',{'refreshToken':False})
            current_account=current.get('account') if isinstance(current,dict) else None
            if not isinstance(current_account,dict) or make_snapshot(current_account,limits)['usage']['accountId']!=identity:
                raise RefreshError('账户已切换，自动使用已暂停')
            fresh=request(5,'account/rateLimits/read')
            matching=[c for c in card_rows(fresh) if c.get('id')==card['id']]
            if (len(matching)!=1 or not in_window(matching[0],clock(),policy)
                    or epoch(matching[0]['expiresAt'])!=epoch(card['expiresAt'])
                    or cancel.is_set() or read_config(config_path)!=policy):
                return {'message':'自动使用：状态变化，本轮跳过','delay':30}
            state['attempts'][key]['outcome']='pending'
            save_snapshot(state_path,state)
            if cancel.is_set() or not in_window(matching[0],clock(),policy) or read_config(config_path)!=policy:
                state['attempts'][key]['outcome']=initial_outcome
                save_snapshot(state_path,state)
                return {'message':'自动使用：已取消或超出窗口','delay':30}
            response=request(6,'account/rateLimitResetCredit/consume',
                             {'creditId':card['id'],'idempotencyKey':key})
            outcome=response.get('outcome') if isinstance(response,dict) else None
            if outcome not in {'reset','alreadyRedeemed','nothingToReset','noCredit'}:
                raise RefreshError('兑换结果未知，保留同一记录等待核实')
            state['attempts'][key].update(outcome=outcome,finished_at=clock())
            save_snapshot(state_path,state)
            message={'reset':'自动使用：临期卡已使用','alreadyRedeemed':'自动使用：已核实此前兑换成功',
                     'nothingToReset':'自动使用：当前无需重置，窗口内重试',
                     'noCredit':'自动使用：卡片已不可用'}[outcome]
            try:
                after=make_snapshot(account,request(7,'account/rateLimits/read'))
                save_snapshot(usage_path,after)
            except (RefreshError,OSError,ValueError):
                after=None
                message+=' · 额度待刷新'
            return {'message':message,'delay':30,'snapshot':after,'outcome':outcome}

        return execute(operation,cancel=cancel,timeout=30,executable=executable)
