"""Offline reverse geocoding (GPS → "Baga, Goa, India") via reverse_geocoder.

The library bundles GeoNames data, so it works with no internet. Quirks handled
here: mode=1 (the default multiprocessing mode misbehaves on Windows), lazy load
(first call reads ~100MB into RAM), and graceful degradation — a geocoding
failure must never break ingestion, photos just get no place name.
"""
from typing import List, Optional, Tuple

_rg = None
_failed = False

COUNTRY_NAMES = {
    "IN": "India", "US": "United States", "GB": "United Kingdom", "AE": "UAE",
    "SG": "Singapore", "TH": "Thailand", "NP": "Nepal", "LK": "Sri Lanka",
    "MY": "Malaysia", "ID": "Indonesia", "VN": "Vietnam", "JP": "Japan",
    "CN": "China", "AU": "Australia", "NZ": "New Zealand", "CA": "Canada",
    "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain",
    "CH": "Switzerland", "NL": "Netherlands", "RU": "Russia", "BR": "Brazil",
    "ZA": "South Africa", "EG": "Egypt", "TR": "Turkey", "SA": "Saudi Arabia",
    "QA": "Qatar", "KW": "Kuwait", "OM": "Oman", "BH": "Bahrain",
    "BD": "Bangladesh", "PK": "Pakistan", "MM": "Myanmar", "BT": "Bhutan",
    "MV": "Maldives", "KR": "South Korea", "HK": "Hong Kong", "TW": "Taiwan",
    "PH": "Philippines", "KH": "Cambodia", "MU": "Mauritius", "KE": "Kenya",
    "TZ": "Tanzania", "MX": "Mexico", "AT": "Austria",
    "BE": "Belgium", "SE": "Sweden", "NO": "Norway", "DK": "Denmark",
    "FI": "Finland", "PT": "Portugal", "GR": "Greece", "IE": "Ireland",
    "CZ": "Czechia", "PL": "Poland", "HU": "Hungary", "IL": "Israel",
}


def _get_rg():
    global _rg, _failed
    if _rg is None and not _failed:
        try:
            import reverse_geocoder
            _rg = reverse_geocoder
        except Exception:
            _failed = True
    return _rg


def lookup_many(coords: List[Tuple[float, float]]) -> List[Optional[dict]]:
    """Batch lookup. Returns {name, admin, cc, country} per coord, or None on failure."""
    rg = _get_rg()
    if rg is None or not coords:
        return [None] * len(coords)
    try:
        results = rg.search(coords, mode=1)
    except Exception:
        return [None] * len(coords)
    out = []
    for r in results:
        cc = r.get("cc", "")
        out.append({
            "name": r.get("name", ""),
            "admin": r.get("admin1", ""),
            "cc": cc,
            "country": COUNTRY_NAMES.get(cc, cc),
        })
    return out


def place_label(name: str, admin: str, country: str) -> str:
    parts = [p for p in (name, admin, country) if p]
    return ", ".join(dict.fromkeys(parts))  # dedupe while keeping order
