from packetvoyage import geo


def test_haversine_distance():
    # Tokyo (HND) to San Jose (SJC) is approx 8,280 km
    hnd = geo.IATA_AIRPORTS["HND"]
    sjc = geo.IATA_AIRPORTS["SJC"]
    dist = geo.haversine_km(hnd.lat, hnd.lon, sjc.lat, sjc.lon)
    assert 8000 < dist < 9000


def test_min_rtt_physics():
    # 8,280 km in fiber (~200,860 km/s) requires min ~82.4 ms round-trip
    dist = 8280.0
    rtt_floor = geo.min_rtt_ms(dist)
    assert 80.0 < rtt_floor < 85.0


def test_extract_iata_from_hostname():
    # Various PTR naming conventions
    assert geo.extract_iata_from_hostname("ae-2.sjc10.ip4.gtt.net")[0] == "SJC"
    assert geo.extract_iata_from_hostname("bundle-ether1.tokyo-hnd.bb.net")[0] == "HND"
    assert geo.extract_iata_from_hostname("xe-0-0-0.lhr-cr1.isp.co.uk")[0] == "LHR"
    assert geo.extract_iata_from_hostname("100ge.nrt1.bb.net")[0] == "NRT"
    assert geo.extract_iata_from_hostname("plain-router.local") is None


def test_identify_oceanic_corridor():
    # Tokyo to San Jose
    hnd = geo.IATA_AIRPORTS["HND"]
    sjc = geo.IATA_AIRPORTS["SJC"]
    corridor = geo.identify_oceanic_corridor(hnd.lat, hnd.lon, sjc.lat, sjc.lon)
    assert corridor is not None
    assert corridor[0] == "trans-pacific"
