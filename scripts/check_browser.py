#!/usr/bin/env python3
"""Optional Playwright smoke: real UI + real Python service, simulated Tauri transport.
No native OS integration or real face-recognition quality is tested here.
Run after npm run build, with Playwright and a Chromium executable installed.
"""
from pathlib import Path
import argparse
import sys
import tempfile
import zipfile
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from yorevia.service import Service
from make_standalone_demo import html_document
from playwright.sync_api import sync_playwright


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--chromium',default='/usr/bin/chromium');args=parser.parse_args()
    errors=[];requests=[]
    with tempfile.TemporaryDirectory(prefix='yorevia-browser-') as folder:
        base=Path(folder);source=base/'测试照片';source.mkdir();home=base/'资料库';home.mkdir()
        for name,color in [('20140512.jpg',(80,110,60)),('20201004.jpg',(170,100,60))]:
            Image.new('RGB',(240,160),color).save(source/name)
        (source/'没有日期的日记.txt').write_text('这是用于自动测试的虚构文字。',encoding='utf-8')
        service=Service();choices=iter([str(home),str(source)])
        def invoke(command,arguments=None):
            arguments=arguments or {}
            if command=='choose_folder':return next(choices)
            if command=='rpc':return service.call(arguments['method'],arguments.get('params',{}))
            raise ValueError('Unexpected native command in test: '+command)
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.chromium,headless=True,args=['--no-sandbox'])
                page=browser.new_page(viewport={'width':1440,'height':1024})
                page.on('pageerror',lambda err:errors.append(str(err)))
                page.on('request',lambda request:requests.append(request.url))
                page.expose_function('testInvoke',invoke)
                shim='<script>window.__TAURI__={core:{invoke:(cmd,args)=>window.testInvoke(cmd,args)}};</script>'
                page.set_content(html_document(False).replace('</head>',shim+'</head>'))
                page.locator('[data-action="open-vault"]').wait_for()
                page.screenshot(path=str(ROOT/'docs/screenshots/welcome.png'),full_page=True)
                page.locator('[data-action="open-vault"]').click()
                page.locator('.people-invitation').wait_for()
                page.locator('[data-action="add-source"]').first.click()
                page.locator('[data-action="local-source"]').click()
                page.wait_for_function("document.querySelectorAll('.memory-card').length === 3")
                page.locator('[data-year="2014"]').click()
                page.wait_for_function("document.querySelectorAll('.memory-card').length === 1")
                page.locator('.memory-card').click()
                page.locator('[data-write-for]').click()
                page.locator('input[name="title"]').fill('第一段故事 <script>不会执行</script>')
                page.locator('textarea[name="body"]').fill('图像之外的记忆。<img src=x onerror=alert(1)>')
                page.locator('input[name="date"]').fill('2014-05-12')
                page.get_by_role('button',name='保存这段故事',exact=True).click()
                page.wait_for_function("!document.querySelector('#modal').open")
                page.locator('[data-view="stories"]').first.click()
                page.get_by_text('第一段故事 <script>不会执行</script>',exact=True).wait_for()
                assert not page.locator('script').filter(has_text='不会执行').count()
                assert len(service.vault.stories())==1
                assert len(service.vault.stories()[0]['asset_ids'])==1
                page.locator('[data-view="settings"]').click()
                page.locator('[data-action="export"]').click()
                page.get_by_text('你的故事，已经可以带走。',exact=True).wait_for()
                exports=list((service.vault.root/'exports').glob('*.zip'));assert len(exports)==1
                with zipfile.ZipFile(exports[0]) as z:
                    assert {'manifest.json','index.html'}<=set(z.namelist())
                    assert '&lt;script&gt;' in z.read('index.html').decode()
                # Regression: enter Baidu from an already-open source picker.
                page.locator('[data-action="close-modal"]').click()
                page.locator('[data-action="add-source"]').first.click()
                page.locator('#modal [data-action="baidu-source"]').click()
                page.locator('#modal input[name="token"]').wait_for()
                page.locator('[data-action="close-modal"]').click()
                page.locator('[data-action="baidu-source"]').first.click()
                page.locator('#modal input[name="token"]').wait_for()
                page.locator('[data-action="close-modal"]').click()
                browser.close()
            assert not errors,errors
            assert not requests,requests
            print('PASS: real local vault → import 3 assets → year filter → linked story → escaped rendering → portable export')
            print('PASS: no page errors; no network requests. Native folder/IPC transport was simulated.')
        finally:service.close()
if __name__=='__main__':main()
