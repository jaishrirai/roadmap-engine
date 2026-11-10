"""NPV and cost helpers.

NPV = sum of business value of year n discounted by (1 + rate) ** n, minus upfront cost.
Cost of a use case = sum of the cost of its data sources that are still 'planned'.
"""
from __future__ import annotations

import pandas as pd


def calculate_npv(business_values, costs, discount_rate):
    """NPV of a use case: discounted business value (years 1..n) minus upfront cost."""
    return sum([bv / ((1 + discount_rate) ** (year + 1)) for year, bv in enumerate(business_values)]) - costs


def calculate_use_case_cost(use_case_id, project_source: pd.DataFrame, data_sources: pd.DataFrame):
    """Cost of a use case: planned (not yet enabled) data sources it needs."""
    associated_sources = project_source[project_source["use_case_id"] == use_case_id]["data_source_id"]
    unique_sources = data_sources[
        (data_sources["data_source_id"].isin(associated_sources)) & (data_sources["data_source_status"] == "planned")
    ]
    return unique_sources["cost"].sum()


def count_unique_data_sources(use_case_id, project_source: pd.DataFrame, data_sources: pd.DataFrame):
    """Number of distinct data sources a use case needs."""
    associated_sources = project_source[project_source["use_case_id"] == use_case_id]["data_source_id"]
    return data_sources[data_sources["data_source_id"].isin(associated_sources)]["data_source_id"].nunique()


def find_zero_cost_use_case(use_cases_with_sources: pd.DataFrame):
    """First planned use case that costs nothing (all its sources already enabled), or None."""
    zero_cost = use_cases_with_sources[
        (use_cases_with_sources["status"] == "planned") & (use_cases_with_sources["cost"] == 0)
    ]
    if not zero_cost.empty:
        return zero_cost.iloc[0]
    return None
