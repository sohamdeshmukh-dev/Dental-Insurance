"""Geocoding/distance only. Never used to decide network participation."""
from __future__ import annotations

import json
import math
import os
import urllib.parse
import urllib.request
from abc import ABC, abstractmethod

from data.mock import ZIP_CENTROIDS


def haversine_miles(lat1, lng1, lat2, lng2) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lng2 - lng1) / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


class Geocoder(ABC):
    @abstractmethod
    def geocode(self, query: str) -> tuple[float, float]: ...


class MockGeocoder(Geocoder):
    def geocode(self, query):
        try:
            return ZIP_CENTROIDS[query.strip()]
        except KeyError:
            raise ValueError(f"Unknown ZIP {query!r} in mock geocoder")


class MapboxGeocoder(Geocoder):  # pragma: no cover - needs network + server-side token
    def geocode(self, query):
        token = os.environ["MAPBOX_SECRET_TOKEN"]
        url = f"https://api.mapbox.com/search/geocode/v6/forward?q={urllib.parse.quote(query)}&limit=1&access_token={token}"
        with urllib.request.urlopen(url, timeout=5) as r:
            lng, lat = json.load(r)["features"][0]["geometry"]["coordinates"]
        return lat, lng


def default_geocoder() -> Geocoder:
    return MapboxGeocoder() if os.environ.get("MAPBOX_SECRET_TOKEN") else MockGeocoder()
