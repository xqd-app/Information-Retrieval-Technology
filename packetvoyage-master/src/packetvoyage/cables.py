"""Submarine-cable matching for educational path analysis.

A bundled snapshot of all cable systems from TeleGeography's Submarine Cable
Map (submarinecablemap.com API v3): every cable with name, total length, RFS
year, owners, its coastal landing points (lat/lon) and the cable's actual surveyed
path as simplified per-segment polylines (``segments``), so routes can be drawn
along real cable geometry instead of great circles between landings. The snapshot
lives in ``data/cables.json``, is shipped inside the package, and is only read at
runtime - no network I/O on the matching path.
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import math
import os
import re
import threading
import time
import urllib.request
from datetime import date, datetime, timezone
from importlib.resources import files
from pathlib import Path
from typing import Any

from packetvoyage import geo

logger = logging.getLogger("packetvoyage.cables")


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


SNAPSHOT_LIFETIME_DAYS = 7
SNAPSHOT_FORMAT = 2
_LANDING_RADIUS_KM = 300.0
_LOOSE_RADIUS_KM = 500.0
_MAX_CANDIDATES = 3

_CABLE_GEO_URL = "https://www.submarinecablemap.com/api/v3/cable/cable-geo.json"
_LANDING_POINT_GEO_URL = (
    "https://www.submarinecablemap.com/api/v3/landing-point/landing-point-geo.json"
)
_CABLE_DETAIL_URL = "https://www.submarinecablemap.com/api/v3/cable/{id}.json"
_CATALOG_URL = "https://www.submarinecablemap.com/api/v3/cable/all.json"

_cache: list[dict[str, Any]] | None = None
_snapshot_at: date | None = None
_auto_refresh = False
_refresh_started = False
_refresh_error: str | None = None
_refresh_lock = threading.Lock()


def _bundled_snapshot() -> dict[str, Any] | None:
    """The bundled data/cables.json as a dict, or None when missing/broken."""
    try:
        raw = json.loads(files("packetvoyage").joinpath("data", "cables.json").read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None
    return raw if isinstance(raw, dict) and raw.get("cables") else None


def _load() -> list[dict[str, Any]]:
    """Load and cache the bundled cable snapshot."""
    global _cache, _snapshot_at
    if _cache is None:
        bundled = _bundled_snapshot()
        if bundled is None:
            _cache = []
            _snapshot_at = None
            logger.warning("bundled cable snapshot missing -> no cable annotations")
        else:
            _cache = bundled.get("cables") or []
            _snapshot_at = _parse_date(bundled.get("updated_at"))
    return _cache


def cable_count() -> int:
    """Number of cables in the bundled snapshot."""
    return len(_load())


def cable_by_id(cable_id: Any) -> dict[str, Any] | None:
    """The full cable record or None."""
    for c in _load():
        if str(c.get("id")) == str(cable_id):
            return c
    return None


def _parse_date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None
    return None


def _fetch_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=120) as r:
        return json.load(r)


def snapshot_status() -> dict[str, Any]:
    """Freshness/refresh diagnostics."""
    _load()
    return {
        "updated_at": _snapshot_at.isoformat() if _snapshot_at else None,
        "snapshot_expired": snapshot_expired(),
        "auto_refresh": _auto_refresh,
        "refresh_in_progress": _refresh_started,
        "last_error": _refresh_error,
        "cable_count": len(_cache or []),
    }


def set_auto_refresh(enabled: bool) -> None:
    global _auto_refresh
    _auto_refresh = enabled


def snapshot_expired() -> bool:
    _load()
    if _snapshot_at is None:
        return True
    return (_today_utc() - _snapshot_at).days >= SNAPSHOT_LIFETIME_DAYS


def maybe_refresh() -> None:
    global _refresh_started
    if not _auto_refresh or not snapshot_expired():
        return
    with _refresh_lock:
        if _refresh_started:
            return
        _refresh_started = True
    threading.Thread(target=_refresh_worker, name="cable-refresh", daemon=True).start()


def _refresh_worker() -> None:
    global _cache, _snapshot_at, _refresh_error
    try:
        snap = fetch_and_build_snapshot()
        new_cables = (snap or {}).get("cables") or []
        if not new_cables:
            raise ValueError("refreshed snapshot contains no cables")
        current_ids = sorted(str(c.get("id")) for c in (_cache or []))
        new_ids = sorted(str(c.get("id")) for c in new_cables)
        if current_ids and current_ids == new_ids:
            logger.info("cable catalog unchanged - already current")
            _refresh_error = None
            return
        _cache = new_cables
        _snapshot_at = _parse_date(snap.get("updated_at"))
        _refresh_error = None
        if not _save_to_disk(snap):
            logger.warning("cable snapshot refreshed but could not be persisted")
        logger.info("cable snapshot refreshed to %s (%d cables)", _snapshot_at, len(new_cables))
    except Exception as exc:  # noqa: BLE001
        _refresh_error = f"{type(exc).__name__}: {exc}"
        logger.warning("cable snapshot refresh failed, keeping last snapshot: %s", exc)


def _save_to_disk(snapshot: dict[str, Any]) -> bool:
    try:
        path = Path(str(files("packetvoyage").joinpath("data", "cables.json")))
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")))
        os.replace(tmp, path)
        return True
    except OSError as exc:
        logger.warning("cannot persist cable snapshot to disk: %s", exc)
        return False


_PARSED_KM_RE = re.compile(r"([\d,]+)")
_RFS_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def _parse_length(text: str | None) -> int | None:
    if not text:
        return None
    m = _PARSED_KM_RE.search(text.replace(",", ""))
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None


def _parse_rfs_year(rfs_year: Any, rfs: Any) -> int | None:
    if isinstance(rfs_year, int):
        return rfs_year
    m = _RFS_YEAR_RE.search(str(rfs or ""))
    return int(m.group(0)) if m else None


def _polyline_length_km(coords: list) -> float:
    total = 0.0
    for i in range(len(coords) - 1):
        x1, y1 = coords[i]
        x2, y2 = coords[i + 1]
        total += geo.haversine_km(float(y1), float(x1), float(y2), float(x2))
    return total


def _simplify_segment(
    points: list[list[float]],
    tolerance_km: float = 8.0,
    max_points: int = 120,
) -> list[list[float]]:
    n = len(points)
    if n <= 2:
        return points[:]
    tolerance = tolerance_km
    while True:
        keep = [False] * n
        keep[0] = keep[n - 1] = True
        stack: list[tuple[int, int]] = [(0, n - 1)]
        while stack:
            start, end = stack.pop()
            if end - start < 2:
                continue
            a, b = points[start], points[end]
            ax, ay, bx, by = a[0], a[1], b[0], b[1]
            chord = geo.haversine_km(ax, ay, bx, by)
            if chord < 1e-6:
                max_d, max_i = 0.0, -1
                for i in range(start + 1, end):
                    d = geo.haversine_km(ax, ay, points[i][0], points[i][1])
                    if d > max_d:
                        max_d, max_i = d, i
            else:
                max_d, max_i = -1.0, -1
                for i in range(start + 1, end):
                    px, py = points[i][0], points[i][1]
                    cross = abs((ax - px) * (by - ay) - (bx - ax) * (ay - py)) / max(
                        1e-6, math.hypot(bx - ax, by - ay)
                    )
                    cross_km = cross * 110.0
                    if cross_km > max_d:
                        max_d, max_i = cross_km, i
            if max_d > tolerance and max_i > 0:
                keep[max_i] = True
                stack.append((start, max_i))
                stack.append((max_i, end))
        out = [p for p, k in zip(points, keep) if k] or [points[0], points[-1]]
        if len(out) <= max_points:
            return out
        tolerance *= 1.6
        if tolerance > 200.0:
            step = max(1, (n - 1) // max_points)
            return out[::step][:max_points]


def fetch_and_build_snapshot(
    deadline_seconds: float = 420.0,
) -> dict[str, Any]:
    deadline_until = time.monotonic() + deadline_seconds
    bundled = _bundled_snapshot()
    try:
        catalog = _fetch_json(_CATALOG_URL)
        catalog_ids = sorted(str(c["id"]) for c in catalog)
    except (OSError, json.JSONDecodeError, KeyError):
        catalog_ids = None
    if (
        bundled is not None
        and bundled.get("format") == SNAPSHOT_FORMAT
        and catalog_ids is not None
        and catalog_ids == sorted(str(c.get("id")) for c in bundled["cables"])
    ):
        return bundled

    cables_geo = _fetch_json(_CABLE_GEO_URL)
    lps = _fetch_json(_LANDING_POINT_GEO_URL)
    lp_by_id = {
        f["properties"]["id"]: {
            "id": f["properties"]["id"],
            "name": f["properties"]["name"],
            "lat": f["geometry"]["coordinates"][1],
            "lon": f["geometry"]["coordinates"][0],
        }
        for f in lps["features"]
    }

    ids: list[str] = []
    geo_len: dict[str, float] = {}
    geo_segments: dict[str, list[list[list[float]]]] = {}
    for f in cables_geo["features"]:
        cid = f["properties"]["id"]
        if cid not in ids:
            ids.append(cid)
        segs: list[list[list[float]]] = []
        for line in f["geometry"]["coordinates"]:
            pts = [[float(p[1]), float(p[0])] for p in line]
            segs.append(_simplify_segment(pts))
        geo_len[cid] = geo_len.get(cid, 0.0) + sum(
            _polyline_length_km(line) for line in f["geometry"]["coordinates"]
        )
        geo_segments[cid] = segs

    def get(cid: str) -> dict[str, Any]:
        last: Exception | None = None
        for attempt in range(3):
            if time.monotonic() > deadline_until:
                raise TimeoutError("cable snapshot fetch exceeded deadline")
            try:
                return _fetch_json(_CABLE_DETAIL_URL.format(id=cid))
            except (OSError, json.JSONDecodeError, KeyError) as exc:
                last = exc
                time.sleep(0.3 * (2**attempt) + (attempt * 0.15))
        logger.warning("cable detail fetch failed for %s (%d tries): %s", cid, 3, last)
        return {}

    built: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=24) as ex:
        for d in ex.map(get, ids):
            if not d:
                continue
            lps_out = [
                {
                    "id": lp.get("id"),
                    "name": lp.get("name"),
                    "country": lp.get("country"),
                    "lat": (lp_by_id.get(lp.get("id")) or {}).get("lat"),
                    "lon": (lp_by_id.get(lp.get("id")) or {}).get("lon"),
                }
                for lp in d.get("landing_points") or []
            ]
            built.append(
                {
                    "id": d["id"],
                    "name": d.get("name"),
                    "length_km": _parse_length(d.get("length")),
                    "length_km_computed": round(geo_len.get(d["id"], 0.0)),
                    "rfs_year": _parse_rfs_year(d.get("rfs_year"), d.get("rfs")),
                    "is_planned": bool(d.get("is_planned")),
                    "owners": [o.strip() for o in (d.get("owners") or "").split(",") if o.strip()],
                    "url": d.get("url"),
                    "landing_points": [lp for lp in lps_out if lp["lat"] is not None],
                    "segments": geo_segments.get(d["id"]) or [],
                }
            )
    built.sort(key=lambda c: c["name"] or "")
    return {
        "source": "TeleGeography Submarine Cable Map (submarinecablemap.com API v3)",
        "updated_at": _today_utc().isoformat(),
        "description": "Static copy of all cable systems and landing points",
        "format": SNAPSHOT_FORMAT,
        "cables": built,
    }


def _usable_length(c: dict[str, Any]) -> float | None:
    return c.get("length_km") or c.get("length_km_computed")


def _nearest(cable: dict[str, Any], lat: float, lon: float) -> tuple[dict[str, Any] | None, float]:
    """Nearest landing point of a cable to (lat, lon): (lp, distance_km)."""
    best_lp, best_d = None, float("inf")
    for lp in cable.get("landing_points") or []:
        if lp.get("lat") is None or lp.get("lon") is None:
            continue
        d = geo.haversine_km(lat, lon, lp["lat"], lp["lon"])
        if d < best_d:
            best_d, best_lp = d, lp
    return best_lp, best_d


def cable_candidates(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    *,
    max_landing_km: float = _LANDING_RADIUS_KM,
    limit: int = _MAX_CANDIDATES,
) -> list[dict[str, Any]]:
    """Best-effort cable systems whose landing points sit near both ends of a leg."""
    if not (lat1 and lon1 and lat2 and lon2):
        return []
    d_endpoints = geo.haversine_km(lat1, lon1, lat2, lon2)
    hits: list[dict[str, Any]] = []
    for c in _load():
        lps = c.get("landing_points") or []
        if len(lps) < 2:
            continue
        lp1, d1 = _nearest(c, lat1, lon1)
        lp2, d2 = _nearest(c, lat2, lon2)
        if lp1 is None or lp2 is None or lp1.get("id") == lp2.get("id"):
            continue
        if d1 > max_landing_km or d2 > max_landing_km:
            continue
        length = _usable_length(c)
        if length and length < 0.4 * d_endpoints:
            continue
        hits.append(
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "length_km": c.get("length_km"),
                "rfs_year": c.get("rfs_year"),
                "is_planned": bool(c.get("is_planned")),
                "owners": c.get("owners") or [],
                "url": c.get("url"),
                "match_score_km": round(d1 + d2, 1),
                "landing_points": [
                    {
                        "name": lp1.get("name"),
                        "country": lp1.get("country"),
                        "distance_km": round(d1, 1),
                    },
                    {
                        "name": lp2.get("name"),
                        "country": lp2.get("country"),
                        "distance_km": round(d2, 1),
                    },
                ],
            }
        )
    if not hits and max_landing_km < _LOOSE_RADIUS_KM:
        hits = cable_candidates(
            lat1, lon1, lat2, lon2, max_landing_km=_LOOSE_RADIUS_KM, limit=limit
        )
        for h in hits:
            h["loose"] = True
        return hits
    hits.sort(key=lambda h: h["match_score_km"] + (200.0 if h.get("is_planned") else 0.0))
    for h in hits:
        h.setdefault("loose", False)
    return hits[:limit]
