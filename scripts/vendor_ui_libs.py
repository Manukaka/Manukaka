"""Download the UI's JavaScript/GeoJSON dependencies into assistant/ui/vendor/.

These files are committed to the repo so the end user never needs internet for
them. Run this only when bumping a version. Pinned on purpose.
"""
import sys
import urllib.request
from pathlib import Path

VENDOR = Path(__file__).resolve().parent.parent / "assistant" / "ui" / "vendor"

ASSETS = {
    # 3d-force-graph bundles three.js internally — no separate three.min.js needed
    "3d-force-graph.min.js": "https://unpkg.com/3d-force-graph@1.80.0/dist/3d-force-graph.min.js",
    "force-graph.min.js": "https://unpkg.com/force-graph@1.51.4/dist/force-graph.min.js",
    # Natural Earth 1:110m countries (small, fine for pin context)
    "world-110m.geojson": "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/"
                          "master/geojson/ne_110m_admin_0_countries.geojson",
}


def main():
    VENDOR.mkdir(parents=True, exist_ok=True)
    for name, url in ASSETS.items():
        dest = VENDOR / name
        print(f"Downloading {name} …")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Manu-vendor"})
            with urllib.request.urlopen(req, timeout=60) as r:
                dest.write_bytes(r.read())
            print(f"  -> {dest} ({dest.stat().st_size // 1024} kB)")
        except Exception as e:
            print(f"  FAILED: {e}", file=sys.stderr)


if __name__ == "__main__":
    main()
