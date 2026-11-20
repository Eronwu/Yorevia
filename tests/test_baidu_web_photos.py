import base64
from io import BytesIO
import json
import http.client
import re
import sys
import threading
from pathlib import Path
import time
import urllib.parse

from PIL import Image
import pytest

from yorevia.baidu import BaiduSource
from yorevia.service import Service


def jpg(size):
    buf = BytesIO()
    Image.new('RGB', size, 'orange').save(buf, 'JPEG')
    return buf.getvalue()


def done(service, job_id):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        job = service.call('job.status', {'job_id': job_id})
        if job['status'] != 'running':
            assert job['status'] == 'done', job
            return job['result']
        time.sleep(.01)
    pytest.fail('index job did not finish')


class LoopbackRPC:
    """Actual local-web listener, running in a test thread with synthetic picker."""
    def __init__(self, workspace, monkeypatch):
        root = Path(__file__).resolve().parents[1]
        assert (root/'dist'/'index.html').is_file(), 'build the frontend before running loopback checks'
        monkeypatch.syspath_prepend(str(root/'scripts'))
        import preview
        created = threading.Event()
        self.server = None
        class Listener(preview.ThreadingHTTPServer):
            def serve_forever(listener, *args, **kwargs):
                self.server = listener
                created.set()
                return super().serve_forever(*args, **kwargs)
        monkeypatch.setattr(preview,'ThreadingHTTPServer',Listener)
        monkeypatch.setattr(sys,'argv',['preview.py','--local-web','--profile',str(workspace/'profile'),
                                       '--port','0','--no-open'])
        boot_errors = []
        def run_server():
            try:
                preview.main(picker=lambda *_:str(workspace))
            except Exception as exc:
                boot_errors.append(exc)
                created.set()
        self.thread = threading.Thread(target=run_server,daemon=True)
        self.thread.start()
        assert created.wait(45), 'synthetic local-web listener did not start within 45 seconds'
        assert not boot_errors, boot_errors
        assert self.server is not None
        self.port = self.server.server_port
        self.origin = f'http://127.0.0.1:{self.port}'
        connection = http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            connection.request('GET','/')
            response = connection.getresponse()
            assert response.status == 200
            html = response.read().decode()
        finally:
            connection.close()
        assert 'window.__YOREVIA_LOCAL_WEB__=true' in html
        self.token = json.loads(re.search(r'window\.__YOREVIA_TOKEN__=("[^"]+")',html).group(1))

    def call(self, method, params=None):
        if method == 'vault.open':
            params = {'path':self.call('local.pick',{'purpose':'vault.open','locale':'en'})}
        connection = http.client.HTTPConnection('127.0.0.1',self.port,timeout=5)
        try:
            connection.request('POST','/api',json.dumps({'method':method,'params':params or {}}),
                               {'Origin':self.origin,'X-Yorevia-Token':self.token,'Content-Type':'application/json'})
            response = connection.getresponse()
            payload = json.loads(response.read())
        finally:
            connection.close()
        if response.status != 200:
            raise ValueError(payload.get('error',{}).get('message','Unexpected HTTP response'))
        return payload['result']

    def close(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        assert not self.thread.is_alive()


@pytest.mark.parametrize("transport", ["direct", "http"])
def test_recursive_photo_index_and_on_demand_account_bound_renditions(tmp_path, monkeypatch, transport):
    requests = []
    grid, big = jpg((40, 30)), jpg((240, 180))

    def row(fsid, path, folder=False):
        return dict(fs_id=fsid, path=path, server_filename=path.rsplit('/', 1)[-1],
                    isdir=int(folder), size=0 if folder else 8000, server_mtime=1700000000)

    def fake_open(source, url):
        p = urllib.parse.urlsplit(url)
        q = urllib.parse.parse_qs(p.query)
        requests.append((p.path, q))
        if p.hostname == 'thumbnail.baidu.com':
            assert 'access_token' not in q
            assert p.path in ('/small', '/large')
            return BytesIO(grid if p.path == '/small' else big)
        assert p.hostname == 'pan.baidu.com'
        method = q['method'][0]
        if method == 'uinfo':
            data = {'uk': '102' if q['access_token']==['synthetic.other.account'] else '101'}
        elif method == 'list':
            path, start = q['dir'][0], int(q['start'][0])
            files = {('/', 0): [row(2,'/album',True)],
                ('/album',0): [row(i,f'/album/ignore{i}.txt') for i in range(200, 300)],
                ('/album',100): [row(3,'/album/nested',True)],
                ('/album/nested',0): [row(4,'/album/nested/reunion.jpg'),row(5,'/sibling/never.jpg')]}
            data = {'list': files.get((path,start), [])}
        elif method == 'filemetas':
            assert q['dlink'] == ['0'] and q['thumb'] == ['1'] and q['fsids'] == ['[4]']
            data = {'list': [dict(fs_id=4, size=8000, thumbs={'url2':'https://thumbnail.baidu.com/small','url3':'https://thumbnail.baidu.com/large'})]}
        else:
            pytest.fail('unexpected provider call: '+method)
        return BytesIO(json.dumps(data).encode())

    monkeypatch.setattr(BaiduSource, '_open', fake_open)
    s = Service() if transport == "direct" else LoopbackRPC(tmp_path, monkeypatch)
    try:
        s.call('vault.open', {'path':str(tmp_path)})
        s.call('baidu.connect', {'access_token':'synthetic.one.account'})
        result=done(s,s.call('baidu.scan_photos', {'directory':'/album'})['job_id'])
        assert result == {'cancelled':False,'indexed':1}
        assert all(q.get('method') != ['filemetas'] for _,q in requests)
        asset_row, = s.call('timeline')['items']
        assert asset_row['remote_photo'] and asset_row['title']=='reunion' and asset_row['captured_at'] is None
        assert not list((tmp_path/'YoreviaVault'/'thumbs').iterdir())
        asset = asset_row['id']
        assert s.call('asset.detail',{'asset_id':asset})['locations'][0]['relative_path']=='album/nested/reunion.jpg'
        for variant, expected in [('grid',grid),('grid',grid),('detail',big)]:
            image = s.call('image', {'asset_id':asset,'variant':variant})
            assert base64.b64decode(image['data'].split(',')[1]) == expected
        assert len([path for path,q in requests if q.get('method')==['filemetas']])==2
        s.call('baidu.disconnect')
        s.call('baidu.connect', {'access_token':'synthetic.other.account'})
        with pytest.raises(ValueError, match='百度网盘账户'):
            s.call('image', {'asset_id':asset,'variant':'grid'})
        assert len([path for path,q in requests if q.get('method')==['filemetas']])==2
    finally:
        s.close()
