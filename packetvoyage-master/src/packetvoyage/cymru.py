"""Team Cymru IP-to-ASN bulk whois lookups.

Uses the free bulk interface of whois.cymru.com:43: one TCP connection
carries every IP in a batch ("begin\\nverbose\\n<ip>...\\nend\\n"), which is
the mode Team Cymru asks automated tools to use (per-IP individual whois
connections get null-routed). No HTTP, no API key, no published per-minute
rate limit to respect - failures just degrade to no annotation.

https://www.team-cymru.com/ip-asn-mapping
"""

from __future__ import annotations

import ipaddress
import logging
import socket
from typing import Any

logger = logging.getLogger("packetvoyage")

HOST = "whois.cymru.com"
PORT = 43
TIMEOUT_SEC = 8.0
_RECV_CHUNK = 4096


def _query(ips: list[str]) -> str:
    """Send one bulk whois query and return the raw pipe-delimited response."""
    body = "begin\nverbose\n" + "\n".join(ips) + "\nend\n"
    chunks: list[bytes] = []
    with socket.create_connection((HOST, PORT), timeout=TIMEOUT_SEC) as sock:
        sock.sendall(body.encode("ascii"))
        sock.settimeout(TIMEOUT_SEC)
        try:
            while True:
                chunk = sock.recv(_RECV_CHUNK)
                if not chunk:
                    break
                chunks.append(chunk)
        except TimeoutError:
            # The server closes on "end" but a slow/partial read can time out
            # after useful data has already arrived; use what was received.
            pass
    return b"".join(chunks).decode("utf-8", errors="replace")


def _parse(raw: str) -> dict[str, dict[str, Any]]:
    """Parse bulk whois output into {ip: {asn, as_name, prefix, ...}}.

    Each data line is ``AS | IP | BGP Prefix | CC | Registry | Allocated |
    AS Name``. The header line (and any "Bulk mode" banner) is skipped.
    """
    out: dict[str, dict[str, Any]] = {}
    for line in raw.splitlines():
        if "|" not in line:
            continue
        cols = [c.strip() for c in line.split("|")]
        if len(cols) < 7 or cols[0] in ("AS", ""):
            continue
        as_num, ip, prefix, cc, registry, allocated, as_name = cols[:7]
        if as_num in ("NA",) or not ip:
            continue
        out[ip] = {
            "asn": as_num,
            "as_name": as_name or None,
            "prefix": prefix or None,
            "country_code": cc or None,
            "registry": registry or None,
            "allocated": allocated or None,
        }
    return out


def annotate_ips(ips: list[str]) -> dict[str, dict[str, Any] | None]:
    """Bulk ASN/org lookup for `ips` in a single connection.

    Best-effort: any failure (network, timeout, malformed response) yields
    None for every requested IP instead of raising.
    """
    valid_ips: list[str] = []
    unique = sorted(set(ips))
    for ip in unique:
        try:
            ipaddress.ip_address(ip.strip())
            valid_ips.append(ip.strip())
        except ValueError:
            continue

    if not valid_ips:
        return dict.fromkeys(unique)
    try:
        raw = _query(valid_ips)
        parsed = _parse(raw)
    except Exception as exc:  # noqa: BLE001 - enrichment never fails the caller
        logger.debug("cymru bulk lookup failed: %s", exc)
        return dict.fromkeys(unique)
    return {ip: parsed.get(ip) for ip in unique}
