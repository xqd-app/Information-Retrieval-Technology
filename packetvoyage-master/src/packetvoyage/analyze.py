"""Packet Voyage path analysis, narrative storytelling, and physics verification.

Produces:
- `voyage_narrative`: A rich chronological story of how the packet journeyed across cities, borders, and oceans.
- `route_summary`: Concise textual journey flow showing major hubs and submarine cables.
- `detailed_story`: Complete structured markdown breakdown of all voyage legs.
- `physics_check`: Verification against the physical speed of light in fiber optics.
- `suggested_corrections`: Automated correction suggestions for GeoIP/misattributed router coordinates.
- `geojson`: Clean GeoJSON FeatureCollection of the voyage path.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from packetvoyage import cables, geo
from packetvoyage.parser import Hop, ParsedTrace

logger = logging.getLogger("packetvoyage.analyze")


@dataclass
class VoyageLeg:
    from_hop: int
    to_hop: int
    from_city: str
    to_city: str
    from_lat: float
    from_lon: float
    to_lat: float
    to_lon: float
    distance_km: float
    rtt_delta_ms: float
    min_physical_rtt_ms: float
    leg_type: str = (
        "transit"  # local_metro, terrestrial_transit, trans_oceanic, trans_continental, geo_anomaly
    )
    from_iata: str | None = None
    to_iata: str | None = None
    corridor_fact: str | None = None
    cable_candidates: list[str] = field(default_factory=list)
    implied_speed_c: float = 0.0
    is_oceanic_crossing: bool = False
    is_physically_suspicious: bool = False
    explanation: str = ""


@dataclass
class VoyageAnalysis:
    legs: list[VoyageLeg] = field(default_factory=list)
    narrative: list[str] = field(default_factory=list)
    route_summary: str = ""
    detailed_story: str = ""
    total_physical_distance_km: float = 0.0
    oceanic_crossings: list[str] = field(default_factory=list)
    matched_cables: list[str] = field(default_factory=list)
    suggested_corrections: dict[str, dict[str, Any]] = field(default_factory=dict)
    geojson: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "legs": [asdict(leg) for leg in self.legs],
            "narrative": self.narrative,
            "route_summary": self.route_summary,
            "detailed_story": self.detailed_story,
            "total_physical_distance_km": self.total_physical_distance_km,
            "oceanic_crossings": self.oceanic_crossings,
            "matched_cables": self.matched_cables,
            "suggested_corrections": self.suggested_corrections,
            "geojson": self.geojson,
        }


def analyze_voyage(trace: ParsedTrace, origin_name: str = "Origin") -> VoyageAnalysis:
    """Analyze a parsed traceroute and construct its packet voyage narrative with deep physical and geographical insights."""
    hops = [h for h in trace.hops if h.ip and h.rtt_ms is not None]
    narrative: list[str] = []
    legs: list[VoyageLeg] = []
    oceanic_crossings: list[str] = []
    all_matched_cables: list[str] = []
    suggested_corrections: dict[str, dict[str, Any]] = {}
    total_dist_km = 0.0

    if not hops:
        msg = "No responding hops found to construct a voyage."
        return VoyageAnalysis(
            narrative=[msg],
            route_summary=msg,
            detailed_story=f"**Voyage Status**: {msg}",
        )

    target_name = trace.destination or trace.destination_ip or "target"
    narrative.append(f"🚢 **Voyage Departure**: The packet departed towards {target_name}.")

    prev_loc_hop: Hop | None = None

    for h in hops:
        # Check if we have coordinate data
        if h.lat is not None and h.lon is not None:
            from_iata_match = (
                geo.extract_iata_from_hostname(prev_loc_hop.hostname) if prev_loc_hop else None
            )
            to_iata_match = geo.extract_iata_from_hostname(h.hostname)

            if prev_loc_hop is None:
                iata_str = f" [{to_iata_match[0]}]" if to_iata_match else ""
                narrative.append(
                    f"📍 **Hop {h.hop} ({h.city or 'Local Metro'}{iata_str})**: "
                    f"Initial geographic anchor at {h.city or 'local hub'} (RTT {h.rtt_ms:.1f}ms)."
                )
                prev_loc_hop = h
            else:
                dist_km = geo.haversine_km(prev_loc_hop.lat, prev_loc_hop.lon, h.lat, h.lon)
                rtt_delta = max(0.0, (h.rtt_ms or 0.0) - (prev_loc_hop.rtt_ms or 0.0))
                min_phys_rtt = geo.min_rtt_ms(dist_km)
                c_frac = geo.implied_c_fraction(dist_km, rtt_delta) if rtt_delta > 0 else 0.0

                from_iata_code = from_iata_match[0] if from_iata_match else None
                to_iata_code = to_iata_match[0] if to_iata_match else None

                # Oceanic corridor & cable candidate detection
                corridor_info = geo.identify_oceanic_corridor(
                    prev_loc_hop.lat, prev_loc_hop.lon, h.lat, h.lon
                )
                corridor_name, corridor_fact = corridor_info if corridor_info else (None, None)
                is_oceanic = corridor_name is not None

                # Submarine cable lookup
                cable_hits = cables.cable_candidates(
                    prev_loc_hop.lat, prev_loc_hop.lon, h.lat, h.lon
                )
                matched_cable_names = [c["name"] for c in cable_hits if c.get("name")]
                all_matched_cables.extend(matched_cable_names)

                # Physical plausibility & leg classification
                is_suspicious = False
                leg_type = "terrestrial_transit"
                explanation = ""

                if dist_km > 1500.0 and rtt_delta < 2.0:
                    is_suspicious = True
                    leg_type = "geo_anomaly"
                    explanation = (
                        f"GeoIP database claims a {dist_km:.0f} km jump ({prev_loc_hop.city} -> {h.city}), "
                        f"but RTT increased by only +{rtt_delta:.1f}ms (physical minimum is +{min_phys_rtt:.1f}ms). "
                        "The packet is almost certainly still in the local metro."
                    )
                    suggested_corrections[str(h.hop)] = {
                        "hop": h.hop,
                        "ip": h.ip,
                        "original_city": h.city,
                        "corrected_city": prev_loc_hop.city,
                        "lat": prev_loc_hop.lat,
                        "lon": prev_loc_hop.lon,
                        "reason": explanation,
                    }
                elif is_oceanic:
                    leg_type = "trans_oceanic"
                    cable_note = (
                        f" (Potential cables: {', '.join(matched_cable_names[:3])})"
                        if matched_cable_names
                        else ""
                    )
                    explanation = (
                        f"Crossed {dist_km:.0f} km via {corridor_fact or 'trans-oceanic subsea fiber'}{cable_note}. "
                        f"Latency jumped from {prev_loc_hop.rtt_ms:.1f}ms to {h.rtt_ms:.1f}ms (+{rtt_delta:.1f}ms)."
                    )
                elif dist_km > 2500.0:
                    leg_type = "trans_continental"
                    explanation = (
                        f"Trans-continental terrestrial trunk: {dist_km:.0f} km from {prev_loc_hop.city} to {h.city} "
                        f"(+{rtt_delta:.1f}ms RTT, fiber speed: {c_frac:.2f}c)."
                    )
                elif dist_km < 100.0 and rtt_delta < 5.0:
                    leg_type = "local_metro"
                    explanation = f"Local metro routing in {h.city or 'regional hub'} ({dist_km:.0f} km, +{rtt_delta:.1f}ms RTT)."
                else:
                    leg_type = "terrestrial_transit"
                    explanation = f"Regional transit: {dist_km:.0f} km from {prev_loc_hop.city} to {h.city} (+{rtt_delta:.1f}ms RTT)."

                leg = VoyageLeg(
                    from_hop=prev_loc_hop.hop,
                    to_hop=h.hop,
                    from_city=prev_loc_hop.city or "Unknown",
                    to_city=h.city or "Unknown",
                    from_lat=prev_loc_hop.lat,
                    from_lon=prev_loc_hop.lon,
                    to_lat=h.lat,
                    to_lon=h.lon,
                    distance_km=dist_km,
                    rtt_delta_ms=rtt_delta,
                    min_physical_rtt_ms=min_phys_rtt,
                    leg_type=leg_type,
                    from_iata=from_iata_code,
                    to_iata=to_iata_code,
                    corridor_fact=corridor_fact,
                    cable_candidates=matched_cable_names[:3],
                    implied_speed_c=round(c_frac, 2),
                    is_oceanic_crossing=is_oceanic,
                    is_physically_suspicious=is_suspicious,
                    explanation=explanation,
                )
                legs.append(leg)

                if not is_suspicious:
                    total_dist_km += dist_km

                if is_oceanic and corridor_fact:
                    oceanic_crossings.append(corridor_fact)
                    cable_str = (
                        f" [Cables: {', '.join(matched_cable_names[:2])}]"
                        if matched_cable_names
                        else ""
                    )
                    narrative.append(
                        f"🌊 **Trans-Oceanic Voyage (Hop {prev_loc_hop.hop} -> {h.hop})**: "
                        f"Crossed {dist_km:.0f} km via {corridor_fact}{cable_str}. "
                        f"Latency leaped from {prev_loc_hop.rtt_ms:.1f}ms to {h.rtt_ms:.1f}ms (+{rtt_delta:.1f}ms)."
                    )
                elif dist_km > 300.0 and not is_suspicious:
                    narrative.append(
                        f"🚀 **Terrestrial Transit (Hop {prev_loc_hop.hop} -> {h.hop})**: "
                        f"Journeyed {dist_km:.0f} km from {prev_loc_hop.city} to {h.city} (+{rtt_delta:.1f}ms RTT)."
                    )

                prev_loc_hop = h

    last_hop = hops[-1]
    if trace.completed:
        narrative.append(
            f"🏁 **Voyage Complete**: Packet successfully arrived at destination {last_hop.ip} "
            f"with final RTT of {last_hop.rtt_ms:.1f}ms."
        )
    else:
        narrative.append(
            f"⚓ **Voyage Terminus**: Packet reached anchor point at hop {last_hop.hop} ({last_hop.ip}) "
            f"at RTT {last_hop.rtt_ms:.1f}ms."
        )

    # Build concise route summary and detailed story
    unique_cables = list(dict.fromkeys(all_matched_cables))
    route_summary = _build_route_summary(legs, trace)
    detailed_story = _build_detailed_story(legs, trace, total_dist_km, unique_cables)

    # Generate GeoJSON
    geojson = _build_geojson(hops, legs, suggested_corrections)

    return VoyageAnalysis(
        legs=legs,
        narrative=narrative,
        route_summary=route_summary,
        detailed_story=detailed_story,
        total_physical_distance_km=total_dist_km,
        oceanic_crossings=list(dict.fromkeys(oceanic_crossings)),
        matched_cables=unique_cables,
        suggested_corrections=suggested_corrections,
        geojson=geojson,
    )


def _build_route_summary(legs: list[VoyageLeg], trace: ParsedTrace) -> str:
    """Build a concise textual summary representing the packet's path journey."""
    if not legs:
        return f"Direct or local routing to {trace.destination or trace.destination_ip or 'target'}"

    nodes: list[str] = []
    first_leg = legs[0]
    origin_city = first_leg.from_city
    if first_leg.from_iata:
        origin_city += f" ({first_leg.from_iata})"
    nodes.append(origin_city)

    for leg in legs:
        if leg.is_physically_suspicious:
            continue
        to_name = leg.to_city
        if leg.to_iata:
            to_name += f" ({leg.to_iata})"

        if leg.is_oceanic_crossing:
            cables_desc = (
                f" [{leg.cable_candidates[0]}]" if leg.cable_candidates else " [Subsea Cable]"
            )
            nodes.append(f"🌊{cables_desc} ➔ {to_name}")
        elif leg.distance_km > 500:
            nodes.append(f"➔ {to_name}")
        elif nodes[-1] != to_name and not nodes[-1].startswith(to_name):
            nodes.append(f"➔ {to_name}")

    return " ".join(nodes)


def _build_detailed_story(
    legs: list[VoyageLeg],
    trace: ParsedTrace,
    total_dist_km: float,
    matched_cables: list[str],
) -> str:
    """Construct a full markdown formatted journey report."""
    target = trace.destination or trace.destination_ip or "Target"
    lines: list[str] = [
        f"### 🌐 Packet Voyage Journey Report: {target}",
        f"- **Estimated Physical Distance**: ~{total_dist_km:,.0f} km",
        f"- **Final Measured RTT**: {f'{trace.hops[-1].rtt_ms:.1f} ms' if trace.hops and trace.hops[-1].rtt_ms else 'N/A'}",
        f"- **Status**: {'✅ Arrived at destination' if trace.completed else '⚠️ Terminated early'}",
    ]

    if matched_cables:
        lines.append(f"- **Matched Submarine Cable Systems**: {', '.join(matched_cables[:4])}")

    lines.append("")
    lines.append("#### 🗺️ Geographic & Physical Leg Breakdown")

    if not legs:
        lines.append(
            "*All hops remained within the same metro area or did not expose geographic coordinates.*"
        )
        return "\n".join(lines)

    for idx, leg in enumerate(legs, start=1):
        icon = "🏙️"
        if leg.is_physically_suspicious:
            icon = "⚠️"
        elif leg.is_oceanic_crossing:
            icon = "🌊"
        elif leg.distance_km > 2000:
            icon = "🚄"
        elif leg.distance_km > 300:
            icon = "🚀"

        from_tag = f"{leg.from_city}{f' ({leg.from_iata})' if leg.from_iata else ''}"
        to_tag = f"{leg.to_city}{f' ({leg.to_iata})' if leg.to_iata else ''}"

        lines.append(
            f"{icon} **Leg {idx} (Hop {leg.from_hop} ➔ {leg.to_hop})**: `{from_tag}` ➔ `{to_tag}`"
        )
        lines.append(
            f"  - **Distance**: ~{leg.distance_km:,.0f} km | **ΔRTT**: +{leg.rtt_delta_ms:.1f} ms (Min physical fiber RTT: {leg.min_physical_rtt_ms:.1f} ms)"
        )
        if leg.cable_candidates:
            lines.append(f"  - **Likely Subsea Cables**: {', '.join(leg.cable_candidates)}")
        lines.append(f"  - **Insight**: {leg.explanation}")
        lines.append("")

    return "\n".join(lines)


def _build_geojson(
    hops: list[Hop],
    legs: list[VoyageLeg],
    corrections: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Generate a clean GeoJSON FeatureCollection."""
    features: list[dict[str, Any]] = []
    line_coords: list[list[float]] = []

    for h in hops:
        lat, lon, city = h.lat, h.lon, h.city
        corrected = False
        if str(h.hop) in corrections:
            lat = corrections[str(h.hop)]["lat"]
            lon = corrections[str(h.hop)]["lon"]
            city = corrections[str(h.hop)]["corrected_city"]
            corrected = True

        if lat is not None and lon is not None:
            line_coords.append([lon, lat])
            features.append(
                {
                    "type": "Feature",
                    "geometry": {"type": "Point", "coordinates": [lon, lat]},
                    "properties": {
                        "hop": h.hop,
                        "ip": h.ip,
                        "hostname": h.hostname,
                        "city": city,
                        "rtt_ms": h.rtt_ms,
                        "corrected": corrected,
                    },
                }
            )

    if len(line_coords) >= 2:
        features.append(
            {
                "type": "Feature",
                "geometry": {"type": "LineString", "coordinates": line_coords},
                "properties": {"type": "packet_voyage_path"},
            }
        )

    return {"type": "FeatureCollection", "features": features}
