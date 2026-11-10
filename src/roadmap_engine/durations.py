"""Expected days per activity (one row of project_sources = use case + project + data source).

Default days come from the config. Days shrink when the source system, the domain or the
use case has already been enabled (by existing work or by an earlier activity in the plan).
"""
from __future__ import annotations

import pandas as pd

from .config import Config


def _apply_enabled_rules(df: pd.DataFrame, data_sources: pd.DataFrame, cfg: Config):
    """Shorten durations for already enabled sources, domains and use cases (in place).

    Returns the mask of rows where both the data source and the use case are enabled.
    """
    enabled_data_sources = df[df["processed_datasource_status"] == "enabled"]
    enabled_data_source_ids = enabled_data_sources["data_source_id"].tolist()
    enabled_from_ds = data_sources[data_sources["data_source_status"] == "enabled"]["data_source_id"].tolist()
    enabled_ds_combined = list(set(enabled_data_source_ids + enabled_from_ds))
    # source systems already connected
    unique_sources = df[df["data_source_id"].isin(enabled_ds_combined)]["source"].unique()
    df.loc[df["source"].isin(unique_sources), "roadmap_days_source_status"] = "enabled"
    df.loc[df["roadmap_days_source_status"] == "enabled", "source_days"] = cfg.subsequent_source_days
    # domains already modelled
    unique_domains = df[df["data_source_id"].isin(enabled_ds_combined)]["domain"].unique()
    df.loc[df["domain"].isin(unique_domains), "roadmap_days_domain_status"] = "enabled"
    df.loc[df["roadmap_days_domain_status"] == "enabled", "domain_days"] = cfg.subsequent_domain_days
    # use cases already started
    unique_use_cases = enabled_data_sources["use_case_id"].unique()
    df.loc[df["use_case_id"].isin(unique_use_cases), "use_case_roadmap_days_status"] = "enabled"
    df.loc[df["use_case_roadmap_days_status"] == "enabled", "use_case_days"] = cfg.subsequent_use_case_days
    # totals
    df["source_and_domain_days"] = df["source_days"] + df["domain_days"]
    df["expected_roadmap_days"] = df["use_case_days"] + df["source_and_domain_days"]
    # the data source itself is already enabled
    df.loc[df["data_source_id"].isin(enabled_ds_combined), "linked_data_source_status"] = "enabled"
    df.loc[df["linked_data_source_status"] == "enabled", "source_and_domain_days"] = cfg.enabled_datasource_days
    df["expected_roadmap_days"] = df["use_case_days"] + df["source_and_domain_days"]
    # both enabled: nothing left to do
    mask = (df["linked_data_source_status"] == "enabled") & (df["use_case_roadmap_days_status"] == "enabled")
    df.loc[mask, "expected_roadmap_days"] = cfg.enabled_datasource_usecase_days
    return mask


def initial_calculate_expected_time_taken(df, data_sources, start_date, cfg: Config):
    """First pass: also books the fully enabled rows (zero effort) at the global start date."""
    mask = _apply_enabled_rules(df, data_sources, cfg)
    df.loc[mask, "actual_roadmap_days"] = cfg.enabled_datasource_usecase_days
    df.loc[mask, "start_date"] = start_date
    df.loc[mask, "end_date"] = df.loc[mask, "start_date"] + pd.to_timedelta(df.loc[mask, "actual_roadmap_days"], unit="D")
    df.loc[mask, "processed_datasource_status"] = "enabled"
    return df


def calculate_expected_time_taken(df, data_sources, cfg: Config):
    """Recalculate expected days after each scheduling step."""
    _apply_enabled_rules(df, data_sources, cfg)
    return df
