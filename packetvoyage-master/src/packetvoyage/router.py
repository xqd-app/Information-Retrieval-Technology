"""Physical-path routing for map legs, based on real submarine cable data.

For each long leg between two plotted hops this module answers "which physical route
would the packets take?" instead of falling back to a bare great circle. It matches
the leg's endpoints against real cable systems (bundled TeleGeography snapshot), builds
the concrete waypoint route hop -> landing -> ... -> landing -> hop along surveyed
cable polylines (or great-circle sub-arcs), and scores each candidate against the
observed RTT.
"""

from __future__ import annotations

from typing import Any

from packetvoyage import cables, geo

MIN_ROUTE_KM = 1200.0  # only legs this long get cable routing (sea crossings)
_LOOSE_OK_KM = 4000.0  # very long legs tolerate the loose (500 km) landing tier
C_FIT = 0.67  # typical fibre speed as a fraction of c
IMPLIED_MIN_C = 0.3
IMPLIED_MAX_C = 1.2
_MATCH_LIMIT = 10
_MAX_DETOUR_X = 2.2  # reject routes much longer than the direct great circle


def _cable_waypoints(
    cable: dict[str, Any],
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> dict[str, Any] | None:
    """Waypoint route hop A -> matched landing -> ... -> matched landing -> hop B."""
    lps = [
        (lp["lat"], lp["lon"], lp.get("name"))
        for lp in cable.get("landing_points") or []
        if lp.get("lat") is not None and lp.get("lon") is not None
    ]
    if len(lps) < 2:
        return None
    da = [geo.haversine_km(lat1, lon1, la, lo) for la, lo, _ in lps]
    db = [geo.haversine_km(lat2, lon2, la, lo) for la, lo, _ in lps]
    ia = min(range(len(lps)), key=lambda k: da[k])
    ib = min(range(len(lps)), key=lambda k: db[k])
    if ia == ib:
        return None
    step = 1 if ib > ia else -1
    idx = list(range(ia, ib + step, step))
    via = [lps[k][2] for k in idx]

    segs = cable.get("segments") or []
    geometry_ok = len(segs) == len(lps) - 1 and _segments_aligned(segs, lps)
    interior: list[tuple[float, float]] | None = None
    if geometry_ok:
        seg_idx = list(range(ia, ib)) if step == 1 else list(range(ia - 1, ib - 1, -1))
        interior = []
        for si in seg_idx:
            s = segs[si]
            interior.extend(s if step == 1 else reversed(s))
        waypoints = [(lat1, lon1)] + interior + [(lat2, lon2)]
    else:
        waypoints = [(lat1, lon1)] + [(lps[k][0], lps[k][1]) for k in idx] + [(lat2, lon2)]
    length_km = sum(
        geo.haversine_km(waypoints[i][0], waypoints[i][1], waypoints[i + 1][0], waypoints[i + 1][1])
        for i in range(len(waypoints) - 1)
    )
    return {
        "waypoints": waypoints,
        "interior": interior,
        "via": via,
        "length_km": length_km,
    }


def _segments_aligned(segs: list[list[list[float]]], lps: list[tuple[float, float, str]]) -> bool:
    for i, s in enumerate(segs):
        if i >= len(lps) - 1:
            break
        if not s:
            return False
        if geo.haversine_km(s[0][0], s[0][1], lps[i][0], lps[i][1]) > 90.0:
            return False
        if geo.haversine_km(s[-1][0], s[-1][1], lps[i + 1][0], lps[i + 1][1]) > 90.0:
            return False
    return True


def _arc_kinds(n: int) -> list[str]:
    if n <= 1:
        return ["cable"] * n
    if n == 2:
        return ["access", "access"]
    return ["access"] + ["cable"] * (n - 2) + ["access"]


def _implied_speed_c(length_km: float, rtt_delta_ms: float | None) -> float | None:
    if not rtt_delta_ms or rtt_delta_ms <= 0:
        return None
    return length_km / (rtt_delta_ms / 2 / 1000) / geo.SPEED_OF_LIGHT_KM_S


def route_leg(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
    rtt_delta_ms: float | None = None,
) -> dict[str, Any] | None:
    """Best physical-path hypothesis for one long leg, or None."""
    if not (lat1 and lon1 and lat2 and lon2):
        return None
    d_endpoints = geo.haversine_km(lat1, lon1, lat2, lon2)
    if d_endpoints < MIN_ROUTE_KM:
        return None

    scored: list[dict[str, Any]] = []
    for cand in cables.cable_candidates(lat1, lon1, lat2, lon2, limit=_MATCH_LIMIT):
        cable = cables.cable_by_id(cand.get("id")) or {}
        built = _cable_waypoints(cable, lat1, lon1, lat2, lon2)
        if not built:
            continue
        length_km = built["length_km"]
        if length_km > _MAX_DETOUR_X * d_endpoints:
            continue
        arcs = [
            geo.great_circle_arc(built["waypoints"][i], built["waypoints"][i + 1])
            for i in range(len(built["waypoints"]) - 1)
        ]
        implied = _implied_speed_c(length_km, rtt_delta_ms)
        if implied is not None and not (IMPLIED_MIN_C <= implied <= IMPLIED_MAX_C):
            speed_score = abs(implied - C_FIT) + 5.0
        elif implied is not None:
            speed_score = abs(implied - C_FIT)
        else:
            speed_score = cand.get("match_score_km", 0.0) / 1000.0
        scored.append(
            {
                "arcs": arcs,
                "via": built["via"],
                "length_km": round(length_km),
                "implied_speed_c": round(implied, 2) if implied is not None else None,
                "speed_score": speed_score,
                "strict": not bool(cand.get("loose")),
                "match_score_km": cand.get("match_score_km"),
                "cable": {
                    "name": cable.get("name"),
                    "rfs_year": cable.get("rfs_year"),
                    "owners": cable.get("owners") or [],
                    "length_km": cable.get("length_km"),
                },
            }
        )

    strict = [s for s in scored if s["strict"]]
    pool = strict or ([s for s in scored if not s["strict"]] if d_endpoints >= _LOOSE_OK_KM else [])
    if not pool:
        return None
    pool.sort(key=lambda s: s["speed_score"])
    best, *rest = pool
    alt = rest[0] if rest else None

    note: str | None = None
    if best["implied_speed_c"] is not None and not (
        IMPLIED_MIN_C <= best["implied_speed_c"] <= IMPLIED_MAX_C
    ):
        note = (
            f"RTT implies {best['implied_speed_c']}x c along {best['cable']['name']} - "
            "the real path is probably longer (e.g. a detour), so this cable is a "
            "hypothesis only"
        )
    return {
        "arcs": best["arcs"],
        "arc_kinds": _arc_kinds(len(best["arcs"])),
        "cable": best["cable"],
        "via": best["via"],
        "length_km": best["length_km"],
        "implied_speed_c": best["implied_speed_c"],
        "alternative": (
            {"name": alt["cable"]["name"], "rfs_year": alt["cable"]["rfs_year"]}
            if alt and alt["cable"].get("name")
            else None
        ),
        "note": note,
    }
