"""Plain containers passed between the engine stages."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass
class InputData:
    """The four input tables (sheet names match the input workbook)."""
    use_cases: pd.DataFrame
    projects: pd.DataFrame
    data_sources: pd.DataFrame
    project_sources: pd.DataFrame


@dataclass
class RoadmapResult:
    """The five output tables (sheet names match the output workbook)."""
    df_schedule: pd.DataFrame
    project_sources: pd.DataFrame
    use_cases_with_sources: pd.DataFrame
    projects: pd.DataFrame
    data_sources: pd.DataFrame
