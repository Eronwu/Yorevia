#!/usr/bin/env python3
"""Developer-only loopback preview. The packaged desktop app never starts this server."""
from __future__ import annotations
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import mimetypes
from pathlib import Path
import secrets
import sys
import threading
import urllib.parse
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from yorevia.service import Service


def main():
    parser=argparse.ArgumentParser(description='Local Yorevia developer preview (127.0.0.1 only)')
    parser.add_argument('--port',type=int,default=4173)
    parser.add_argument('--no-open',action='store_true')
    parser.add_argument('--vault',type=Path)
    args=parser.parse_args()
    static=(ROOT/'dist').resolve()
    if not (static/'index.html').exists():
        raise SystemExit('Build the frontend first: npm run build')
    service=Service(); guard=threading.Lock(); token=secrets.token_urlsafe(32); nonce=secrets.token_urlsafe(24)
    if args.vault:
        service.call('vault.open',{'path':str(args.vault)})
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):pass
        def allowed_host(self):
            return self.headers.get('Host') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
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
            path=urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
            target=(static/(path.lstrip('/') or 'index.html')).resolve()
            if not target.is_relative_to(static) or not target.is_file():self.send(b'Not found',status=404);return
            data=target.read_bytes()
            if target.name=='index.html':
                data=data.replace(b'</head>',f'<script nonce="{nonce}">window.__YOREVIA_TOKEN__={json.dumps(token)}</script></head>'.encode())
            content=mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
            if target.suffix=='.js':content='text/javascript'
            self.send(data,content+'; charset=utf-8')
        def do_POST(self):
            expected={f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}
            valid=self.allowed_host() and self.path=='/api' and self.headers.get('Origin') in expected
            valid=valid and secrets.compare_digest(self.headers.get('X-Yorevia-Token',''),token)
            if not valid:self.send(b'{"error":{"message":"Forbidden"}}',status=403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=2_000_000:raise ValueError('Invalid request size')
                if not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError('JSON required')
                request=json.loads(self.rfile.read(length))
                with guard:result=service.call(request['method'],request.get('params',{}))
                response={'result':result};status=200
            except Exception as exc:
                response={'error':{'message':str(exc)[:1000]}};status=400
            self.send(json.dumps(response,ensure_ascii=False).encode(),status=status)
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    url=f'http://127.0.0.1:{server.server_port}'
    print('Yorevia developer preview: '+url,flush=True)
    print('No external requests. Close with Ctrl+C. Not a packaged desktop build.',flush=True)
    if not args.no_open:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close();service.close()

if __name__=='__main__':main()
