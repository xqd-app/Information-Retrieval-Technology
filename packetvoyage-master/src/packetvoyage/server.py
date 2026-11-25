"""PacketVoyage Model Context Protocol (MCP) Server.

Educational traceroute analyzer, physics verifier, and packet voyage storytelling engine.
Zero external commercial APIs, pure fiber physics, submarine cable telemetry, and detective insight.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from packetvoyage import (
    analyze,
    geo,
    local_trace,
    parser,
    preflight,
    sleuth,
)

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("packetvoyage.server")

mcp = FastMCP("packetvoyage")


@mcp.tool()
def analyze_voyage_text(data: str) -> dict[str, Any]:
    """Analyze any traceroute output (from terminal, Looking Glass, or Globalping).

    Parses hops, extracts router IATA codes, verifies speed-of-light in fiber optics (~0.67c),
    identifies submarine cable corridors, detects oceanic crossings, and discovers routing mysteries.

    Args:
        data: Raw traceroute text or JSON from any source.
    """
    trace = parser.parse_traceroute(data)
    voyage_analysis = analyze.analyze_voyage(trace)
    casefile = sleuth.build_casefile(trace)

    return {
        "destination": trace.destination,
        "completed": trace.completed,
        "stop_reason": trace.stop_reason,
        "total_hops": len(trace.hops),
        "route_summary": voyage_analysis.route_summary,
        "detailed_story": voyage_analysis.detailed_story,
        "voyage_narrative": voyage_analysis.narrative,
        "oceanic_crossings": voyage_analysis.oceanic_crossings,
        "matched_cables": voyage_analysis.matched_cables,
        "total_distance_km": voyage_analysis.total_physical_distance_km,
        "suggested_corrections": voyage_analysis.suggested_corrections,
        "casefile_summary": sleuth.format_casefile(casefile),
        "mysteries": [m.to_dict() for m in casefile.mysteries],
        "hops": [h.to_dict() for h in trace.hops],
    }


@mcp.tool()
def voyage_investigate(
    target: str | None = None,
    data: str | None = None,
    protocol: str = "icmp",
) -> str:
    """Run a detective investigation into a network path to uncover routing anomalies and explain the geographic journey.

    Identifies silent router gaps (*), latency inversions, geo-location illusions, physical speed violations,
    and constructs a comprehensive journey report with fiber optic physics verification.

    Args:
        target: Hostname or IP to trace from local machine.
        data: Optional past traceroute text/JSON to analyze without executing a new trace.
        protocol: Protocol to use if running a new trace ('icmp', 'tcp', or 'udp').
    """
    if data:
        trace = parser.parse_traceroute(data)
    elif target:
        trace = local_trace.run_local_traceroute(target, protocol=protocol)
    else:
        return "Error: Please provide either a `target` hostname/IP or past traceroute `data`."

    casefile = sleuth.build_casefile(trace)
    voyage_analysis = analyze.analyze_voyage(trace)

    # Combine mystery casefile and detailed geographic voyage story
    parts = [
        sleuth.format_casefile(casefile),
        "",
        "---",
        "",
        voyage_analysis.detailed_story,
        "",
        f"**Summary Route Flow**: `{voyage_analysis.route_summary}`",
    ]
    return "\n".join(parts)


@mcp.tool()
def run_protocol_experiment(target: str) -> dict[str, Any]:
    """Run a parallel multi-protocol battery (ICMP, TCP/443, UDP/53) against a target.

    Compares how different transport protocols and firewall rules affect packet paths.

    Args:
        target: Destination hostname or IP address.
    """
    results = local_trace.run_protocol_battery(target)
    comparison: dict[str, Any] = {}
    for proto_name, trace in results.items():
        case = sleuth.build_casefile(trace)
        comparison[proto_name] = {
            "completed": trace.completed,
            "stop_reason": trace.stop_reason,
            "total_hops": len(trace.hops),
            "final_rtt_ms": case.monitored_rtt_ms,
            "mysteries_detected": len(case.mysteries),
        }
    return {
        "target": target,
        "protocol_comparison": comparison,
        "educational_note": (
            "Firewalls and edge load balancers often allow TCP/443 (HTTPS) while blocking ICMP/UDP probes. "
            "Comparing protocols reveals where security boundaries exist in the path."
        ),
    }


@mcp.tool()
def research_host(
    host: str,
    extra_resolvers: list[str] | None = None,
    enable_asn_lookup: bool = False,
    enable_peeringdb_lookup: bool = False,
) -> dict[str, Any]:
    """Research a target host's real identity locally, before tracing it.

    Resolves the host with the system resolver plus public resolvers (1.1.1.1,
    8.8.8.8 by default), walks the CNAME chain, and reports whether the host
    is fronted by a global CDN / anycast network or appears to be a direct
    origin - the check to run *before* spending time on a traceroute, since a
    CDN-fronted host only shows the nearest edge, never the origin path.

    Args:
        host: Hostname or IP address to research.
        extra_resolvers: Optional extra public resolver IPs to compare against.
        enable_asn_lookup: Opt in to the Team Cymru bulk whois lookup for ASN/org annotation.
        enable_peeringdb_lookup: Opt in to an additional PeeringDB (peeringdb.com) HTTPS
            lookup per resolved ASN for network type, peering policy, and IX presence.
            Requires enable_asn_lookup=True to also be set; discloses the resolved ASN
            numbers (not the target host/IP) to peeringdb.com.
    """
    report = preflight.research_host(
        host, extra_resolvers, enable_asn_lookup, enable_peeringdb_lookup
    )
    return {
        **report.to_dict(),
        "report": preflight.format_report(report),
    }


@mcp.tool()
def list_known_iata_airports() -> dict[str, Any]:
    """List reference IATA airport codes used to identify router locations from PTR hostnames."""
    airports = {
        code: {
            "city": coords.city,
            "country": coords.country,
            "lat": coords.lat,
            "lon": coords.lon,
        }
        for code, coords in sorted(geo.IATA_AIRPORTS.items())
    }
    return {
        "total_airports": len(airports),
        "airports": airports,
        "note": "Extracted from standard PTR naming conventions (e.g., 'ae-1.sjc.net' -> San Jose, SJC).",
    }


def main():
    mcp.run()


if __name__ == "__main__":
    main()
