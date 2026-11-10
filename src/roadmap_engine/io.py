"""Read the input workbook and write the output workbook."""
from __future__ import annotations

import pandas as pd

from .models import InputData, RoadmapResult


def load_input(path) -> InputData:
    """Read sheets use_cases, projects, data_sources and project_sources."""
    return InputData(
        use_cases=pd.read_excel(path, sheet_name="use_cases"),
        projects=pd.read_excel(path, sheet_name="projects"),
        data_sources=pd.read_excel(path, sheet_name="data_sources"),
        project_sources=pd.read_excel(path, sheet_name="project_sources"),
    )


def write_output(result: RoadmapResult, path) -> None:
    """Write the five result tables to one workbook."""
    with pd.ExcelWriter(path) as writer:
        result.df_schedule.to_excel(writer, sheet_name="df_schedule", index=False)
        result.project_sources.to_excel(writer, sheet_name="project_sources", index=False)
        result.use_cases_with_sources.to_excel(writer, sheet_name="use_cases_with_sources", index=False)
        result.projects.to_excel(writer, sheet_name="projects", index=False)
        result.data_sources.to_excel(writer, sheet_name="data_sources", index=False)
