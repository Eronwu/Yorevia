#!/usr/bin/env python3
"""Real standalone HTTP and Chromium, with synthetic fixture + injected OS picker results."""
from __future__ import annotations

from contextlib import contextmanager
import argparse
from io import BytesIO
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import parse_qs, urlsplit

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def install_test_provider(trace: Path):
    from yorevia.baidu import BaiduSource

    def jpg(size):
        target = BytesIO()
        Image.new('RGB', size, 'orange').save(target, 'JPEG')
        return target.getvalue()

    def record(value):
        with trace.open('a', encoding='utf-8') as out:
            out.write(value + '\n')

    def row(id_, path, folder=False):
        return {'fs_id': id_, 'path':path, 'server_filename':path.rsplit('/',1)[-1],
                'isdir':int(folder), 'size':0 if folder else 8000}

    def fake_open(_, url):
        p = urlsplit(url)
        q = parse_qs(p.query)
        if p.hostname == 'thumbnail.baidu.com' and p.path in {'/small','/large'}:
            assert 'access_token' not in q
            record(p.path)
            return BytesIO(jpg((40,30) if p.path == '/small' else (240,180)))
        assert p.hostname == 'pan.baidu.com'
        method = q['method'][0]
        record(method)
        if method == 'uinfo':
            result = {'uk':'101'}
        elif method == 'list':
            files = {'/':[row(1,'/album',True)], '/album':[row(2,'/album/nested',True)],
                     '/album/nested':[row(4,'/album/nested/Cloud-fixture.jpg')]}
            result = {'list':files.get(q['dir'][0],[])}
        elif method == 'filemetas':
            assert q['dlink']==['0'] and q['fsids']==['[4]']
            result = {'list':[{'fs_id':4,'size':8000,'thumbs':{
                'url2':'https://thumbnail.baidu.com/small','url3':'https://thumbnail.baidu.com/large'}}]}
        else:
            raise AssertionError('Unexpected provider method.')
        return BytesIO(json.dumps(result).encode())

    BaiduSource._open = fake_open


@contextmanager
def web_process(profile: Path, port: int = 0, vault: Path | None = None, source: Path | None = None, provider_trace: Path | None = None):
    code = (
        "import os,sys; from pathlib import Path; sys.path.insert(0,'scripts'); import preview;"
        "from check_local_web_browser import install_test_provider;"
        "trace=os.environ.get('YOREVIA_QA_PROVIDER_TRACE'); trace and install_test_provider(Path(trace));"
        "selected=[None,os.environ.get('YOREVIA_QA_VAULT')];"
        "preview.main(picker=lambda purpose,locale: selected.pop(0) if purpose=='vault.open' else os.environ.get('YOREVIA_QA_SOURCE'))"
    )
    env = dict(os.environ, YOREVIA_QA_VAULT=str(vault or ''), YOREVIA_QA_SOURCE=str(source or ''))
    env.pop('YOREVIA_BAIDU_OAUTH_URL',None)
    if provider_trace is not None:
        env['YOREVIA_QA_PROVIDER_TRACE'] = str(provider_trace)
    cmd = [sys.executable, '-c', code, '--local-web', '--no-open', '--profile', str(profile), '--port', str(port)]
    process = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    try:
        assert process.stdout
        url = process.stdout.readline().strip().removeprefix('Yorevia local Web: ')
        if not url.startswith('http://127.0.0.1:'):
            raise RuntimeError('Local Web server failed to start: ' + (process.stderr.read() if process.poll() is not None else url))
        yield url
    finally:
        if process.poll() is None:
            process.terminate()
        _, errors = process.communicate(timeout=10)
        assert process.returncode == 0, errors


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chromium')
    parser.add_argument('--screenshot', type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='yorevia-local-web-qa-') as temporary, sync_playwright() as playwright:
        base = Path(temporary)
        parent, source = base/'vault-location', base/'originals'
        parent.mkdir()
        (source/'2024'/'trip').mkdir(parents=True)
        image = source/'2024'/'trip'/'20240512.jpg'
        Image.new('RGB', (240,160), (80,110,60)).save(image)
        (source/'2024'/'detail.txt').write_text('Nested original, untouched.', encoding='utf-8')
        options = {'headless': True, 'chromium_sandbox': True}
        if args.chromium:
            options['executable_path'] = args.chromium
        browser = playwright.chromium.launch(**options)
        context = browser.new_context(locale='en-US', viewport={'width': 1420,'height': 1000})
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        profile = base/'profile'
        trace = base/'provider-trace.txt'
        with web_process(profile, vault=parent, source=source, provider_trace=trace) as url:
            response = page.goto(url)
            assert response and response.status == 200
            create = page.locator('[data-action="open-vault"]')
            create.wait_for()
            with page.expect_response(lambda resp: resp.url.endswith('/api') and resp.request.post_data_json.get('method') == 'local.pick') as cancelled:
                create.click()
            assert cancelled.value.json() == {'result':None}
            assert create.is_visible()
            assert not (parent/'YoreviaVault').exists()
            create.click()
            page.locator('.people-invitation').wait_for()
            page.locator('[data-action="add-source"]').first.click()
            page.locator('[data-action="local-source"]').click()
            page.wait_for_function("document.querySelectorAll('.memory-card').length === 2")
            page.locator('.memory-card img').first.wait_for(state='visible')
            page.wait_for_function("document.querySelector('.memory-card img').naturalWidth > 0")
            page.locator('.memory-card').filter(has=page.locator('img[data-media]')).first.click()
            page.locator('#modal .detail-photo').wait_for(state='visible')
            page.wait_for_function("document.querySelector('#modal .detail-photo').naturalWidth > 0")
            page.locator('#modal [data-action="close-modal"]').click()
            page.locator('[data-action="write-story"]').click()
            title = 'Browser restart fixture'
            page.locator('input[name="title"]').fill(title)
            page.locator('textarea[name="body"]').fill('Verified using synthetic local data.')
            page.locator('#modal button[type=submit]').click()
            page.locator('#modal').wait_for(state='hidden')
            page.locator('[data-action="add-source"]').first.click()
            page.locator('#modal [data-action="baidu-source"]').click()
            page.locator('#modal input[name="token"]').fill('synthetic.ci.provider')
            page.locator('#modal button[type=submit]').click()
            page.locator('#modal [data-baidu-folder]').click()
            page.wait_for_function("document.querySelector('#modal .path')?.textContent === '/album'")
            page.locator('#modal button[type=submit]').click()
            remote = page.locator('.memory-card').filter(has_text='Cloud-fixture')
            remote.wait_for()
            remote.scroll_into_view_if_needed()
            page.wait_for_function("document.querySelector('.memory-card img[data-remote-photo]')?.naturalWidth === 40")
            remote.click()
            page.wait_for_function("document.querySelector('#modal .detail-photo')?.naturalWidth === 240")
            calls = trace.read_text().splitlines()
            assert set(calls) == {'uinfo','list','filemetas','/small','/large'}, calls
            assert calls.count('/small') == calls.count('/large') == 1, calls
            old_token = page.evaluate('window.__YOREVIA_TOKEN__')
            if args.screenshot:
                page.screenshot(path=str(args.screenshot), full_page=True)
        port = int(url.rsplit(':',1)[1])
        context.close()
        context = browser.new_context(locale='en-US', viewport={'width': 1420,'height': 1000})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        with web_process(profile, port=port) as restarted:
            assert restarted == url
            page.goto(url)
            assert page.evaluate('window.__YOREVIA_TOKEN__') != old_token
            page.locator('.people-invitation').wait_for()
            page.locator('[data-view="stories"]').first.click()
            page.get_by_text(title, exact=True).wait_for()
            page.get_by_text('Verified using synthetic local data.', exact=True).wait_for()
        (parent/'YoreviaVault').rename(parent/'offline-vault')
        with web_process(profile, port=port):
            page.goto(url)
            page.get_by_text('The previous vault could not open.', exact=False).wait_for()
            assert not (parent/'YoreviaVault').exists()
        assert not errors, errors
        assert image.is_file()
        browser.close()
        print('PASS: native picker result/cancel simulation, nested read-only indexing, thumbnail/detail (including simulated Baidu without originals), story write, process restart on same URL, offline-vault recovery.')


if __name__ == '__main__':
    main()
