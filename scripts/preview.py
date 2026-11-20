#!/usr/bin/env python3
"""Loopback frontend for development or an explicitly enabled local Web profile."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import signal
import sys
import threading
import urllib.parse
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from yorevia.service import Service
from local_web_settings import LocalWebSettings, default_profile

LOCAL_PORT = 4173


def main(picker=None):
    parser=argparse.ArgumentParser(description='Local Yorevia Web (127.0.0.1 only)')
    parser.add_argument('--port',type=int,default=LOCAL_PORT)
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--vault',type=Path)
    parser.add_argument('--local-web',action='store_true',help='Enable persistent local Web profile and native folder consent.')
    parser.add_argument('--profile',type=Path,help='Separate local Web profile (default: OS user profile).')
    args=parser.parse_args()
    if (args.local_web and args.vault) or (args.profile and not args.local_web):
        parser.error('--vault is for developer preview; --profile is for local Web only.')
    static=(ROOT/'dist').resolve()
    if not (static/'index.html').exists():
        raise SystemExit('Build the frontend first: npm run build')
    service=Service(); guard=threading.Lock(); token=secrets.token_urlsafe(32); nonce=secrets.token_urlsafe(24)
    local=None
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(10)
            super().setup()
        def log_message(self,*_):pass
        def allowed_host(self):
            hosts = {f'127.0.0.1:{self.server.server_port}'}
            if not local:
                hosts.add(f'localhost:{self.server.server_port}')
            return self.headers.get_all('Host', []) in [[host] for host in hosts]
        def send(self,data:bytes,content_type='application/json; charset=utf-8',status=200):
            self.send_response(status)
            self.send_header('Content-Type',content_type)
            self.send_header('Content-Length',str(len(data)))
            self.send_header('Cache-Control','no-store')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('Cross-Origin-Resource-Policy','same-origin')
            self.send_header('Referrer-Policy','no-referrer')
            self.send_header('Content-Security-Policy',f"default-src 'self'; script-src 'self' 'nonce-{nonce}'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'")
            self.end_headers();self.wfile.write(data)
        def do_GET(self):
            if not self.allowed_host():self.send(b'Forbidden',status=403);return
            if local and self.path == '/health':
                self.send(b'{"service":"yorevia-local-web","protocol":1}');return
            path=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            target=(static/(path.lstrip('/') or 'index.html')).resolve()
            if not target.is_relative_to(static) or not target.is_file():self.send(b'Not found',status=404);return
            data=target.read_bytes()
            if target.name=='index.html':
                web_mode=';window.__YOREVIA_LOCAL_WEB__=true' if local else ''
                data=data.replace(b'</head>',f'<script nonce="{nonce}">window.__YOREVIA_TOKEN__={json.dumps(token)}{web_mode}</script></head>'.encode())
            content=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            if target.suffix=='.js':content='text/javascript'
            self.send(data,content+'; charset=utf-8')
        def do_POST(self):
            expected={f'http://127.0.0.1:{self.server.server_port}'}
            if not local:
                expected.add(f'http://localhost:{self.server.server_port}')
            valid=self.allowed_host() and self.path=='/api' and self.headers.get_all('Origin',[]) in [[origin] for origin in expected]
            headers=self.headers.get_all('X-Yorevia-Token',[])
            valid=valid and len(headers)==1 and secrets.compare_digest(headers[0].encode('utf-8'),token.encode('ascii'))
            if not valid:self.send(b'{"error":{"message":"Forbidden"}}',status=403);return
            try:
                lengths=self.headers.get_all('Content-Length',[])
                if len(lengths)!=1 or self.headers.get('Transfer-Encoding'):
                    raise ValueError('Invalid request framing')
                length=int(lengths[0])
                if not 0<length<=2_000_000:raise ValueError('Invalid request size')
                if self.headers.get_content_type()!='application/json':raise ValueError('JSON required')
                request=json.loads(self.rfile.read(length))
                if not isinstance(request,dict) or not isinstance(request.get('method'),str) or not isinstance(request.get('params',{}),dict):
                    raise ValueError('Invalid RPC request')
                method,params=request['method'],request.get('params',{})
                if local and method=='local.pick':
                    result=local.pick(params.get('purpose'),params.get('locale'))
                else:
                    with guard:
                        result=service.call(method,local.authorized_params(method,params) if local else params)
                        if local and method=='vault.open':
                            local.remember(result['path'])
                            local.startup_error=False
                        if local and method=='status':
                            result['local_web_startup_error']=local.startup_error
                response={'result':result};status=200
            except Exception as exc:
                response={'error':{'message':str(exc)[:1000]}};status=400
            self.send(json.dumps(response,ensure_ascii=False).encode(),status=status)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}'
    try:
        if args.local_web:
            local=LocalWebSettings(args.profile or default_profile(),picker)
            try:
                saved=local.saved_vault()
                if saved is not None:
                    service.call('vault.open',{'path':str(saved)})
            except (OSError, ValueError):
                # An offline/locked vault is not recreated and the user can reselect.
                local.startup_error=True
        elif args.vault:
            service.call('vault.open',{'path':str(args.vault)})
        print(('Yorevia local Web: ' if local else 'Yorevia developer preview: ')+url,flush=True)
        if not args.no_open:webbrowser.open(url)
        def stop(*_):
            raise KeyboardInterrupt
        signal.signal(signal.SIGTERM,stop)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        with guard:
            service.close()

if __name__=='__main__':main()
