from pathlib import Path
import json
import subprocess
import sys

def test_stdio_transport_is_persistent_and_reports_errors():
    root=Path(__file__).resolve().parents[1]
    requests=[{'id':1,'method':'status','params':{}},{'id':2,'method':'not.allowed','params':{}},{'id':3,'method':'status','params':{}}]
    result=subprocess.run([sys.executable,str(root/'engine/worker.py')],input='\n'.join(json.dumps(x) for x in requests)+'\n',text=True,capture_output=True,timeout=10)
    assert result.returncode==0
    rows=[json.loads(x) for x in result.stdout.splitlines()]
    assert [x['id'] for x in rows]==[1,2,3]
    assert rows[0]['result']['telemetry'] is False
    assert 'error' in rows[1]
    assert rows[2]['result']['vault'] is None
