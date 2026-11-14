#!/usr/bin/env python3
"""Build a native Python sidecar on the SAME OS and architecture as the target."""
from pathlib import Path
import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--target');args=parser.parse_args()
    host=subprocess.check_output(['rustc','-vV'],text=True).split('host: ')[1].splitlines()[0].strip()
    target=args.target or host
    if target!=host:
        raise SystemExit('Cross-building a Python sidecar is unsafe. Use a native runner for '+target+' (host: '+host+').')
    for model in json.loads((ROOT/'models/manifest.json').read_text())['models']:
        file=ROOT/'models'/model['file']
        if not file.exists() or hashlib.sha256(file.read_bytes()).hexdigest()!=model['sha256']:
            raise SystemExit('Models missing or invalid. Run: python scripts/fetch_models.py')
        if not (ROOT/'models'/(model['file']+'.LICENSE')).exists():
            raise SystemExit('Model licence missing; rerun fetch_models.py')
    cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onefile','--console',
         '--name','yorevia-engine','--paths',str(ROOT/'engine'),
         '--add-data',str(ROOT/'engine/yorevia/schema.sql')+':yorevia',
         '--add-data',str(ROOT/'models')+':models',
         '--collect-all','cv2','--collect-all','pillow_heif',
         '--hidden-import','PIL.Image','--hidden-import','numpy',
         '--hidden-import','yorevia.faces','--distpath',str(ROOT/'build/sidecar'),
         '--workpath',str(ROOT/'build/pyinstaller'),'--specpath',str(ROOT/'build'),str(ROOT/'engine/worker.py')]
    subprocess.run(cmd,cwd=ROOT,check=True)
    extension='.exe' if platform.system()=='Windows' else ''
    destination=ROOT/'src-tauri/binaries'/('yorevia-engine-'+target+extension)
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(ROOT/'build/sidecar'/('yorevia-engine'+extension),destination)
    print('Native sidecar:',destination)

if __name__=='__main__':main()
