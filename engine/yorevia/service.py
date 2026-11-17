"""Transport-independent RPC dispatcher with one cancellable background writer."""
from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import threading
from .vault import Vault, uid
from .faces import model_status
from .baidu import BaiduSource
from .baidu_oauth import BaiduOAuth

METHODS = {'status','vault.open','summary','source.add','scan.start','faces.start','job.status','job.cancel',
           'timeline','people','graph','image','asset.detail','asset.date','asset.path','person.rename',
           'person.merge','person.faces','face.split','relationship.add','story.save','stories','export',
           'biometrics.erase','baidu.connect','baidu.disconnect','baidu.status','baidu.list','baidu.import','baidu.auth.start','baidu.auth.poll','baidu.auth.cancel'}


class Service:
    def __init__(self):
        self.vault: Vault | None = None
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix='yorevia-index')
        self.jobs: dict[str, dict] = {}
        self.guard = threading.RLock()
        self.cancel = threading.Event()
        self.active = None
        self.baidu = None
        self.baidu_connection_id = None
        self.baidu_oauth = BaiduOAuth()

    def close(self):
        self.cancel.set()
        self.baidu_oauth.cancel()
        self.baidu = None
        self.baidu_connection_id = None
        self.pool.shutdown(wait=True, cancel_futures=True)
        if self.vault:
            self.vault.close()
            self.vault = None

    def _start(self, operation) -> dict:
        with self.guard:
            if self.active and self.jobs[self.active]['status'] == 'running':
                raise ValueError('已有本地任务在运行，请等待完成或先取消。')
            self.cancel.clear()
            job_id = uid()
            self.active = job_id
            self.jobs[job_id] = dict(id=job_id,status='running',done=0,total=0,label='正在准备',result=None,error=None)
            if len(self.jobs)>20:
                self.jobs.pop(next(iter(self.jobs)))
        def progress(done,total,label):
            with self.guard:
                self.jobs[job_id].update(done=done,total=total,label=label)
        def run():
            try:
                result=operation(progress,self.cancel.is_set)
                with self.guard:
                    self.jobs[job_id].update(status='cancelled' if result.get('cancelled') else 'done',result=result)
            except Exception as exc:
                with self.guard:
                    self.jobs[job_id].update(status='error',error=str(exc)[:1000])
        self.pool.submit(run)
        return {'job_id':job_id}

    def call(self, method: str, params: dict | None = None):
        if method not in METHODS:
            raise ValueError('未知操作')
        p=params or {}
        if method=='status':
            return {'version':'0.1.0-alpha.1','vault':self.vault.summary() if self.vault else None,
                    'models':model_status(),'transport':'local','telemetry':False}
        if method=='vault.open':
            if self.active and self.jobs[self.active]['status']=='running':
                raise ValueError('任务运行中，不能切换资料库。')
            selected=Path(p['path']).expanduser().resolve(strict=True)
            if not selected.is_dir():
                raise ValueError('请选择文件夹')
            root=selected if (selected/'vault.json').is_file() else selected/'YoreviaVault'
            if self.vault and root==self.vault.root:
                return self.vault.summary()
            # Open new first so failures never destroy the current in-memory session.
            new_vault=Vault(root)
            if self.vault:
                self.vault.close()
            self.vault=new_vault
            self.baidu_oauth.cancel()
            self.baidu=None
            self.baidu_connection_id=None
            return self.vault.summary()
        if method=='job.status':
            with self.guard:
                if p['job_id'] not in self.jobs:
                    raise ValueError('任务不存在')
                return dict(self.jobs[p['job_id']])
        if method=='job.cancel':
            self.cancel.set()
            return {'ok':True}
        if not self.vault:
            raise ValueError('请先创建或打开人生资料库。')
        v=self.vault
        if method in {'person.merge','face.split'} and self.active and self.jobs[self.active]['status']=='running':
            raise ValueError('请先完成或取消当前整理任务，再修正人物分组。')
        if method.startswith('baidu.'):
            if self.active and self.jobs[self.active]['status']=='running' and method != 'baidu.status':
                raise ValueError('请先完成或取消当前任务，再操作网盘连接。')
            if method=='baidu.status': return {'connected':self.baidu is not None,'oauth_available':bool(self.baidu_oauth.origin),'mode':'session'}
            if method=='baidu.auth.start':
                return self.baidu_oauth.start(p.get('attempt'))
            if method=='baidu.auth.cancel':
                self.baidu_oauth.cancel(p.get('attempt'))
                return {'ok':True}
            if method=='baidu.auth.poll':
                token=self.baidu_oauth.poll(p.get('attempt'))
                if token is None: return {'status':'pending'}
                source=BaiduSource(token)
                listing=source.list()
                if self.vault is not v:
                    raise ValueError('资料库已切换，请重新登录。')
                self.baidu=source
                self.baidu_connection_id=p.get('attempt')
                return {'status':'authorized','listing':listing}
            if method=='baidu.disconnect':
                if p.get('connection_id') and p['connection_id'] != self.baidu_connection_id:
                    return {'ok':True}
                self.baidu_oauth.cancel()
                self.baidu=None
                self.baidu_connection_id=None
                return {'ok':True}
            if method=='baidu.connect':
                source=BaiduSource(p.get('access_token'))
                listing=source.list()
                if self.vault is not v:
                    raise ValueError('资料库已切换，请重新登录。')
                self.baidu=source
                self.baidu_connection_id=p.get('connection_id') or uid()
                return listing
            if not self.baidu: raise ValueError('请先连接百度网盘。')
            if method=='baidu.list': return self.baidu.list(p.get('directory','/'),p.get('page',0))
            if method=='baidu.import':
                client=self.baidu
                items=client.selection(p.get('ids'))
                parent=Path(p['destination']).expanduser().resolve(strict=True)
                if not parent.is_dir() or parent==v.root or parent.is_relative_to(v.root):
                    raise ValueError('请选择资料库以外的本地下载目录。')
                destination=parent/('Yorevia-Baidu-'+uid())
                destination.mkdir(mode=0o700)
                source=v.add_source(str(destination))
                def download(progress,cancelled):
                    result=client.download(items,destination,progress,cancelled)
                    if not result['cancelled']:
                        result['scan']=v.scan(source['id'],progress,cancelled)
                        result['cancelled']=result['scan'].get('cancelled',False)
                        result['errors']=result['scan'].get('errors',[])
                    return dict(result,source_id=source['id'],destination=str(destination))
                return self._start(download)
        if method=='summary': return v.summary()
        if method=='source.add': return v.add_source(p['path'])
        if method=='scan.start': return self._start(lambda progress,cancelled:v.scan(p['source_id'],progress,cancelled,bool(p.get('force',False))))
        if method=='faces.start':
            if p.get('consent') is not True:
                raise ValueError('需要你明确同意在本地分析人像。')
            return self._start(lambda progress,cancelled:v.analyze_faces(progress,cancelled))
        if method=='timeline': return v.timeline(**p)
        if method=='people': return v.people(**p)
        if method=='graph': return v.graph(**p)
        if method=='image': return v.image(**p)
        if method=='asset.detail': return v.detail(p['asset_id'])
        if method=='asset.path': return {'path':str(v.asset_path(p['asset_id']))}
        if method=='asset.date': return v.set_date(p['asset_id'],p.get('date'))
        if method=='person.rename': return v.rename_person(p['person_id'],p['name'],p.get('description',''))
        if method=='person.merge': return v.merge_people(p['keep'],p['merge'])
        if method=='person.faces': return v.person_faces(p['person_id'],p.get('offset',0))
        if method=='face.split': return v.split_face(p['face_id'],p.get('name',''))
        if method=='relationship.add': return v.add_relationship(**p)
        if method=='story.save': return v.save_story(**p)
        if method=='stories': return v.stories()
        if method=='export': return v.export()
        if method=='biometrics.erase':
            if self.active and self.jobs[self.active]['status']=='running':
                raise ValueError('请先停止当前扫描任务。')
            if p.get('confirm')!='ERASE':
                raise ValueError('需要明确确认删除本地人像特征。')
            return v.erase_biometrics()
        raise ValueError('操作未实现')
