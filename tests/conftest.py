from pathlib import Path

import pytest

from roadmap_engine import load_config, load_input, run_roadmap

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def config():
    return load_config(ROOT / "data/synthetic/configuration_sheet.xlsx")


@pytest.fixture(scope="session")
def data():
    return load_input(ROOT / "data/synthetic/input_data.xlsx")


@pytest.fixture(scope="session")
def result(config, data):
    return run_roadmap(config, data)
