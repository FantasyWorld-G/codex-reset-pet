"""Offline JSON-lines fixture; never contacts an account or network service."""
import json
import sys
import time

mode = sys.argv[1]
for line in sys.stdin:
    request = json.loads(line)
    if 'id' not in request:
        continue
    method = request['method']
    result = {}
    if method == 'account/read':
        result = {'account': None if mode == 'signed_out' else {'type':'chatgpt'}}
        if mode=='auto':result={'account':{'type':'chatgpt','email':'test@example.invalid','planType':'pro'}}
    if method == 'account/rateLimits/read':
        if mode == 'disconnect':
            sys.exit(0)
        if mode == 'invalid_encoding':
            sys.stdout.buffer.write(b'\xff\n')
            sys.stdout.buffer.flush()
            sys.exit(0)
        if mode == 'timeout':
            time.sleep(60)
        if mode == 'offline':
            print(json.dumps({'id':request['id'],'error':{'code':-32000,'message':'simulated offline'}}),flush=True)
            continue
        if mode == 'noisy':
            print('not-json',flush=True)
            print('[]',flush=True)
            print(json.dumps({'method':'account/rateLimits/updated','params':{}}),flush=True)
        result = {'rateLimits':{'primary':{'usedPercent':None if mode=='bad_quota' else 40,
                                           'resetsAt':time.time()+7200}},
                  'rateLimitResetCredits':{'availableCount':1}}
        if mode=='auto':result['rateLimitResetCredits']['credits']=[{
            'id':'soon','status':'available','resetType':'codexRateLimits','expiresAt':1792700100}]
    if mode=='auto' and method=='account/rateLimitResetCredit/consume':
        from pathlib import Path
        Path(sys.argv[2]).write_text(json.dumps(request['params']),'utf-8')
        result={'outcome':'reset'}
    print(json.dumps({'id':request['id'],'result':result}),flush=True)
