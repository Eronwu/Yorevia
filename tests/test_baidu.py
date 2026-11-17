from io import BytesIO
from pathlib import Path
import time
import pytest
from yorevia.baidu import BaiduSource, safe_url, MAX_FILE
from yorevia.service import Service

TOKEN='test_token_not_a_real_credential'

def raw(name='20200101.txt', ident=1, size=3):
    return dict(fs_id=ident, server_filename=name, path='/'+name, isdir=0,size=size)

def client(monkeypatch, rows=None):
    c=BaiduSource(TOKEN)
    monkeypatch.setattr(c,'_api',lambda *args,**kwargs: {'list': rows or [raw()]})
    c.list()
    return c

@pytest.mark.parametrize('url',['http://pan.baidu.com/a','https://pan.baidu.com.evil.test/a','https://evil.test/a','https://127.0.0.1/a','https://name:pass@pan.baidu.com/a','https://pan.baidu.com:444/a'])
def test_disallow_download_destinations(url):
    with pytest.raises(ValueError):safe_url(url)

def test_valid_download_hosts():
    assert safe_url('https://d.pcs.baidu.com/a')
    assert safe_url('https://d.baidupcs.com/a')

def test_selection_and_limits(monkeypatch):
    c=client(monkeypatch)
    assert c.selection(['1'])[0]['name']=='20200101.txt'
    for ids in ([],['1','1'],['not-listed']):
        with pytest.raises(ValueError):c.selection(ids)
    c=client(monkeypatch,[raw(size=MAX_FILE+1)])
    with pytest.raises(ValueError):c.selection(['1'])

def test_page_replaces_selection(monkeypatch):
    c=client(monkeypatch)
    monkeypatch.setattr(c,'_api',lambda *a,**k:{'list':[raw(ident=2)]})
    c.list()
    with pytest.raises(ValueError):c.selection(['1'])

def test_traversal_and_page(monkeypatch):
    c=client(monkeypatch)
    for path in ('relative','/../x','/a\\b'):
        with pytest.raises(ValueError):c.list(path)
    with pytest.raises(ValueError):c.list('/',-1)

def test_download_safe_name_and_atomic(monkeypatch,tmp_path):
    c=client(monkeypatch,[raw('../hello.txt')]);items=c.selection(['1'])
    monkeypatch.setattr(c,'_api',lambda *a,**k:{'list':[dict(fs_id=1,size=3,dlink='https://d.pcs.baidu.com/file')]})
    monkeypatch.setattr(c,'_open',lambda url:BytesIO(b'hey'))
    result=c.download(items,tmp_path,lambda *a:None,lambda:False)
    assert result['downloaded']==1
    assert [p.name for p in tmp_path.iterdir()]==['1__hello.txt']
    assert (tmp_path/'1__hello.txt').read_bytes()==b'hey'

def test_incomplete_download_no_partial(monkeypatch,tmp_path):
    c=client(monkeypatch);items=c.selection(['1'])
    monkeypatch.setattr(c,'_api',lambda *a,**k:{'list':[dict(fs_id=1,size=3,dlink='https://d.pcs.baidu.com/file')]})
    monkeypatch.setattr(c,'_open',lambda url:BytesIO(b'x'))
    with pytest.raises(ValueError):c.download(items,tmp_path,lambda *a:None,lambda:False)
    assert not list(tmp_path.iterdir())

def test_cancel_keeps_completed_only(monkeypatch,tmp_path):
    c=client(monkeypatch)
    assert c.download(c.selection(['1']),tmp_path,lambda *a:None,lambda:True)['cancelled']
    assert not list(tmp_path.iterdir())

def test_http_error_redacts_token(monkeypatch):
    c=BaiduSource(TOKEN)
    def fail(*a,**k):raise RuntimeError('https://example.test/?access_token='+TOKEN)
    monkeypatch.setattr(c._opener,'open',fail)
    with pytest.raises(ValueError) as exc:c._open('https://pan.baidu.com/?access_token='+TOKEN)
    assert TOKEN not in str(exc.value)

def test_service_import_and_disconnect(monkeypatch,tmp_path):
    s=Service();s.call('vault.open',{'path':str(tmp_path)})
    monkeypatch.setattr(BaiduSource,'_api',lambda *a,**k:{'list':[raw()]})
    s.call('baidu.connect',{'access_token':TOKEN})
    c=s.baidu
    monkeypatch.setattr(c,'_api',lambda *a,**k:{'list':[dict(fs_id=1,size=3,dlink='https://d.pcs.baidu.com/file')]})
    monkeypatch.setattr(c,'_open',lambda url:BytesIO(b'hey'))
    job=s.call('baidu.import',{'ids':['1'],'destination':str(tmp_path)})
    for _ in range(100):
        status=s.call('job.status',job)
        if status['status']!='running':break
        time.sleep(.01)
    assert status['status']=='done'
    assert s.call('summary')['assets']==1
    assert TOKEN not in str(s.call('summary'))
    s.call('baidu.disconnect')
    assert not s.call('baidu.status')['connected']
    with pytest.raises(ValueError):s.call('baidu.list')
    s.close()
    for p in tmp_path.rglob('*'):
        if p.is_file():assert TOKEN.encode() not in p.read_bytes()

def test_stale_disconnect_does_not_clear_new_session(monkeypatch,tmp_path):
    s=Service()
    try:
        s.call('vault.open',{'path':str(tmp_path)})
        monkeypatch.setattr(BaiduSource,'_api',lambda *a,**k:{'list':[raw()]})
        s.call('baidu.connect',{'access_token':TOKEN,'connection_id':'current'})
        s.call('baidu.disconnect',{'connection_id':'stale'})
        assert s.call('baidu.status')['connected']
        s.call('baidu.disconnect',{'connection_id':'current'})
        assert not s.call('baidu.status')['connected']
    finally:s.close()


def test_reject_download_into_vault(monkeypatch,tmp_path):
    s=Service()
    try:
        s.call('vault.open',{'path':str(tmp_path)})
        monkeypatch.setattr(BaiduSource,'_api',lambda *a,**k:{'list':[raw()]})
        s.call('baidu.connect',{'access_token':TOKEN})
        with pytest.raises(ValueError):s.call('baidu.import',{'ids':['1'],'destination':str(s.vault.root)})
    finally:s.close()

def test_oauth_rpc_keeps_token_out_of_frontend_and_vault(monkeypatch,tmp_path):
    s=Service()
    try:
        s.call('vault.open',{'path':str(tmp_path)})
        monkeypatch.setattr(s.baidu_oauth,'poll',lambda attempt:TOKEN)
        monkeypatch.setattr(BaiduSource,'_api',lambda *a,**k:{'list':[raw()]})
        result=s.call('baidu.auth.poll',{'attempt':'attempt-synthetic'})
        assert result['status']=='authorized'
        assert TOKEN not in str(result)
        assert s.baidu_connection_id=='attempt-synthetic'
        s.call('baidu.disconnect',{'connection_id':'attempt-synthetic'})
        assert not s.call('baidu.status')['connected']
    finally:s.close()
    for p in tmp_path.rglob('*'):
        if p.is_file():assert TOKEN.encode() not in p.read_bytes()
