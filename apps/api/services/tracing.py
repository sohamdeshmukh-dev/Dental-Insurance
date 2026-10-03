from __future__ import annotations

import time
from contextlib import contextmanager

from schemas import TraceEvent


class Tracer:
    def __init__(self):
        self.events: list[TraceEvent] = []

    @contextmanager
    def span(self, agent: str, tool: str, detail: str = "", calculation_version: str | None = None):
        t0 = time.perf_counter()
        try:
            yield
        finally:
            self.events.append(TraceEvent(agent=agent, tool=tool, detail=detail, calculation_version=calculation_version,
                                          latency_ms=round((time.perf_counter() - t0) * 1000, 2)))
