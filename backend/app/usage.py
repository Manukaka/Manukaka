"""Per-device token & cost tracking, for the 'low cost' goal.

In-memory and process-wide (good for a single instance / the user's own trial).
For a multi-instance rollout, back this with the same interface over Redis/DB.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict

# Approximate list prices in USD per 1M tokens. These are ESTIMATES for showing a
# ballpark spend — update them if Anthropic pricing changes. Override at runtime by
# editing this table. Unknown models fall back to the "default" row.
PRICES_PER_MTOK: Dict[str, tuple] = {
    # model substring : (input_usd_per_mtok, output_usd_per_mtok)
    "haiku": (1.0, 5.0),
    "sonnet": (3.0, 15.0),
    "opus": (15.0, 75.0),
    "default": (3.0, 15.0),
}


def _price_for(model: str) -> tuple:
    m = (model or "").lower()
    for key, price in PRICES_PER_MTOK.items():
        if key != "default" and key in m:
            return price
    return PRICES_PER_MTOK["default"]


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = _price_for(model)
    return (input_tokens * pin + output_tokens * pout) / 1_000_000.0


@dataclass
class DeviceUsage:
    requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    est_cost_usd: float = 0.0
    last_seen: float = field(default_factory=time.time)


class UsageTracker:
    def __init__(self) -> None:
        self._by_device: Dict[str, DeviceUsage] = defaultdict(DeviceUsage)
        self._lock = threading.Lock()

    def record(self, device_id: str, model: str, input_tokens: int, output_tokens: int) -> None:
        cost = estimate_cost_usd(model, input_tokens, output_tokens)
        with self._lock:
            u = self._by_device[device_id]
            u.requests += 1
            u.input_tokens += input_tokens
            u.output_tokens += output_tokens
            u.est_cost_usd += cost
            u.last_seen = time.time()

    def for_device(self, device_id: str) -> DeviceUsage:
        with self._lock:
            return self._by_device.get(device_id, DeviceUsage())

    def snapshot(self) -> Dict[str, DeviceUsage]:
        with self._lock:
            return dict(self._by_device)

    def totals(self) -> DeviceUsage:
        with self._lock:
            t = DeviceUsage()
            for u in self._by_device.values():
                t.requests += u.requests
                t.input_tokens += u.input_tokens
                t.output_tokens += u.output_tokens
                t.est_cost_usd += u.est_cost_usd
            return t


# Process-wide singleton used by the app.
tracker = UsageTracker()
