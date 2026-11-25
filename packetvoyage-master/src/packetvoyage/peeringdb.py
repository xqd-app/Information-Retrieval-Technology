"""PeeringDB network lookups (opt-in, HTTPS, no API key required).

Queries the public PeeringDB REST API (https://www.peeringdb.com/apidocs/)
for network records by ASN: org name, network type (Content/NSP/ISP/...),
general peering policy, and which Internet Exchanges the ASN is present on.
This is community-maintained, self-reported data - it can be missing,
stale, or wrong for any given ASN - so callers should treat it as a hint,
not ground truth.

Anonymous (no API key) queries are capped by PeeringDB at 20 requests/minute
per IP, and identical repeated queries are throttled further, so this module
makes exactly one batched HTTP request per ``annotate_asns`` call (via the
``asn__in`` filter) rather than one request per ASN.

https://docs.peeringdb.com/howto/work_within_peeringdbs_query_limits/
"""

from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from collections.abc import Sequence
from typing import Any

logger = logging.getLogger("packetvoyage")

API_BASE = "https://www.peeringdb.com/api"
TIMEOUT_SEC = 8.0
_MAX_ASNS_PER_QUERY = 150
_USER_AGENT = "packetvoyage-mcp/0.1 (educational traceroute tool; +https://github.com/)"


def _query(asns: list[int]) -> dict[str, Any]:
    """Fetch net records for `asns` in a single request (depth=2 embeds netixlan_set)."""
    params = {
        "asn__in": ",".join(str(a) for a in asns),
        "depth": "2",
    }
    url = f"{API_BASE}/net?{urllib.parse.urlencode(params)}"
    request = urllib.request.Request(
        url, headers={"User-Agent": _USER_AGENT, "Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=TIMEOUT_SEC) as resp:  # noqa: S310 - fixed https host
        body = resp.read()
    return json.loads(body)


def _parse(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Parse a PeeringDB `/api/net` response into {asn_str: {...}}."""
    out: dict[str, dict[str, Any]] = {}
    for net in payload.get("data", []):
        asn = net.get("asn")
        if not asn:
            continue
        ix_entries = net.get("netixlan_set") or []
        out[str(asn)] = {
            "name": net.get("name") or None,
            "aka": net.get("aka") or None,
            "info_type": net.get("info_type") or None,
            "policy_general": net.get("policy_general") or None,
            "website": net.get("website") or None,
            "ix_count": len(ix_entries),
            "ix_names": sorted({ix.get("name") for ix in ix_entries if ix.get("name")}),
        }
    return out


def annotate_asns(asns: Sequence[str | int]) -> dict[str, dict[str, Any] | None]:
    """Look up PeeringDB network records for `asns` in one batched request.

    Best-effort: any failure (network, timeout, HTTP error, malformed JSON)
    yields None for every requested ASN instead of raising. ASNs without a
    PeeringDB network record (most ASNs don't self-register) also yield None
    - that's a normal, expected outcome, not an error.
    """
    unique: list[int] = []
    seen: set[int] = set()
    for asn in asns:
        try:
            num = int(asn)
        except (TypeError, ValueError):
            continue
        if num > 0 and num not in seen:
            seen.add(num)
            unique.append(num)

    if not unique:
        return {}

    keys = [str(a) for a in unique]
    if len(unique) > _MAX_ASNS_PER_QUERY:
        logger.debug(
            "peeringdb: truncating %d ASNs to %d per query limit", len(unique), _MAX_ASNS_PER_QUERY
        )
        unique = unique[:_MAX_ASNS_PER_QUERY]

    try:
        payload = _query(unique)
        parsed = _parse(payload)
    except Exception as exc:  # noqa: BLE001 - enrichment never fails the caller
        logger.debug("peeringdb lookup failed: %s", exc)
        return dict.fromkeys(keys)
    return {key: parsed.get(key) for key in keys}
