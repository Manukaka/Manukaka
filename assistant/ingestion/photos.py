"""Google Takeout photo ingestion: ZIP extraction, sidecar metadata, EXIF
fallback, thumbnails, and fuzzy person linking.

Takeout's sidecar naming is messy — `photo.jpg.json`,
`photo.jpg.supplemental-metadata.json`, 46-char truncated stems, `(1)` duplicate
suffixes. The reliable anchor is the `"title"` field inside each JSON, so we
index every sidecar in a directory by title first and fall back to filename
heuristics. Pillow (and pillow-heif for iPhone photos) are imported lazily.
"""
import difflib
import json
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .. import config

PHOTO_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".3gp", ".mkv", ".webm", ".m4v"}
EXTRACT_DIR_NAME = "_extracted"


@dataclass
class PhotoRecord:
    rel_path: str            # relative to ingest/photos/
    file_size: int
    mtime: float
    taken_ts: Optional[float] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
    people: List[str] = field(default_factory=list)
    width: Optional[int] = None
    height: Optional[int] = None


# ---------------------------------------------------------------- extraction

def extract_takeout_zips(status=print) -> List[Path]:
    """Extract Google Photos entries from new Takeout ZIPs. Returns processed zips."""
    photos_root = config.INGEST_PHOTOS
    done = []
    for zp in sorted(photos_root.glob("*.zip")):
        target = photos_root / EXTRACT_DIR_NAME / zp.stem
        if target.exists():
            continue  # already extracted on a previous run
        status(f"Extracting {zp.name}…")
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zp) as zf:
            members = [m for m in zf.namelist()
                       if "/google photos/" in m.lower() and not m.endswith("/")]
            for m in members:
                # Flatten "Takeout/Google Photos/<album>/<file>" → "<album>/<file>"
                parts = Path(m).parts
                try:
                    idx = [p.lower() for p in parts].index("google photos")
                except ValueError:
                    continue
                rel = Path(*parts[idx + 1:])
                if not rel.parts:
                    continue
                dest = target / rel
                if not str(dest.resolve()).startswith(str(target.resolve())):
                    continue  # zip-slip guard
                dest.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(m) as src, open(dest, "wb") as out:
                    out.write(src.read())
        done.append(zp)
    return done


def discover_photos() -> Tuple[List[Path], int]:
    """All photo files under ingest/photos (extracted or dropped as folders).
    Returns (photos, skipped_video_count). '-edited' copies are skipped when the
    original exists."""
    photos: List[Path] = []
    videos = 0
    for p in sorted(config.INGEST_PHOTOS.rglob("*")):
        if not p.is_file() or p.suffix.lower() == ".zip" or p.name == ".gitkeep":
            continue
        ext = p.suffix.lower()
        if ext in VIDEO_EXTS:
            videos += 1
            continue
        if ext not in PHOTO_EXTS:
            continue
        if "-edited" in p.stem.lower():
            original = p.with_name(p.name.replace("-edited", "").replace("-EDITED", ""))
            if original.exists():
                continue
        photos.append(p)
    return photos, videos


# ---------------------------------------------------------------- sidecars

def _index_sidecars(directory: Path) -> Dict[str, Path]:
    """Map sidecar 'title' (the original photo filename) → sidecar path."""
    index: Dict[str, Path] = {}
    for j in directory.glob("*.json"):
        try:
            data = json.loads(j.read_text(encoding="utf-8", errors="replace"))
        except (ValueError, OSError):
            continue
        title = data.get("title")
        if isinstance(title, str) and title:
            index.setdefault(title, j)
    return index


_DUP_RE = re.compile(r"^(.*?)(\(\d+\))(\.[^.]+)$")  # "IMG_1234(1).jpg"


def find_sidecar(photo: Path, sidecar_index: Dict[str, Path]) -> Optional[Path]:
    name = photo.name
    # 1. Exact title match (handles truncated/odd sidecar filenames)
    if name in sidecar_index:
        return sidecar_index[name]
    # 2. "(1)" duplicates: photo "IMG(1).jpg" ↔ sidecar of title "IMG.jpg"
    m = _DUP_RE.match(name)
    if m and (m.group(1) + m.group(3)) in sidecar_index:
        return sidecar_index[m.group(1) + m.group(3)]
    # 3. Filename heuristics
    for cand in (
        photo.with_name(name + ".json"),
        photo.with_name(name + ".supplemental-metadata.json"),
        photo.with_suffix(".json"),
    ):
        if cand.exists():
            return cand
    # 4. Truncated stems: any sidecar whose name starts with the (long) photo stem
    if len(photo.stem) > 40:
        for j in photo.parent.glob(photo.stem[:40] + "*.json"):
            return j
    return None


def parse_sidecar(sidecar: Path) -> dict:
    """Extract taken_ts, lat/lon, and people tags from a Takeout JSON sidecar."""
    out = {"taken_ts": None, "lat": None, "lon": None, "people": []}
    try:
        data = json.loads(sidecar.read_text(encoding="utf-8", errors="replace"))
    except (ValueError, OSError):
        return out
    ts = (data.get("photoTakenTime") or {}).get("timestamp")
    if ts:
        try:
            out["taken_ts"] = float(ts)
        except (TypeError, ValueError):
            pass
    geo = data.get("geoData") or {}
    lat, lon = geo.get("latitude"), geo.get("longitude")
    if lat and lon and not (lat == 0.0 and lon == 0.0):
        out["lat"], out["lon"] = float(lat), float(lon)
    out["people"] = [p.get("name") for p in (data.get("people") or [])
                     if isinstance(p, dict) and p.get("name")]
    return out


# ---------------------------------------------------------------- EXIF fallback

def parse_exif(photo: Path) -> dict:
    """taken_ts + GPS from the image itself, for photos without a sidecar."""
    out = {"taken_ts": None, "lat": None, "lon": None, "people": []}
    try:
        img = _open_image(photo)
        exif = img.getexif()
    except Exception:
        return out
    # 0x9003 DateTimeOriginal lives in the Exif sub-IFD; 0x0132 DateTime in main
    dt = None
    try:
        sub = exif.get_ifd(0x8769)
        dt = sub.get(0x9003)
    except Exception:
        pass
    dt = dt or exif.get(0x0132)
    if isinstance(dt, str):
        try:
            from datetime import datetime
            out["taken_ts"] = datetime.strptime(dt.strip(), "%Y:%m:%d %H:%M:%S").timestamp()
        except ValueError:
            pass
    try:
        gps = exif.get_ifd(0x8825)
        lat = _dms_to_deg(gps.get(2), gps.get(1))
        lon = _dms_to_deg(gps.get(4), gps.get(3))
        if lat is not None and lon is not None:
            out["lat"], out["lon"] = lat, lon
    except Exception:
        pass
    return out


def _dms_to_deg(dms, ref) -> Optional[float]:
    if not dms or len(dms) != 3:
        return None
    deg = float(dms[0]) + float(dms[1]) / 60 + float(dms[2]) / 3600
    if ref in ("S", "W"):
        deg = -deg
    return deg


# ---------------------------------------------------------------- images

_heif_registered = False


def _open_image(path: Path):
    global _heif_registered
    from PIL import Image
    if path.suffix.lower() == ".heic" and not _heif_registered:
        try:
            from pillow_heif import register_heif_opener
            register_heif_opener()
        except ImportError:
            pass
        _heif_registered = True
    return Image.open(path)


def make_thumbnail(photo: Path, photo_id: str) -> bool:
    """320px JPEG thumbnail into data/thumbs/<photo_id>.jpg."""
    try:
        from PIL import ImageOps
        img = _open_image(photo)
        img = ImageOps.exif_transpose(img).convert("RGB")
        size = config.CFG["photos"]["thumb_px"]
        img.thumbnail((size, size))
        config.THUMBS_DIR.mkdir(parents=True, exist_ok=True)
        img.save(config.THUMBS_DIR / f"{photo_id}.jpg", "JPEG", quality=80)
        return True
    except Exception:
        return False


def downscaled_jpeg_b64(photo: Path) -> Optional[str]:
    """Base64 JPEG ≤ caption_max_px on the long side — what the vision model sees."""
    import base64
    import io
    try:
        from PIL import ImageOps
        img = _open_image(photo)
        img = ImageOps.exif_transpose(img).convert("RGB")
        max_px = config.CFG["photos"]["caption_max_px"]
        img.thumbnail((max_px, max_px))
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=85)
        return base64.b64encode(buf.getvalue()).decode("ascii")
    except Exception:
        return None


def image_size(photo: Path) -> Tuple[Optional[int], Optional[int]]:
    try:
        img = _open_image(photo)
        return img.width, img.height
    except Exception:
        return None, None


# ---------------------------------------------------------------- people match

def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def match_person(tag: str, contacts: List[str]) -> Optional[str]:
    """Fuzzy-match a Takeout people tag ('Rahul Sharma') to a chat contact ('Rahul').

    Returns the matched contact name, or None."""
    tag_n = _norm(tag)
    tag_tokens = set(tag_n.split())
    best, best_score = None, 0.0
    for contact in contacts:
        c_n = _norm(contact)
        if c_n == tag_n:
            return contact
        c_tokens = set(c_n.split())
        # token-subset: "rahul" ⊆ "rahul sharma" either direction
        if c_tokens <= tag_tokens or tag_tokens <= c_tokens:
            score = 0.9
        else:
            score = difflib.SequenceMatcher(None, tag_n, c_n).ratio()
        if score > best_score:
            best, best_score = contact, score
    return best if best_score >= 0.75 else None


# ---------------------------------------------------------------- top level

def scan_photo(photo: Path, sidecar_index: Dict[str, Path]) -> PhotoRecord:
    """Full metadata for one photo: sidecar first, EXIF fallback, mtime last."""
    stat = photo.stat()
    rec = PhotoRecord(
        rel_path=str(photo.relative_to(config.INGEST_PHOTOS)),
        file_size=stat.st_size, mtime=stat.st_mtime,
    )
    sidecar = find_sidecar(photo, sidecar_index)
    meta = parse_sidecar(sidecar) if sidecar else {}
    if not meta.get("taken_ts") or (meta.get("lat") is None):
        exif = parse_exif(photo)
        meta = {
            "taken_ts": meta.get("taken_ts") or exif["taken_ts"],
            "lat": meta.get("lat") if meta.get("lat") is not None else exif["lat"],
            "lon": meta.get("lon") if meta.get("lon") is not None else exif["lon"],
            "people": meta.get("people") or [],
        }
    rec.taken_ts = meta.get("taken_ts") or stat.st_mtime
    rec.lat, rec.lon = meta.get("lat"), meta.get("lon")
    rec.people = meta.get("people") or []
    rec.width, rec.height = image_size(photo)
    return rec
