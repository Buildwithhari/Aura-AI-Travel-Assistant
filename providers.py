"""
Layer 4 - Sample data providers.

Everything here is SAMPLE DATA for a demo: fictional airlines, indicative fares,
curated hotel and itinerary content. Nothing is live, nothing is bookable.

The provider interfaces (`search_leg`, `hotels_for`, itinerary plans) are the
seam a licensed GDS / airline / hotel API would replace; the conversation layer
only depends on these return shapes.

Results are deterministic (seeded from route + date + cabin) so the demo and
the tests are repeatable.
"""

from __future__ import annotations

import hashlib
import json
import math
from abc import ABC, abstractmethod
from pathlib import Path

import locations as L

DATA = Path(__file__).resolve().parent / "data"

DOMESTIC_AIRLINES = [("Aurora Air", "AU"), ("IndSky", "IS"), ("Vistabird", "VB"), ("GoNorth", "GN")]
INTL_AIRLINES = [("Aurora Air", "AU"), ("Gulfwing", "GW"), ("Lion Coast", "LC"), ("Vistabird", "VB")]
CABIN_MULT = {"Economy": 1.0, "Premium Economy": 1.6, "Business": 3.1, "First": 4.8}
CHILD_FACTOR = 0.75   # sample rule: child (2-11) pays 75% of the adult fare
INFANT_FACTOR = 0.10  # sample rule: infant (<2, on lap) pays 10% of the adult fare
DOMESTIC_HUBS = ["DEL", "BOM", "BLR", "HYD", "MAA", "CCU"]
INTL_HUBS = ["DXB", "DOH", "SIN"]
METROS = set(DOMESTIC_HUBS) | {"COK", "AMD", "PNQ", "GOI", "GOX", "JAI", "LKO", "GAU", "TRV", "NMI", "CCJ", "IXE"}


def _seed(*parts) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:12], 16)


def distance_km(a: str, b: str) -> float:
    A, B = L.airport(a), L.airport(b)
    if not A or not B:
        return 1000.0
    p1, p2 = math.radians(A["lat"]), math.radians(B["lat"])
    dphi, dl = p2 - p1, math.radians(B["lon"] - A["lon"])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _fmt_minutes(m: int) -> str:
    return f"{m // 60}h {m % 60:02d}m"


def _hhmm(total_min: int) -> tuple[str, int]:
    day, rem = divmod(total_min, 24 * 60)
    return f"{rem // 60:02d}:{rem % 60:02d}", day


def _local_arrival(origin: str, destination: str, travel_date: str, dep_min: int, block: int) -> tuple[str, int]:
    """Arrival clock time in the destination's own time zone (+day offset vs departure date)."""
    try:
        from datetime import datetime, timedelta
        from zoneinfo import ZoneInfo
        d = datetime.fromisoformat(travel_date)
        dep = datetime(d.year, d.month, d.day, dep_min // 60, dep_min % 60, tzinfo=ZoneInfo(L.tz_of(origin)))
        arr = (dep + timedelta(minutes=block)).astimezone(ZoneInfo(L.tz_of(destination)))
        return arr.strftime("%H:%M"), (arr.date() - dep.date()).days
    except Exception:
        return _hhmm(dep_min + block)


class FlightProvider(ABC):
    @abstractmethod
    def search_leg(self, origin: str, destination: str, travel_date: str, cabin: str, leg: int = 0) -> list[dict]:
        ...


class SampleFlightProvider(FlightProvider):
    """Deterministic sample schedules for any pair of airports in the catalogue."""

    def search_leg(self, origin: str, destination: str, travel_date: str, cabin: str, leg: int = 0) -> list[dict]:
        if not L.airport(origin) or not L.airport(destination) or origin == destination:
            return []
        cabin = cabin if cabin in CABIN_MULT else "Economy"
        domestic = L.is_domestic(origin, destination)
        dist = distance_km(origin, destination)
        airlines = DOMESTIC_AIRLINES if domestic else INTL_AIRLINES
        pool = DOMESTIC_HUBS if domestic else INTL_HUBS + (DOMESTIC_HUBS if not L.is_domestic(origin) or not L.is_domestic(destination) else [])
        if not domestic and not (L.is_domestic(origin) or L.is_domestic(destination)):
            pool = INTL_HUBS
        hubs = [h for h in dict.fromkeys(pool) if h not in (origin, destination)]
        needs_stop = (domestic and origin not in METROS and destination not in METROS) or dist > 9500
        # only hubs roughly "on the way" (a connection must not double the trip)
        hubs.sort(key=lambda h: distance_km(origin, h) + distance_km(h, destination))
        limit = dist * (1.6 if needs_stop else 1.3)
        hubs = [h for h in hubs if distance_km(origin, h) + distance_km(h, destination) <= limit] or (hubs[:1] if needs_stop else [])
        base_fare = (2400 + 3.1 * dist) if domestic else (6500 + 4.4 * dist)
        departures = [6 * 60 + 10, 9 * 60 + 35, 13 * 60 + 50, 18 * 60 + 25, 21 * 60 + 40]
        s = _seed(origin, destination, travel_date, cabin)
        options = []
        used_numbers = set()
        for i in range(4):
            airline, code = airlines[(s + i) % len(airlines)]
            dep = departures[(s // 7 + i) % len(departures)] + ((s >> (i + 3)) % 4) * 5
            block = int(dist / 760 * 60) + 35
            stops, via = 0, None
            if (needs_stop or i == 3) and hubs:
                stops = 1
                via = hubs[i % len(hubs)] if needs_stop else hubs[0]
                detour = distance_km(origin, via) + distance_km(via, destination)
                block = int(detour / 760 * 60) + 70 + 75 + ((s >> i) % 4) * 25
            block = int(round(block / 5.0) * 5)
            arr, plus_days = _local_arrival(origin, destination, travel_date, dep, block)
            dep_s, _ = _hhmm(dep)
            variance = 0.88 + ((s >> (i * 2)) % 25) / 100.0  # 0.88 .. 1.12
            if stops:
                variance -= 0.06
            adult = int(round(base_fare * CABIN_MULT[cabin] * variance / 10.0) * 10)
            number = 100 + (s // (i + 7)) % 880
            while (code, number) in used_numbers:
                number += 1
            used_numbers.add((code, number))
            options.append({
                "id": f"L{leg}-{code}{number}",
                "leg": leg,
                "airline": airline, "flight_no": f"{code} {number}",
                "origin": origin, "destination": destination,
                "origin_city": L.airport(origin)["city"], "destination_city": L.airport(destination)["city"],
                "date": travel_date, "depart": dep_s, "arrive": arr, "arrive_day_offset": plus_days,
                "duration_min": block, "duration": _fmt_minutes(block),
                "stops": stops, "via": via, "cabin": cabin,
                "fare_adult": adult,
                "fare_child": int(round(adult * CHILD_FACTOR / 10.0) * 10),
                "fare_infant": int(round(adult * INFANT_FACTOR / 10.0) * 10),
                "currency": "INR", "domestic": domestic, "sample": True,
            })
        options.sort(key=lambda o: o["fare_adult"])
        return options


# ------------------------------------------------------------------ hotels
class HotelProvider(ABC):
    @abstractmethod
    def hotels_for(self, city_id: str) -> list[dict]:
        ...


class SampleHotelProvider(HotelProvider):
    def __init__(self, path: Path = DATA / "hotels.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.cities: dict[str, dict] = raw["cities"]

    def city_for_codes(self, codes: list[str]) -> str | None:
        for cid, info in self.cities.items():
            if set(codes) & set(info["airports"]):
                return cid
        return None

    def hotels_for(self, city_id: str) -> list[dict]:
        info = self.cities.get(city_id)
        if not info:
            return []
        out = []
        for h in info["hotels"]:
            item = dict(h)
            item.update({"city_id": city_id, "city": info["name"], "currency": "INR", "sample": True,
                         "image": f"/static/img/hotels/{h['id']}.svg",
                         "image_fallback": "/static/img/hotels/fallback.svg"})
            out.append(item)
        return out

    def supported(self) -> list[str]:
        return [info["name"] for info in self.cities.values()]


# ------------------------------------------------------------------ itineraries
class SampleItineraryProvider:
    def __init__(self, path: Path = DATA / "itineraries.json"):
        self.plans: dict[str, dict] = json.loads(path.read_text(encoding="utf-8"))["plans"]

    def match(self, places: list, text: str) -> str | None:
        low = (text or "").lower()
        for pid, plan in self.plans.items():
            for kw in plan["match"]:
                if kw.lower() in low:
                    return pid
        codes = {c for p in places for c in p.codes}
        names = {p.name for p in places}
        for pid, plan in self.plans.items():
            if codes & set(plan.get("airports", [])) or names & set(plan.get("states", [])):
                return pid
        return None


# ------------------------------------------------------------------ pricing
def price_summary(pax: dict, flights: list[dict], hotel: dict | None, nights: int, rooms: int,
                  seats: dict | None = None) -> dict:
    """Single source of truth for the indicative total shown in review/checkout."""
    adults = int(pax.get("adults") or 0)
    children = int(pax.get("children") or 0)
    infants = int(pax.get("infants") or 0)
    lines = []
    total = 0
    for f in flights:
        amount = adults * f["fare_adult"] + children * f["fare_child"] + infants * f["fare_infant"]
        lines.append({"kind": "flight", "leg": f["leg"], "flight_no": f["flight_no"], "airline": f["airline"],
                      "origin": f["origin"], "destination": f["destination"], "date": f["date"],
                      "adults": adults, "children": children, "infants": infants,
                      "fare_adult": f["fare_adult"], "fare_child": f["fare_child"], "fare_infant": f["fare_infant"],
                      "amount": amount})
        total += amount
    for leg, seat_list in sorted((seats or {}).items()):
        fee = sum(int(s.get("price") or 0) for s in seat_list)
        lines.append({"kind": "seats", "leg": int(leg), "seats": [s.get("seat") for s in seat_list], "amount": fee})
        total += fee
    if hotel and nights > 0:
        rooms = max(1, int(rooms or 1))
        amount = hotel["price_per_night"] * nights * rooms
        lines.append({"kind": "hotel", "name": hotel["name"], "city": hotel["city"], "nights": nights,
                      "rooms": rooms, "price_per_night": hotel["price_per_night"], "amount": amount})
        total += amount
    return {"lines": lines, "total": total, "currency": "INR", "sample": True}


FLIGHTS = SampleFlightProvider()
HOTELS = SampleHotelProvider()
ITINERARIES = SampleItineraryProvider()
