#!/usr/bin/env python3
"""Bilingual UI regression with synthetic data and simulated native IPC, not native OS QA."""
from pathlib import Path
import argparse
import sys
import tempfile
import zipfile
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'engine'))
from yorevia.service import Service
from make_standalone_demo import html_document
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--chromium')
    parser.add_argument('--screenshots')
    args = parser.parse_args()
    errors, unexpected_requests = [], []
    with tempfile.TemporaryDirectory(prefix='yorevia-i18n-') as directory:
        base = Path(directory)
        source = base / '原始资料'; source.mkdir()
        Image.new('RGB', (240, 160), (80, 110, 60)).save(source / '20140512.jpg')
        (source / '故事.txt').write_text('原文 English <script>原文</script>', encoding='utf-8')
        home = base / 'vault'; home.mkdir()
        service = Service()
        choices = iter([str(home), str(source)])
        def invoke(command, arguments=None):
            arguments = arguments or {}
            if command == 'choose_folder': return next(choices)
            if command == 'rpc': return service.call(arguments['method'], arguments.get('params', {}))
            raise ValueError('Unexpected native command: ' + command)
        try:
            with sync_playwright() as p:
                options = {'headless': True, 'args': ['--no-sandbox']}
                if args.chromium: options['executable_path'] = args.chromium
                browser = p.chromium.launch(**options)
                context = browser.new_context(locale='en-US', viewport={'width': 1440, 'height': 1024})
                page = context.new_page()
                page.on('pageerror', lambda err: errors.append(str(err)))
                page.expose_function('testInvoke', invoke)
                shim = '<script>window.__TAURI__={core:{invoke:(cmd,args)=>window.testInvoke(cmd,args)}};</script>'
                markup = html_document(False).replace('</head>', shim + '</head>')
                def route(request):
                    if request.request.url == 'https://yorevia.test/': request.fulfill(body=markup, content_type='text/html')
                    else:
                        unexpected_requests.append(request.request.url)
                        request.abort()
                page.route('**/*', route)
                page.goto('https://yorevia.test/')
                page.locator('#app-language').wait_for()
                assert page.locator('html').get_attribute('lang') == 'en'
                assert page.locator('[data-action="open-vault"]').inner_text() == 'Create or open a life vault'
                page.select_option('#app-language', 'zh-CN')
                assert page.locator('html').get_attribute('lang') == 'zh-CN'
                page.reload()
                page.locator('#app-language').wait_for()
                assert page.locator('#app-language').input_value() == 'zh-CN'
                if args.screenshots:
                    Path(args.screenshots).mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(Path(args.screenshots) / 'welcome-zh.png'), full_page=True)
                page.locator('[data-action="open-vault"]').click()
                page.locator('.people-invitation').wait_for()
                page.locator('[data-action="add-source"]').first.click()
                page.locator('[data-action="local-source"]').click()
                page.wait_for_function("document.querySelectorAll('.memory-card').length === 2")
                page.locator('[data-view="settings"]').click()
                page.select_option('#app-language', 'en')
                page.reload()
                page.locator('[data-view="settings"]').click()
                page.locator('#app-language').wait_for()
                assert page.locator('#app-language').input_value() == 'en'
                page.locator('[data-view="timeline"]').first.click()
                page.locator('[data-action="write-story"]').click()
                title, body = '故事 <script>不执行</script>', '原文 English <img src=x onerror=alert(1)>'
                page.locator('input[name="title"]').fill(title)
                page.locator('textarea[name="body"]').fill(body)
                # System language changes never replace or discard a live form.
                page.evaluate("window.dispatchEvent(new StorageEvent('storage',{key:'yorevia.language',newValue:'system'}))")
                page.evaluate("Object.defineProperty(navigator,'languages',{configurable:true,value:['zh-CN']});window.dispatchEvent(new Event('languagechange'))")
                assert page.locator('input[name="title"]').input_value() == title
                assert page.locator('textarea[name="body"]').input_value() == body
                page.locator('#modal button[type="submit"]').click()
                page.wait_for_function("!document.querySelector('#modal').open")
                page.locator('[data-view="stories"]').first.click()
                page.get_by_text(title, exact=True).wait_for()
                assert service.vault.stories()[0]['body'] == body
                page.locator('[data-view="people"]').first.click()
                page.locator('[data-view="settings"]').click()
                page.select_option('#app-language', 'en')
                page.locator('[data-action="export"]').click()
                page.locator('#modal .path').wait_for()
                with zipfile.ZipFile(next((service.vault.root / 'exports').glob('*.zip'))) as archive:
                    exported = archive.read('index.html').decode()
                    assert 'lang="en"' in exported and '&lt;script&gt;' in exported
                    assert body in archive.read('stories/' + service.vault.stories()[0]['id'] + '.md').decode()
                page.locator('[data-action="close-modal"]').click()
                for _ in range(2):
                    page.locator('[data-action="baidu-source"]').first.click()
                    page.locator('#modal input[name="token"]').wait_for()
                    assert 'Developer preview' in page.locator('#modal').inner_text()
                    page.locator('[data-action="close-modal"]').click()
                if args.screenshots: page.screenshot(path=str(Path(args.screenshots) / 'settings-en.png'), full_page=True)
                # Responsive English chrome must not force horizontal page scrolling.
                for width in [1440, 1024, 820]:
                    page.set_viewport_size({'width': width, 'height': 1000})
                    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                    assert page.evaluate("document.querySelector('main').scrollWidth <= document.querySelector('main').clientWidth + 1")
                # The real standalone demo bundle also loads without modules or network.
                demo = context.new_page()
                demo.on('pageerror', lambda err: errors.append(str(err)))
                demo.on('request', lambda request: unexpected_requests.append(request.url))
                demo.set_content(html_document(True))
                demo.locator('.memory-card').first.wait_for()
                assert demo.locator('[data-action="exit-demo"]').count() == 0
                browser.close()
            assert not errors, errors
            assert not unexpected_requests, unexpected_requests
            print('PASS: system locale, saved preference/reload, local import, language switch, preserved draft/content, localized export, repeated Baidu open/close, responsive layout; no external requests.')
        finally:
            service.close()

if __name__ == '__main__': main()
