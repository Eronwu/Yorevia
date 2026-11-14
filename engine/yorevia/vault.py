"""The user's on-disk vault: stable content IDs, SQLite, and portable exports."""
from __future__ import annotations
import base64
from contextlib import contextmanager
from datetime import datetime, timezone
import html
import json
import os
from pathlib import Path
import sqlite3
import uuid
import zipfile
from .media import checked_date, extract, hash_file, is_placeholder, media_kind


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def uid() -> str:
    return uuid.uuid4().hex


def atomic_text(path: Path, content: str) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(content, encoding='utf-8')
    os.replace(temporary, path)


class Vault:
    def __init__(self, root: Path):
        self.root = root.expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for name in ('vault.sqlite', 'vault.sqlite-wal', 'vault.sqlite-shm', '.lock', 'vault.json',
                     'thumbs', 'faces', 'records', 'exports'):
            if (self.root / name).is_symlink():
                raise ValueError('资料库内部不允许符号链接。请选择独立的本地目录。')
        for name in ('thumbs', 'faces', 'records', 'exports'):
            (self.root / name).mkdir(exist_ok=True, mode=0o700)
        self._lock = (self.root / '.lock').open('a+b')
        try:
            if os.name == 'nt':
                import msvcrt
                self._lock.seek(0)
                if not self._lock.read(1):
                    self._lock.write(b'0'); self._lock.flush()
                self._lock.seek(0)
                msvcrt.locking(self._lock.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self._lock.close()
            raise ValueError('此资料库已被另一进程打开。请关闭后再试。') from exc
        try:
            with self.db() as db:
                version = db.execute('PRAGMA user_version').fetchone()[0]
                if version > 1:
                    raise ValueError('资料库来自更新版本，请升级 Yorevia 后打开。')
                db.execute('PRAGMA journal_mode=WAL')
                db.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))
            if not (self.root / 'vault.json').exists():
                atomic_text(self.root / 'vault.json', json.dumps({'format': 'yorevia-vault', 'version': 1,
                            'id': uid(), 'created_at': now()}, ensure_ascii=False, indent=2))
        except Exception:
            self._lock.close()
            raise

    @contextmanager
    def db(self):
        connection = sqlite3.connect(self.root / 'vault.sqlite', timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA foreign_keys=ON')
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def close(self) -> None:
        with self.db() as db:
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)')
        self._lock.close()

    def summary(self) -> dict:
        with self.db() as db:
            count = lambda table: db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
            years = [r[0] for r in db.execute("SELECT DISTINCT substr(captured_at,1,4) AS year FROM assets WHERE captured_at IS NOT NULL ORDER BY year DESC")]
            return {'path': str(self.root), 'assets': count('assets'), 'people': count('people'),
                    'stories': count('stories'), 'years': years,
                    'unknown_dates': db.execute('SELECT count(*) FROM assets WHERE captured_at IS NULL').fetchone()[0],
                    'sources': [dict(r) for r in db.execute('SELECT * FROM sources ORDER BY created_at')]}

    def add_source(self, path: str) -> dict:
        root = Path(path).expanduser().resolve(strict=True)
        if not root.is_dir() or root == self.root or root.is_relative_to(self.root):
            raise ValueError('请选原始资料目录，不能选资料库或其子目录。')
        with self.db() as db:
            existing = db.execute('SELECT * FROM sources WHERE root=?', (str(root),)).fetchone()
            if existing:
                return dict(existing)
            item = {'id': uid(), 'root': str(root), 'name': root.name or str(root), 'created_at': now()}
            db.execute('INSERT INTO sources VALUES(:id,:root,:name,:created_at)', item)
            return item

    def scan(self, source_id: str, progress, cancelled, force: bool = False) -> dict:
        with self.db() as db:
            source = db.execute('SELECT * FROM sources WHERE id=?', (source_id,)).fetchone()
        if not source:
            raise ValueError('资料来源不存在')
        root = Path(source['root'])
        if not root.is_dir():
            raise ValueError('来源目录不在线；原有索引保留，不会将离线磁盘误判为文件删除。')
        token, paths, errors = uid(), [], []
        walk_errors = []
        for parent, dirs, files in os.walk(root, followlinks=False, onerror=lambda e: walk_errors.append(str(e))):
            if cancelled():
                return {'cancelled': True, 'processed': 0, 'errors': []}
            base = Path(parent)
            dirs[:] = [n for n in sorted(dirs) if not n.startswith('.') and n not in {'node_modules', '__pycache__'}
                       and not (base/n).is_symlink() and not (base/n).resolve().is_relative_to(self.root)]
            for filename in sorted(files):
                path = base / filename
                if not path.is_symlink() and media_kind(path):
                    paths.append(path)
        processed = reused = added = placeholders = 0
        for path in paths:
            if cancelled():
                return {'cancelled': True, 'processed': processed, 'errors': errors}
            relative = path.relative_to(root).as_posix()
            try:
                before = path.stat()
                if is_placeholder(before):
                    placeholders += 1
                    # Keep an existing location alive, without downloading cloud-only bytes.
                    with self.db() as db:
                        db.execute('UPDATE locations SET scan_id=? WHERE source_id=? AND relative_path=?', (token, source_id, relative))
                    continue
                with self.db() as db:
                    previous = db.execute('SELECT * FROM locations WHERE source_id=? AND relative_path=?', (source_id, relative)).fetchone()
                    if previous and previous['size'] == before.st_size and previous['mtime_ns'] == before.st_mtime_ns and not force:
                        db.execute('UPDATE locations SET available=1,scan_id=? WHERE source_id=? AND relative_path=?', (token, source_id, relative))
                        reused += 1
                        continue
                asset_id = hash_file(path, cancelled)
                after = path.stat()
                if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
                    raise ValueError('扫描时文件正在改变，请完成复制后重新扫描')
                with self.db() as db:
                    exists = db.execute('SELECT id FROM assets WHERE id=?', (asset_id,)).fetchone()
                if not exists:
                    kind = media_kind(path)
                    values = extract(path, kind, self.root / 'thumbs' / f'{asset_id}.jpg')
                    with self.db() as db:
                        db.execute('''INSERT INTO assets(id,kind,title,captured_at,date_source,width,height,latitude,longitude,thumb,note_text,created_at)
                            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''', (asset_id, kind, path.stem, values['captured_at'], values['date_source'],
                            values['width'], values['height'], values['latitude'], values['longitude'], values['thumb'], values['note_text'], now()))
                    added += 1
                else:
                    reused += 1
                with self.db() as db:
                    db.execute('''INSERT INTO locations(source_id,relative_path,asset_id,size,mtime_ns,available,scan_id)
                        VALUES(?,?,?,?,?,1,?) ON CONFLICT(source_id,relative_path) DO UPDATE SET
                        asset_id=excluded.asset_id,size=excluded.size,mtime_ns=excluded.mtime_ns,available=1,scan_id=excluded.scan_id''',
                        (source_id, relative, asset_id, before.st_size, before.st_mtime_ns, token))
            except InterruptedError:
                return {'cancelled': True, 'processed': processed, 'errors': errors}
            except Exception as exc:
                if len(errors) < 100:
                    errors.append({'file': relative, 'message': str(exc)[:300]})
                # Failure is not deletion. Keep old references and report the error.
                with self.db() as db:
                    db.execute('UPDATE locations SET scan_id=? WHERE source_id=? AND relative_path=?', (token, source_id, relative))
            finally:
                processed += 1
                progress(processed, len(paths), path.name)
        # Incomplete traversal must not mark unseen files as deleted.
        if not walk_errors and not cancelled():
            with self.db() as db:
                db.execute('UPDATE locations SET available=0 WHERE source_id=? AND scan_id<>?', (source_id, token))
        return {'added': added, 'reused': reused, 'processed': processed, 'placeholders': placeholders,
                'errors': errors, 'walk_errors': walk_errors[:10], 'cancelled': cancelled()}

    @staticmethod
    def _filter(filters: dict, alias: str = 'a') -> tuple[str, list]:
        terms, params = [], []
        year = filters.get('year')
        if year == 'unknown':
            terms.append(f'{alias}.captured_at IS NULL')
        elif year and year != 'all':
            if len(str(year)) != 4 or not str(year).isdigit():
                raise ValueError('无效年份')
            terms.append(f'substr({alias}.captured_at,1,4)=?'); params.append(str(year))
        person = filters.get('person_id')
        if person:
            terms.append(f'EXISTS(SELECT 1 FROM faces f WHERE f.asset_id={alias}.id AND f.person_id=? AND f.ignored=0)'); params.append(person)
        query = str(filters.get('query', '')).strip()[:200]
        if query:
            # Literal substring search, with bound parameters. No SQL or HTML execution.
            escaped = query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
            terms.append(f"({alias}.title LIKE ? ESCAPE '\\' OR {alias}.note_text LIKE ? ESCAPE '\\' OR EXISTS(SELECT 1 FROM story_assets sa JOIN stories s ON s.id=sa.story_id WHERE sa.asset_id={alias}.id AND (s.body LIKE ? ESCAPE '\\' OR s.title LIKE ? ESCAPE '\\')))")
            params.extend([f'%{escaped}%']*4)
        return ' AND '.join(terms) or '1=1', params

    def timeline(self, **filters) -> dict:
        where, params = self._filter(filters)
        limit, offset = min(max(int(filters.get('limit', 60)), 1), 120), max(int(filters.get('offset', 0)), 0)
        with self.db() as db:
            total = db.execute(f'SELECT count(*) FROM assets a WHERE {where}', params).fetchone()[0]
            rows = db.execute(f'''SELECT a.id,a.kind,a.title,a.captured_at,a.date_source,a.width,a.height,a.thumb,
                EXISTS(SELECT 1 FROM locations l WHERE l.asset_id=a.id AND l.available=1) AS available,
                (SELECT count(DISTINCT person_id) FROM faces f WHERE f.asset_id=a.id AND f.ignored=0) AS people_count,
                (SELECT count(*) FROM story_assets s WHERE s.asset_id=a.id) AS story_count
                FROM assets a WHERE {where} ORDER BY a.captured_at IS NULL,a.captured_at DESC,a.id LIMIT ? OFFSET ?''', params+[limit,offset]).fetchall()
        return {'items': [dict(r) for r in rows], 'total': total, 'offset': offset, 'limit': limit}

    def asset_path(self, asset_id: str) -> Path:
        with self.db() as db:
            locations = db.execute('SELECT s.root,l.relative_path FROM locations l JOIN sources s ON s.id=l.source_id WHERE l.asset_id=? AND l.available=1', (asset_id,)).fetchall()
        for location in locations:
            root = Path(location['root']).resolve()
            path = root / location['relative_path']
            resolved = path.resolve()
            if resolved.is_relative_to(root) and not path.is_symlink() and resolved.is_file():
                return resolved
        raise ValueError('原文件暂时离线或已移动；请连接磁盘后重新扫描。故事与人物索引仍然保留。')

    def image(self, asset_id: str | None = None, face_id: str | None = None) -> dict:
        with self.db() as db:
            if face_id:
                row = db.execute('SELECT thumb FROM faces WHERE id=? AND ignored=0', (face_id,)).fetchone(); directory = 'faces'
            else:
                row = db.execute('SELECT thumb FROM assets WHERE id=?', (asset_id,)).fetchone(); directory = 'thumbs'
        if not row or not row['thumb']:
            return {'data': None}
        path = (self.root / directory / row['thumb']).resolve()
        if not path.is_relative_to(self.root / directory) or not path.is_file():
            return {'data': None}
        if path.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('缩略图超出安全大小')
        return {'data': 'data:image/jpeg;base64,' + base64.b64encode(path.read_bytes()).decode('ascii')}

    def detail(self, asset_id: str) -> dict:
        with self.db() as db:
            row = db.execute('SELECT * FROM assets WHERE id=?', (asset_id,)).fetchone()
            if not row:
                raise ValueError('资料不存在')
            item = dict(row)
            item['faces'] = [dict(r) for r in db.execute('''SELECT f.id,f.person_id,f.confidence,p.name,f.locked FROM faces f
                 JOIN people p ON p.id=f.person_id WHERE f.asset_id=? AND f.ignored=0''', (asset_id,))]
            item['stories'] = [dict(r) for r in db.execute('SELECT s.* FROM stories s JOIN story_assets sa ON sa.story_id=s.id WHERE sa.asset_id=? ORDER BY s.created_at', (asset_id,))]
            item['locations'] = [dict(r) for r in db.execute('SELECT s.name,l.relative_path,l.available FROM locations l JOIN sources s ON s.id=l.source_id WHERE l.asset_id=?', (asset_id,))]
            return item

    def set_date(self, asset_id: str, date: str | None) -> dict:
        date = checked_date(date)
        with self.db() as db:
            if not db.execute('SELECT 1 FROM assets WHERE id=?', (asset_id,)).fetchone():
                raise ValueError('资料不存在')
            db.execute("UPDATE assets SET captured_at=?,date_source='manual',date_manual=1 WHERE id=?", (date,asset_id))
        return {'ok': True}

    def people(self, **filters) -> list:
        where, params = self._filter(filters)
        period = filters.get('year') not in (None, '', 'all')
        with self.db() as db:
            rows = db.execute(f'''SELECT p.id,p.name,p.description,
               count(DISTINCT CASE WHEN {where} THEN a.id END) AS count,
               min(CASE WHEN {where} THEN a.captured_at END) AS first_seen,
               max(CASE WHEN {where} THEN a.captured_at END) AS last_seen,
               (SELECT f2.id FROM faces f2 WHERE f2.person_id=p.id AND f2.ignored=0 ORDER BY f2.confidence DESC LIMIT 1) AS face_id
               FROM people p LEFT JOIN faces f ON f.person_id=p.id AND f.ignored=0
               LEFT JOIN assets a ON a.id=f.asset_id GROUP BY p.id
               {'HAVING count>0' if period else ''} ORDER BY count DESC,p.created_at''', params*3).fetchall()
            return [dict(r) for r in rows]

    def rename_person(self, person_id: str, name: str, description: str = '') -> dict:
        if len(name) > 100 or len(description) > 5000:
            raise ValueError('名字或说明过长')
        with self.db() as db:
            if not db.execute('SELECT 1 FROM people WHERE id=?',(person_id,)).fetchone():
                raise ValueError('人物不存在')
            db.execute('UPDATE people SET name=?,description=? WHERE id=?', (name.strip(),description,person_id))
        return {'ok': True}

    def merge_people(self, keep: str, merge: str) -> dict:
        if keep == merge:
            raise ValueError('不能合并同一个人物')
        with self.db() as db:
            if db.execute('SELECT count(*) FROM people WHERE id IN (?,?)',(keep,merge)).fetchone()[0] != 2:
                raise ValueError('人物不存在')
            retained = db.execute('SELECT name,description FROM people WHERE id=?',(keep,)).fetchone()
            donor = db.execute('SELECT name,description FROM people WHERE id=?',(merge,)).fetchone()
            name = retained['name'] or donor['name']
            notes = [retained['description']] if retained['description'] else []
            if donor['name'] and donor['name'] != name:
                notes.append('曾用称呼：' + donor['name'])
            if donor['description'] and donor['description'] != retained['description']:
                notes.append(donor['description'])
            db.execute('UPDATE people SET name=?,description=? WHERE id=?',(name,'\n\n'.join(notes),keep))
            db.execute('UPDATE faces SET person_id=?,locked=1 WHERE person_id=?',(keep,merge))
            for row in db.execute('SELECT * FROM relationships WHERE a=? OR b=?',(merge,merge)).fetchall():
                a, b = (keep if row['a']==merge else row['a']), (keep if row['b']==merge else row['b'])
                if a==b:
                    db.execute('DELETE FROM relationships WHERE id=?',(row['id'],))
                else:
                    db.execute('UPDATE relationships SET a=?,b=? WHERE id=?',(a,b,row['id']))
            db.execute('INSERT OR IGNORE INTO story_people SELECT story_id,? FROM story_people WHERE person_id=?',(keep,merge))
            db.execute('DELETE FROM story_people WHERE person_id=?',(merge,))
            db.execute('DELETE FROM people WHERE id=?',(merge,))
        return {'ok': True}

    def split_face(self, face_id: str, name: str = '') -> dict:
        if len(name)>100:
            raise ValueError('名字过长')
        person_id=uid()
        with self.db() as db:
            if not db.execute('SELECT 1 FROM faces WHERE id=?',(face_id,)).fetchone():
                raise ValueError('人脸不存在')
            db.execute('INSERT INTO people VALUES(?,?,?,?)',(person_id,name.strip(),'',now()))
            db.execute('UPDATE faces SET person_id=?,locked=1 WHERE id=?',(person_id,face_id))
        return {'person_id':person_id}

    def person_faces(self, person_id: str, offset: int = 0) -> dict:
        with self.db() as db:
            rows = db.execute('''SELECT f.id,f.asset_id,f.locked,a.captured_at,a.title FROM faces f
               JOIN assets a ON a.id=f.asset_id WHERE f.person_id=? AND f.ignored=0
               ORDER BY a.captured_at DESC,f.id LIMIT 100 OFFSET ?''',(person_id,max(int(offset),0))).fetchall()
            total = db.execute('SELECT count(*) FROM faces WHERE person_id=? AND ignored=0',(person_id,)).fetchone()[0]
        return {'items':[dict(r) for r in rows], 'total':total}

    def graph(self, **filters) -> dict:
        where, params = self._filter(filters)
        with self.db() as db:
            edges = [dict(r) for r in db.execute(f'''SELECT f1.person_id AS a,f2.person_id AS b,count(DISTINCT a.id) AS count
                FROM faces f1 JOIN faces f2 ON f1.asset_id=f2.asset_id AND f1.person_id<f2.person_id
                JOIN assets a ON a.id=f1.asset_id WHERE f1.ignored=0 AND f2.ignored=0 AND {where}
                GROUP BY f1.person_id,f2.person_id ORDER BY count DESC LIMIT 300''',params)]
            relation = [dict(r) for r in db.execute('SELECT * FROM relationships')]
        year = filters.get('year')
        if year not in (None,'','all','unknown'):
            relation = [r for r in relation if (not r['start_date'] or r['start_date'][:4]<=year)
                        and (not r['end_date'] or r['end_date'][:4]>=year)]
        return {'nodes': self.people(**filters), 'edges': edges, 'relationships': relation}

    def add_relationship(self, a: str, b: str, label: str, start_date=None, end_date=None) -> dict:
        start_date,end_date=checked_date(start_date),checked_date(end_date)
        if a==b or not label.strip() or len(label)>100 or (start_date and end_date and start_date>end_date):
            raise ValueError('请检查关系双方、名称与起止日期')
        item=dict(id=uid(),a=a,b=b,label=label.strip(),start_date=start_date,end_date=end_date)
        with self.db() as db:
            db.execute('INSERT INTO relationships VALUES(:id,:a,:b,:label,:start_date,:end_date)',item)
        return item

    def save_story(self, title: str, body: str, happened_at=None, asset_ids=None, person_ids=None, story_id=None) -> dict:
        if not title.strip() or len(title)>200 or len(body)>200_000:
            raise ValueError('请填写标题；标题最多 200 字，正文最多 20 万字。')
        happened_at=checked_date(happened_at)
        stamp=now(); story_id=story_id or uid()
        with self.db() as db:
            previous=db.execute('SELECT created_at FROM stories WHERE id=?',(story_id,)).fetchone()
            db.execute('''INSERT INTO stories VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET
                title=excluded.title,body=excluded.body,happened_at=excluded.happened_at,updated_at=excluded.updated_at''',
                (story_id,title.strip(),body,happened_at,previous['created_at'] if previous else stamp,stamp))
            db.execute('DELETE FROM story_assets WHERE story_id=?',(story_id,))
            db.execute('DELETE FROM story_people WHERE story_id=?',(story_id,))
            for asset_id in set(asset_ids or []):
                db.execute('INSERT INTO story_assets VALUES(?,?)',(story_id,asset_id))
            for person_id in set(person_ids or []):
                db.execute('INSERT INTO story_people VALUES(?,?)',(story_id,person_id))
        return {'id':story_id}

    def stories(self) -> list:
        with self.db() as db:
            result=[]
            for row in db.execute('SELECT * FROM stories ORDER BY happened_at IS NULL,happened_at DESC,created_at DESC'):
                story=dict(row)
                story['asset_ids']=[r[0] for r in db.execute('SELECT asset_id FROM story_assets WHERE story_id=?',(row['id'],))]
                story['person_ids']=[r[0] for r in db.execute('SELECT person_id FROM story_people WHERE story_id=?',(row['id'],))]
                result.append(story)
            return result

    def analyze_faces(self, progress, cancelled, engine=None) -> dict:
        import numpy as np
        from PIL import Image
        from .faces import FaceEngine, candidate, normalize
        engine=engine or FaceEngine()
        with self.db() as db:
            assets=db.execute("SELECT id FROM assets a WHERE kind='photo' AND face_status<>'done' AND EXISTS(SELECT 1 FROM locations l WHERE l.asset_id=a.id AND l.available=1) ORDER BY captured_at,id").fetchall()
            prototypes={}
            for person in db.execute('SELECT id FROM people'):
                vectors=[np.frombuffer(r[0],dtype='<f4') for r in db.execute('SELECT embedding FROM faces WHERE person_id=? AND ignored=0',(person['id'],))]
                if vectors:
                    prototypes[person['id']]=normalize(np.mean(vectors,axis=0))
        errors=[]; added=0
        for index, asset in enumerate(assets):
            if cancelled():
                return {'cancelled':True,'faces':added,'errors':errors}
            created_thumbs = []
            try:
                detections=engine.detect(self.asset_path(asset['id']))
                used=set()
                next_prototypes = dict(prototypes)
                created_thumbs = []
                committed_faces = 0
                with self.db() as db:
                    for detection in detections:
                        vector=detection['embedding']; person_id=candidate(vector,next_prototypes,used)
                        if person_id is None:
                            person_id=uid()
                            db.execute('INSERT INTO people VALUES(?,?,?,?)',(person_id,'','',now()))
                        used.add(person_id)
                        face_id=uid(); thumb=f'{face_id}.jpg'
                        from .media import write_jpeg
                        created_thumbs.append(self.root/'faces'/thumb)
                        write_jpeg(Image.fromarray(detection['crop']),created_thumbs[-1],(160,160))
                        db.execute('INSERT INTO faces VALUES(?,?,?,?,?,?,?,0,0)',(face_id,asset['id'],person_id,detection['box'],
                                   np.asarray(vector,dtype='<f4').tobytes(),thumb,detection['confidence']))
                        vectors=[np.frombuffer(r[0],dtype='<f4') for r in db.execute('SELECT embedding FROM faces WHERE person_id=? AND ignored=0',(person_id,))]
                        next_prototypes[person_id]=normalize(np.mean(vectors,axis=0)); committed_faces+=1
                    db.execute("UPDATE assets SET face_status='done' WHERE id=?",(asset['id'],))
                prototypes = next_prototypes
                added += committed_faces
            except Exception as exc:
                for thumbnail in created_thumbs:
                    thumbnail.unlink(missing_ok=True)
                if len(errors)<100:
                    errors.append({'asset_id':asset['id'],'message':str(exc)[:300]})
                with self.db() as db:
                    db.execute("UPDATE assets SET face_status='error' WHERE id=?",(asset['id'],))
            progress(index+1,len(assets),'本地人像归类')
        return {'faces':added,'processed':len(assets),'errors':errors,'cancelled':False}

    def erase_biometrics(self) -> dict:
        # User-written names/stories/relationships survive; all biometric rows/crops are removed.
        with self.db() as db:
            db.execute('DELETE FROM faces')
            db.execute("UPDATE assets SET face_status='pending' WHERE kind='photo'")
        for file in (self.root/'faces').glob('*.jpg'):
            file.unlink(missing_ok=True)
        return {'ok':True,'note':'已移除逻辑记录与缓存，不保证 SSD、文件系统快照或旧备份中的物理抹除。'}

    def export(self) -> dict:
        """Portable, human-readable snapshot; no embeddings or original media bytes."""
        with self.db() as db:
            assets=[dict(r) for r in db.execute('SELECT id,kind,title,captured_at,date_source,thumb FROM assets ORDER BY captured_at')]
            people=[dict(r) for r in db.execute('SELECT * FROM people')]
            relations=[dict(r) for r in db.execute('SELECT * FROM relationships')]
            # Root paths and GPS omitted from export; relative location references are explicit.
            locations=[dict(r) for r in db.execute('SELECT s.name AS source,l.relative_path,l.asset_id FROM locations l JOIN sources s ON s.id=l.source_id')]
        stories=self.stories()
        manifest={'format':'yorevia-export','version':1,'created_at':now(),'assets':assets,'people':people,
                  'relationships':relations,'stories':stories,'locations':locations,
                  'omitted':['original_files','face_embeddings','absolute_source_paths','gps']}
        name='Yorevia-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uid()[:6]+'.zip'
        output=self.root/'exports'/name
        by_id={a['id']:a for a in assets}
        chapters=[]
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr('manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2))
            for story in reversed(stories):
                metadata={'id':story['id'],'date':story['happened_at'],'assets':story['asset_ids'],'people':story['person_ids']}
                archive.writestr(f"stories/{story['id']}.md",f"<!-- {json.dumps(metadata,ensure_ascii=False)} -->\n# {story['title']}\n\n{story['body']}\n")
                images=[]
                for asset_id in story['asset_ids']:
                    a=by_id.get(asset_id)
                    if a and a['thumb']:
                        images.append(f'<img src="thumbs/{html.escape(a["thumb"])}" alt="{html.escape(a["title"],quote=True)}">')
                chapters.append(f'<article><small>{html.escape(story["happened_at"] or "时间待确认")}</small><h2>{html.escape(story["title"])}</h2><p>{html.escape(story["body"])}</p>{"".join(images)}</article>')
            for a in assets:
                if a['thumb']:
                    path=(self.root/'thumbs'/a['thumb']).resolve()
                    if path.is_relative_to(self.root/'thumbs') and path.is_file():
                        archive.write(path,'thumbs/'+a['thumb'])
            markup='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Yorevia · 往途</title><style>body{background:#f5f2ea;color:#2f3631;max-width:800px;padding:50px 24px;margin:auto;font:18px/1.8 Georgia,serif}h1{font-size:64px;font-weight:400}h2{font-weight:400}p{white-space:pre-wrap}article{border-top:1px solid #d9d3c7;margin-top:50px;padding-top:20px;break-inside:avoid}img{max-width:100%;max-height:550px}small{color:#717a70}@media print{body{background:white}article{break-before:page}}</style><header><h1>Yorevia</h1><p>往途 · 记忆属于你。</p><small>个人档案导出 · 不含原始媒体和人脸特征向量</small></header>'''+''.join(chapters or ['<p>尚未写下故事。资料索引保存在 manifest.json 中。</p>'])+'</html>'
            archive.writestr('index.html',markup)
        return {'path':str(output),'filename':name,'size':output.stat().st_size}
