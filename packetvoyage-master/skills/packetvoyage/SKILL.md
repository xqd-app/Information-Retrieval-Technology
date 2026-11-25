---
name: packetvoyage
description: Guides the use of the PacketVoyage MCP server (research_host, analyze_voyage_text, voyage_investigate, run_protocol_experiment, list_known_iata_airports) for educational network traceroute analysis, fiber-optic physics verification, submarine cable telemetry, and packet voyage storytelling. Trigger this whenever the user wants to trace network hops to a host, understand why a route is slow, analyze a pasted traceroute / mtr / tracert / pathping / Looking Glass / Globalping output, understand the geographic journey and fiber optics path or submarine cable crossing across cities and oceans, ask whether a site is behind a CDN, investigate anomalies (silent * hops, latency inversions, speed-of-light violations), pick a good target host to demonstrate a real path (e.g. "分析したい" with no specific host given), or learn how the physical Internet works — from casual queries like "trace to 1.1.1.1", "why are there asterisks in my traceroute", "analyze this looking glass output", "explain this with the speed of light", or "パケットの経路を教えて". Always load this skill when "packetvoyage" is named explicitly.
---

# PacketVoyage: Educational Network & Physics Analyzer

PacketVoyage transforms dry traceroute output into an engaging, story-driven lesson in global Internet infrastructure, submarine cables, and fiber-optic physics.

Unlike raw diagnostic tools, PacketVoyage is designed to **teach *why* the Internet behaves the way it does** through rigorous physical calculation and router telemetry detective work.

---

## 🧭 Tool Map

| Tool | Cost / Speed | When to Use |
|---|---|---|
| `research_host` | Free, ~1-6s (parallel DNS, 10 min per-host cache), DNS-only by default | **Run this before tracing any target you're picking (not one the user pasted output for).** Resolves via DNS only, walks CNAMEs, flags CDN/anycast/GeoDNS from hostname + resolution signatures. Pass `enable_asn_lookup=True` to also opt in to a Team Cymru bulk whois query (sends the resolved IP to whois.cymru.com) for ASN/org/country and ASN-based CDN detection — mention this outbound call to the user before enabling it, since it's off by default precisely because it discloses the target IP to a third party. Without it, `as_name`/`as_country` are simply absent from the result. Additionally pass `enable_peeringdb_lookup=True` (requires `enable_asn_lookup=True` too) to also query peeringdb.com by ASN for network type, peering policy, and which Internet Exchanges it's on — self-reported, community data, so treat it as a hint, not ground truth. See Principle 6 for how to read `verdict`. |
| `analyze_voyage_text` | Free, Instant, Offline | **Primary entrypoint for pasted logs.** Parses text or JSON from terminal `traceroute`, Windows `tracert`, Looking Glasses, or Globalping (IPv4 hops only — see Principle 9). Returns a **dict** with `route_summary`, `detailed_story`/`voyage_narrative`, `matched_cables`, `oceanic_crossings`, `total_distance_km`, `mysteries`/`casefile_summary`. |
| `voyage_investigate` | Free / Instant if `data` given; local trace can take up to ~15s if `target` given | Run a detective investigation into a path's anomalies (silent gaps, latency inversions, geo illusions) and return a complete journey report **as a single Markdown string** (not structured data — use `analyze_voyage_text` if you need the dict fields). Pass `data` for offline analysis, or `target` to trace locally with optional `protocol="icmp"\|"tcp"\|"udp"` (default `icmp`, which needs raw-socket privileges on Linux — see Principle 10 if it comes back empty). |
| `run_protocol_experiment` | Free, Parallel Local | Runs parallel ICMP, TCP/443, and UDP/53 probes against a target to demonstrate firewall filtering and transport-layer routing differences. On Windows this falls back to `tracert` for all three and the comparison is not meaningful — see Principle 10. |
| `list_known_iata_airports` | Free, Reference | Lists the ~87 reference 3-letter IATA airport codes used to infer router geographic locations from PTR hostnames. Coverage is partial and matching is a simple token match — see Principle 5. |

---

## 🔬 Core Pedagogical Principles to Convey to Users

When presenting results to the user, always emphasize these physical realities and protocol truths:

### 1. The Speed of Light in Fiber (~0.67c ≈ 200,000 km/s)
- Light propagates through optical fiber (silica glass, refractive index n ≈ 1.49) at approximately **201,000 km/s** (~67% of vacuum light speed).
- **Rule of Thumb**: Every 1,000 km of fiber adds **~10 ms of Round-Trip Time (RTT)**.
- **Trans-Pacific Crossing**: ~8,000–9,000 km → Theoretical physical minimum RTT is ~80–90 ms.
- **Trans-Atlantic Crossing**: ~5,500–6,500 km → Theoretical physical minimum RTT is ~55–65 ms.

### 2. Disproving GeoIP "Illusions" with Physics
- Many GeoIP databases associate IP addresses with corporate headquarters (e.g., California or Virginia) even when the router is physically located in Tokyo.
- **The Proof**: If Hop N (Tokyo, 2 ms RTT) jumps to Hop N+1 (GeoIP says "USA", 3 ms RTT), **it is physically impossible for the packet to have reached the USA and returned in 1 ms**. The router is physically in Japan.

### 3. The Truth Behind Asterisks (`* * *`)
- An asterisk does **NOT** mean the link is broken or traffic is being dropped.
- Regular user traffic is forwarded in hardware ASICs (Data Plane) in nanoseconds.
- Responding with an `ICMP Time Exceeded` packet requires sending the packet to the router's slow CPU (Control Plane). Routers intentionally rate-limit or drop ICMP generation to protect themselves from denial-of-service attacks.

### 4. Latency Inversions (Why Hop 5 is Slower than Hop 6)
- If Hop 5 reports 80 ms but Hop 6 reports 20 ms, Hop 5's router is slow at generating ICMP replies. The actual forwarding path is running at 20 ms.

### 5. Interpreting Router Hostnames (PTR & IATA Codes) & Subsea Cables
- High-tier carrier routers frequently embed 3-letter IATA airport codes (e.g., `nrt` / `hnd` = Tokyo, `sjc` / `sfo` = Bay Area, `lax` = Los Angeles, `ord` = Chicago, `iad` = Washington DC, `lhr` = London, `fra` = Frankfurt, `sin` = Singapore).
- Combine RTT deltas (+70~90ms jump) with IATA transitions (e.g., `tyo` ➔ `sjc`) and known submarine cable systems (e.g., PC-1, FASTER, Unity, Jupiter, MAREA) to explain the physical path in vivid, structured narrative text.
- IATA matching is a simple token match against a ~87-code reference list (`list_known_iata_airports`), not a verified geolocation — codes like `sin`, `man`, `bom`, or `ord` can also appear as customer labels or unrelated abbreviations in a hostname, and cities outside the ~87 covered are silently unresolved. If an IATA-derived location contradicts the RTT physics (e.g. implies continent-hopping in 1 ms), treat it as a false match and say so rather than narrating it as fact.

### 6. CDN/WAF Fronting Isn't Always Auto-Flagged
- `research_host`'s `verdict` field takes one of four values: `cdn` (provider-signature or anycast match — e.g. Cloudflare, Akamai, Fastly, Edgio, StackPath, Limelight, CloudFront are already detected here, so don't re-flag them manually), `geodns` (different resolvers return different IPs — the path is resolver/vantage-point dependent, which is itself a great teaching moment; explain this rather than treating it as a failure), `direct` (single stable answer, best demo candidate), or `dns_error` (name didn't resolve — discard as a candidate). Don't confuse this with the unrelated `verdict` field inside a Mystery/Case File entry from `analyze_voyage_text`, which is a free-text conclusion about an anomaly, not one of these four values.
- A reverse-proxy/WAF like **Incapsula/Imperva** or **Sucuri** can still return `verdict: "direct"` while only terminating at a security edge, not the true origin — these aren't covered by the automatic CDN keyword match. Treat any ASN whose `as_name` reads as such a vendor as edge-fronted even when `verdict` says direct. This `as_name` check only works when `enable_asn_lookup=True` was passed (see Tool Map) — without it there's no `as_name` to check.
- When picking a *demonstration* target (not a user-supplied one), prefer a host that resolves to a single stable IP whose ASN's `country_code` and `as_name` actually match the country you're trying to illustrate (e.g. a university mirror, an AS registered to a local telco/ISP/govt/ac.nz-style org) — commercial sites are very often CDN- or GeoDNS-fronted today and make poor "real path" demos.
- `enable_peeringdb_lookup=True` adds network type (Content/NSP/ISP/...), peering policy, and IX presence per ASN from peeringdb.com. This is self-reported and often absent — most ASNs, especially smaller or non-Western ones, have no PeeringDB record at all, which is normal and not itself evidence of anything. Don't treat a missing record as "this network is obscure/suspicious"; just note the data wasn't available.

### 7. Pasted Logs From a Third-Party Vantage Point Need Their Origin Read Manually
- A plain local `traceroute`/`tracert` paste starts at the user's own machine, so the origin is implicit. But Looking Glass and Globalping pastes run from *someone else's* vantage point (a remote router, a probe in another country) — that origin is a separate piece of data that lives outside the hop list and `analyze_voyage_text` does not surface it in its output.
- Concretely: Globalping's JSON shape (`{"result": {"hops": [...]}, "probe": {...}}`) is parsed for `result.hops` only — the sibling `probe` object (`probe.city`, `probe.country`, `probe.network`/`asn`) is silently dropped. Its plain-text output instead opens with a `> <target> from <City, Country> (ASxxxxx)`-style header carrying the same info. Looking Glass pages usually name the router/city in their own page header or prompt (e.g. `router.isp.jp> traceroute ...`) rather than in the hop lines.
- Since every physics check in this skill (speed-of-light distance math, ocean-crossing validation) needs a known start point, always read the origin out of whatever surrounds the pasted hop list yourself before narrating, and state it explicitly ("this trace started from a Globalping probe in Frankfurt, DE" / "from a Looking Glass router in Tokyo") — don't let the narrative default to assuming the trace started at the user's own location.
- The same applies to the **destination**: `analyze_voyage_text`'s destination extraction only recognizes `traceroute to ...` / `Tracing route to ...`-style headers. Globalping's plain-text `> <target> from <City, Country> (ASxxxxx)` header doesn't match either pattern, so the destination also comes back unset for that format — read both the origin and the destination out of the pasted text yourself and state them explicitly.
- If the origin isn't visible anywhere in what was pasted, ask the user where the trace was run from rather than guessing.

### 8. Multi-Location Pastes Are Split Into One Block Per Vantage Point
- Some sources let a user run the same target from several vantage points at once and export it as one blob — e.g. Globalping's multi-probe comparison (a JSON array, one element per probe) or a user pasting results from two different Looking Glasses back to back. `analyze_voyage_text` expects one trace's worth of data per call, so a multi-element blob won't parse cleanly as a single voyage.
- If the user pastes a multi-location comparison, split it: call `analyze_voyage_text` once per vantage-point block, keeping each one's origin (Principle 7) attached to its own narrative.
- This is a distinct, valuable lesson on its own — the same destination reached from e.g. Tokyo vs. Frankfurt vs. São Paulo will show completely different paths, hop counts, and RTTs. After analyzing each block, explicitly compare them for the user (which region got the shortest path, any surprising asymmetries) instead of just presenting them as isolated cases.

### 9. Parsing Limits: IPv4 Only, MTR Columns, and Private IPs
- The hop parser only recognizes IPv4 addresses. If a pasted trace contains IPv6 hops (`2001:...`-style), those hops parse with no IP, which the mystery detector reads as a **silent, non-responding router** — producing a confidently wrong Case File for hops that actually responded fine. If you see IPv6 addresses in a paste, don't trust the mystery/silent-gap output; narrate the RTTs and PTR names manually instead.
- `mtr` output has multiple numeric columns (Loss%, Snt, Last, Avg, Best, Wrst) per hop, not one RTT — don't assume the first or last number in an `mtr` line is "the" RTT without checking the column header the user pasted.
- A private/RFC1918 first hop (`10.x.x.x`, `192.168.x.x`, `172.16-31.x.x`) is the user's home router — treat it as physical distance ≈ 0 and skip GeoIP/IATA reasoning for it, since public geolocation data is meaningless for private space.

### 10. Local Traces and Protocol Experiments Can Fail Silently
- `voyage_investigate(target=...)` and `run_protocol_experiment` run a local `traceroute`/`tracert` process. On failure (missing binary, 15s per-attempt timeout, or — for the default `protocol="icmp"` — missing raw-socket privileges on Linux) they don't raise an error; they return a normal-looking result with zero or very few hops. If a local trace comes back empty or unexpectedly short, don't narrate it as "the path ends here" — retry with `protocol="udp"` (usually needs no elevated privileges), and if it's still empty, tell the user and ask them to paste their own local `traceroute`/`tracert` output for `analyze_voyage_text` instead of guessing.
- On Windows, `run_protocol_experiment`'s three probes all fall back to `tracert` regardless of the requested protocol, so identical results across ICMP/TCP/UDP on Windows mean "the tool can't vary protocol here," not "no firewall filtering is happening" — say so rather than drawing a firewall conclusion from it.

---

## 🗺️ Decision Flow

1. **User pastes a traceroute / mtr / Looking Glass / Globalping log**:
   - If the paste is from a remote vantage point (Looking Glass, Globalping) rather than the user's own machine, first extract that origin (and destination — see Principle 7) yourself. If it bundles multiple vantage points, split per Principle 8 and analyze each separately.
   - Check for IPv6 hops, `mtr`-style multi-column RTTs, or a private/RFC1918 first hop before trusting the raw numbers (Principle 9).
   - Call `analyze_voyage_text(data=...)` (once per vantage point if multiple).
   - Present the packet's journey using `route_summary` and `detailed_story` / `voyage_narrative`, and pull submarine cable telemetry from `matched_cables`, `oceanic_crossings`, and `total_distance_km`.
   - Highlight any detected anomalies from `mysteries` / `casefile_summary`.
   - If every hop came back unresponsive, or the parse looks empty/degenerate, check for the IPv6 or MTR pitfalls in Principle 9 before concluding the path is broken.

2. **User wants to trace/analyze a target but gives no specific host** (e.g. "◯◯国のホストを分析したい", "trace something in Brazil"):
   - Don't guess-and-trace blind. Shortlist 2-4 candidate hosts for that region/country, then run `research_host` on each *before* tracing.
   - Discard candidates with `verdict: "cdn"` or `verdict: "dns_error"` (see Principle 6) — explain briefly why they were rejected, it's part of the lesson. A `verdict: "geodns"` candidate is usable but explain that the path is resolver-dependent before proceeding.
   - Pick the first candidate with a `verdict: "direct"` result (or, failing that, `geodns`) and an ASN whose org/country genuinely matches the target region, then proceed to `voyage_investigate` on it.

3. **User gives a specific hostname to trace**:
   - Run `research_host` first if you haven't already established it's a direct origin. If it's CDN-fronted, tell the user up front that the trace will only reach the nearest edge, not the origin, and ask whether they still want to proceed or want to find the origin IP instead.
   - Run `voyage_investigate(target=...)` to trace and produce the complete casefile & geographic journey report (a Markdown string — see Tool Map).
   - If the result comes back empty or with very few hops, don't report "the trace stopped here" — walk through the failure modes in Principle 10 (privileges, timeout, missing binary) first, retry with `protocol="udp"`, and fall back to asking the user for their own local trace output if it's still empty.

4. **User asks "Why are there asterisks / stars in my traceroute?"**:
   - Explain the Control Plane vs. Data Plane distinction using PacketVoyage's Sleuth insights.

5. **User asks why a site is blocked or unreachable**:
   - Call `run_protocol_experiment(target=...)` to compare ICMP vs. TCP/443 vs. UDP/53. Explain how firewalls allow web traffic while blocking traceroute probes.
   - If all three results are identical, check whether the user is on Windows before concluding there's no filtering — see Principle 10.
