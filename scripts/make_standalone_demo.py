#!/usr/bin/env python3
"""Build a zero-network, read-only HTML demo from the real compiled UI modules."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]

def bundle(demo=True):
    result=[]
    for filename in ('domain.js','demo.js','bridge.js','baidu.js','app.js'):
        text=(ROOT/'dist'/filename).read_text(encoding='utf-8')
        text=re.sub(r'^import .*?;\s*$', '', text, flags=re.M)
        text=re.sub(r'\bexport (?=(?:async |const |function |let |class ))','',text)
        if filename=='bridge.js' and demo:
            text=re.sub(r"const isDemo = [^\n]+;",'const isDemo = true;',text)
        if filename=='app.js':
            if demo:
                text=text.replace('<button class="text-button" data-action="exit-demo">退出示例</button>', '')
            text='const e=escapeHTML;\n'+text
        result.append(text)
    return '\n'.join(result)

def html_document(demo=True):
    markup=(ROOT/'public/index.html').read_text(encoding='utf-8')
    css=(ROOT/'public/style.css').read_text(encoding='utf-8')
    script=bundle(demo).replace('</script','<\\/script')
    markup=markup.replace('<link rel="stylesheet" href="./style.css">','<style>'+css+'</style>')
    return markup.replace('<script type="module" src="./app.js"></script>','<script type="module">'+script+'</script>')

if __name__=='__main__':
    path=ROOT/'Yorevia-visual-demo.html'
    path.write_text(html_document(),encoding='utf-8')
    print(path)
