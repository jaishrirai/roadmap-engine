"""End to end run: prioritise use cases, estimate durations, schedule pods.

    from roadmap_engine import load_config, load_input, run_roadmap
    result = run_roadmap(load_config("configuration_sheet.xlsx"), load_input("input_data.xlsx"))
"""
from __future__ import annotations

import pandas as pd

from .config import Config
from .durations import initial_calculate_expected_time_taken
from .models import InputData, RoadmapResult
from .prioritize import prioritize_use_cases
from .scheduler import PodScheduler


def run_roadmap(config: Config, data: InputData) -> RoadmapResult:
    """Run the whole prototype pipeline. Inputs are not modified."""
    use_cases = data.use_cases.copy()
    projects = data.projects.copy()
    data_sources = data.data_sources.copy()
    project_source = data.project_sources.copy()

    # 1. Rank use cases by dynamic NPV (exceptions first, zero cost first)
    use_cases_with_sources, enabled_ds_from_ds, enabled_ps_instances = prioritize_use_cases(
        use_cases, data_sources, project_source, config.exception_use_cases, config.discount_rate
    )

    # 2. Default durations from the config
    project_source["domain_days"] = config.domain_days
    project_source["source_days"] = config.source_days
    project_source["use_case_days"] = config.use_case_days
    project_source = project_source.merge(data_sources[["data_source_id", "source", "domain"]], on="data_source_id", how="left")
    project_source["roadmap_days_domain_status"] = "planned"
    project_source["roadmap_days_source_status"] = "planned"
    project_source["linked_data_source_status"] = "planned"
    project_source["source_and_domain_days"] = project_source["domain_days"] + project_source["source_days"]
    project_source["use_case_roadmap_days_status"] = "planned"
    project_source["expected_roadmap_days"] = project_source["use_case_days"] + project_source["source_and_domain_days"]
    project_source["actual_roadmap_days"] = 0
    project_source["workstream"] = None

    # 3. Activities that were enabled before the plan starts
    key = ["use_case_id", "project_id", "data_source_id"]
    project_source["processed_datasource_status"] = "planned"
    project_source.loc[project_source[key].apply(tuple, axis=1).isin(enabled_ps_instances), "processed_datasource_status"] = "enabled"
    data_sources["data_source_status"] = "planned"
    data_sources.loc[data_sources["data_source_id"].isin(enabled_ds_from_ds), "data_source_status"] = "enabled"

    project_source = initial_calculate_expected_time_taken(project_source, data_sources, config.start_date, config)
    use_cases_with_sources["use_case_priority_sequence"] = use_cases_with_sources["Priority"]
    project_source = project_source.merge(
        use_cases_with_sources[["use_case_id", "use_case_priority_sequence"]], on="use_case_id", how="left"
    )
    project_source.loc[
        project_source[key].apply(tuple, axis=1).isin(enabled_ps_instances), ["start_date", "end_date"]
    ] = project_source[["actual_start_date", "actual_end_date"]]
    project_source = project_source.sort_values(by=["use_case_priority_sequence", "project_id", "data_source_id"]).reset_index(drop=True)

    # 4. Priority sequence for projects and data sources inside each use case
    for _, use_case in use_cases_with_sources.iterrows():
        use_case_id = use_case["use_case_id"]
        use_case_priority = use_case["use_case_priority_sequence"]
        associated_projects = projects[projects["use_case_id"] == use_case_id].sort_values(by="project_id").reset_index(drop=True)
        for project_priority, (_, project) in enumerate(associated_projects.iterrows(), start=1):
            project_id = project["project_id"]
            in_project = (project_source["project_id"] == project_id) & (project_source["use_case_id"] == use_case_id)
            projects.loc[(projects["project_id"] == project_id) & (projects["use_case_id"] == use_case_id), "project_priority_sequence"] = project_priority
            project_source.loc[in_project, "project_priority_sequence"] = project_priority
            project_source.loc[in_project, "use_case_priority_sequence"] = use_case_priority
            associated_sources = project_source[
                (project_source["use_case_id"] == use_case_id) & (project_source["project_id"] == project_id)
            ].sort_values(by="data_source_id").reset_index(drop=True)
            for source_priority, (_, source_row) in enumerate(associated_sources.iterrows(), start=1):
                project_source.loc[
                    in_project & (project_source["data_source_id"] == source_row["data_source_id"]),
                    "data_source_priority_sequence",
                ] = source_priority
    project_source = project_source.sort_values(
        by=["use_case_priority_sequence", "project_priority_sequence", "data_source_priority_sequence"]
    ).reset_index(drop=True)

    # 5. Pod of each activity comes from its use case
    project_source = project_source.merge(use_cases[["use_case_id", "pod_name"]], on="use_case_id", how="left")

    # 6. Schedule
    scheduler = PodScheduler(project_source, data_sources, config)
    final_schedule = scheduler.dynamic_scheduling()
    project_source = scheduler.project_source

    df_schedule = pd.DataFrame(final_schedule)
    df_schedule["start_date"] = pd.to_datetime(df_schedule["start_date"], format="%d %b %Y")
    df_schedule["end_date"] = pd.to_datetime(df_schedule["end_date"], format="%d %b %Y")
    df_schedule[key] = pd.DataFrame(df_schedule["Activity"].tolist(), index=df_schedule.index)
    df_schedule = (
        df_schedule.merge(use_cases_with_sources[["use_case_id", "use_case_title", "use_case_priority_sequence"]], on="use_case_id", how="left")
        .merge(data_sources[["data_source_id", "data_source_title"]], on="data_source_id", how="left")
        .merge(projects[["project_id", "project_title"]].drop_duplicates(subset=["project_id"]), on="project_id", how="left")
    )
    df_schedule = df_schedule.sort_values(
        by=["start_date", "use_case_priority_sequence", "project_id", "data_source_id"]
    ).reset_index(drop=True)

    # 7. Total roadmap days per use case
    days = project_source.groupby("use_case_id")["actual_roadmap_days"].sum().reset_index()
    use_cases_with_sources = pd.merge(use_cases_with_sources, days, on="use_case_id", how="left")

    return RoadmapResult(
        df_schedule=df_schedule,
        project_sources=project_source,
        use_cases_with_sources=use_cases_with_sources,
        projects=projects,
        data_sources=data_sources,
    )
