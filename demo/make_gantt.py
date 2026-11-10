"""Demo: run the engine on the synthetic data and draw the Gantt charts.

    python demo/make_gantt.py                      # uses data/synthetic, writes output/
    python demo/make_gantt.py --out-dir output --config my_config.xlsx --input my_input.xlsx

Writes (all headless, nothing is shown on screen):
    output/output_data.xlsx                         the five result sheets
    output/charts/use_case_gantt.png                one bar per use case, coloured by pod
    output/charts/use_case_gantt_data.xlsx          the dates behind that chart
    output/charts/data_source_gantt.xlsx            month grid, one row per activity
    output/charts/pods/<pod>_data_source_gantt.png  one chart per pod
Needs the optional chart packages: pip install "roadmap-engine[charts]"
"""
from __future__ import annotations

import argparse
import sys
import textwrap
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless: never opens a window
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import xlsxwriter  # noqa: E402

try:
    from roadmap_engine import load_config, load_input, run_roadmap, write_output
except ImportError:  # running from a fresh clone without installing the package
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from roadmap_engine import load_config, load_input, run_roadmap, write_output

BAR_COLOUR = "#ADD8E6"  # light blue as an explicit hex value (named colours are not valid in Excel)


def pod_colours(pods):
    cmap = plt.get_cmap("tab10")
    return {pod: cmap(i % 10) for i, pod in enumerate(pods)}


def use_case_dates(schedule: pd.DataFrame) -> pd.DataFrame:
    dates = schedule.groupby("use_case_id").agg(start_date=("start_date", "min"), end_date=("end_date", "max")).reset_index()
    dates = dates.merge(schedule[["use_case_id", "use_case_title", "Team"]].drop_duplicates(), on="use_case_id")
    return dates.sort_values(["Team", "start_date"]).reset_index(drop=True)


def draw_use_case_gantt(dates: pd.DataFrame, colours: dict, path: Path) -> None:
    fig, ax = plt.subplots(figsize=(18, max(6, 0.38 * len(dates))))
    for _, row in dates.iterrows():
        days = (row["end_date"] - row["start_date"]).days
        ax.barh(row["use_case_title"], days, left=row["start_date"], color=colours[row["Team"]],
                edgecolor="black", alpha=0.9, height=0.6)
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.set_xlabel("Date")
    ax.set_ylabel("Use case")
    ax.set_title("Use case Gantt chart by pod (synthetic data)")
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    handles = [plt.Line2D([0], [0], color=c, lw=6, label=p) for p, c in colours.items()]
    ax.legend(handles=handles, title="Pods", loc="upper left")
    # cumulative number of use cases started, per month
    started = dates.groupby(dates["start_date"].dt.to_period("M")).size().cumsum()
    ax2 = ax.twinx()
    ax2.plot(started.index.to_timestamp(), started.values, color="navy", linewidth=2)
    ax2.set_ylabel("Cumulative use cases started", color="navy")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def write_excel_gantt(schedule: pd.DataFrame, path: Path) -> None:
    df = schedule.sort_values(["Team", "start_date", "use_case_priority_sequence", "project_id"]).reset_index(drop=True)
    df["label"] = df["use_case_title"] + " / " + df["data_source_title"].astype(str)
    first = datetime(df["start_date"].min().year, df["start_date"].min().month, 1)
    last = datetime(df["end_date"].max().year, df["end_date"].max().month, 1)
    month_index = lambda d: d.year * 12 + d.month  # noqa: E731
    base = month_index(df["start_date"].min())

    workbook = xlsxwriter.Workbook(str(path))
    sheet = workbook.add_worksheet("Gantt Chart")
    bar = workbook.add_format({"bg_color": BAR_COLOUR})  # one shared format for every bar cell
    sheet.write("A1", "Use case / data source")
    month, col = first, 1
    while month <= last:
        sheet.write(0, col, month.strftime("%b %Y"))
        month += pd.DateOffset(months=1)
        col += 1
    sheet.set_column(0, 0, 60)
    for i, row in df.iterrows():
        sheet.write(i + 1, 0, row["label"])
        for c in range(1 + month_index(row["start_date"]) - base, 2 + month_index(row["end_date"]) - base):
            sheet.write(i + 1, c, "", bar)
    workbook.close()


def draw_pod_gantts(schedule: pd.DataFrame, colours: dict, folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    df = schedule.sort_values(["Team", "start_date", "use_case_priority_sequence", "project_id"]).copy()
    df["label"] = df["use_case_title"] + " / " + df["data_source_title"].astype(str)
    for pod, rows in df.groupby("Team"):
        rows = rows[rows["Actual_Days"] > 0].copy()
        rows["wrapped"] = rows["label"].apply(lambda x: "\n".join(textwrap.wrap(x, width=55)))
        fig, ax = plt.subplots(figsize=(18, max(5, 0.42 * len(rows))))
        for _, r in rows.iterrows():
            ax.barh(r["wrapped"], (r["end_date"] - r["start_date"]).days, left=r["start_date"],
                    color=colours[pod], edgecolor="black", alpha=0.9, height=0.5)
        ax.invert_yaxis()
        ax.xaxis.set_major_locator(mdates.MonthLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
        for quarter in pd.date_range(rows["start_date"].min(), rows["end_date"].max(), freq="QS"):
            ax.axvline(quarter, color="gray", linestyle="--", linewidth=0.8)
        ax.set_title(f"{pod}: data source Gantt chart (synthetic data)")
        ax.tick_params(axis="y", labelsize=7)
        plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
        fig.tight_layout()
        fig.savefig(folder / f"{pod.replace(' ', '_')}_data_source_gantt.png", dpi=110)
        plt.close(fig)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--config", default=str(root / "data/synthetic/configuration_sheet.xlsx"))
    ap.add_argument("--input", default=str(root / "data/synthetic/input_data.xlsx"))
    ap.add_argument("--out-dir", default="output")
    args = ap.parse_args()

    out = Path(args.out_dir)
    charts = out / "charts"
    charts.mkdir(parents=True, exist_ok=True)

    result = run_roadmap(load_config(args.config), load_input(args.input))
    write_output(result, out / "output_data.xlsx")

    schedule = result.df_schedule.copy()
    schedule["start_date"] = pd.to_datetime(schedule["start_date"])
    schedule["end_date"] = pd.to_datetime(schedule["end_date"])
    schedule["use_case_title"] = schedule["use_case_title"].str.strip()
    dates = use_case_dates(schedule)
    colours = pod_colours(dates["Team"].unique())

    draw_use_case_gantt(dates, colours, charts / "use_case_gantt.png")
    dates.to_excel(charts / "use_case_gantt_data.xlsx", index=False, sheet_name="Use Case Gantt Chart Data")
    write_excel_gantt(schedule, charts / "data_source_gantt.xlsx")
    draw_pod_gantts(schedule, colours, charts / "pods")
    print(f"Charts written to {charts}")


if __name__ == "__main__":
    main()
