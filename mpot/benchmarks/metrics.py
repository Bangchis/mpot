"""Metrics used by the report figures and correctness checks."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
import math

from mpot.benchmarks.reduction import RankTiming


@dataclass
class LoadBalanceSummary:
    """Compact load-balance result for report and JSON output."""

    max_total_time_s: float
    min_total_time_s: float
    idle_fraction: float
    balanced_under_25_percent: bool

    def to_json(self) -> dict[str, float | bool]:
        return {
            "max_total_time_s": self.max_total_time_s,
            "min_total_time_s": self.min_total_time_s,
            "idle_fraction": self.idle_fraction,
            "balanced_under_25_percent": self.balanced_under_25_percent,
        }


def runtime_with_communication(rank_timings: Iterable[RankTiming]) -> float:
    """Program runtime is the slowest rank's total time."""

    timings = list(rank_timings)
    if not timings:
        return 0.0
    return max(t.total_time_s for t in timings)


def runtime_without_communication(rank_timings: Iterable[RankTiming]) -> float:
    """Compute-only runtime is the slowest rank's compute time."""

    timings = list(rank_timings)
    if not timings:
        return 0.0
    return max(t.compute_time_s for t in timings)


def compute_speedup(serial_time_s: float, parallel_time_s: float) -> float:
    """Return S(P) = T(1) / T(P)."""

    if serial_time_s <= 0 or parallel_time_s <= 0:
        return math.nan
    return serial_time_s / parallel_time_s


def compute_efficiency(speedup: float, process_count: int) -> float:
    """Return E(P) = S(P) / P."""

    if process_count <= 0 or math.isnan(speedup):
        return math.nan
    return speedup / float(process_count)


def summarize_load_balance(rank_timings: Iterable[RankTiming]) -> LoadBalanceSummary:
    """Check the 25% imbalance rule requested by the instructor."""

    totals = [float(t.total_time_s) for t in rank_timings]
    if not totals:
        return LoadBalanceSummary(0.0, 0.0, 0.0, True)
    max_t = max(totals)
    min_t = min(totals)
    idle_fraction = 0.0 if max_t <= 0 else (max_t - min_t) / max_t
    return LoadBalanceSummary(
        max_total_time_s=max_t,
        min_total_time_s=min_t,
        idle_fraction=idle_fraction,
        balanced_under_25_percent=idle_fraction <= 0.25,
    )


def rank_timing_records(rank_timings: Iterable[RankTiming], run_id: str) -> list[dict[str, object]]:
    """Convert rank timings to serializable rows."""

    return [timing.to_record(run_id) for timing in rank_timings]

