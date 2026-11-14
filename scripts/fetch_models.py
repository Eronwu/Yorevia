#!/usr/bin/env python3
"""Explicit build-time download. Only official model URLs; verify complete SHA-256."""
from pathlib import Path
import hashlib
import json
import os
import urllib.request

ROOT=Path(__file__).resolve().parents[1]

def main():
    for model in json.loads((ROOT/'models/manifest.json').read_text())['models']:
        target=ROOT/'models'/model['file']
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=model['sha256']:
            print('Downloading official OpenCV model:',model['file'],flush=True)
            temporary=target.with_suffix('.part')
            try:
                request=urllib.request.Request(model['url'],headers={'User-Agent':'Yorevia-build/0.1'})
                with urllib.request.urlopen(request,timeout=90) as response,temporary.open('wb') as out:
                    total=0
                    while chunk:=response.read(1024*1024):
                        total+=len(chunk)
                        if total>60*1024*1024:
                            raise RuntimeError('Model unexpectedly exceeds 60 MiB')
                        out.write(chunk)
                if hashlib.sha256(temporary.read_bytes()).hexdigest()!=model['sha256']:
                    raise RuntimeError('Model checksum mismatch: '+model['file'])
                os.replace(temporary,target)
            finally:
                temporary.unlink(missing_ok=True)
        # Preserve the upstream licence beside each bundled weight file.
        with urllib.request.urlopen(model['license_url'],timeout=30) as response:
            (ROOT/'models'/(model['file']+'.LICENSE')).write_bytes(response.read(100_000))
        print('Verified:',model['file'])

if __name__=='__main__': main()
