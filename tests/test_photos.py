import shutil
from datetime import datetime
from pathlib import Path

from assistant import config
from assistant.ingestion import photos

FIXTURES = Path(__file__).parent / "fixtures" / "photos"


def _copy_fixtures(dest: Path):
    for p in FIXTURES.iterdir():
        shutil.copy(p, dest / p.name)


def test_sidecar_classic(tmp_data):
    _copy_fixtures(tmp_data["photos"])
    photo = config.INGEST_PHOTOS / "IMG_001.jpg"
    idx = photos._index_sidecars(config.INGEST_PHOTOS)
    rec = photos.scan_photo(photo, idx)
    assert rec.taken_ts == 1686566400.0
    assert round(rec.lat, 3) == 15.552 and round(rec.lon, 3) == 73.752
    assert rec.people == ["Rahul Sharma", "Kalpesh"]


def test_sidecar_supplemental_and_zero_geo(tmp_data):
    _copy_fixtures(tmp_data["photos"])
    idx = photos._index_sidecars(config.INGEST_PHOTOS)
    rec = photos.scan_photo(config.INGEST_PHOTOS / "IMG_002.jpg", idx)
    assert rec.people == ["Aai"]
    assert rec.lat is None and rec.lon is None   # 0,0 ignored


def test_sidecar_duplicate_suffix(tmp_data):
    _copy_fixtures(tmp_data["photos"])
    idx = photos._index_sidecars(config.INGEST_PHOTOS)
    rec = photos.scan_photo(config.INGEST_PHOTOS / "IMG_003(1).jpg", idx)
    assert rec.people == ["Rahul"]   # matched the (1)-stripped sidecar


def test_exif_fallback(tmp_data):
    _copy_fixtures(tmp_data["photos"])
    idx = photos._index_sidecars(config.INGEST_PHOTOS)
    rec = photos.scan_photo(config.INGEST_PHOTOS / "no_sidecar.jpg", idx)
    # date comes from EXIF DateTimeOriginal
    assert datetime.fromtimestamp(rec.taken_ts).year == 2022
    # GPS Mumbai ~19.07 N, 72.87 E from EXIF
    assert 18.9 < rec.lat < 19.2 and 72.7 < rec.lon < 73.0


def test_discover_skips_videos_and_edited(tmp_data):
    _copy_fixtures(tmp_data["photos"])
    (config.INGEST_PHOTOS / "clip.mp4").write_bytes(b"x")
    # an -edited copy whose original exists should be skipped
    shutil.copy(config.INGEST_PHOTOS / "IMG_001.jpg",
                config.INGEST_PHOTOS / "IMG_001-edited.jpg")
    found, videos = photos.discover_photos()
    names = {p.name for p in found}
    assert "clip.mp4" not in names and videos == 1
    assert "IMG_001-edited.jpg" not in names
    assert "IMG_001.jpg" in names


def test_thumbnail(tmp_data):
    _copy_fixtures(tmp_data["photos"])
    ok = photos.make_thumbnail(config.INGEST_PHOTOS / "IMG_001.jpg", "abc123")
    assert ok and (config.THUMBS_DIR / "abc123.jpg").exists()


def test_match_person():
    contacts = ["Rahul", "Aai", "Amol Patil"]
    assert photos.match_person("Rahul Sharma", contacts) == "Rahul"
    assert photos.match_person("Aai", contacts) == "Aai"
    assert photos.match_person("Amol Patil", contacts) == "Amol Patil"
    assert photos.match_person("Totally Unknown Person", contacts) is None
