"""Read-only metadata extraction. A filesystem mtime is never a life-event date."""
from __future__ import annotations
import hashlib
import os
import re
import stat
from datetime import datetime
from pathlib import Path
from typing import Callable

PHOTOS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif', '.heic', '.heif'}
VIDEOS = {'.mp4', '.mov', '.m4v', '.avi', '.mkv'}
NOTES = {'.md', '.txt'}
MAX_PIXELS = 80_000_000


def media_kind(path: Path) -> str | None:
    suffix = path.suffix.lower()
    return 'photo' if suffix in PHOTOS else 'video' if suffix in VIDEOS else 'note' if suffix in NOTES else None


def date_from_filename(name: str) -> str | None:
    match = re.search(r'(?<!\d)((?:19|20)\d{2})[-_]?([01]\d)[-_]?([0-3]\d)(?!\d)', name)
    if not match:
        return None
    try:
        return datetime(*(int(x) for x in match.groups())).date().isoformat()
    except ValueError:
        return None


def checked_date(value: str | None) -> str | None:
    if not value:
        return None
    # Only complete, unambiguous calendar dates in V0.1. No guessed birthdays/years.
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
        raise ValueError('日期必须为 YYYY-MM-DD；不确定时请留空。')
    return datetime.strptime(value, '%Y-%m-%d').date().isoformat()


def is_placeholder(info: os.stat_result) -> bool:
    attrs = getattr(info, 'st_file_attributes', 0)
    flags = (getattr(stat, 'FILE_ATTRIBUTE_OFFLINE', 0x1000) | 0x00400000 | 0x00040000)
    return bool(attrs & flags) or bool(getattr(info, 'st_flags', 0) & 0x40000000)


def hash_file(path: Path, cancelled: Callable[[], bool] = lambda: False) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        while block := handle.read(1024 * 1024):
            if cancelled():
                raise InterruptedError('已取消')
            digest.update(block)
    return digest.hexdigest()


def load_photo(path: Path):
    from PIL import Image, ImageOps
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    if path.suffix.lower() in {'.heic', '.heif'}:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError as exc:
            raise ValueError('此构建未包含 HEIC 解码器；请使用 JPEG，或安装 pillow-heif。') from exc
    with Image.open(path) as source:
        if source.width * source.height > MAX_PIXELS:
            raise ValueError('图片超过 8000 万像素安全上限')
        return ImageOps.exif_transpose(source).convert('RGB')


def write_jpeg(image, destination: Path, size: tuple[int, int] = (1280, 960)) -> None:
    image.thumbnail(size)
    temporary = destination.with_suffix('.tmp')
    image.save(temporary, format='JPEG', quality=83, optimize=True)
    os.replace(temporary, destination)


def extract(path: Path, kind: str, thumb: Path) -> dict:
    result = dict(captured_at=date_from_filename(path.name), date_source='filename',
                  width=None, height=None, latitude=None, longitude=None, thumb=None, note_text='')
    if result['captured_at'] is None:
        result['date_source'] = 'unknown'
    if kind == 'note':
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ValueError('文字文件超过 8 MiB，未读取内容')
        result['note_text'] = path.read_text(encoding='utf-8-sig', errors='replace')
    elif kind == 'photo':
        from PIL import Image
        image = load_photo(path)
        result['width'], result['height'] = image.size
        with Image.open(path) as original:
            exif = original.getexif()
            try:
                sub = exif.get_ifd(0x8769)
            except Exception:
                sub = {}
            # DateTimeOriginal, not modification time.
            value = sub.get(36867) or exif.get(36867)
            if value:
                try:
                    result['captured_at'] = datetime.strptime(str(value)[:19], '%Y:%m:%d %H:%M:%S').isoformat()
                    result['date_source'] = 'exif'
                except ValueError:
                    pass
            try:
                gps = exif.get_ifd(0x8825)
                def degrees(v):
                    return float(v[0]) + float(v[1]) / 60 + float(v[2]) / 3600
                if gps.get(2) and gps.get(4):
                    result['latitude'] = degrees(gps[2]) * (-1 if gps.get(1) == 'S' else 1)
                    result['longitude'] = degrees(gps[4]) * (-1 if gps.get(3) == 'W' else 1)
            except (KeyError, TypeError, ValueError, ZeroDivisionError):
                pass
        write_jpeg(image, thumb)
        result['thumb'] = str(thumb.name)
    elif kind == 'video':
        # Video container dates vary by camera/timezone. V0.1 uses a labelled filename
        # date or keeps it unknown; it does not invent a shooting time from mtime.
        import cv2
        cap = cv2.VideoCapture(str(path))
        try:
            ok, frame = cap.read()
            if ok:
                from PIL import Image
                result['height'], result['width'] = frame.shape[:2]
                write_jpeg(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), thumb)
                result['thumb'] = str(thumb.name)
        finally:
            cap.release()
    return result
