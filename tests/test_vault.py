from __future__ import annotations
import json
from pathlib import Path
import shutil
import time
import zipfile
import numpy as np
import pytest
from PIL import Image
from yorevia.vault import Vault
from yorevia.media import checked_date, date_from_filename, hash_file
from yorevia.faces import candidate, normalize
from yorevia.service import Service


def photo(path: Path, color=(80,100,120), date=None, orientation=None):
    path.parent.mkdir(parents=True,exist_ok=True)
    image=Image.new('RGB',(120,80),color)
    exif=Image.Exif()
    if date: exif[36867]=date
    if orientation: exif[274]=orientation
    image.save(path,exif=exif)
    return path

@pytest.fixture
def vault(tmp_path):
    v=Vault(tmp_path/'vault')
    yield v
    v.close()

@pytest.fixture
def source(tmp_path,vault):
    root=tmp_path/'照片'
    root.mkdir()
    return root,vault.add_source(str(root))['id']

def scan(vault,source_id,force=False):
    return vault.scan(source_id,lambda *a:None,lambda:False,force)


def test_empty_vault(vault):
    assert vault.summary()['assets']==0
    assert vault.timeline()['items']==[]
    assert vault.people()==[]
    assert vault.graph()['edges']==[]


def test_scan_read_only_and_repeated(vault,source):
    root,sid=source
    p=photo(root/'IMG_20140512.jpg'); digest=hash_file(p)
    assert scan(vault,sid)['added']==1
    assert scan(vault,sid)['reused']==1
    assert hash_file(p)==digest
    assert vault.summary()['assets']==1
    item=vault.timeline()['items'][0]
    assert item['captured_at']=='2014-05-12'
    assert item['date_source']=='filename'
    assert vault.image(asset_id=item['id'])['data'].startswith('data:image/jpeg;base64,')


def test_unknown_date_never_uses_mtime(vault,source):
    root,sid=source
    photo(root/'old_picture.jpg')
    scan(vault,sid)
    assert vault.timeline()['items'][0]['captured_at'] is None
    assert vault.summary()['unknown_dates']==1


def test_exif_wins_and_orientation(vault,source):
    root,sid=source
    photo(root/'IMG_20240101.jpg',date='2011:02:03 14:15:16',orientation=6)
    scan(vault,sid)
    a=vault.timeline()['items'][0]
    assert a['captured_at']=='2011-02-03T14:15:16'
    assert (a['width'],a['height'])==(80,120)


def test_duplicate_and_move_keep_story(vault,source):
    root,sid=source
    p=photo(root/'20140101_original.jpg')
    scan(vault,sid); a=vault.timeline()['items'][0]['id']
    story=vault.save_story('相遇','最初的一天',asset_ids=[a])
    p.rename(root/'renamed.jpg')
    scan(vault,sid)
    assert vault.summary()['assets']==1
    assert vault.detail(a)['stories'][0]['id']==story['id']
    assert vault.asset_path(a).name=='renamed.jpg'
    shutil.copyfile(root/'renamed.jpg',root/'duplicate.jpg')
    scan(vault,sid)
    assert vault.summary()['assets']==1


def test_changed_file_at_same_path(vault,source):
    root,sid=source
    p=photo(root/'20140101_a.jpg');scan(vault,sid)
    old=vault.timeline()['items'][0]['id']
    photo(p,color=(200,10,30));scan(vault,sid,force=True)
    assert vault.summary()['assets']==2
    with pytest.raises(ValueError):vault.asset_path(old)


def test_deleted_file_keeps_record(vault,source):
    root,sid=source
    p=photo(root/'20140101_a.jpg');scan(vault,sid);p.unlink();scan(vault,sid)
    assert vault.timeline()['items'][0]['available']==0
    assert vault.summary()['assets']==1


def test_offline_root_does_not_delete(vault,source):
    root,sid=source
    photo(root/'20140101_a.jpg');scan(vault,sid)
    root.rename(root.with_name('unmounted'))
    with pytest.raises(ValueError,match='不在线'):scan(vault,sid)
    assert vault.timeline()['items'][0]['available']==1


def test_manual_date_survives_rescan(vault,source):
    root,sid=source
    photo(root/'no_date.jpg');scan(vault,sid)
    a=vault.timeline()['items'][0]['id']
    vault.set_date(a,'2002-03-04');scan(vault,sid,force=True)
    assert vault.detail(a)['captured_at']=='2002-03-04'
    assert vault.detail(a)['date_source']=='manual'


def test_unicode_notes_and_literal_search(vault,source):
    root,sid=source
    (root/'20180203_日记.txt').write_text('这一天我们在湖边。100% 很重要。',encoding='utf-8')
    scan(vault,sid)
    assert vault.timeline(query='湖边')['total']==1
    assert vault.timeline(query='%')['total']==1
    assert vault.timeline(query="' OR 1=1 --")['total']==0


def test_story_without_media(vault):
    vault.save_story('没有照片的夜晚','那一天决定离开',happened_at='2010-05-01')
    assert len(vault.stories())==1
    assert vault.stories()[0]['asset_ids']==[]


def test_story_foreign_key_rollback(vault):
    with pytest.raises(Exception):vault.save_story('坏引用','abc',asset_ids=['missing'])
    assert vault.stories()==[]


def test_symlink_escape_not_scanned(vault,source,tmp_path):
    if not hasattr(Path,'symlink_to'): pytest.skip('No symlinks')
    root,sid=source
    external=photo(tmp_path/'outside.jpg')
    try:(root/'escape.jpg').symlink_to(external)
    except OSError:pytest.skip('OS requires symlink privilege')
    scan(vault,sid)
    assert vault.summary()['assets']==0


def test_vault_source_rejected(vault):
    with pytest.raises(ValueError):vault.add_source(str(vault.root))


def test_cancel_does_not_mark_missing(vault,source):
    root,sid=source
    photo(root/'20100101_a.jpg');scan(vault,sid)
    result=vault.scan(sid,lambda *a:None,lambda:True)
    assert result['cancelled']
    assert vault.timeline()['items'][0]['available']==1


def test_vault_lock(vault):
    with pytest.raises(ValueError,match='已被'):Vault(vault.root)


def test_export_is_portable_not_biometric(vault,source):
    root,sid=source
    photo(root/'20100101_a.jpg');scan(vault,sid)
    a=vault.timeline()['items'][0]['id']
    vault.save_story('<script>bad</script>','<img src=x onerror=bad()>',asset_ids=[a])
    result=vault.export()
    with zipfile.ZipFile(result['path']) as z:
        manifest=z.read('manifest.json').decode()
        content=z.read('index.html').decode()
        assert str(root) not in manifest
        assert 'embedding' not in manifest.replace('face_embeddings','')
        assert '<script>bad' not in content
        assert '&lt;script&gt;bad' in content
        assert any(x.startswith('stories/') for x in z.namelist())
        assert not any('vault.sqlite' in x for x in z.namelist())


@pytest.mark.parametrize(('locale','lang','date_label'),[
    (None,'zh-CN','时间待确认'),('zh-CN','zh-CN','时间待确认'),
    ('en','en','Date unconfirmed'),('invalid','zh-CN','时间待确认'),
    (['en'],'zh-CN','时间待确认'),
])
def test_export_locale_changes_only_html_labels(vault,source,locale,lang,date_label):
    root,sid=source
    filename='记忆 & 回忆.jpg'
    photo(root/filename);scan(vault,sid)
    asset=vault.timeline()['items'][0]['id']
    title='我记得 <script>alert(1)</script>'
    body='未翻译的内容 & <img src=x onerror=bad()>'
    vault.save_story(title,body,asset_ids=[asset])
    service=Service()
    service.vault=vault
    try:
        result=service.call('export',{} if locale is None else {'locale':locale})
    finally:
        service.vault=None
        service.close()
    with zipfile.ZipFile(result['path']) as z:
        content=z.read('index.html').decode()
        assert f'<html lang="{lang}">' in content
        assert f'<small>{date_label}</small>' in content
        assert '我记得 &lt;script&gt;alert(1)&lt;/script&gt;' in content
        assert '未翻译的内容 &amp; &lt;img src=x onerror=bad()&gt;' in content
        assert 'alt="记忆 &amp; 回忆"' in content
        assert '<script>' not in content
        manifest=json.loads(z.read('manifest.json'))
        assert manifest['stories'][0]['title']==title
        assert manifest['stories'][0]['body']==body
        assert manifest['locations'][0]['relative_path']==filename
        md=z.read(f"stories/{manifest['stories'][0]['id']}.md").decode()
        assert f'# {title}\n\n{body}\n' in md


@pytest.mark.parametrize(('locale','empty_text'),[
    ('zh-CN','尚未写下故事。资料索引保存在 manifest.json 中。'),
    ('en','No stories yet. The archive index is in manifest.json.'),
])
def test_export_localizes_empty_state(vault,locale,empty_text):
    result=vault.export(locale)
    with zipfile.ZipFile(result['path']) as z:
        assert empty_text in z.read('index.html').decode()


class FakeEngine:
    """Test vectors only: these tests do NOT evaluate a real recognition model."""
    def __init__(self, same_frame=False):self.same_frame=same_frame
    def detect(self,path):
        x=dict(box='[0,0,0.5,0.5]',embedding=normalize([1,0,0]),confidence=0.99,
               crop=np.full((30,30,3),180,dtype=np.uint8))
        return [x,x.copy()] if self.same_frame else [x]


def face_seed(vault,source,same_frame=False):
    root,sid=source
    photo(root/'20100101_a.jpg');photo(root/'20150101_b.jpg',(25,50,75))
    scan(vault,sid)
    result=vault.analyze_faces(lambda *a:None,lambda:False,FakeEngine(same_frame))
    assert result['errors']==[]
    return result


def test_faces_cluster_and_period_filter(vault,source):
    assert face_seed(vault,source)['faces']==2
    people=vault.people()
    assert len(people)==1
    assert people[0]['count']==2
    assert vault.people(year='2010')[0]['count']==1
    assert vault.people(year='2022')==[]
    vault.rename_person(people[0]['id'],'朋友甲','大学时代')
    assert vault.people()[0]['name']=='朋友甲'


def test_same_frame_faces_do_not_auto_merge(vault,source):
    face_seed(vault,source,True)
    graph=vault.graph()
    assert len(graph['nodes'])>=2
    assert len(graph['edges'])>=1
    assert graph['relationships']==[]


def test_split_merge_and_rescan_corrections(vault,source):
    face_seed(vault,source)
    first=vault.people()[0]['id']
    face_id=vault.person_faces(first)['items'][0]['id']
    second=vault.split_face(face_id,'另一位')['person_id']
    assert len(vault.people())==2
    vault.analyze_faces(lambda *a:None,lambda:False,FakeEngine())
    assert len(vault.people())==2
    vault.add_relationship(first,second,'同学','2009-01-01','2013-07-01')
    assert len(vault.graph(year='2010')['relationships'])==1
    assert vault.graph(year='2020')['relationships']==[]
    vault.merge_people(first,second)
    assert len(vault.people())==1
    assert vault.graph()['relationships']==[]


def test_biometrics_erasure_retains_stories(vault,source):
    face_seed(vault,source)
    person=vault.people()[0]['id'];vault.rename_person(person,'旧友')
    vault.save_story('重逢','文字保留',person_ids=[person])
    vault.erase_biometrics()
    assert vault.people()[0]['name']=='旧友'
    assert vault.person_faces(person)['total']==0
    assert len(vault.stories())==1
    assert not list((vault.root/'faces').glob('*.jpg'))

@pytest.mark.parametrize('filename,expected',[
    ('IMG_19990103.JPG','1999-01-03'),('2023-02-29.jpg',None),('2024_02_29.jpg','2024-02-29'),
    ('photo.jpg',None),('1202301012.jpg',None)])
def test_filename_dates(filename,expected):assert date_from_filename(filename)==expected

@pytest.mark.parametrize('value',['2024-02-30','2024-13-01','2024','yesterday','20240101'])
def test_invalid_manual_dates(value):
    with pytest.raises(ValueError):checked_date(value)


def test_conservative_match():
    a=normalize([1,0]);b=normalize([0,1])
    assert candidate(a,{'a':a,'b':b})=='a'
    assert candidate(a,{'a':a,'b':a}) is None
    assert candidate(a,{'a':a},excluded={'a'}) is None
    with pytest.raises(ValueError):normalize([0,0])


def test_service_open_jobs_and_consent(tmp_path):
    service=Service()
    try:
        assert service.call('status')['vault'] is None
        with pytest.raises(ValueError):service.call('timeline')
        service.call('vault.open',{'path':str(tmp_path)})
        root=tmp_path/'originals';root.mkdir();photo(root/'20200101.jpg')
        source=service.call('source.add',{'path':str(root)})
        job=service.call('scan.start',{'source_id':source['id']})['job_id']
        for _ in range(100):
            state=service.call('job.status',{'job_id':job})
            if state['status']!='running':break
            time.sleep(.02)
        assert state['status']=='done'
        assert service.call('summary')['assets']==1
        with pytest.raises(ValueError,match='同意'):service.call('faces.start',{})
        with pytest.raises(ValueError):service.call('biometrics.erase',{})
    finally:service.close()


def test_merge_keeps_donor_name_and_notes(vault,source):
    face_seed(vault,source)
    first=vault.people()[0]['id']
    second=vault.split_face(vault.person_faces(first)['items'][0]['id'],'儿时昵称')['person_id']
    vault.rename_person(first,'成年名字','工作时期')
    vault.rename_person(second,'儿时昵称','童年时期')
    vault.save_story('小学','这是真实手写记录',person_ids=[second])
    vault.merge_people(first,second)
    person=vault.people()[0]
    assert person['name']=='成年名字'
    assert all(x in person['description'] for x in ['儿时昵称','工作时期','童年时期'])
    assert vault.stories()[0]['person_ids']==[first]


def test_partial_face_failure_rolls_back_centroid_and_crop(vault,source):
    root,sid=source
    photo(root/'20100101.jpg');photo(root/'20200101.jpg',(20,50,80));scan(vault,sid)
    class BrokenThenValid(FakeEngine):
        def detect(self,path):
            values=super().detect(path)
            if path.name.startswith('2010'):
                invalid=values[0].copy();invalid['crop']=None
                return values+[invalid]
            return values
    result=vault.analyze_faces(lambda *a:None,lambda:False,BrokenThenValid())
    assert len(result['errors'])==1
    assert result['faces']==1
    assert len(vault.people())==1
    assert len(list((vault.root/'faces').glob('*.jpg')))==1
