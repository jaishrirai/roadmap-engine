"""Properties the schedule must always satisfy, plus the check_capacity tool."""
from datetime import date, timedelta

import pandas as pd
import pytest

from roadmap_engine import tools


def _max_concurrent(rows):
    events = []
    for s, e in zip(rows["start_date"], rows["end_date"]):
        events += [(s, 1), (e, -1)]  # ends sort before starts on the same day
    events.sort(key=lambda x: (x[0], x[1]))
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    return peak


def test_no_pod_exceeds_its_capacity(config, result):
    s = result.df_schedule
    s = s[s["Actual_Days"] > 0]
    for pod, rows in s.groupby("Team"):
        assert _max_concurrent(rows) <= config.get_pod_max_activity(pod), pod


def test_end_equals_start_plus_days(result):
    s = result.df_schedule
    assert ((s["end_date"] - s["start_date"]).dt.days == s["Actual_Days"]).all()


def test_no_activity_starts_before_its_pod_start(config, result):
    s = result.df_schedule
    for pod, rows in s.groupby("Team"):
        assert (rows["start_date"] >= pd.Timestamp(config.get_pod_start_date(pod))).all()


def test_every_activity_scheduled_at_most_once(result):
    assert not result.df_schedule["Activity"].duplicated().any()


# ------------------------------------------------------------------ check_capacity
@pytest.fixture(scope="module")
def state(config, result):
    return tools.RoadmapState.from_result(config, result)


def test_free_pod_fits_on_requested_start(state, config):
    pod = "Platform Pod"
    far = date(2030, 1, 1)
    out = tools.check_capacity(state, pod, 30, far)
    assert out["fits_on_requested_start"] is True
    assert out["wait_days"] == 0
    assert out["proposed_end"] == (far + timedelta(days=30)).isoformat()


def test_request_before_pod_start_is_moved_to_pod_start(state, config):
    out = tools.check_capacity(state, "Platform Pod", 10, date(2020, 1, 1))
    assert out["proposed_start"] >= config.get_pod_start_date("Platform Pod").date().isoformat()
    assert out["fits_on_requested_start"] is False


def test_busy_pod_waits_and_result_respects_capacity(state, config):
    pod = "Supply Chain Pod"
    start = config.get_pod_start_date(pod).date()
    out = tools.check_capacity(state, pod, 40, start)
    assert out["active_on_requested_start"] >= config.get_pod_max_activity(pod)
    assert out["fits_on_requested_start"] is False and out["wait_days"] > 0
    # booking it must not push the pod over capacity
    new = pd.DataFrame([{
        "Team": pod, "Actual_Days": 40,
        "start_date": pd.Timestamp(out["proposed_start"]), "end_date": pd.Timestamp(out["proposed_end"]),
    }])
    s = pd.concat([state.schedule[["Team", "Actual_Days", "start_date", "end_date"]], new])
    s = s[(s["Team"] == pod) & (s["Actual_Days"] > 0)]
    assert _max_concurrent(s) <= config.get_pod_max_activity(pod)


def test_unknown_pod_raises(state):
    with pytest.raises(ValueError):
        tools.check_capacity(state, "No Such Pod", 10, date(2026, 1, 1))


def test_zero_effort_always_fits(state):
    out = tools.check_capacity(state, "Supply Chain Pod", 0, date(2026, 1, 5))
    assert out["proposed_start"] == "2026-01-05" and out["proposed_end"] == "2026-01-05"
