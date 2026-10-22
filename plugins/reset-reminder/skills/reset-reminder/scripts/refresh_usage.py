"""Read-only Codex app-server client. No model turns or credential-file access."""
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import queue
import shutil
import subprocess
import tempfile
import threading
import time


class RefreshError(RuntimeError):
    pass


def find_codex():
    candidates = [shutil.which('codex.exe' if os.name == 'nt' else 'codex')]
    if os.name == 'nt' and os.environ.get('LOCALAPPDATA'):
        candidates.append(str(Path(os.environ['LOCALAPPDATA'])/'Programs/OpenAI/Codex/bin/codex.exe'))
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate
    raise RefreshError('请先安装 Codex')


def make_snapshot(account, limits):
    if not isinstance(account,dict) or account.get('type') != 'chatgpt':
        raise RefreshError('请先登录 Codex')
    if not isinstance(limits,dict):
        raise RefreshError('额度响应无效')
    buckets = limits.get('rateLimitsByLimitId')
    if not isinstance(buckets,dict) or not buckets:
        buckets = {'codex':limits.get('rateLimits')}
    used = [w.get('usedPercent') for b in buckets.values() if isinstance(b,dict)
            for w in (b.get('primary'),b.get('secondary')) if isinstance(w,dict)]
    if not any(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in used):
        raise RefreshError('账户未返回可用额度')
    # A separate desktop-only namespace, never an official account ID and never
    # used for reminder deduplication. Do not save the account's email address.
    identity = hashlib.sha256(str(account.get('email') or 'local-chatgpt').encode()).hexdigest()
    usage = {key:limits.get(key) for key in ('rateLimits','rateLimitsByLimitId','rateLimitResetCredits')}
    usage['accountId'] = 'desktop-app-server:'+identity
    return {'captured_at':datetime.now(timezone.utc).isoformat(),
            'source':'codex-app-server','usage':usage}


def fetch_snapshot(cancel=None, timeout=30, executable=None):
    cancel = cancel or threading.Event()
    command = [executable or find_codex(),'app-server','--stdio']
    options = {'creationflags':subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    try:
        process = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,text=True,encoding='utf-8',**options)
    except OSError:
        raise RefreshError('无法启动 Codex') from None
    messages = queue.Queue()
    deadline = time.monotonic()+timeout

    def reader():
        try:
            for line in process.stdout:
                try:
                    message = json.loads(line)
                    if isinstance(message,dict):
                        messages.put(message)
                except ValueError:
                    continue
        except (OSError, UnicodeError):
            # Treat a broken pipe/encoding as a disconnected server. The reader
            # must not leave an unhandled thread exception in pythonw.
            pass
        finally:
            messages.put(None)

    thread = threading.Thread(target=reader,daemon=True)
    thread.start()

    def send(message):
        process.stdin.write(json.dumps(message)+'\n')
        process.stdin.flush()

    def request(request_id,method,params=None):
        payload = {'id':request_id,'method':method}
        if params is not None:
            payload['params'] = params
        send(payload)
        while True:
            if cancel.is_set():
                raise RefreshError('已取消刷新')
            left = deadline-time.monotonic()
            if left <= 0:
                raise RefreshError('请求超时，请稍后重试')
            try:
                message = messages.get(timeout=min(.2,left))
            except queue.Empty:
                continue
            if message is None:
                raise RefreshError('Codex连接已断开')
            if 'method' in message and 'id' in message:
                # No auth-token sharing, approvals, tool calls or model turns.
                send({'id':message['id'],'error':{'code':-32601,'message':'Unsupported client request'}})
                continue
            if message.get('id') != request_id:
                continue
            if 'error' in message:
                raise RefreshError('请检查登录或网络')
            return message.get('result')

    try:
        request(1,'initialize',{'clientInfo':{'name':'codex_reset_pet',
            'title':'Codex Reset Pet','version':'0.4.3'}})
        send({'method':'initialized','params':{}})
        account_response = request(2,'account/read',{'refreshToken':False})
        account = account_response.get('account') if isinstance(account_response,dict) else None
        if not isinstance(account,dict) or account.get('type') != 'chatgpt':
            raise RefreshError('请先登录 Codex')
        return make_snapshot(account,request(3,'account/rateLimits/read'))
    except (OSError,ValueError):
        raise RefreshError('Codex连接异常') from None
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)
        thread.join(timeout=1)
        process.stdin.close()
        process.stdout.close()


def save_snapshot(path, snapshot):
    """Publish an independent desktop cache without rewriting full-sync data."""
    path = Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w',encoding='utf-8',dir=path.parent,
                                         prefix=path.name+'.',suffix='.tmp',delete=False) as out:
            temporary = Path(out.name)
            json.dump(snapshot,out,ensure_ascii=False,indent=2)
        os.replace(temporary,path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
