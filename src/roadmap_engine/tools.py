"""Agent facing tools. The model passes arguments and reads results; all maths happens here.

Every function takes plain Python values and returns JSON friendly dicts or lists, so it can
be registered as a tool in any agent framework.

    from roadmap_engine import tools

    tools.calculate_npv([100, 200, 300], costs=50, rate=0.10)
    state = tools.RoadmapState.from_files("configuration_sheet.xlsx", "output_data.xlsx")
    tools.check_capacity(state, pod="Finance Pod", effort_days=30, earliest_start="2026-03-01")
    tools.rank_use_cases(config, data)

Days are calendar days. An activity occupies one slot of its pod from its start date up to,
but not including, its end date (the slot is free again on the end date).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pandas as pd

from .config import Config, load_config
from .models import InputData, RoadmapResult
from .npv import calculate_npv as _npv
from .prioritize import prioritize_use_cases


# --------------------------------------------------------------------------- NPV
def calculate_npv(business_values, costs, rate):
    """NPV of a use case.

    business_values: yearly business value, year 1 first (for example 3 numbers).
    costs: upfront cost, 0 or more.
    rate: yearly discount rate, for example 0.10 for 10 percent.
    Returns {"npv", "discounted_values", "costs", "rate"}.
    """
    values = [float(v) for v in business_values]
    if not values:
        raise ValueError("business_values must contain at least one year")
    if float(costs) < 0:
        raise ValueError("costs must be 0 or more")
    if float(rate) <= -1:
        raise ValueError("rate must be greater than -1")
    discounted = [v / ((1 + float(rate)) ** (year + 1)) for year, v in enumerate(values)]
    return {
        "npv": float(_npv(values, float(costs), float(rate))),
        "discounted_values": discounted,
        "costs": float(costs),
        "rate": float(rate),
    }


# --------------------------------------------------------------------------- capacity
@dataclass
class RoadmapState:
    """What check_capacity needs: pod capacities and start dates, plus the booked schedule."""
    config: Config
    schedule: pd.DataFrame  # df_schedule: Team, start_date, end_date, Actual_Days

    @classmethod
    def from_result(cls, config: Config, result: RoadmapResult) -> "RoadmapState":
        return cls(config=config, schedule=result.df_schedule)

    @classmethod
    def from_files(cls, config_path, output_path) -> "RoadmapState":
        schedule = pd.read_excel(output_path, sheet_name="df_schedule")
        return cls(config=load_config(config_path), schedule=schedule)

    def pods(self):
        return sorted(set(self.config.pod_max_activities) | set(self.schedule["Team"].unique()))


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return pd.to_datetime(value).date()


def _intervals(state: RoadmapState, pod: str):
    """Booked (start, end) date pairs of a pod. Zero day activities use no capacity."""
    rows = state.schedule[(state.schedule["Team"] == pod) & (state.schedule["Actual_Days"] > 0)]
    return [(_as_date(s), _as_date(e)) for s, e in zip(rows["start_date"], rows["end_date"])]


def _active(intervals, day: date) -> int:
    return sum(1 for s, e in intervals if s <= day < e)


def _fits(intervals, start: date, end: date, capacity: int) -> bool:
    """True if one more activity over [start, end) never pushes the pod over capacity."""
    points = [start] + [s for s, _ in intervals if start < s < end]
    return all(_active(intervals, p) < capacity for p in points)


def check_capacity(state: RoadmapState, pod: str, effort_days: int, earliest_start):
    """Can `pod` take `effort_days` of work starting no earlier than `earliest_start`?

    Returns {"pod", "max_activity", "requested_start", "fits_on_requested_start",
             "active_on_requested_start", "proposed_start", "proposed_end", "wait_days"}.
    proposed_start is the earliest date on or after the request (and after the pod start date)
    when a slot is free for the whole duration.
    """
    effort_days = int(effort_days)
    if effort_days < 0:
        raise ValueError("effort_days must be 0 or more")
    if pod not in state.pods():
        raise ValueError(f"unknown pod {pod!r}; known pods: {state.pods()}")
    capacity = int(state.config.get_pod_max_activity(pod))
    pod_start = _as_date(state.config.get_pod_start_date(pod))
    requested = _as_date(earliest_start)
    first = max(requested, pod_start)
    intervals = _intervals(state, pod)

    proposed = None
    if capacity > 0:
        candidates = sorted({first} | {e for _, e in intervals if e > first})
        for day in candidates:
            if effort_days == 0 or _fits(intervals, day, day + timedelta(days=effort_days), capacity):
                proposed = day
                break
    result = {
        "pod": pod,
        "max_activity": capacity,
        "requested_start": requested.isoformat(),
        "active_on_requested_start": _active(intervals, requested),
    }
    if proposed is None:
        result.update(fits_on_requested_start=False, proposed_start=None, proposed_end=None, wait_days=None)
        return result
    result.update(
        fits_on_requested_start=proposed == requested,
        proposed_start=proposed.isoformat(),
        proposed_end=(proposed + timedelta(days=effort_days)).isoformat(),
        wait_days=(proposed - requested).days,
    )
    return result


# --------------------------------------------------------------------------- ranking
def rank_use_cases(config: Config, data: InputData):
    """Priority order of all use cases (1 = first), without scheduling.

    Returns a list of {"priority", "use_case_id", "use_case_title", "pod_name", "npv", "cost",
    "initial_npv", "initial_cost"}. npv and cost are the values at the moment the use case was
    picked, after earlier picks enabled shared data sources.
    """
    ranked, _, _ = prioritize_use_cases(
        data.use_cases.copy(), data.data_sources.copy(), data.project_sources.copy(),
        config.exception_use_cases, config.discount_rate,
    )
    return [
        {
            "priority": int(r["Priority"]),
            "use_case_id": int(r["use_case_id"]),
            "use_case_title": r["use_case_title"],
            "pod_name": r["pod_name"],
            "npv": float(r["Anchor_NPV"]),
            "cost": float(r["Anchor_Cost"]),
            "initial_npv": float(r["initial_NPV"]),
            "initial_cost": float(r["initial_cost"]),
        }
        for _, r in ranked.iterrows()
    ]
