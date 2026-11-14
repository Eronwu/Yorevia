"""Loopback HTTP boundary checks against the actual developer preview server."""
import json
from pathlib import Path
import re
import subprocess
import sys
from urllib.request import Request,urlopen
from urllib.error import HTTPError


def test_loopback_preview_boundary():
    root=Path(__file__).parents[1]
    process=subprocess.Popen([sys.executable,str(root/'scripts/preview.py'),'--port','0','--no-open'],
                             cwd=root,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        url=process.stdout.readline().strip().removeprefix('Yorevia developer preview: ')
        assert url.startswith('http://127.0.0.1:')
        with urlopen(url,timeout=10) as response:
            html=response.read().decode();assert response.headers['X-Frame-Options']=='DENY'
        token=json.loads(re.search(r'window\.__YOREVIA_TOKEN__=("[^"]+")',html).group(1))
        def status(request):
            try:
                with urlopen(request,timeout=10) as response:return response.status,response.read()
            except HTTPError as error:return error.code,error.read()
        payload=json.dumps({'method':'status','params':{}}).encode()
        assert status(Request(url+'/api',data=payload,headers={'Content-Type':'application/json'}))[0]==403
        assert status(Request(url,headers={'Host':'attacker.invalid'}))[0]==403
        assert status(Request(url+'/%2e%2e/README.md'))[0]==404
        headers={'Content-Type':'application/json','Origin':url,'X-Yorevia-Token':token}
        code,body=status(Request(url+'/api',data=payload,headers=headers))
        assert code==200 and json.loads(body)['result']['telemetry'] is False
        headers['Origin']='https://attacker.invalid'
        assert status(Request(url+'/api',data=payload,headers=headers))[0]==403
    finally:
        process.terminate();process.communicate(timeout=10)
