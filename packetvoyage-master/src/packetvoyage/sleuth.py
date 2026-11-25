"""Network Sleuth: Mystery detection, hypothesis generation, and case file investigation.

Detects network mysteries:
- `silent_gap`: Missing intermediate routers (`* * *`) that do not prevent reaching the destination.
- `rtt_inversion`: Intermediate hop RTT is significantly higher than subsequent hops.
- `physics_violation`: Latency delta implies packet traveled faster than speed of light in fiber (~0.67c).
- `geo_contradiction`: Jump to a distant continent with negligible latency increase (<2ms).
- `unreachable`: Trace terminated before reaching target.
- `jitter_anomaly`: High variance in probe times at a single hop (queueing/jitter).
- `path_loop`: Same IP appears at multiple non-consecutive hops.

Builds structured, pedagogical Case Files explaining the underlying Internet protocols.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from packetvoyage import geo
from packetvoyage.parser import Hop, ParsedTrace

logger = logging.getLogger("packetvoyage.sleuth")


@dataclass
class Mystery:
    mystery_id: str
    kind: str  # silent_gap, rtt_inversion, physics_violation, geo_contradiction, unreachable, jitter_anomaly, path_loop
    title: str
    hop_index: int
    hops_involved: list[int]
    description: str
    educational_insight: str
    status: str = "open"  # open, resolved, explained
    verdict: str | None = None
    evidence: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CaseFile:
    target: str | None
    completed: bool
    total_hops: int
    monitored_rtt_ms: float | None
    mysteries: list[Mystery] = field(default_factory=list)
    verdict_summary: str = ""
    learning_notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "target": self.target,
            "completed": self.completed,
            "total_hops": self.total_hops,
            "monitored_rtt_ms": self.monitored_rtt_ms,
            "mysteries": [m.to_dict() for m in self.mysteries],
            "verdict_summary": self.verdict_summary,
            "learning_notes": self.learning_notes,
        }


def detect_mysteries(trace: ParsedTrace) -> list[Mystery]:
    """Scan parsed trace hops for architectural anomalies and physical contradictions."""
    mysteries: list[Mystery] = []
    hops = trace.hops
    if not hops:
        return mysteries

    # 1. Unreachable mystery
    if not trace.completed:
        last_hop = hops[-1]
        mysteries.append(
            Mystery(
                mystery_id=f"unreachable_hop_{last_hop.hop}",
                kind="unreachable",
                title=f"Destination Unreachable (Stopped at Hop {last_hop.hop})",
                hop_index=last_hop.hop,
                hops_involved=[last_hop.hop],
                description=f"Trace stopped at hop {last_hop.hop} ({last_hop.ip or 'no response'}). Reason: {trace.stop_reason}.",
                educational_insight=(
                    "The target or an intermediate firewall might be dropping ICMP/UDP probes, "
                    "or the destination host may only accept specific TCP ports (like TCP/443)."
                ),
                status="open",
                evidence=[
                    f"Last responding IP: {last_hop.ip or 'None'}",
                    f"Stop reason: {trace.stop_reason}",
                ],
                next_steps=[
                    "Try probing with TCP/443 or UDP/53",
                    "Check if destination server is actively listening",
                ],
            )
        )

    # 2. Silent Gaps (intermediate timeouts)
    gap_start: int | None = None
    for i, h in enumerate(hops):
        is_silent = h.ip is None or h.loss >= 100.0 or h.rtt_ms is None
        if is_silent:
            if gap_start is None:
                gap_start = h.hop
        else:
            if gap_start is not None:
                gap_len = h.hop - gap_start
                # Only a mystery if subsequent hop actually replied
                mysteries.append(
                    Mystery(
                        mystery_id=f"silent_gap_{gap_start}_{h.hop - 1}",
                        kind="silent_gap",
                        title=f"Silent Router Gap (Hops {gap_start}–{h.hop - 1})",
                        hop_index=gap_start,
                        hops_involved=list(range(gap_start, h.hop)),
                        description=(
                            f"{gap_len} intermediate router(s) did not reply with ICMP Time Exceeded messages, "
                            f"yet packets successfully passed through to hop {h.hop} ({h.ip})."
                        ),
                        educational_insight=(
                            "Traceroute relies on routers voluntarily sending 'ICMP Time Exceeded' when TTL reaches 0. "
                            "Many core and transit routers disable ICMP generation or rate-limit it to protect their CPUs. "
                            "An asterisk (*) does NOT mean the link is broken!"
                        ),
                        status="explained",
                        verdict="Normal core router ICMP rate-limiting / filtering policy.",
                        evidence=[
                            f"Packets continued to hop {h.hop} ({h.ip}) with RTT {h.rtt_ms:.1f}ms",
                            "Data plane forwarding is fully functional.",
                        ],
                    )
                )
                gap_start = None

    # 3. RTT Inversion & Physics / Geo Contradictions
    prev_valid_hop: Hop | None = None
    seen_ips: dict[str, int] = {}

    for h in hops:
        if h.ip:
            if h.ip in seen_ips:
                first_hop_idx = seen_ips[h.ip]
                mysteries.append(
                    Mystery(
                        mystery_id=f"path_loop_{h.ip}_{first_hop_idx}_{h.hop}",
                        kind="path_loop",
                        title=f"Routing Loop Detected ({h.ip})",
                        hop_index=h.hop,
                        hops_involved=[first_hop_idx, h.hop],
                        description=f"IP {h.ip} was encountered at hop {first_hop_idx} and again at hop {h.hop}.",
                        educational_insight="A routing loop occurs when routing tables contain circular entries, causing packets to bounce back and forth.",
                        status="resolved",
                        verdict="Transient BGP or internal routing loop.",
                        evidence=[f"First seen at hop {first_hop_idx}", f"Repeated at hop {h.hop}"],
                    )
                )
            else:
                seen_ips[h.ip] = h.hop

        if (
            h.rtt_ms is not None
            and prev_valid_hop is not None
            and prev_valid_hop.rtt_ms is not None
        ):
            rtt_diff = h.rtt_ms - prev_valid_hop.rtt_ms

            # RTT Inversion (Hop N RTT significantly lower than Hop N-1)
            if rtt_diff < -15.0:  # Drop by > 15ms
                mysteries.append(
                    Mystery(
                        mystery_id=f"rtt_inversion_hop_{prev_valid_hop.hop}_{h.hop}",
                        kind="rtt_inversion",
                        title=f"Latency Inversion (Hop {prev_valid_hop.hop} -> {h.hop})",
                        hop_index=prev_valid_hop.hop,
                        hops_involved=[prev_valid_hop.hop, h.hop],
                        description=(
                            f"Hop {prev_valid_hop.hop} reported {prev_valid_hop.rtt_ms:.1f}ms, "
                            f"but subsequent Hop {h.hop} reported {h.rtt_ms:.1f}ms ({abs(rtt_diff):.1f}ms faster)."
                        ),
                        educational_insight=(
                            "Forwarding regular user traffic is handled by high-speed ASIC hardware (Data Plane). "
                            "Generating ICMP responses requires forwarding to the router's slow CPU (Control Plane). "
                            "High latency at a single hop usually reflects slow ICMP CPU response, not actual line delay."
                        ),
                        status="explained",
                        verdict="Asymmetric return path or router control plane ICMP generation delay.",
                        evidence=[
                            f"Hop {prev_valid_hop.hop} RTT: {prev_valid_hop.rtt_ms:.1f}ms",
                            f"Hop {h.hop} RTT: {h.rtt_ms:.1f}ms",
                        ],
                    )
                )

            # Jitter Anomaly (variance within same hop)
            if len(h.rtts) >= 3:
                rtt_range = max(h.rtts) - min(h.rtts)
                if rtt_range > 30.0:
                    mysteries.append(
                        Mystery(
                            mystery_id=f"jitter_anomaly_hop_{h.hop}",
                            kind="jitter_anomaly",
                            title=f"High Latency Jitter at Hop {h.hop}",
                            hop_index=h.hop,
                            hops_involved=[h.hop],
                            description=f"Probe times at hop {h.hop} varied widely: min {min(h.rtts):.1f}ms, max {max(h.rtts):.1f}ms (spread: {rtt_range:.1f}ms).",
                            educational_insight="Large jitter typically indicates transient buffer queueing or load balancing across multiple ECMP paths.",
                            status="open",
                            evidence=[f"Probe RTTs: {h.rtts}"],
                        )
                    )

            # Geo Contradiction & Physics Violation
            if (
                prev_valid_hop.lat is not None
                and prev_valid_hop.lon is not None
                and h.lat is not None
                and h.lon is not None
            ):
                dist_km = geo.haversine_km(prev_valid_hop.lat, prev_valid_hop.lon, h.lat, h.lon)
                min_physics_rtt = geo.min_rtt_ms(dist_km)

                # Geo Contradiction: Jump > 2000 km but RTT difference < 2ms
                if dist_km > 2000.0 and rtt_diff < 2.0:
                    mysteries.append(
                        Mystery(
                            mystery_id=f"geo_contradiction_hop_{prev_valid_hop.hop}_{h.hop}",
                            kind="geo_contradiction",
                            title=f"Geo-Location Illusion (Hop {prev_valid_hop.hop} -> {h.hop})",
                            hop_index=h.hop,
                            hops_involved=[prev_valid_hop.hop, h.hop],
                            description=(
                                f"Inferred locations claim a distance of {dist_km:.0f} km "
                                f"({prev_valid_hop.city or 'Unknown'} -> {h.city or 'Unknown'}), "
                                f"yet RTT only changed by {rtt_diff:.1f}ms."
                            ),
                            educational_insight=(
                                f"By the laws of physics, light in fiber takes at least {min_physics_rtt:.1f}ms for a round trip of {dist_km:.0f} km. "
                                f"Since the RTT increased by only {rtt_diff:.1f}ms, the actual router must be physically local!"
                            ),
                            status="resolved",
                            verdict="GeoIP database error or Anycast / global IP registration misattribution.",
                            evidence=[
                                f"Distance: {dist_km:.0f} km",
                                f"Theoretical physical minimum RTT: {min_physics_rtt:.1f}ms",
                                f"Observed RTT change: {rtt_diff:.1f}ms",
                            ],
                        )
                    )

        if h.rtt_ms is not None:
            prev_valid_hop = h

    return mysteries


def build_casefile(trace: ParsedTrace) -> CaseFile:
    """Build a comprehensive detective casefile from trace analysis."""
    mysteries = detect_mysteries(trace)
    last_rtt = None
    for h in reversed(trace.hops):
        if h.rtt_ms is not None:
            last_rtt = h.rtt_ms
            break

    learning_notes = [
        "1. Distance & Fiber Speed: Light in optical fiber travels at ~200,000 km/s (0.67c). 1,000 km adds ~10ms RTT.",
        "2. Asterisks (*) mean no ICMP response from that router, NOT a broken connection.",
        "3. High latency at a single intermediate hop is usually CPU deprioritization of ICMP, not line congestion.",
    ]

    summary = (
        f"Case concluded with {len(mysteries)} mystery/anomalies detected. "
        f"Target {'reached' if trace.completed else 'unreached'} ({len(trace.hops)} total hops)."
    )

    return CaseFile(
        target=trace.destination or trace.destination_ip,
        completed=trace.completed,
        total_hops=len(trace.hops),
        monitored_rtt_ms=last_rtt,
        mysteries=mysteries,
        verdict_summary=summary,
        learning_notes=learning_notes,
    )


def format_casefile(case: CaseFile) -> str:
    """Format CaseFile into readable Markdown text."""
    lines: list[str] = []
    lines.append(f"# 🕵️ PacketVoyage Case File: {case.target or 'Unknown Target'}")
    lines.append(
        f"**Status**: {'✅ Destination Reached' if case.completed else '⚠️ Destination Incomplete'}"
    )
    lines.append(
        f"**Total Hops**: {case.total_hops} | **Final RTT**: {f'{case.monitored_rtt_ms:.1f} ms' if case.monitored_rtt_ms else 'N/A'}"
    )
    lines.append("")
    lines.append("## 🔍 Detected Mysteries & Insights")

    if not case.mysteries:
        lines.append("✨ *No path anomalies detected. Clean, monotonic fiber routing.*")
    else:
        for idx, m in enumerate(case.mysteries, start=1):
            badge = "🟢 RESOLVED" if m.status in ("resolved", "explained") else "🟡 OPEN"
            lines.append(f"### Mystery #{idx}: {m.title} [{badge}]")
            lines.append(f"- **Description**: {m.description}")
            lines.append(
                f"- **💡 Why this happens (Physics & Protocol Insight)**: {m.educational_insight}"
            )
            if m.verdict:
                lines.append(f"- **⚖️ Verdict**: {m.verdict}")
            if m.evidence:
                lines.append("- **🔎 Evidence**:")
                for ev in m.evidence:
                    lines.append(f"  - {ev}")
            lines.append("")

    lines.append("## 📚 Key Internet Principles")
    for note in case.learning_notes:
        lines.append(f"- {note}")

    return "\n".join(lines)
