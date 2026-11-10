"""Configuration: global day counts, discount rate, per-pod start dates and capacity."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd


@dataclass
class Config:
    discount_rate: float
    domain_days: float
    source_days: float
    use_case_days: float
    start_date: datetime
    subsequent_domain_days: float
    subsequent_source_days: float
    subsequent_use_case_days: float
    enabled_datasource_days: float
    enabled_datasource_usecase_days: float
    # pod name -> start date / max concurrent activities (workstreams)
    pod_start_dates: dict = field(default_factory=dict)
    pod_max_activities: dict = field(default_factory=dict)
    # use case ids that must be done before the NPV-ranked ones
    exception_use_cases: list = field(default_factory=list)

    def get_pod_start_date(self, pod_name):
        """Start date of a pod, falling back to the global start date."""
        return self.pod_start_dates.get(pod_name, self.start_date)

    def get_pod_max_activity(self, pod_name):
        """Max concurrent activities for a pod (default 1)."""
        return self.pod_max_activities.get(pod_name, 1)


def _as_datetime(value) -> datetime:
    return value if isinstance(value, datetime) else datetime.strptime(value, "%d %b %Y")


def load_config(path) -> Config:
    """Read the configuration workbook (sheets: config, start_date, exception_use_cases)."""
    config_df = pd.read_excel(path, sheet_name="config")
    exceptions_df = pd.read_excel(path, sheet_name="exception_use_cases")
    values = {row["variable"]: row["value"] for _, row in config_df.iterrows()}
    exception_ids = exceptions_df["use_case_id"].dropna().tolist()
    default_start = _as_datetime(values["start_date"])

    try:
        pods_df = pd.read_excel(path, sheet_name="start_date")
        pod_start_dates = dict(zip(pods_df["pod_name"], pd.to_datetime(pods_df["start_date"], errors="coerce")))
        pod_max_activities = dict(zip(pods_df["pod_name"], pods_df["max_activity"]))
        for pod_name in pod_start_dates:
            if pd.isna(pod_start_dates[pod_name]):
                pod_start_dates[pod_name] = default_start
    except Exception:  # sheet missing: every pod uses the global start date and capacity 1
        pod_start_dates, pod_max_activities = {}, {}

    return Config(
        discount_rate=values["discount_rate"],
        domain_days=values["domain_days"],
        source_days=values["source_days"],
        use_case_days=values["use_case_days"],
        start_date=default_start,
        subsequent_domain_days=values["subsequent_domain_days"],
        subsequent_source_days=values["subsequent_source_days"],
        subsequent_use_case_days=values["subsequent_use_case_days"],
        enabled_datasource_days=values["enabled_datasource_days"],
        enabled_datasource_usecase_days=values["enabled_datasource_usecase_days"],
        pod_start_dates=pod_start_dates,
        pod_max_activities=pod_max_activities,
        exception_use_cases=exception_ids,
    )
