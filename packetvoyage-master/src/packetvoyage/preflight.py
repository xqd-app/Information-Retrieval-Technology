"""Host preflight: research a target's real identity before tracing it.

Runs entirely on the MCP server host (no AWS involvement). It resolves the
target with the system resolver plus public resolvers (1.1.1.1, 8.8.8.8) for
both A and AAAA records, walks the CNAME chain, annotates the resulting IPs
with ASN/org (Team Cymru bulk whois - no HTTP, no API key), and classifies
the host:

verdict = "cdn"       -> fronted by a global CDN / anycast network: the case
                         that defeats a traceroute (the trace terminates at
                         the nearest CDN edge, the origin path is never shown)
        = "geodns"    -> different resolvers see different IPs (GeoDNS /
                         geo-routed CDN) - regional edges, origin still masked
        = "direct"    -> single IP, no CDN signals - fine to traceroute
        = "dns_error" -> could not resolve locally

Everything is best-effort: DNS or ASN lookup failures degrade the verdict,
never raise. Results are cached per process (10 min).
"""

from __future__ import annotations

import ipaddress
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

import dns.rdatatype
import dns.resolver

from packetvoyage import cymru, peeringdb

logger = logging.getLogger("packetvoyage")

DEFAULT_PUBLIC_RESOLVERS = ["1.1.1.1", "8.8.8.8"]
_RESOLVER_TIMEOUT_SEC = 3.0
_CNAME_MAX = 10
_CACHE_TTL_SEC = 600.0

# CDN hostname suffix -> provider, matched on CNAME targets. The leading dot
# keeps the match on the full label ("cdn.akamai.net" matches, "fakeakamai.net"
# does not); the bare apex without subdomain is also accepted.
CDN_HOSTNAMES: tuple[tuple[str, str], ...] = (
    (".cloudfront.net", "Amazon CloudFront"),
    (".awsglobalaccelerator.com", "AWS Global Accelerator"),
    (".edgekey.net", "Akamai"),
    (".akamaiedge.net", "Akamai"),
    (".akamai.net", "Akamai"),
    (".edgesuite.net", "Akamai"),
    (".akamaized.net", "Akamai"),
    (".fastly.net", "Fastly"),
    (".fastlylb.net", "Fastly"),
    (".cloudflare.net", "Cloudflare"),
    (".cloudflare.com", "Cloudflare"),
    (".workers.dev", "Cloudflare"),
    (".pages.dev", "Cloudflare Pages"),
    (".edgecastcdn.net", "Edgio"),
    (".edgio.net", "Edgio"),
    (".llnw.net", "Limelight"),
    (".azureedge.net", "Microsoft Azure"),
    (".azurefd.net", "Microsoft Azure"),
    (".trafficmanager.net", "Microsoft Azure"),
    (".stackpathcdn.com", "StackPath"),
    (".netlify.app", "Netlify"),
    (".vercel.app", "Vercel"),
    (".web.app", "Firebase Hosting"),
    (".firebaseapp.com", "Firebase Hosting"),
    (".github.io", "GitHub Pages"),
)

# Dedicated CDN / anycast ASNs (exact match against the ASN number). Generic
# cloud ASNs (Amazon 16509, Google 15169, Microsoft 8075, ...) are left out on
# purpose: they also host plain origin servers and would false-positive.
CDN_ASNS: dict[int, str] = {
    13335: "Cloudflare",
    20946: "Cloudflare",
    54113: "Fastly",
    20940: "Akamai",
    16625: "Akamai",
    15133: "Edgio",
    33438: "StackPath",
    22822: "Limelight",
}

# Fallback: substring match against the Cymru AS name (covers "CLOUDFLARENET",
# "AKAMAI-ASN1", "FASTLY" and the like).
CDN_ORG_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("cloudflare", "Cloudflare"),
    ("akamai", "Akamai"),
    ("fastly", "Fastly"),
    ("edgecast", "Edgio"),
    ("edgio", "Edgio"),
    ("stackpath", "StackPath"),
    ("limelight", "Limelight"),
    ("cloudfront", "Amazon CloudFront"),
)

_CACHE: dict[str, tuple[float, "HostReport"]] = {}
_CACHE_LOCK = threading.Lock()


@dataclass
class HostReport:
    host: str
    verdict: str = "dns_error"
    providers: list[str] = field(default_factory=list)
    anycast: bool = False
    cname_chain: list[str] = field(default_factory=list)
    addresses: list[str] = field(default_factory=list)
    asn: dict[str, dict[str, Any]] = field(default_factory=dict)
    resolver_sets: dict[str, list[str]] = field(default_factory=dict)
    asn_lookup_skipped: bool = False
    peering: dict[str, dict[str, Any]] = field(default_factory=dict)
    peeringdb_lookup_skipped: bool = True
    peeringdb_lookup_skip_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "host": self.host,
            "verdict": self.verdict,
            "providers": list(self.providers),
            "anycast": self.anycast,
            "cname_chain": list(self.cname_chain),
            "addresses": list(self.addresses),
            "asn": self.asn,
            "resolver_sets": self.resolver_sets,
            "asn_lookup_skipped": self.asn_lookup_skipped,
            "peering": self.peering,
            "peeringdb_lookup_skipped": self.peeringdb_lookup_skipped,
            "peeringdb_lookup_skip_reason": self.peeringdb_lookup_skip_reason,
        }


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def hostname_provider(name: str) -> str | None:
    """CDN provider for a hostname (CNAME target), else None."""
    lowered = name.lower().rstrip(".")
    for suffix, provider in CDN_HOSTNAMES:
        bare = suffix[1:]
        if lowered == bare or lowered.endswith(suffix):
            return provider
    return None


def classify(
    host: str,
    cname_chain: list[str] | None = None,
    resolver_sets: dict[str, list[str]] | None = None,
    asn: dict[str, dict[str, Any]] | None = None,
    asn_lookup_skipped: bool = False,
) -> HostReport:
    """Combine DNS + ASN signals into a verdict (pure, no network).

    ``cname_chain`` is the full CNAME chain for the query host; ``resolver_sets``
    maps resolver label -> IPs it returned; ``asn`` maps IP -> Cymru annotation.
    """
    chain = list(cname_chain or [])
    sets = {k: list(v) for k, v in (resolver_sets or {}).items()}
    asn = asn or {}
    report = HostReport(
        host=host,
        cname_chain=chain,
        resolver_sets=sets,
        asn=asn,
        asn_lookup_skipped=asn_lookup_skipped,
    )
    ips = sorted({ip for ip_list in sets.values() for ip in ip_list})
    report.addresses = ips

    providers: set[str] = set()
    for name in chain:
        provider = hostname_provider(name)
        if provider:
            providers.add(provider)
    asn_hit = False
    for ip in ips:
        ann = asn.get(ip) or {}
        try:
            asn_num = int(ann.get("asn") or 0)
        except ValueError:
            asn_num = 0
        if asn_num and asn_num in CDN_ASNS:
            providers.add(CDN_ASNS[asn_num])
            asn_hit = True
            continue
        as_name = (ann.get("as_name") or "").lower()
        for keyword, provider in CDN_ORG_KEYWORDS:
            if keyword in as_name:
                providers.add(provider)

    answered = [ip_list for ip_list in sets.values() if ip_list]
    unique = {ip for ip_list in answered for ip in ip_list}
    diverse = len(answered) >= 2 and len({tuple(sorted(s)) for s in answered}) > 1

    report.providers = sorted(providers)
    if providers:
        report.verdict = "cdn"
    elif diverse:
        report.verdict = "geodns"
    elif unique:
        report.verdict = "direct"
    report.anycast = asn_hit or (bool(providers) and len(unique) == 1)
    return report


@dataclass
class _Resolved:
    ips: list[str] = field(default_factory=list)
    chain: list[str] = field(default_factory=list)


def _make_resolver(nameservers: list[str] | None) -> dns.resolver.Resolver:
    if nameservers:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = list(nameservers)
    else:
        resolver = dns.resolver.Resolver()
    resolver.lifetime = _RESOLVER_TIMEOUT_SEC
    resolver.timeout = _RESOLVER_TIMEOUT_SEC
    return resolver


def _resolve_with(resolver: dns.resolver.Resolver, name: str, rdtype: str) -> _Resolved:
    """A/AAAA-record walk following the CNAME chain (bounded depth)."""
    result = _Resolved(chain=[name])
    qname = name
    want = dns.rdatatype.from_text(rdtype)
    for _ in range(_CNAME_MAX):
        ans = resolver.resolve(qname, rdtype, raise_on_no_answer=False)
        target: str | None = None
        for rrset in ans.response.answer:
            if rrset.rdtype == dns.rdatatype.CNAME:
                candidate = rrset[0].target.to_text(omit_final_dot=True)
                if candidate.lower() != qname.lower():
                    target = candidate
            elif rrset.rdtype == want:
                result.ips.extend(rr.address for rr in rrset)
        if target is None:
            break
        result.chain.append(target)
        qname = target
    return result


def resolve_host(
    host: str, extra_resolvers: list[str] | None = None
) -> tuple[dict[str, list[str]], list[str]]:
    """Resolve `host` with the system resolver + extra public resolvers.

    Returns ``(resolver_sets, cname_chain)``: ``resolver_sets`` maps a resolver
    label ("system", then the IPs in ``extra_resolvers``) -> A+AAAA records it
    returned (missing label = that resolver failed both queries). The CNAME
    chain comes from whichever of the two queries walked the longest chain.
    Each resolver is time-bounded (~3 s) per record type; failures degrade to
    empty sets, never raise.
    """
    tasks: list[tuple[str, list[str] | None]] = [("system", None)]
    for ns in extra_resolvers or DEFAULT_PUBLIC_RESOLVERS:
        tasks.append((ns, [ns]))

    def one(task: tuple[str, list[str] | None]) -> tuple[str, _Resolved]:
        label, nameservers = task
        resolver = _make_resolver(nameservers)
        merged = _Resolved()
        for rdtype in ("A", "AAAA"):
            try:
                resolved = _resolve_with(resolver, host, rdtype)
            except Exception as exc:  # noqa: BLE001 - degrade per resolver/rdtype
                logger.debug("resolver %s failed for %s (%s): %s", label, host, rdtype, exc)
                continue
            merged.ips.extend(resolved.ips)
            if len(resolved.chain) > len(merged.chain):
                merged.chain = resolved.chain
        return label, merged

    sets: dict[str, list[str]] = {}
    chains: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=len(tasks)) as pool:
        for future in as_completed([pool.submit(one, task) for task in tasks]):
            label, resolved = future.result()
            sets[label] = resolved.ips
            chains[label] = resolved.chain

    chain: list[str] = []
    for label in dict(tasks):
        if sets.get(label) and chains.get(label):
            chain = chains[label]
            break
    return sets, chain


def _cache_get(host: str) -> HostReport | None:
    with _CACHE_LOCK:
        entry = _CACHE.get(host)
        if entry and time.monotonic() - entry[0] < _CACHE_TTL_SEC:
            return entry[1]
    return None


def _cache_put(host: str, report: HostReport) -> None:
    with _CACHE_LOCK:
        _CACHE[host] = (time.monotonic(), report)


def _annotate_peering(report: HostReport, enable_peeringdb_lookup: bool) -> None:
    """Best-effort PeeringDB enrichment, mutating `report` in place.

    Requires ASN numbers already resolved via Cymru (``report.asn``); PeeringDB
    is queried by ASN, not by IP. If ``enable_asn_lookup`` wasn't also set,
    there's nothing to key the query on, so this is skipped with a reason.
    """
    if not enable_peeringdb_lookup:
        report.peeringdb_lookup_skipped = True
        report.peeringdb_lookup_skip_reason = None
        return

    asn_numbers: list[str] = sorted(
        {str(ann["asn"]) for ann in report.asn.values() if ann and ann.get("asn")}
    )
    if not asn_numbers:
        report.peeringdb_lookup_skipped = True
        report.peeringdb_lookup_skip_reason = (
            "no ASN numbers available - enable_asn_lookup must also be True"
        )
        return

    try:
        report.peering = {
            asn: (info or {}) for asn, info in peeringdb.annotate_asns(asn_numbers).items() if info
        }
    except Exception as exc:  # noqa: BLE001 - best-effort peering annotation
        logger.debug("peeringdb annotation failed: %s", exc)
        report.peering = {}
    report.peeringdb_lookup_skipped = False
    report.peeringdb_lookup_skip_reason = None


def research_host(
    host: str,
    extra_resolvers: list[str] | None = None,
    enable_asn_lookup: bool = False,
    enable_peeringdb_lookup: bool = False,
) -> HostReport:
    """Local research of `host`: DNS resolve + optional ASN/peering + CDN verdict.

    Entry point for the ``research_host`` MCP tool. Never raises; DNS/ASN/
    peering failures degrade the verdict. Results are cached per host (custom
    resolvers bypass the cache).

    ``enable_asn_lookup`` opts in to querying Team Cymru's bulk whois service
    (whois.cymru.com:43) to annotate resolved IPs with ASN/org/country. This
    is off by default; without it, CDN detection falls back to CNAME hostname
    signatures only (ASN-only CDNs and anycast detection are skipped, and the
    verdict may under-report "cdn").

    ``enable_peeringdb_lookup`` opts in to an additional HTTPS request to the
    public PeeringDB API (peeringdb.com) for each resolved ASN, annotating
    network type, general peering policy, and which Internet Exchanges the
    ASN is present on. It requires ``enable_asn_lookup`` to also be True
    (PeeringDB is queried by ASN, which only Cymru provides) and discloses the
    resolved ASN numbers (not the target host/IP) to peeringdb.com.
    """
    host = host.strip().rstrip(".")
    if not host:
        return HostReport(host="(empty)")

    if _is_ip_literal(host):
        ip_asn: dict[str, dict[str, Any]] = {}
        if enable_asn_lookup:
            ip_asn = {k: (v or {}) for k, v in cymru.annotate_ips([host]).items()}
        report = classify(
            host,
            None,
            {"local": [host]},
            ip_asn,
            asn_lookup_skipped=not enable_asn_lookup,
        )
        _annotate_peering(report, enable_peeringdb_lookup)
        return report

    if extra_resolvers is None:
        cached = _cache_get(host)
        if (
            cached is not None
            and cached.asn_lookup_skipped == (not enable_asn_lookup)
            and cached.peeringdb_lookup_skipped == (not enable_peeringdb_lookup)
        ):
            return cached

    resolver_sets, chain = resolve_host(host, extra_resolvers)
    ips = sorted({ip for ip_list in resolver_sets.values() for ip in ip_list})
    asn: dict[str, dict[str, Any]] = {}
    if ips and enable_asn_lookup:
        try:
            asn = {ip: (ann or {}) for ip, ann in cymru.annotate_ips(ips).items()}
        except Exception as exc:  # noqa: BLE001 - best-effort ASN annotation
            logger.debug("asn annotation for %s failed: %s", host, exc)

    report = classify(host, chain, resolver_sets, asn, asn_lookup_skipped=not enable_asn_lookup)
    _annotate_peering(report, enable_peeringdb_lookup)
    if extra_resolvers is None and report.verdict != "dns_error":
        _cache_put(host, report)
    return report


def _ip_hint(ann: dict[str, Any]) -> str:
    """Inline annotation for one resolved IP: ASN/org."""
    parts = []
    if ann.get("asn"):
        parts.append(f"AS{ann['asn']}")
    if ann.get("as_name"):
        parts.append(ann["as_name"])
    if ann.get("country_code"):
        parts.append(ann["country_code"])
    return " · ".join(parts)


def format_report(report: HostReport) -> str:
    """Human-readable preflight report for the MCP tool result."""
    lines = [f"host: {report.host}"]
    if report.cname_chain:
        lines.append("cnames: " + " -> ".join(report.cname_chain))
    if report.addresses:
        sets = report.resolver_sets
        same = len({tuple(ips) for ips in sets.values() if ips}) <= 1
        told = "consistent" if same else "differs across resolvers (GeoDNS)"
        labels = ", ".join(sorted(sets)) or "?"
        lines.append(f"resolved: {len(report.addresses)} IPs via {labels} ({told})")
        for ip in report.addresses:
            hint = _ip_hint(report.asn.get(ip) or {})
            lines.append(f"  {ip:<16} {hint}" if hint else f"  {ip}")
    else:
        lines.append("resolved: none (DNS failure)")

    verdict = report.verdict
    if verdict == "cdn":
        providers = ", ".join(report.providers) or "a global CDN"
        anycast = " (anycast)" if report.anycast else ""
        lines.append(
            "verdict: "
            f"{report.host} is fronted by {providers}{anycast} - a traceroute "
            "will terminate at the nearest CDN edge, not the real origin path. "
            "Trace the origin IP/hostname instead if you can find it."
        )
    elif verdict == "geodns":
        lines.append(
            "verdict: "
            f"{report.host} resolves to different IPs per resolver (GeoDNS / "
            "geo-routed CDN): the traced path depends on which edge you hit."
        )
    elif verdict == "direct":
        lines.append(
            "verdict: "
            f"{report.host} shows no CDN signals: a traceroute should reveal "
            "the real path to the origin."
        )
    else:
        lines.append(f"verdict: could not resolve {report.host} locally (DNS problem)")

    if report.asn_lookup_skipped:
        lines.append(
            "note: ASN/org lookup skipped (opt-in) - no query was sent to Team Cymru "
            "whois.cymru.com. Pass enable_asn_lookup=True for ASN-based CDN/anycast "
            "detection and org/country annotation."
        )

    if report.peering:
        lines.append("peering (PeeringDB, self-reported - may be missing or stale):")
        for asn, info in sorted(report.peering.items()):
            name = info.get("name") or "?"
            info_type = info.get("info_type") or "unknown type"
            policy = info.get("policy_general") or "unknown policy"
            ix_count = info.get("ix_count") or 0
            lines.append(
                f"  AS{asn} {name} - {info_type}, {policy} peering policy, on {ix_count} IX(es)"
            )
    elif report.peeringdb_lookup_skipped and report.peeringdb_lookup_skip_reason:
        lines.append(f"note: PeeringDB lookup skipped - {report.peeringdb_lookup_skip_reason}")
    elif report.peeringdb_lookup_skipped:
        lines.append(
            "note: PeeringDB lookup skipped (opt-in) - no query was sent to peeringdb.com. "
            "Pass enable_peeringdb_lookup=True (with enable_asn_lookup=True) for network "
            "type, peering policy, and IX presence."
        )
    return "\n".join(lines)
