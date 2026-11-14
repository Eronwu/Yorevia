#!/usr/bin/env python3
from pathlib import Path
import argparse
import json
import subprocess

parser=argparse.ArgumentParser();parser.add_argument('executable',type=Path);args=parser.parse_args()
request={'id':1,'method':'status','params':{}}
result=subprocess.run([str(args.executable.resolve())],input=json.dumps(request)+'\n',text=True,encoding='utf-8',capture_output=True,timeout=90,check=True)
reply=json.loads(result.stdout.strip())
assert reply['id']==1 and reply['result']['models']['installed'] is True,reply
assert reply['result']['telemetry'] is False
print('Bundled native engine starts; model files are included; no telemetry.')
