"""Read-only Baidu source. Developer access tokens live only in this process.

No shared app secret, OAuth broker, refresh token or account persistence here.
"""
from __future__ import annotations
import base64
from collections import OrderedDict
import hashlib
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
        self._account = None
        self._renditions = OrderedDict()
        self._rendition_size = 0

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

    def list(self, directory='/', page=0, *, internal=False):
        if not isinstance(directory, str) or not directory.startswith('/') or '..' in PurePosixPath(directory).parts or '\\' in directory:
            raise ValueError('网盘目录格式无效。')
        if not isinstance(page, int) or not 0 <= page <= 10000:
            raise ValueError('页码无效。')
        data = self._api('xpan/file', method='list', dir=directory, start=page*100, limit=100, order='name')
        items = []
        raw_items = data.get('list')
        if internal and (not isinstance(raw_items, list) or len(raw_items)>100):
            raise ValueError('网盘目录响应无效。')
        raw_items = raw_items or []
        for raw in raw_items:
            try:
                item = dict(id=str(int(raw['fs_id'])), name=str(raw['server_filename']),
                            path=str(raw['path']), directory=bool(raw['isdir']), size=int(raw['size']))
                item['mtime'] = int(raw.get('server_mtime') or 0)
                if internal and (int(item['id']) <= 0 or item['size'] < 0):
                    raise ValueError()
                item['supported'] = not item['directory'] and bool(media_kind(Path(item['name'])))
            except (ValueError, TypeError, KeyError):
                if internal: raise ValueError('网盘目录记录无效。') from None
                continue
            items.append(item)
        # Bound session memory. A selection must be from the currently viewed page.
        if not internal:
            self._listed = {i['id']: i for i in items}
        return dict(items=items, directory=directory, page=page, has_more=len(raw_items)==100)

    def account(self):
        if self._account is None:
            value = str(self._api('xpan/nas', method='uinfo').get('uk', ''))
            if not re.fullmatch(r'[0-9]{1,24}', value):
                raise ValueError('无法确认百度网盘账户。')
            self._account = hashlib.sha256(('baidu:' + value).encode()).hexdigest()
        return self._account

    def scan_photos(self, directory, progress, cancelled):
        """Enumerate only metadata, never file contents, from exactly one selected subtree."""
        root = PurePosixPath(directory)
        if not root.is_absolute() or directory.startswith('//') or '..' in root.parts or '\\' in directory:
            raise ValueError('网盘目录格式无效。')
        pending, done, photos = [str(root)], set(), {}
        total_pages = 0
        while pending:
            current = pending.pop()
            if current in done:
                continue
            done.add(current)
            if len(done) > 2500:
                raise ValueError('目录太大，请选择更小的子目录。')
            page = 0
            page_signatures = set()
            while True:
                if cancelled():
                    return None
                total_pages += 1
                if total_pages > 5000:
                    raise ValueError('目录太大，请选择更小的子目录。')
                listing = self.list(current, page, internal=True)
                signature = tuple(item['id'] for item in listing['items'])
                if signature in page_signatures:
                    raise ValueError('网盘返回了重复的分页记录，请重试。')
                page_signatures.add(signature)
                for item in listing['items']:
                    path = PurePosixPath(item['path'])
                    if (str(path.parent) != current or '\\' in item['path'] or '..' in path.parts
                            or not path.is_relative_to(root)):
                        continue
                    if item['directory']:
                        pending.append(str(path))
                    elif media_kind(Path(item['name'])) == 'photo':
                        photos[item['id']] = item
                        if len(photos) > 50000:
                            raise ValueError('照片太多，请选择更小的子目录。')
                progress(len(photos), 0, '正在索引网盘照片（不下载原图）')
                if not listing['has_more']:
                    break
                page += 1
        return list(photos.values()) if not cancelled() else None

    def photo_preview(self, item, variant):
        if variant not in ('grid', 'detail'):
            raise ValueError('预览尺寸不支持。')
        key = (item['fsid'], item['mtime'], item['size'], variant)
        if key in self._renditions:
            self._renditions.move_to_end(key)
            return {'data': self._renditions[key]}
        rows = self._api('xpan/multimedia', method='filemetas', fsids=json.dumps([int(item['fsid'])]), thumb=1, dlink=0).get('list', [])
        if (not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict)
                or str(rows[0].get('fs_id')) != item['fsid'] or rows[0].get('isdir')
                or str(rows[0].get('size')) != str(item['size'])
                or ('server_mtime' in rows[0] and str(rows[0]['server_mtime']) != str(item['mtime']))):
            raise ValueError('网盘照片已变化，请重新扫描。')
        links = rows[0].get('thumbs', {})
        choices = ('url2','url1') if variant == 'grid' else ('url3','url2','url1')
        link = next((links[k] for k in choices if isinstance(links.get(k), str) and links[k]), None) if isinstance(links, dict) else None
        if not link:
            return {'data': None}
        limit = 384 * 1024 if variant == 'grid' else 4 * 1024 * 1024
        # Use only provider-generated preview links; never append the token or ask for an original.
        try:
            with self._open(link) as response:
                raw = response.read(limit + 1)
        except Exception:
            raise ValueError('无法读取网盘照片预览。') from None
        formats = (('jpeg',raw.startswith(b'\xff\xd8\xff')),
                   ('png',raw.startswith(b'\x89PNG\r\n\x1a\n')),
                   ('webp',raw.startswith(b'RIFF') and raw[8:12] == b'WEBP'))
        kind = next((name for name,matches in formats if matches), None)
        if len(raw) > limit or kind is None:
            return {'data': None}
        encoded = 'data:image/' + kind + ';base64,' + base64.b64encode(raw).decode('ascii')
        while self._renditions and (len(self._renditions) >= 48 or self._rendition_size + len(encoded) > 12 * 1024 * 1024):
            self._rendition_size -= len(self._renditions.popitem(last=False)[1])
        self._renditions[key] = encoded
        self._rendition_size += len(encoded)
        return {'data': encoded}

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
