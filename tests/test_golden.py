"""Regression test: the packaged engine must reproduce the output of the original single
script prototype on the synthetic data, sheet by sheet and value by value.

tests/golden/golden_output.xlsx was produced once by running the original script on
data/synthetic/. It is a fixed reference file, so this test needs no other code.
"""
from pathlib import Path

import pandas as pd
import pytest

from roadmap_engine import load_config, load_input, run_roadmap, write_output

ROOT = Path(__file__).resolve().parents[1]
SHEETS = ["df_schedule", "project_sources", "use_cases_with_sources", "projects", "data_sources"]


@pytest.fixture(scope="module")
def produced(tmp_path_factory):
    result = run_roadmap(
        load_config(ROOT / "data/synthetic/configuration_sheet.xlsx"),
        load_input(ROOT / "data/synthetic/input_data.xlsx"),
    )
    path = tmp_path_factory.mktemp("out") / "output_data.xlsx"
    write_output(result, path)
    return pd.read_excel(path, sheet_name=None)


@pytest.fixture(scope="module")
def golden():
    return pd.read_excel(ROOT / "tests/golden/golden_output.xlsx", sheet_name=None)


@pytest.mark.parametrize("sheet", SHEETS)
def test_sheet_matches_golden(produced, golden, sheet):
    got, want = produced[sheet], golden[sheet]
    assert list(got.columns) == list(want.columns)
    pd.testing.assert_frame_equal(got, want, check_dtype=False, rtol=1e-9, atol=1e-9)
