"""Validation, native picker grants and launcher behavior in temporary directories."""
import os
from pathlib import Path
import sys

import pytest

scripts = Path(__file__).parents[1] / 'scripts'
sys.path.insert(0,str(scripts))
from launch_local_web import install_linux_shortcuts, linux_desktop_entry
from local_web_settings import LocalWebSettings
from yorevia.service import Service


def test_folder_consent_and_vault_restore(tmp_path):
    root=tmp_path/'user-chosen'
    root.mkdir()
    profile=tmp_path/'profile'
    chooser=LocalWebSettings(profile,lambda *_:str(root))
    with pytest.raises(ValueError,match='system dialog'):
        chooser.authorized_params('vault.open',{'path':str(root)})
    ticket=chooser.pick('vault.open','en')
    with pytest.raises(ValueError,match='system dialog'):
        chooser.authorized_params('source.add',{'path':ticket})
    ticket=chooser.pick('vault.open','zh-CN')
    service=Service()
    try:
        canonical=service.call('vault.open',chooser.authorized_params('vault.open',{'path':ticket}))['path']
        chooser.remember(canonical)
        with pytest.raises(ValueError,match='system dialog'):
            chooser.authorized_params('vault.open',{'path':ticket})
        assert Path(canonical)==(root/'YoreviaVault').resolve()
        assert chooser.saved_vault()==Path(canonical)
        if os.name!='nt':
            assert chooser.settings.stat().st_mode & 0o077 == 0
        with pytest.raises(ValueError,match='另一进程'):
            from yorevia.vault import Vault
            Vault(Path(canonical))
    finally:
        service.close()
    (root/'YoreviaVault'/'vault.sqlite').unlink()
    with pytest.raises(ValueError,match='not recreated'):
        chooser.saved_vault()
    assert not (root/'YoreviaVault'/'vault.sqlite').exists()


def test_linked_vault_rejected_without_creating_files(tmp_path):
    picked=tmp_path/'picked'
    elsewhere=tmp_path/'other'
    picked.mkdir()
    elsewhere.mkdir()
    try:
        (picked/'YoreviaVault').symlink_to(elsewhere,target_is_directory=True)
    except OSError:
        if os.name=='nt':
            pytest.skip('Windows runner lacks directory symlink privilege')
        raise
    chooser=LocalWebSettings(tmp_path/'profile',lambda *_:str(picked))
    with pytest.raises(ValueError,match='linked vault'):
        chooser.authorized_params('vault.open',{'path':chooser.pick('vault.open','en')})
    assert not list(elsewhere.iterdir())


@pytest.mark.skipif(not sys.platform.startswith('linux'),reason='Linux desktop shortcuts')
def test_shortcut_does_not_use_terminal_and_autostart_is_opt_in(tmp_path,monkeypatch):
    monkeypatch.setenv('XDG_DATA_HOME',str(tmp_path/'data'))
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path/'config'))
    install_linux_shortcuts(False)
    desktop=(tmp_path/'data/applications/yorevia-web.desktop').read_text()
    assert 'Terminal=false' in desktop and '--no-browser' not in desktop
    assert not (tmp_path/'config/autostart').exists()
    install_linux_shortcuts(True)
    background=(tmp_path/'config/autostart/yorevia-web.desktop').read_text()
    assert 'Terminal=false' in background and '--no-browser' in background
    assert desktop==linux_desktop_entry(False)


def test_real_loopback_process_restart_recovers_nested_photos_and_story(tmp_path):
    from contextlib import contextmanager
    import http.client
    import json
    from PIL import Image
    import re
    import subprocess
    import time

    vault_parent, source, profile = [tmp_path/n for n in ('vault-parent','source','profile')]
    vault_parent.mkdir()
    nested = source/'2024'/'trip'
    nested.mkdir(parents=True)
    img = nested/'20240512.jpg'
    Image.new('RGB',(240,160),(108,135,75)).save(img)
    original = img.read_bytes()
    (source/'2024'/'note.txt').write_text('Synthetic nested note.',encoding='utf-8')
    code = (
        'import sys; sys.path.insert(0,"scripts"); import preview;'
        f'selections={{"vault.open":[None,{str(vault_parent)!r}],"source.add":[{str(source)!r}]}};'
        'preview.main(picker=lambda purpose, locale: selections[purpose].pop(0))'
    )

    @contextmanager
    def spawn(port):
        command=[sys.executable,'-c',code,'--local-web','--port',str(port),'--no-open','--profile',str(profile)]
        process=subprocess.Popen(command,cwd=scripts.parent,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            assert process.stdout is not None
            url=process.stdout.readline().strip().removeprefix('Yorevia local Web: ')
            assert url.startswith('http://127.0.0.1:')
            yield process.pid,url,int(url.rsplit(':',1)[1])
        finally:
            if process.poll() is not None:
                pytest.fail('Loopback server stopped before test teardown: '+process.stderr.read())
            process.terminate()
            _,error=process.communicate(timeout=10)
            assert process.returncode in ({0,1} if os.name=='nt' else {0}),error

    def request(port,method,path,body=None,headers=None):
        # A new connection for each request; deliberately no cookie jar.
        connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        try:
            connection.request(method,path,body=body,headers=headers or {})
            response=connection.getresponse()
            return response.status,response.read(),dict(response.getheaders())
        finally:
            connection.close()

    def token_for(port):
        status,html,headers=request(port,'GET','/')
        assert status==200 and b'window.__YOREVIA_LOCAL_WEB__=true' in html and 'Set-Cookie' not in headers
        return json.loads(re.search(rb'window\.__YOREVIA_TOKEN__=("[^"]+")',html).group(1))

    def rpc(port,token,method,params=None,expected=200,origin=None):
        headers={'Content-Type':'application/json','Origin':origin or f'http://127.0.0.1:{port}','X-Yorevia-Token':token}
        status,result,_=request(port,'POST','/api',json.dumps({'method':method,'params':params or {}}),headers)
        assert status==expected,result
        return json.loads(result).get('result')

    with spawn(0) as (first_pid,url,port):
        original_token=token_for(port)
        assert request(port,'GET','/',headers={'Host':f'localhost:{port}'})[0]==403
        assert request(port,'POST','/api','{}',{'Content-Type':'application/json','Origin':url})[0]==403
        assert rpc(port,original_token,'status',expected=403,origin='https://elsewhere.invalid') is None
        assert rpc(port,original_token,'status')['vault'] is None
        assert rpc(port,original_token,'local.pick',{'purpose':'vault.open'}) is None
        assert not (vault_parent/'YoreviaVault').exists()
        assert rpc(port,original_token,'vault.open',{'path':str(vault_parent)},expected=400) is None
        grant=rpc(port,original_token,'local.pick',{'purpose':'vault.open'})
        vault=rpc(port,original_token,'vault.open',{'path':grant})
        assert vault['path']==str((vault_parent/'YoreviaVault').resolve())
        assert rpc(port,original_token,'vault.open',{'path':grant},expected=400) is None
        grant=rpc(port,original_token,'local.pick',{'purpose':'source.add'})
        added=rpc(port,original_token,'source.add',{'path':grant})
        job_id=rpc(port,original_token,'scan.start',{'source_id':added['id']})['job_id']
        deadline=time.monotonic()+10
        while time.monotonic() < deadline:
            job=rpc(port,original_token,'job.status',{'job_id':job_id})
            if job['status']!='running':
                break
            time.sleep(.05)
        assert job['status']=='done',job
        timeline=rpc(port,original_token,'timeline')
        assert timeline['total']==2
        photo=next(item for item in timeline['items'] if item['kind']=='photo')
        detail=rpc(port,original_token,'asset.detail',{'asset_id':photo['id']})
        assert detail['locations'][0]['relative_path']=='2024/trip/20240512.jpg'
        assert rpc(port,original_token,'image',{'asset_id':photo['id']})['data'].startswith('data:image/jpeg;base64,')
        story=rpc(port,original_token,'story.save',{'title':'Restart story fixture','body':'Synthetic story.', 'asset_ids':[photo['id']]})
        assert img.read_bytes()==original
    with spawn(port) as (restarted_pid,restarted,port):
        assert restarted_pid!=first_pid and restarted==url
        new_token=token_for(port)
        assert new_token!=original_token
        assert rpc(port,original_token,'status',expected=403) is None
        restored=rpc(port,new_token,'status')
        assert restored['vault']['path']==vault['path'] and restored['vault']['assets']==2
        stories=rpc(port,new_token,'stories')
        assert stories[0]['id']==story['id'] and stories[0]['body']=='Synthetic story.'
        assert stories[0]['asset_ids']==[photo['id']]
    (vault_parent/'YoreviaVault').rename(tmp_path/'unmounted-vault')
    with spawn(port) as (_,restarted,port):
        assert restarted==url
        status=rpc(port,token_for(port),'status')
        assert status['vault'] is None and status['local_web_startup_error'] is True
        assert not (vault_parent/'YoreviaVault').exists()


def test_launcher_starts_single_background_process_and_reuses_address(tmp_path, monkeypatch):
    import socket
    import subprocess
    import launch_local_web as launcher

    # Same loopback behavior as 4173, random test port avoids interfering with
    # a legitimate service on a developer machine.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0))
        port=sock.getsockname()[1]
    monkeypatch.setenv('XDG_CONFIG_HOME',str(tmp_path/'config'))
    monkeypatch.setattr(launcher,'default_profile',lambda: tmp_path/'config'/'yorevia-web')
    monkeypatch.setattr(launcher,'PORT',port)
    address=f'http://127.0.0.1:{port}'
    monkeypatch.setattr(launcher,'URL',address)
    opened=[]
    monkeypatch.setattr(launcher.webbrowser,'open',lambda url: opened.append(url) or True)
    children=[]
    real_popen=subprocess.Popen
    def record_popen(command, **kwargs):
        assert kwargs['stdin'] is subprocess.DEVNULL and kwargs.get('start_new_session') is True
        child=real_popen(command+['--port',str(port),'--profile',str(launcher.default_profile())],**kwargs)
        children.append(child)
        return child
    monkeypatch.setattr(launcher.subprocess,'Popen',record_popen)
    try:
        try:
            launcher.launch(no_browser=True)
        except ValueError:
            log=launcher.default_profile()/'launcher.log'
            if log.is_file():
                pytest.fail(f'Synthetic Yorevia launcher failed: {log.read_text(errors="replace")[-4000:]}')
            raise
        assert launcher.service_ready() and not opened
        launcher.launch(no_browser=False)
        assert len(children)==1 and opened==[address]
    finally:
        for child in children:
            child.terminate()
            child.wait(timeout=10)
