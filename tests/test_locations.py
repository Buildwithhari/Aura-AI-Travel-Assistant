import re

import locations as L

STATES_28 = {"Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
             "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur",
             "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu", "Telangana",
             "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal"}
UTS_8 = {"Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu", "Delhi",
         "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry"}


def test_iata_codes_are_well_formed_and_unique():
    for code, rec in L.AIRPORTS.items():
        assert re.fullmatch(r"[A-Z]{3}", code), code
        assert len(rec) == 6 and -90 <= rec[4] <= 90 and -180 <= rec[5] <= 180
    assert len(L.AIRPORTS) == len(set(L.AIRPORTS))


def test_all_28_states_and_8_uts_covered():
    assert {s for s, v in L.STATES.items() if v["type"] == "state"} == STATES_28
    assert {s for s, v in L.STATES.items() if v["type"] == "ut"} == UTS_8
    for state, info in L.STATES.items():
        codes, _ = L.state_airports(state)
        assert codes, f"{state} has no airports"
        for c in codes:
            assert c in L.AIRPORTS and L.AIRPORTS[c][3] == "India"
        for c in info["airports"]:
            assert L.AIRPORTS[c][2] == state, f"{c} listed under {state} but catalogued in {L.AIRPORTS[c][2]}"


def test_every_alias_points_at_real_codes():
    for alias, codes in L.CITY_ALIASES.items():
        assert codes and all(c in L.AIRPORTS for c in codes), alias
    for alias, (name, codes) in L.COUNTRY_ALIASES.items():
        assert all(c in L.AIRPORTS for c in codes), alias
    for alias, st in L.STATE_ALIASES.items():
        assert st in L.STATES, alias


def test_known_code_corrections():
    assert L.CITY_ALIASES["ranchi"] == ["IXR"]      # was RNC in the old table
    assert L.CITY_ALIASES["udaipur"] == ["UDR"]     # was UDP in the old table
    assert "RNC" not in L.AIRPORTS and "UDP" not in L.AIRPORTS


def test_state_is_not_an_airport():
    p = L.find_places("flight to Karnataka")[0]
    assert p.kind == "state" and len(p.codes) > 1
    p = L.find_places("Haryana")[0]
    assert p.kind == "state" and p.note == "gateway"


def test_ambiguous_cities_return_all_options():
    for name, codes in {"Mumbai": {"BOM", "NMI"}, "Goa": {"GOI", "GOX"}, "London": {"LHR", "LGW"}}.items():
        assert set(L.find_places(name)[0].codes) == codes


def test_spellings_scripts_and_codes():
    assert L.find_places("Bangalore")[0].codes == ["BLR"]
    assert L.find_places("bombay")[0].codes == ["BOM", "NMI"]
    assert L.find_places("navi mumbai")[0].codes == ["NMI"]
    assert L.find_places("ಬೆಂಗಳೂರಿನಿಂದ")[0].codes == ["BLR"]
    assert L.find_places("दिल्ली से")[0].codes == ["DEL"]
    assert [p.codes[0] for p in L.find_places("blr to del")] == ["BLR", "DEL"]
    assert L.find_places("BOM-DXB")[1].codes == ["DXB"]
    assert L.find_places("the sin of man") == []          # lowercase words aren't codes


def test_suggestions_for_typos():
    assert "BLR" in L.suggest("Banglor")
    assert "HYD" in L.suggest("hydrabd")
    assert L.suggest("xyzzyville") == []
