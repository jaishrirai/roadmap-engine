"""Command line: run the engine on a config workbook and an input workbook."""
from __future__ import annotations

import argparse
from pathlib import Path

from .config import load_config
from .engine import run_roadmap
from .io import load_input, write_output


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(prog="roadmap-run", description="Run the roadmap engine prototype.")
    parser.add_argument("--config", default="data/synthetic/configuration_sheet.xlsx")
    parser.add_argument("--input", default="data/synthetic/input_data.xlsx")
    parser.add_argument("--out", default="output/output_data.xlsx")
    args = parser.parse_args(argv)

    result = run_roadmap(load_config(args.config), load_input(args.input))
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    write_output(result, args.out)
    print(f"Wrote {args.out}: {len(result.use_cases_with_sources)} use cases, {len(result.df_schedule)} scheduled activities")


if __name__ == "__main__":
    main()
