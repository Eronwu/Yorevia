"""Optional device authorization client. No application secrets or durable tokens.

The broker origin is operator configuration, not an RPC input. Browser URLs are
provider-allowlisted; session proof and user tokens never cross the UI bridge.
"""
import hashlib
import json
import os
import re
import secrets
import time
import urllib.parse
import urllib.request
import webbrowser


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError('授权服务不允许重定向。')


def broker_origin(value):
    p = urllib.parse.urlsplit(value)
    if (p.scheme != 'https' or not p.hostname or p.username or p.password or
            p.port not in (None, 443) or p.path not in ('', '/') or p.query or p.fragment):
        raise ValueError('授权服务需要固定的 HTTPS 根地址。')
    return value.rstrip('/')


def verification_url(value):
    p = urllib.parse.urlsplit(value)
    if (p.scheme != 'https' or p.hostname != 'openapi.baidu.com' or
            p.port not in (None, 443) or p.username or p.password or
            p.path != '/device' or p.query or p.fragment):
        raise ValueError('授权服务返回的百度登录地址不受信任。')
    return value


class BaiduOAuth:
    def __init__(self):
        self.origin = os.environ.get('YOREVIA_BAIDU_OAUTH_URL', '')
        self.config_error = False
        if self.origin:
            try:
                self.origin = broker_origin(self.origin)
            except ValueError:
                self.origin = ''
                self.config_error = True
        self.session = None
        self.generation = 0
        self.opener = urllib.request.build_opener(NoRedirect())

    def request(self, action, payload):
        try:
            request = urllib.request.Request(self.origin + '/v1/device/' + action,
                data=json.dumps(payload).encode(), headers={'Content-Type': 'application/json'}, method='POST')
            with self.opener.open(request, timeout=20) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError()
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError()
            return result
        except Exception:
            raise ValueError('授权服务暂时不可用，请稍后重新登录。') from None

    def cancel(self, attempt=None):
        session = self.session
        if attempt is None or (session and attempt == session['attempt']):
            self.generation += 1
            self.session = None
            if not session:
                return
            # Expiry is also enforced by the service; cancellation is best effort.
            try:
                self.request('cancel', {'session_id': session['id'], 'proof': session['proof']})
            except ValueError:
                pass

    def start(self, attempt):
        if self.config_error:
            raise ValueError('授权服务配置无效，请联系应用维护者；本地整理仍可使用。')
        if not self.origin:
            raise ValueError('此版本尚未配置授权服务，不能使用百度登录。')
        if not isinstance(attempt, str) or not re.fullmatch(r'[a-zA-Z0-9-]{16,64}', attempt):
            raise ValueError('授权请求无效。')
        self.cancel()
        generation = self.generation
        proof = secrets.token_hex(32)
        data = self.request('start', {'proof_hash': hashlib.sha256(proof.encode()).hexdigest()})
        try:
            url = verification_url(data['verification_url'])
            ident = data['session_id']
            code = data['user_code']
            if not isinstance(ident, str) or not re.fullmatch(r'[a-zA-Z0-9_-]{20,128}', ident):
                raise ValueError()
            if not isinstance(code, str) or not re.fullmatch(r'[a-zA-Z0-9-]{4,32}', code):
                raise ValueError()
            ttl = min(600, max(1, int(data['expires_in'])))
            interval = min(60, max(5, int(data['interval'])))
        except (KeyError, TypeError, ValueError):
            raise ValueError('授权服务响应无效，请联系应用维护者。') from None
        if generation != self.generation:
            raise ValueError('授权请求已取消，请重新登录。')
        self.session = dict(id=ident, proof=proof, attempt=attempt,
                            expires=time.monotonic()+ttl, next_poll=time.monotonic()+interval, interval=interval)
        try:
            opened = bool(webbrowser.open(url, new=2))
        except Exception:
            opened = False
        return dict(user_code=code, verification_url=url, interval=interval, expires_in=ttl, browser_opened=opened)

    def poll(self, attempt):
        s = self.session
        if not s or s['attempt'] != attempt:
            raise ValueError('授权请求已取消，请重新登录。')
        if time.monotonic() >= s['expires']:
            self.cancel(attempt)
            raise ValueError('本次登录已过期，请重新登录。')
        if time.monotonic() < s['next_poll']:
            return None
        s['next_poll'] = time.monotonic() + s['interval']
        data = self.request('poll', {'session_id': s['id'], 'proof': s['proof']})
        if self.session is not s:
            raise ValueError('授权请求已取消，请重新登录。')
        if data.get('status') == 'pending':
            interval = data.get('interval', s['interval'])
            if isinstance(interval, int):
                s['interval'] = min(60, max(5, interval))
                s['next_poll'] = time.monotonic() + s['interval']
            return None
        self.session = None
        if data.get('status') != 'authorized':
            raise ValueError('授权未完成，请重新登录。')
        token = data.get('access_token')
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9._~-]{10,4096}', token):
            raise ValueError('授权服务返回了无效的用户令牌。')
        return token
