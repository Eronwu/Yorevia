"""Read-only Baidu source. Developer access tokens live only in this process.

No shared app secret, OAuth broker, refresh token or account persistence here.
"""
from __future__ import annotations
import json
import os
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath
from .media import media_kind

MAX_FILE = 1024**3
MAX_BATCH = 2 * MAX_FILE


def safe_url(url):
    p = urllib.parse.urlsplit(url)
    host = p.hostname or ''
    if (p.scheme != 'https' or p.username or p.password or p.port not in (None, 443)
            or not any(host == d or host.endswith('.' + d) for d in ('baidu.com', 'baidupcs.com'))):
        raise ValueError('百度网盘返回了不受信任的下载地址。')
    return url


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class BaiduSource:
    def __init__(self, token):
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9._~-]{10,4096}', token):
            raise ValueError('请输入有效的百度网盘 Access Token，不是 AppKey 或 SecretKey。')
        self._token = token
        self._opener = urllib.request.build_opener(SafeRedirect())
        self._listed = {}

    def _open(self, url):
        try:
            return self._opener.open(urllib.request.Request(safe_url(url), headers={'User-Agent':'pan.baidu.com'}), timeout=25)
        except Exception:
            # urllib errors contain request URLs, which can contain tokens.
            raise ValueError('百度网盘请求失败。请检查网络、授权有效期及应用权限。') from None

    def _api(self, endpoint, **params):
        url = 'https://pan.baidu.com/rest/2.0/' + endpoint + '?' + urllib.parse.urlencode(dict(params, access_token=self._token))
        try:
            with self._open(url) as response:
                raw = response.read(4 * 1024 * 1024 + 1)
            if len(raw) > 4 * 1024 * 1024:
                raise ValueError()
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError()
        except Exception:
            raise ValueError('无法读取百度网盘响应。请检查网络与授权。') from None
        code = data.get('errno', data.get('error_code', 0))
        if code:
            # Do not echo upstream messages or URLs.
            raise ValueError('百度网盘拒绝请求（错误码 %s）。请检查授权、应用权限或稍后重试。' % (code if isinstance(code, int) else '未知'))
        return data

    def list(self, directory='/', page=0):
        if not isinstance(directory, str) or not directory.startswith('/') or '..' in PurePosixPath(directory).parts or '\\' in directory:
            raise ValueError('网盘目录格式无效。')
        if not isinstance(page, int) or not 0 <= page <= 10000:
            raise ValueError('页码无效。')
        data = self._api('xpan/file', method='list', dir=directory, start=page*100, limit=100, order='name')
        items = []
        for raw in data.get('list', []):
            try:
                item = dict(id=str(int(raw['fs_id'])), name=str(raw['server_filename']),
                            path=str(raw['path']), directory=bool(raw['isdir']), size=int(raw['size']))
                item['supported'] = not item['directory'] and bool(media_kind(Path(item['name'])))
            except (ValueError, TypeError, KeyError):
                continue
            items.append(item)
        # Bound session memory. A selection must be from the currently viewed page.
        self._listed = {i['id']: i for i in items}
        return dict(items=items, directory=directory, page=page, has_more=len(items)==100)

    def selection(self, ids):
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or len(set(ids)) != len(ids):
            raise ValueError('请在当前页面选择 1–100 个文件。')
        items = []
        for ident in ids:
            item = self._listed.get(ident)
            if not item or not item['supported'] or not 0 <= item['size'] <= MAX_FILE:
                raise ValueError('选择已失效、格式不支持或单文件超过 1 GiB，请重新选择。')
            items.append(dict(item))
        if sum(i['size'] for i in items) > MAX_BATCH:
            raise ValueError('单次导入不能超过 2 GiB。')
        return items

    def download(self, items, destination, progress, cancelled):
        """Destination is a newly created, dedicated job folder, never cloud originals."""
        if shutil.disk_usage(destination).free < sum(i['size'] for i in items) + 64*1024**2:
            raise ValueError('本地剩余空间不足。')
        downloaded = 0
        for item in items:
            if cancelled():
                return dict(cancelled=True, downloaded=downloaded)
            progress(downloaded, len(items), '从百度网盘下载：' + item['name'])
            meta = self._api('xpan/multimedia', method='filemetas', fsids=json.dumps([int(item['id'])]), dlink=1)
            rows = meta.get('list', [])
            if len(rows) != 1 or str(rows[0].get('fs_id')) != item['id'] or rows[0].get('isdir') or int(rows[0].get('size', -1)) != item['size']:
                raise ValueError('网盘文件已变化，请刷新目录后重试。')
            link = safe_url(rows[0].get('dlink', ''))
            # Only the approved provider receives the token, including redirected downloads.
            link += ('&' if '?' in link else '?') + urllib.parse.urlencode({'access_token': self._token})
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', item['name']).strip(' .')[:160]
            if not name or not media_kind(Path(name)):
                raise ValueError('文件名不支持安全导入。')
            target = destination / (item['id'] + '_' + name)
            partial = target.with_name('.' + target.name + '.part')
            try:
                count = 0
                with self._open(link) as response, partial.open('xb') as output:
                    while True:
                        if cancelled():
                            return dict(cancelled=True, downloaded=downloaded)
                        chunk = response.read(1024*1024)
                        if not chunk: break
                        count += len(chunk)
                        if count > item['size'] or count > MAX_FILE:
                            raise ValueError('下载大小与网盘记录不一致。')
                        output.write(chunk)
                if count != item['size']:
                    raise ValueError('下载未完成，请重试。')
                os.replace(partial, target)
                downloaded += 1
            except ValueError:
                raise
            except Exception:
                raise ValueError('下载中断。已完成文件保留，未完成文件已清理。') from None
            finally:
                partial.unlink(missing_ok=True)
        return dict(cancelled=False, downloaded=downloaded)
