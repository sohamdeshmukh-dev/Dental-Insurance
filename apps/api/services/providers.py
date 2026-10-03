"""Provider search. Network status comes ONLY from provider_networks membership records."""
from __future__ import annotations

from datetime import date
from typing import Optional

from data.mock import NETWORKS, PROVIDERS
from schemas import Provider, ProviderNetwork, ProviderResult
from services.geo import Geocoder, haversine_miles


def active_membership(provider_id: str, network_id: str, on: date) -> Optional[ProviderNetwork]:
    for n in NETWORKS:
        if (n.provider_id == provider_id and n.network_id == network_id and n.effective_date <= on
                and (n.termination_date is None or n.termination_date >= on)):
            return n
    return None


def get_provider(provider_id: str) -> Provider:
    for p in PROVIDERS:
        if p.provider_id == provider_id:
            return p
    raise KeyError(provider_id)


def search_providers(geocoder: Geocoder, *, zip_code: str, radius: float, network_id: str, on: date,
                     specialty: Optional[str] = None, procedure: Optional[str] = None,
                     include_out_of_network: bool = False) -> list[ProviderResult]:
    lat, lng = geocoder.geocode(zip_code)
    out: list[ProviderResult] = []
    for p in PROVIDERS:
        if specialty and specialty.lower() not in p.specialty.lower():
            continue
        if procedure and procedure not in p.procedures:
            continue
        dist = haversine_miles(lat, lng, p.latitude, p.longitude)
        if dist > radius:
            continue
        m = active_membership(p.provider_id, network_id, on)
        if m is None and not include_out_of_network:
            continue
        out.append(ProviderResult(
            provider=p, distance_miles=round(dist, 1),
            network_status="VERIFIED_IN_NETWORK" if m else "OUT_OF_NETWORK",
            verified_source=m.source if m else None, verified_at=m.verification_timestamp if m else None))
    return sorted(out, key=lambda r: r.distance_miles)
