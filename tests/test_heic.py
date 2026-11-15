"""Synthetic HEIC round-trip: decoder plumbing, not real-camera coverage."""
from PIL import Image
import pillow_heif
from yorevia.media import extract, load_photo


def test_synthetic_heic_decode_and_thumbnail(tmp_path):
    source = tmp_path / '20241115-memory.heic'
    pillow_heif.from_pillow(Image.new('RGB', (96, 64), (80, 120, 160))).save(source)
    image = load_photo(source)
    assert image.mode == 'RGB'
    assert image.size == (96, 64)
    thumb = tmp_path / 'thumb.jpg'
    metadata = extract(source, 'photo', thumb)
    assert metadata['width'] == 96
    assert metadata['height'] == 64
    assert metadata['captured_at'] == '2024-11-15'
    assert metadata['date_source'] == 'filename'
    assert thumb.is_file()
