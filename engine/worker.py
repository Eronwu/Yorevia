#!/usr/bin/env python3
"""One JSON object per line over stdin/stdout. No listening sockets in desktop mode."""
from __future__ import annotations
import json
import sys
from yorevia.service import Service


def main() -> None:
    if hasattr(sys.stdin,'reconfigure'):
        sys.stdin.reconfigure(encoding='utf-8')
        sys.stdout.reconfigure(encoding='utf-8',line_buffering=True)
    service=Service()
    try:
        for line in sys.stdin:
            request={}
            try:
                if len(line)>2_000_000:
                    raise ValueError('请求超过安全大小')
                request=json.loads(line)
                if not isinstance(request,dict) or not isinstance(request.get('params',{}),dict):
                    raise ValueError('请求格式错误')
                result=service.call(request['method'],request.get('params'))
                response={'id':request.get('id'),'result':result}
            except Exception as exc:
                response={'id':request.get('id') if isinstance(request,dict) else None,
                          'error':{'message':str(exc)[:1500],'type':type(exc).__name__}}
            print(json.dumps(response,ensure_ascii=False,separators=(',',':')),flush=True)
    finally:
        service.close()


if __name__=='__main__':
    main()
