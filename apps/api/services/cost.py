"""Cost data provider interface. FairHealthProvider requires authorized/licensed access."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from data.mock import BASE_FEES, ZIP_FACTORS


@dataclass
class CostEstimate:
    code: str
    allowed_in_network: float
    typical_charge: float  # what an out-of-network dentist is likely to bill
    low: float
    high: float
    source: str


class CostDataProvider(ABC):
    @abstractmethod
    def get_estimated_cost(self, procedure_code: str, zipcode: str) -> CostEstimate: ...

    def get_cost_range(self, procedure_code: str, zipcode: str) -> tuple[float, float]:
        e = self.get_estimated_cost(procedure_code, zipcode)
        return e.low, e.high


class MockCostDataProvider(CostDataProvider):
    def get_estimated_cost(self, procedure_code, zipcode):
        if procedure_code not in BASE_FEES:
            raise KeyError(f"No cost data for {procedure_code}")
        factor = ZIP_FACTORS.get(zipcode[:3], 1.05)
        allowed = round(BASE_FEES[procedure_code] * factor, 2)
        charge = round(allowed * 1.25, 2) if allowed != 850 else 1300.0  # keeps the documented root canal example
        return CostEstimate(procedure_code, allowed, charge, round(allowed * 0.9, 2), round(charge * 1.15, 2), "mock-cost-data")


class FairHealthProvider(CostDataProvider):  # pragma: no cover
    """Only implement against an approved FAIR Health dataset/API license. No scraping."""

    def get_estimated_cost(self, procedure_code, zipcode):
        raise NotImplementedError("FAIR Health access is not authorized for this prototype.")
