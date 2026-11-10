"""Dynamic NPV prioritisation of use cases.

Rules (same as the original prototype):
1. Exception use cases go first, in the order listed in the config.
2. After that, a planned use case that costs nothing goes next.
3. Otherwise the planned use case with the highest NPV goes next.
4. After each pick, its data sources become 'enabled', so the cost (and NPV) of every
   remaining use case that shares those sources is recalculated before the next pick.

`data_sources` and `project_source` are updated in place (statuses flip to 'enabled').
"""
from __future__ import annotations

import pandas as pd

from .npv import calculate_npv, calculate_use_case_cost, count_unique_data_sources, find_zero_cost_use_case


def _business_values(uc):
    return [uc["business_value_y1"], uc["business_value_y2"], uc["business_value_y3"]]


def _refresh_costs_and_npv(ucs, project_source, data_sources, rate):
    """Recalculate cost for all, and NPV for the ones still planned. Returns re-sorted table."""
    ucs["cost"] = ucs["use_case_id"].apply(lambda uid: calculate_use_case_cost(uid, project_source, data_sources))
    ucs["NPV"] = ucs.apply(
        lambda uc: calculate_npv(_business_values(uc), uc["cost"], rate) if uc["status"] == "planned" else uc["NPV"],
        axis=1,
    )
    return ucs.sort_values(by="NPV", ascending=False).reset_index(drop=True)


def _complete(ucs, chosen, iteration, project_source, data_sources, rate):
    """Mark `chosen` as done with priority `iteration`, enable its sources, refresh the rest."""
    index = ucs.index[ucs["use_case_id"] == chosen["use_case_id"]].tolist()[0]
    ucs.at[index, "status"] = "done"
    ucs.at[index, "Priority"] = iteration
    ucs.at[index, "Anchor_Cost"] = chosen["cost"]
    ucs.at[index, "Anchor_NPV"] = chosen["NPV"]
    associated_sources = project_source[project_source["use_case_id"] == chosen["use_case_id"]]["data_source_id"]
    data_sources.loc[data_sources["data_source_id"].isin(associated_sources), "data_source_status"] = "enabled"
    project_source.loc[project_source["data_source_id"].isin(associated_sources), "source_status"] = "enabled"
    return _refresh_costs_and_npv(ucs, project_source, data_sources, rate)


def prioritize_use_cases(use_cases, data_sources, project_source, exception_use_case_list, discount_rate):
    """Return (use_cases_with_sources, enabled_ds_from_ds, enabled_ps_instances).

    use_cases_with_sources has the columns NPV, initial_NPV, initial_rank, cost, initial_cost,
    Priority (1 = first), Anchor_Cost and Anchor_NPV.
    """
    # Data sources that are already enabled before any prioritisation
    enabled_ds_from_ds = data_sources[data_sources["data_source_status"] == "enabled"]["data_source_id"].tolist()
    enabled_ds_from_ps = project_source[project_source["source_status"] == "enabled"]["data_source_id"].tolist()
    enabled_ps_instances = (
        project_source[project_source["source_status"] == "enabled"][["use_case_id", "project_id", "data_source_id"]]
        .apply(tuple, axis=1)
        .tolist()
    )
    enabled_ds_combined = list(set(enabled_ds_from_ds + enabled_ds_from_ps))
    project_source.loc[project_source["data_source_id"].isin(enabled_ds_combined), "source_status"] = "enabled"
    data_sources.loc[data_sources["data_source_id"].isin(enabled_ds_combined), "data_source_status"] = "enabled"

    # Use cases without any data source are dropped
    ids_with_sources = project_source["use_case_id"].unique()
    ucs = use_cases[use_cases["use_case_id"].isin(ids_with_sources)].copy()
    ucs["unique_data_sources_count"] = ucs["use_case_id"].apply(
        lambda uid: count_unique_data_sources(uid, project_source, data_sources)
    )

    # Initial cost, NPV and rank
    ucs["cost"] = ucs["use_case_id"].apply(lambda uid: calculate_use_case_cost(uid, project_source, data_sources))
    ucs["initial_cost"] = ucs["cost"]
    ucs["NPV"] = ucs.apply(lambda uc: calculate_npv(_business_values(uc), uc["cost"], discount_rate), axis=1)
    ucs["initial_NPV"] = ucs["NPV"]
    ucs["initial_rank"] = ucs["initial_NPV"].rank(ascending=False, method="dense")
    for column in ("Priority", "Anchor_Cost", "Anchor_NPV"):  # filled in as each use case is picked
        ucs[column] = float("nan")
    ucs = ucs.sort_values(by="NPV", ascending=False).reset_index(drop=True)

    iteration = 0

    # Exception use cases first
    for exception_id in exception_use_case_list:
        match = ucs[(ucs["status"] == "planned") & (ucs["use_case_id"] == exception_id)]
        if not match.empty:
            iteration += 1
            ucs = _complete(ucs, match.iloc[0], iteration, project_source, data_sources, discount_rate)

    # Then zero-cost use cases, then highest NPV, until nothing is planned
    while ucs[ucs["status"] == "planned"].shape[0] > 0:
        chosen = find_zero_cost_use_case(ucs)
        if chosen is None:
            chosen = ucs[ucs["status"] == "planned"].iloc[0]
        iteration += 1
        ucs = _complete(ucs, chosen, iteration, project_source, data_sources, discount_rate)

    ucs = ucs.sort_values(by="Priority").reset_index(drop=True)
    return ucs, enabled_ds_from_ds, enabled_ps_instances
