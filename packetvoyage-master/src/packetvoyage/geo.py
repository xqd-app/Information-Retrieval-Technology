"""Geographic, physics, astronomical, and IATA airport inference helpers.

Provides:
- Fiber optic physics: speed of light in optical fiber (~0.67c ≈ 200,000 km/s) and RTT floor calculation.
- Haversine great-circle distance & geodesic densified arcs (continuous longitude across antimeridian).
- Astronomical day/night terminator curve, solar elevation, solar time, and seasonal snapshot.
- PTR hostname parsing to infer city/airport locations using standard IATA 3-letter airport codes.
- AWS region default hub coordinates.
- Well-known oceanic trans-continental corridor facts.
"""

from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any, NamedTuple

# Physics constants
SPEED_OF_LIGHT_VACUUM_KM_S = 299792.458
SPEED_OF_LIGHT_KM_S = SPEED_OF_LIGHT_VACUUM_KM_S
FIBER_REFRACTIVE_INDEX = 1.49  # Typical silica glass core (n ≈ 1.468 - 1.50)
FIBER_SPEED_KM_S = 200000.0  # ~66.7% of c in glass; standard fiber propagation speed
SPEED_OF_LIGHT_FIBER_KM_S = FIBER_SPEED_KM_S
EARTH_RADIUS_KM = 6371.0

# Fibre-in-glass propagation ceiling as a fraction of c - single source of truth
FIBER_C_FRACTION = FIBER_SPEED_KM_S / SPEED_OF_LIGHT_KM_S


def implied_c_fraction(distance_km: float, rtt_delta_ms: float) -> float:
    """Propagation speed implied by a one-way distance over an RTT delta,
    expressed as a fraction of c. ``rtt_delta_ms`` is a full round-trip
    delta; halved here to get the one-way time."""
    if rtt_delta_ms <= 0:
        return 0.0
    return distance_km / (rtt_delta_ms / 2.0 / 1000.0) / SPEED_OF_LIGHT_KM_S


def _solar_declination_deg(dt_utc: datetime) -> float:
    """Approximate solar declination (deg) for the given UTC date."""
    n = dt_utc.timetuple().tm_yday
    return 23.44 * math.sin(math.radians(360.0 / 365.0 * (n - 81)))


def solar_elevation_deg(lat: float, lon: float, dt_utc: datetime) -> float:
    """Approximate solar elevation angle (deg) above the horizon at this point."""
    decl = math.radians(_solar_declination_deg(dt_utc))
    hour_utc = dt_utc.hour + dt_utc.minute / 60.0 + dt_utc.second / 3600.0
    solar_time = hour_utc + lon / 15.0
    hour_angle = math.radians(15.0 * (solar_time - 12.0))
    phi = math.radians(lat)
    elevation = math.asin(
        math.sin(phi) * math.sin(decl) + math.cos(phi) * math.cos(decl) * math.cos(hour_angle)
    )
    return math.degrees(elevation)


def local_solar_time(lon: float, dt_utc: datetime) -> datetime:
    """Mean solar time at this longitude (offset from UTC by ~1h per 15deg of lon)."""
    return dt_utc + timedelta(hours=lon / 15.0)


_NORTH_SEASON_BY_MONTH = {
    12: "winter",
    1: "winter",
    2: "winter",
    3: "spring",
    4: "spring",
    5: "spring",
    6: "summer",
    7: "summer",
    8: "summer",
    9: "autumn",
    10: "autumn",
    11: "autumn",
}
_FLIP_SEASON = {"winter": "summer", "summer": "winter", "spring": "autumn", "autumn": "spring"}


def season_for(lat: float, dt_utc: datetime) -> str:
    """Meteorological season name, hemisphere-flipped from the Northern calendar."""
    north_season = _NORTH_SEASON_BY_MONTH[dt_utc.month]
    return north_season if lat >= 0 else _FLIP_SEASON[north_season]


def earth_state(lat: float, lon: float, dt_utc: datetime | None = None) -> dict[str, Any]:
    """Snapshot of this point's local solar time, daylight and season."""
    now = dt_utc or datetime.now(timezone.utc)
    lst = local_solar_time(lon, now)
    elevation = solar_elevation_deg(lat, lon, now)
    return {
        "local_solar_time": lst.strftime("%H:%M"),
        "solar_utc_offset_hours": round(lon / 15.0, 1),
        "daylight": elevation > 0,
        "sun_elevation_deg": round(elevation, 1),
        "season": season_for(lat, now),
        "hemisphere": "N" if lat >= 0 else "S",
    }


def night_pole_lat(dt_utc: datetime) -> float:
    """Latitude (+90 or -90) of the pole currently in full darkness."""
    return -90.0 if _solar_declination_deg(dt_utc) > 0 else 90.0


def terminator_points(dt_utc: datetime | None = None, step_deg: float = 2.0) -> list[list[float]]:
    """Day/night boundary as a [lat, lon] polyline spanning lon -180..180."""
    now = dt_utc or datetime.now(timezone.utc)
    decl = math.radians(_solar_declination_deg(now))
    tan_decl = math.tan(decl) or 1e-9
    hour_utc = now.hour + now.minute / 60.0 + now.second / 3600.0
    points: list[list[float]] = []
    lon = -180.0
    while lon <= 180.0 + 1e-9:
        hour_angle = math.radians(15.0 * (hour_utc + lon / 15.0 - 12.0))
        phi = math.atan(-math.cos(hour_angle) / tan_decl)
        points.append([round(math.degrees(phi), 2), round(lon, 2)])
        lon += step_deg
    return points


def great_circle_arc(
    a: tuple[float, float],
    b: tuple[float, float],
    *,
    max_step_km: float = 120.0,
    max_points: int = 200,
) -> list[list[float]]:
    """Densify the shorter great-circle (geodesic) path between two points.

    Returns ``[[lat, lon], ...]`` points along the shortest sphere arc. The
    longitude is kept *continuous* (values may exceed [+-]180) so that
    trans-Pacific or other antimeridian-crossing legs remain unwrapped.
    """
    (lat1, lon1), (lat2, lon2) = a, b

    def to_vec(lat: float, lon: float) -> tuple[float, float, float]:
        phi, lam = math.radians(lat), math.radians(lon)
        return (
            math.cos(phi) * math.cos(lam),
            math.cos(phi) * math.sin(lam),
            math.sin(phi),
        )

    u, v = to_vec(lat1, lon1), to_vec(lat2, lon2)
    dot = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1] + u[2] * v[2]))
    ang = math.acos(dot)
    if ang < 1e-9:
        return [[lat1, lon1]]

    n = min(
        max_points,
        max(2, math.ceil(ang * EARTH_RADIUS_KM / max_step_km)),
    )
    out: list[list[float]] = []
    prev_lon: float | None = None
    for i in range(n + 1):
        f = i / n
        wa = math.sin((1 - f) * ang) / math.sin(ang)
        wb = math.sin(f * ang) / math.sin(ang)
        w = (wa * u[0] + wb * v[0], wa * u[1] + wb * v[1], wa * u[2] + wb * v[2])
        lat = math.degrees(math.asin(w[2]))
        lon = math.degrees(math.atan2(w[1], w[0]))
        if prev_lon is not None:
            while lon - prev_lon > 180.0:
                lon -= 360.0
            while lon - prev_lon < -180.0:
                lon += 360.0
        out.append([round(lat, 5), round(lon, 5)])
        prev_lon = lon
    return out


class Coordinates(NamedTuple):
    lat: float
    lon: float
    city: str
    country: str


# Standard IATA 3-letter airport codes commonly found in router PTR hostnames
IATA_AIRPORTS: dict[str, Coordinates] = {
    # Japan & East Asia
    "HND": Coordinates(35.5494, 139.7798, "Tokyo (Haneda)", "JP"),
    "NRT": Coordinates(35.7647, 140.3863, "Tokyo (Narita)", "JP"),
    "TYO": Coordinates(35.6895, 139.6917, "Tokyo", "JP"),
    "KIX": Coordinates(34.4347, 135.2441, "Osaka (Kansai)", "JP"),
    "ITM": Coordinates(34.7855, 135.4380, "Osaka (Itami)", "JP"),
    "OSA": Coordinates(34.6937, 135.5023, "Osaka", "JP"),
    "ICN": Coordinates(37.4602, 126.4407, "Seoul (Incheon)", "KR"),
    "GMP": Coordinates(37.5583, 126.7906, "Seoul (Gimpo)", "KR"),
    "SEL": Coordinates(37.5665, 126.9780, "Seoul", "KR"),
    "HKG": Coordinates(22.3080, 113.9185, "Hong Kong", "HK"),
    "TPE": Coordinates(25.0797, 121.2342, "Taipei (Taoyuan)", "TW"),
    "TSA": Coordinates(25.0697, 121.5525, "Taipei (Songshan)", "TW"),
    "SIN": Coordinates(1.3644, 103.9915, "Singapore", "SG"),
    "BKK": Coordinates(13.6900, 100.7501, "Bangkok", "TH"),
    "KUL": Coordinates(2.7456, 101.7072, "Kuala Lumpur", "MY"),
    "MNL": Coordinates(14.5086, 121.0194, "Manila", "PH"),
    "CGK": Coordinates(-6.1275, 106.6537, "Jakarta", "ID"),
    # North America - US West & Pacific
    "SJC": Coordinates(37.3639, -121.9289, "San Jose", "US"),
    "SFO": Coordinates(37.6213, -122.3790, "San Francisco", "US"),
    "OAK": Coordinates(37.7213, -122.2207, "Oakland", "US"),
    "LAX": Coordinates(33.9416, -118.4085, "Los Angeles", "US"),
    "SEA": Coordinates(47.4502, -122.3088, "Seattle", "US"),
    "PDX": Coordinates(45.5898, -122.5951, "Portland", "US"),
    "SAN": Coordinates(32.7338, -117.1933, "San Diego", "US"),
    "HNL": Coordinates(21.3187, -157.9224, "Honolulu", "US"),
    # North America - US Mountain & Central
    "DEN": Coordinates(39.8561, -104.6737, "Denver", "US"),
    "PHX": Coordinates(33.4342, -112.0116, "Phoenix", "US"),
    "SLC": Coordinates(40.7884, -111.9778, "Salt Lake City", "US"),
    "LAS": Coordinates(36.0840, -115.1537, "Las Vegas", "US"),
    "DFW": Coordinates(32.8998, -97.0403, "Dallas/Fort Worth", "US"),
    "DAL": Coordinates(32.8471, -96.8518, "Dallas", "US"),
    "IAH": Coordinates(29.9902, -95.3368, "Houston", "US"),
    "ORD": Coordinates(41.9742, -87.9073, "Chicago", "US"),
    "MSP": Coordinates(44.8848, -93.2223, "Minneapolis", "US"),
    # North America - US East & Canada
    "IAD": Coordinates(38.9531, -77.4565, "Washington DC (Dulles)", "US"),
    "DCA": Coordinates(38.8512, -77.0402, "Washington DC (Reagan)", "US"),
    "JFK": Coordinates(40.6413, -73.7781, "New York (JFK)", "US"),
    "EWR": Coordinates(40.6895, -74.1745, "New York (Newark)", "US"),
    "LGA": Coordinates(40.7769, -73.8740, "New York (LaGuardia)", "US"),
    "NYC": Coordinates(40.7128, -74.0060, "New York", "US"),
    "BOS": Coordinates(42.3656, -71.0096, "Boston", "US"),
    "ATL": Coordinates(33.6407, -84.4277, "Atlanta", "US"),
    "MIA": Coordinates(25.7959, -80.2870, "Miami", "US"),
    "YVR": Coordinates(49.1967, -123.1815, "Vancouver", "CA"),
    "YYZ": Coordinates(43.6777, -79.6248, "Toronto", "CA"),
    "YUL": Coordinates(45.4657, -73.7455, "Montreal", "CA"),
    # Europe
    "LHR": Coordinates(51.4700, -0.4543, "London (Heathrow)", "GB"),
    "LGW": Coordinates(51.1537, -0.1821, "London (Gatwick)", "GB"),
    "LON": Coordinates(51.5074, -0.1278, "London", "GB"),
    "FRA": Coordinates(50.0379, 8.5622, "Frankfurt", "DE"),
    "AMS": Coordinates(52.3105, 4.7683, "Amsterdam", "NL"),
    "CDG": Coordinates(49.0097, 2.5479, "Paris (CDG)", "FR"),
    "PAR": Coordinates(48.8566, 2.3522, "Paris", "FR"),
    "DUB": Coordinates(53.4264, -6.2499, "Dublin", "IE"),
    "MAD": Coordinates(40.4839, -3.5680, "Madrid", "ES"),
    "MXP": Coordinates(45.6301, 8.7255, "Milan (Malpensa)", "IT"),
    "MIL": Coordinates(45.4642, 9.1900, "Milan", "IT"),
    "ZRH": Coordinates(47.4582, 8.5555, "Zurich", "CH"),
    "VIE": Coordinates(48.1103, 16.5697, "Vienna", "AT"),
    "ARN": Coordinates(59.6498, 17.9238, "Stockholm", "SE"),
    "CPH": Coordinates(55.6180, 12.6508, "Copenhagen", "DK"),
    "OSL": Coordinates(60.1976, 11.1004, "Oslo", "NO"),
    "HEL": Coordinates(60.3172, 24.9633, "Helsinki", "FI"),
    "WAW": Coordinates(52.1672, 20.9679, "Warsaw", "PL"),
    # Asia Pacific & Oceania
    "SYD": Coordinates(-33.9399, 151.1753, "Sydney", "AU"),
    "MEL": Coordinates(-37.6690, 144.8410, "Melbourne", "AU"),
    "BNE": Coordinates(-27.3942, 153.1218, "Brisbane", "AU"),
    "PER": Coordinates(-31.9385, 115.9672, "Perth", "AU"),
    "AKL": Coordinates(-37.0082, 174.7850, "Auckland", "NZ"),
    "BOM": Coordinates(19.0896, 72.8656, "Mumbai", "IN"),
    "DEL": Coordinates(28.5562, 77.1000, "Delhi", "IN"),
    "BLR": Coordinates(13.1986, 77.7066, "Bengaluru", "IN"),
    "MAA": Coordinates(12.9941, 80.1709, "Chennai", "IN"),
    # Middle East & Africa
    "DXB": Coordinates(25.2532, 55.3657, "Dubai", "AE"),
    "DOH": Coordinates(25.2731, 51.6081, "Doha", "QA"),
    "AUH": Coordinates(24.4330, 54.6511, "Abu Dhabi", "AE"),
    "TLV": Coordinates(32.0055, 34.8854, "Tel Aviv", "IL"),
    "JNB": Coordinates(-26.1367, 28.2411, "Johannesburg", "ZA"),
    "CPT": Coordinates(-33.9715, 18.6021, "Cape Town", "ZA"),
    "CAI": Coordinates(30.1219, 31.4056, "Cairo", "EG"),
    # South America
    "GRU": Coordinates(-23.4356, -46.4731, "Sao Paulo (Guarulhos)", "BR"),
    "SAO": Coordinates(-23.5505, -46.6333, "Sao Paulo", "BR"),
    "GIG": Coordinates(-22.8134, -43.2494, "Rio de Janeiro", "BR"),
    "EZE": Coordinates(-34.8222, -58.5358, "Buenos Aires", "AR"),
    "SCL": Coordinates(-33.3930, -70.7858, "Santiago", "CL"),
    "BOG": Coordinates(4.7016, -74.1469, "Bogota", "CO"),
    "LIM": Coordinates(-12.0219, -77.1143, "Lima", "PE"),
}

# AWS region default coordinates
AWS_REGION_COORDINATES: dict[str, Coordinates] = {
    "ap-northeast-1": Coordinates(35.6762, 139.6503, "Tokyo", "JP"),
    "ap-northeast-2": Coordinates(37.5665, 126.9780, "Seoul", "KR"),
    "ap-northeast-3": Coordinates(34.6937, 135.5023, "Osaka", "JP"),
    "ap-east-1": Coordinates(22.3193, 114.1694, "Hong Kong", "HK"),
    "ap-southeast-1": Coordinates(1.3521, 103.8198, "Singapore", "SG"),
    "ap-southeast-2": Coordinates(-33.8688, 151.2093, "Sydney", "AU"),
    "ap-southeast-3": Coordinates(-6.2088, 106.8456, "Jakarta", "ID"),
    "ap-southeast-4": Coordinates(-37.8136, 144.9631, "Melbourne", "AU"),
    "ap-south-1": Coordinates(19.0760, 72.8777, "Mumbai", "IN"),
    "ap-south-2": Coordinates(17.3850, 78.4867, "Hyderabad", "IN"),
    "us-east-1": Coordinates(39.0438, -77.4874, "N. Virginia", "US"),
    "us-east-2": Coordinates(39.9612, -82.9988, "Ohio", "US"),
    "us-west-1": Coordinates(37.7749, -122.4194, "N. California", "US"),
    "us-west-2": Coordinates(45.5152, -122.6784, "Oregon", "US"),
    "ca-central-1": Coordinates(45.5017, -73.5673, "Montreal", "CA"),
    "ca-west-1": Coordinates(51.0447, -114.0719, "Calgary", "CA"),
    "eu-west-1": Coordinates(53.3498, -6.2603, "Ireland", "IE"),
    "eu-west-2": Coordinates(51.5074, -0.1278, "London", "GB"),
    "eu-west-3": Coordinates(48.8566, 2.3522, "Paris", "FR"),
    "eu-central-1": Coordinates(50.1109, 8.6821, "Frankfurt", "DE"),
    "eu-central-2": Coordinates(47.3769, 8.5417, "Zurich", "CH"),
    "eu-north-1": Coordinates(59.3293, 18.0686, "Stockholm", "SE"),
    "eu-south-1": Coordinates(45.4642, 9.1900, "Milan", "IT"),
    "eu-south-2": Coordinates(40.4168, -3.7038, "Spain", "ES"),
    "sa-east-1": Coordinates(-23.5505, -46.6333, "Sao Paulo", "BR"),
    "me-south-1": Coordinates(26.0667, 50.5577, "Bahrain", "BH"),
    "me-central-1": Coordinates(24.4539, 54.3773, "UAE", "AE"),
    "af-south-1": Coordinates(-33.9249, 18.4241, "Cape Town", "ZA"),
    "il-central-1": Coordinates(32.0853, 34.7818, "Tel Aviv", "IL"),
}


def region_coords(region: str) -> tuple[float, float] | None:
    """Approximate hub location of an AWS region (lat, lon), or None if unknown."""
    coords = AWS_REGION_COORDINATES.get(region)
    if coords:
        return coords.lat, coords.lon
    return None


# Major Trans-Oceanic Global Corridors
CORRIDOR_FACTS: dict[str, str] = {
    "trans-pacific": "Trans-Pacific Ocean Corridor (~8,000-10,000 km, ~80-100ms fiber propagation floor)",
    "trans-atlantic": "Trans-Atlantic Ocean Corridor (~5,500-7,000 km, ~55-70ms fiber propagation floor)",
    "asia-europe": "Asia-Europe Maritime/Terrestrial Corridor (via Malacca Strait, Indian Ocean, Red Sea / Suez Canal, ~10,000-14,000 km)",
    "intra-asia": "Intra-Asia Submarine Network (East Asia / Southeast Asia hub connections)",
    "trans-indian": "Trans-Indian Ocean Corridor (Connecting South Asia, Middle East, and East Africa)",
    "americas-north-south": "Pan-American Subsea Corridor (Connecting North and South America)",
}


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two points on the Earth in kilometers."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * c


def min_rtt_ms(distance_km: float) -> float:
    """Calculate the theoretical minimum round-trip time (RTT) in milliseconds over optical fiber."""
    if distance_km <= 0:
        return 0.0
    return (2.0 * distance_km / SPEED_OF_LIGHT_FIBER_KM_S) * 1000.0


def max_fiber_distance_km(rtt_diff_ms: float) -> float:
    """Calculate the maximum physical distance (km) achievable given an RTT difference (ms)."""
    if rtt_diff_ms <= 0:
        return 0.0
    return (rtt_diff_ms / 2.0) * (SPEED_OF_LIGHT_FIBER_KM_S / 1000.0)


def extract_iata_from_hostname(hostname: str | None) -> tuple[str, Coordinates] | None:
    """Attempt to extract a known IATA airport code from a router PTR hostname."""
    if not hostname:
        return None

    parts = re.split(r"[\.\-_]", hostname.lower())
    for part in parts:
        code_upper = part.upper()
        if code_upper in IATA_AIRPORTS:
            return code_upper, IATA_AIRPORTS[code_upper]

        m = re.match(r"^([a-z]{3})\d+$", part)
        if m:
            c = m.group(1).upper()
            if c in IATA_AIRPORTS:
                return c, IATA_AIRPORTS[c]

    return None


def identify_oceanic_corridor(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> tuple[str, str] | None:
    """Identify if a hop jump crosses a major global trans-oceanic corridor based on geography."""
    dist = haversine_km(lat1, lon1, lat2, lon2)
    if dist < 3000:
        return None

    # Lon span across Pacific
    if (lon1 > 90 and lon2 < -60) or (lon2 > 90 and lon1 < -60):
        return "trans-pacific", CORRIDOR_FACTS["trans-pacific"]

    # Lon span across Atlantic
    if (lon1 < -40 and lon2 > -15 and lat1 > 20 and lat2 > 30) or (
        lon2 < -40 and lon1 > -15 and lat2 > 20 and lat1 > 30
    ):
        return "trans-atlantic", CORRIDOR_FACTS["trans-atlantic"]

    # Europe to Asia
    if (lat1 > 30 and -10 < lon1 < 35 and lon2 > 60) or (
        lat2 > 30 and -10 < lon2 < 35 and lon1 > 60
    ):
        return "asia-europe", CORRIDOR_FACTS["asia-europe"]

    # North to South America
    if (lat1 > 15 and lat2 < -10) or (lat2 > 15 and lat1 < -10):
        return "americas-north-south", CORRIDOR_FACTS["americas-north-south"]

    return None
