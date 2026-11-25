"""Universal traceroute text & JSON parser.

Parses output from:
- Standard Linux / BSD / macOS `traceroute`
- Windows `tracert`
- Looking Glass routers (Cisco IOS, Juniper JunOS, BIRD, etc.) with MPLS labels, AS numbers, ICMP flags (!H, !N)
- Globalping JSON / raw text outputs

Enriches parsed hops with IATA PTR inference and latency statistics.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import asdict, dataclass, field
from typing import Any

from packetvoyage import geo

logger = logging.getLogger("packetvoyage.parser")

_IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_RTT_REGEX = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*ms", re.IGNORECASE)
_WINDOWS_RTT_REGEX = re.compile(r"(<[0-9]+|[0-9]+(?:\.[0-9]+)?)\s*ms", re.IGNORECASE)
_AS_REGEX = re.compile(r"(?:AS|as)(\d+)")


@dataclass
class Hop:
    hop: int
    ip: str | None = None
    hostname: str | None = None
    rtt_ms: float | None = None
    rtts: list[float] = field(default_factory=list)
    asn: str | None = None
    city: str | None = None
    country: str | None = None
    lat: float | None = None
    lon: float | None = None
    iata: str | None = None
    loss: float = 0.0
    flags: list[str] = field(default_factory=list)
    raw_line: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ParsedTrace:
    destination: str | None = None
    destination_ip: str | None = None
    hops: list[Hop] = field(default_factory=list)
    completed: bool = False
    stop_reason: str = "unknown"  # destination_reached, max_hops_truncated, no_reply

    def to_dict(self) -> dict[str, Any]:
        return {
            "destination": self.destination,
            "destination_ip": self.destination_ip,
            "completed": self.completed,
            "stop_reason": self.stop_reason,
            "hops": [h.to_dict() for h in self.hops],
        }


def parse_traceroute(text_or_json: str | dict[str, Any]) -> ParsedTrace:
    """Universal parser entrypoint. Accepts JSON dict/string or raw text."""
    if isinstance(text_or_json, dict):
        return _parse_json_dict(text_or_json)

    cleaned = text_or_json.strip()
    if cleaned.startswith("{") and cleaned.endswith("}"):
        try:
            data = json.loads(cleaned)
            return _parse_json_dict(data)
        except Exception:
            pass

    return _parse_text(cleaned)


def _parse_json_dict(data: dict[str, Any]) -> ParsedTrace:
    """Parse structured JSON (such as previously saved packetvoyage or globalping result)."""
    # Globalping format check
    if "result" in data and isinstance(data["result"], dict) and "hops" in data["result"]:
        data = data["result"]

    hops: list[Hop] = []
    raw_hops = data.get("hops", [])
    destination = data.get("destination") or data.get("target")
    destination_ip = data.get("destination_ip")

    for i, rh in enumerate(raw_hops, start=1):
        if isinstance(rh, dict):
            hop_num = rh.get("hop", i)
            ip = rh.get("ip")
            hostname = rh.get("hostname") or rh.get("ptr")
            rtt_ms = (
                rh.get("rtt_ms")
                or rh.get("rtt")
                or (rh.get("rtts", [None])[0] if rh.get("rtts") else None)
            )
            rtts = rh.get("rtts", [rtt_ms] if rtt_ms is not None else [])
            asn = rh.get("asn")
            city = rh.get("city")
            country = rh.get("country")
            lat = rh.get("lat")
            lon = rh.get("lon")
            iata = rh.get("iata")

            # Try inferring IATA if coordinates missing
            if (lat is None or lon is None) and hostname:
                iata_res = geo.extract_iata_from_hostname(hostname)
                if iata_res:
                    code, coords = iata_res
                    iata = iata or code
                    city = city or coords.city
                    country = country or coords.country
                    lat = lat or coords.lat
                    lon = lon or coords.lon

            hops.append(
                Hop(
                    hop=hop_num,
                    ip=ip,
                    hostname=hostname,
                    rtt_ms=rtt_ms,
                    rtts=[float(x) for x in rtts if x is not None],
                    asn=asn,
                    city=city,
                    country=country,
                    lat=lat,
                    lon=lon,
                    iata=iata,
                )
            )

    completed = data.get("completed", False)
    stop_reason = data.get("stop_reason", "unknown")
    if not completed and hops and destination_ip:
        last_hop = hops[-1]
        if last_hop.ip == destination_ip:
            completed = True
            stop_reason = "destination_reached"

    return ParsedTrace(
        destination=destination,
        destination_ip=destination_ip,
        hops=hops,
        completed=completed,
        stop_reason=stop_reason,
    )


def _parse_text(text: str) -> ParsedTrace:
    """Parse line-by-line standard traceroute / Looking Glass / Windows tracert output."""
    lines = text.splitlines()
    hops: list[Hop] = []
    destination: str | None = None
    destination_ip: str | None = None

    # Try extracting destination from first line e.g. "traceroute to example.com (93.184.216.34), 30 hops max"
    if lines:
        first_line = lines[0]
        ip_match = _IP_REGEX.search(first_line)
        if ip_match:
            destination_ip = ip_match.group(0)
        # Check target name
        m = re.search(
            r"(?:traceroute to|Tracing route to)\s+([^\s\(\)]+)", first_line, re.IGNORECASE
        )
        if m:
            destination = m.group(1)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        # Match hop number at start of line: " 1 ", "1.", "1  "
        m_hop = re.match(r"^(\d+)[\.\s]", stripped)
        if not m_hop:
            continue

        hop_num = int(m_hop.group(1))

        # Check for complete timeout "* * *"
        if re.search(r"^\d+[\.\s]+\*\s+\*\s+\*", stripped) or re.search(
            r"Request timed out", stripped, re.IGNORECASE
        ):
            hops.append(Hop(hop=hop_num, raw_line=stripped, loss=100.0))
            continue

        # Extract IP address
        ip_match = _IP_REGEX.search(stripped)
        ip = ip_match.group(0) if ip_match else None

        # Extract Hostname (word preceding IP or first non-number token)
        hostname: str | None = None
        if ip:
            # e.g. "ae-2.sjc.net (198.51.100.1)"
            m_host = re.search(r"([a-zA-Z0-9\.\-_]+)\s*\(" + re.escape(ip) + r"\)", stripped)
            if m_host:
                hostname = m_host.group(1)
            else:
                # tokens before IP
                tokens = stripped.split()
                if len(tokens) >= 2 and tokens[1] != ip:
                    candidate = tokens[1].strip("()")
                    if not candidate.isdigit() and "." in candidate:
                        hostname = candidate

        # Extract AS number if present e.g. "[AS2914]", "AS1234", "as15169"
        as_match = _AS_REGEX.search(stripped)
        asn = f"AS{as_match.group(1)}" if as_match else None

        # Extract RTTs (supports both standard '1.2 ms' and Windows '<1 ms')
        rtts: list[float] = []
        for wrtt in _WINDOWS_RTT_REGEX.finditer(stripped):
            val_str = wrtt.group(1)
            if val_str.startswith("<"):
                rtts.append(0.5)
            else:
                try:
                    rtts.append(float(val_str))
                except ValueError:
                    pass

        rtt_ms = min(rtts) if rtts else None

        # Extract flags (!H, !N, !X, !P)
        flags = re.findall(r"(![A-Z0-9]+)", stripped)

        # IATA & Geo inference
        iata: str | None = None
        city: str | None = None
        country: str | None = None
        lat: float | None = None
        lon: float | None = None

        if hostname:
            iata_res = geo.extract_iata_from_hostname(hostname)
            if iata_res:
                iata, coords = iata_res
                city = coords.city
                country = coords.country
                lat = coords.lat
                lon = coords.lon

        hops.append(
            Hop(
                hop=hop_num,
                ip=ip,
                hostname=hostname,
                rtt_ms=rtt_ms,
                rtts=rtts,
                asn=asn,
                city=city,
                country=country,
                lat=lat,
                lon=lon,
                iata=iata,
                flags=flags,
                raw_line=stripped,
            )
        )

    # Determine completion
    completed = False
    stop_reason = "max_hops_truncated"
    if hops:
        last_hop = hops[-1]
        if last_hop.ip and destination_ip and last_hop.ip == destination_ip:
            completed = True
            stop_reason = "destination_reached"
        elif last_hop.ip and not last_hop.rtt_ms:
            stop_reason = "no_reply"

    return ParsedTrace(
        destination=destination,
        destination_ip=destination_ip,
        hops=hops,
        completed=completed,
        stop_reason=stop_reason,
    )
