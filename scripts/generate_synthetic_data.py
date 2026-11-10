"""Generate the synthetic dataset for the roadmap engine prototype.

Fictional company: "Larkspur Synthetic Group". Every name, number and date here is
invented. Nothing is derived from a real organisation.

Writes two workbooks:
    configuration_sheet.xlsx   sheets: config, start_date, exception_use_cases
    input_data.xlsx            sheets: use_cases, projects, data_sources, project_sources

Run:
    python scripts/generate_synthetic_data.py --out data/synthetic --seed 42
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

COMPANY = "Larkspur Synthetic Group"
PLAN_START = datetime(2026, 1, 5)

# pod name -> (start date, max concurrent activities)
PODS = {
    "Supply Chain Pod": (datetime(2026, 1, 5), 4),
    "Finance Pod": (datetime(2026, 1, 5), 4),
    "HR Pod": (datetime(2026, 2, 2), 3),
    "Commerce Pod": (datetime(2026, 1, 5), 4),
    "Sales Pod": (datetime(2026, 2, 2), 3),
    "Platform Pod": (datetime(2026, 3, 2), 4),
}

BUSINESS_UNITS = ["Retail", "Wholesale", "Online", "Corporate", "Services"]

# generic system type -> domains it can feed ("Area: Subject")
SOURCE_DOMAINS = {
    "ERP System": ["Supply Chain: Inventory", "Supply Chain: Procurement", "Finance: Revenue",
                   "Finance: Costs", "Sales: Product Sales"],
    "Warehouse Management System": ["Supply Chain: Inventory", "Supply Chain: Logistics"],
    "Transport Management System": ["Supply Chain: Logistics"],
    "Procurement Portal": ["Supply Chain: Procurement", "Finance: Accounts Payable"],
    "Demand Planning Tool": ["Supply Chain: Demand Planning", "Sales: Forecasts"],
    "General Ledger": ["Finance: Revenue", "Finance: Costs", "Finance: Budgeting"],
    "Budgeting Tool": ["Finance: Budgeting", "Finance: Costs"],
    "Accounts Payable System": ["Finance: Accounts Payable", "Finance: Costs"],
    "HRIS": ["HR: Headcount", "HR: Attrition", "HR: Payroll"],
    "Payroll System": ["HR: Payroll", "HR: Headcount", "Finance: Costs"],
    "Applicant Tracking System": ["HR: Recruitment", "HR: Headcount"],
    "E-commerce Platform": ["Commerce: Online Orders", "Commerce: Product Catalog", "Sales: Product Sales"],
    "Product Information Management": ["Commerce: Product Catalog"],
    "Review Aggregator": ["Commerce: Customer Reviews"],
    "CRM": ["Sales: Pipeline", "Sales: Product Sales", "Sales: Forecasts", "Commerce: Customer Reviews"],
    "Sales Forecasting Tool": ["Sales: Forecasts", "Supply Chain: Demand Planning"],
    "Marketplace Feed A": ["Commerce: Online Orders", "Sales: Product Sales"],
    "Marketplace Feed B": ["Commerce: Online Orders", "Commerce: Customer Reviews"],
    "Employee Survey Tool": ["HR: Attrition", "HR: Recruitment"],
    "Central Data Warehouse": ["Finance: Revenue", "Sales: Product Sales", "Supply Chain: Inventory",
                               "HR: Headcount"],
}

# (use case title, area, pod)
USE_CASES = [
    ("Inventory Visibility Dashboard", "Supply Chain", "Supply Chain Pod"),
    ("Supplier Performance Scorecard", "Supply Chain", "Supply Chain Pod"),
    ("Demand Forecast Accuracy Report", "Supply Chain", "Supply Chain Pod"),
    ("Freight Cost Analysis", "Supply Chain", "Supply Chain Pod"),
    ("Stock-out Early Warning", "Supply Chain", "Supply Chain Pod"),
    ("Procurement Spend Analysis", "Supply Chain", "Supply Chain Pod"),
    ("Warehouse Utilisation Report", "Supply Chain", "Supply Chain Pod"),
    ("On-time Delivery Tracker", "Supply Chain", "Supply Chain Pod"),
    ("Revenue Reconciliation Report", "Finance", "Finance Pod"),
    ("Cost Variance Analysis", "Finance", "Finance Pod"),
    ("Budget vs Actual Dashboard", "Finance", "Finance Pod"),
    ("Accounts Payable Ageing", "Finance", "Finance Pod"),
    ("Margin by Product", "Finance", "Finance Pod"),
    ("Expense Compliance Monitor", "Finance", "Finance Pod"),
    ("Cash Flow Outlook", "Finance", "Platform Pod"),
    ("Headcount and Cost Report", "HR", "HR Pod"),
    ("Attrition Risk Dashboard", "HR", "HR Pod"),
    ("Recruitment Funnel Report", "HR", "HR Pod"),
    ("Payroll Variance Check", "HR", "HR Pod"),
    ("Workforce Planning Model", "HR", "Platform Pod"),
    ("Online Orders Overview", "Commerce", "Commerce Pod"),
    ("Cart Abandonment Report", "Commerce", "Commerce Pod"),
    ("Product Catalog Quality Score", "Commerce", "Commerce Pod"),
    ("Customer Review Sentiment", "Commerce", "Commerce Pod"),
    ("Marketplace Performance Compare", "Commerce", "Commerce Pod"),
    ("Promotion Effectiveness", "Commerce", "Platform Pod"),
    ("Pipeline Health Dashboard", "Sales", "Sales Pod"),
    ("Sales Forecast vs Actual", "Sales", "Sales Pod"),
    ("Regional Sales Scorecard", "Sales", "Sales Pod"),
    ("Cross-sell Opportunities", "Sales", "Sales Pod"),
    ("Customer Churn Report", "Sales", "Platform Pod"),
]

PROJECT_CATALOG = {
    "Supply Chain": ["# Open Purchase Orders", "Inventory Turnover", "Days of Supply", "Fill Rate",
                     "Supplier Lead Time", "Freight Cost per Unit", "Warehouse Capacity Used",
                     "Forecast Bias", "Backorder Count", "Order Cycle Time", "Carrier On-time Rate"],
    "Finance": ["Gross Margin", "Operating Cost by Unit", "Budget Variance", "Days Payable Outstanding",
                "Revenue by Product", "Accrual Accuracy", "Cash Conversion Cycle", "Discount Leakage",
                "Expense Claims Flagged", "Invoice Match Rate"],
    "HR": ["Headcount by Unit", "Voluntary Attrition Rate", "Time to Hire", "Offer Acceptance Rate",
           "Payroll Cost per Head", "Overtime Hours", "Engagement Score", "Open Requisitions"],
    "Commerce": ["# Online Orders", "Cart Abandonment Rate", "Catalog Completeness", "Review Rating Trend",
                 "Conversion Rate", "Return Rate", "Marketplace Share of Orders", "Promo Uplift"],
    "Sales": ["Pipeline Coverage", "Win Rate", "Forecast Accuracy", "Revenue per Region",
              "Customer Retention", "Average Deal Size", "Cross-sell Rate", "Quota Attainment"],
}

AREA_ORDER = ["Supply Chain", "Finance", "HR", "Commerce", "Sales"]


def build(seed: int):
    rng = random.Random(seed)

    # ---- data sources: one row per (source system, domain, business unit)
    ds_rows = []
    ds_id = 0
    for source, domains in SOURCE_DOMAINS.items():
        for domain in domains:
            for bu in rng.sample(BUSINESS_UNITS, 2):
                ds_id += 1
                ds_rows.append({
                    "data_source_id": ds_id,
                    "data_source_title": f"{source}_{domain}_{bu}",
                    "cost": round(rng.uniform(15000, 55000), 2),
                    "data_source_status": "planned",
                    "source": source,
                    "domain": domain,
                    "brand": bu,
                })
    data_sources = pd.DataFrame(ds_rows)
    area_of = data_sources["domain"].str.split(":").str[0]

    # already enabled sources: 4 in Commerce, 2 in each other area
    enabled_ids = set()
    for area in AREA_ORDER:
        ids = data_sources.loc[area_of == area, "data_source_id"].tolist()
        enabled_ids.update(rng.sample(ids, 4 if area == "Commerce" else 2))
    data_sources.loc[data_sources["data_source_id"].isin(enabled_ids), "data_source_status"] = "enabled"

    # ---- project catalog (project_id is global, projects can be shared by use cases of an area)
    catalog = []
    for area in AREA_ORDER:
        for title in PROJECT_CATALOG[area]:
            catalog.append((len(catalog) + 1, area, title))

    # ---- use cases, projects, project_sources
    uc_rows, proj_rows, ps_rows = [], [], []
    fully_enabled_uc = "Online Orders Overview"      # zero-cost use case
    exception_titles = ["Revenue Reconciliation Report", "Inventory Visibility Dashboard"]
    enabled_seen = set()
    for uc_id, (title, area, pod) in enumerate(USE_CASES, start=1):
        y1 = round(rng.uniform(25000, 140000), 2)
        uc_rows.append({
            "use_case_id": uc_id, "use_case_title": title,
            "business_value_y1": y1,
            "business_value_y2": round(y1 * 7 / 3, 2),
            "business_value_y3": round(y1 * 10 / 3, 2),
            "status": "planned", "pod_name": pod,
        })
        area_projects = [c for c in catalog if c[1] == area]
        chosen = rng.sample(area_projects, rng.randint(2, 4))
        if title == fully_enabled_uc:
            pool = data_sources[(area_of == area) & data_sources["data_source_id"].isin(enabled_ids)]
        else:
            main = data_sources[area_of == area]
            cross = data_sources[area_of != area]
            pool = pd.concat([main, cross.sample(6, random_state=seed + uc_id)])
        pool_ids = pool["data_source_id"].tolist()
        for pid, _, ptitle in sorted(chosen):
            proj_rows.append({"use_case_id": uc_id, "project_id": pid,
                              "use_case_title": title, "project_title": ptitle})
            k = min(len(pool_ids), rng.randint(3, 6))
            for dsid in sorted(rng.sample(pool_ids, k)):
                ds_title = data_sources.loc[data_sources["data_source_id"] == dsid, "data_source_title"].iloc[0]
                row = {"use_case_id": uc_id, "project_id": pid, "data_source_id": dsid,
                       "use_case_title": title, "project_title": ptitle,
                       "data_source_title": ds_title, "source_status": "planned",
                       "actual_start_date": pd.NaT, "actual_end_date": pd.NaT}
                first_time = dsid in enabled_ids and dsid not in enabled_seen
                if title == fully_enabled_uc or first_time:
                    start = datetime(2025, 9, 1) + timedelta(days=rng.randint(0, 90))
                    row.update(source_status="enabled", actual_start_date=start,
                               actual_end_date=start + timedelta(days=rng.randint(30, 70)))
                    enabled_seen.add(dsid)
                ps_rows.append(row)

    use_cases = pd.DataFrame(uc_rows)
    projects = pd.DataFrame(proj_rows)
    project_sources = pd.DataFrame(ps_rows)

    # ---- configuration workbook
    config = pd.DataFrame([
        ("discount_rate", 0.10), ("domain_days", 30), ("source_days", 42), ("use_case_days", 14),
        ("MAX_WORKSTREAMS", 4), ("start_date", PLAN_START), ("subsequent_domain_days", 8),
        ("subsequent_source_days", 8), ("subsequent_use_case_days", 0),
        ("enabled_datasource_days", 0), ("enabled_datasource_usecase_days", 0),
    ], columns=["variable", "value"])
    start_date = pd.DataFrame(
        [(p, d, cap) for p, (d, cap) in PODS.items()], columns=["pod_name", "start_date", "max_activity"])
    ids_by_title = dict(zip(use_cases["use_case_title"], use_cases["use_case_id"]))
    exceptions = pd.DataFrame({"use_case_id": [ids_by_title[t] for t in exception_titles]})
    return config, start_date, exceptions, use_cases, projects, data_sources, project_sources


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", default="data/synthetic", help="output folder")
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    config, start_date, exceptions, use_cases, projects, data_sources, project_sources = build(args.seed)
    with pd.ExcelWriter(out / "configuration_sheet.xlsx") as w:
        config.to_excel(w, sheet_name="config", index=False)
        start_date.to_excel(w, sheet_name="start_date", index=False)
        exceptions.to_excel(w, sheet_name="exception_use_cases", index=False)
    with pd.ExcelWriter(out / "input_data.xlsx") as w:
        use_cases.to_excel(w, sheet_name="use_cases", index=False)
        projects.to_excel(w, sheet_name="projects", index=False)
        data_sources.to_excel(w, sheet_name="data_sources", index=False)
        project_sources.to_excel(w, sheet_name="project_sources", index=False)
    print(f"{COMPANY}: {len(use_cases)} use cases, {len(projects)} projects, "
          f"{len(data_sources)} data sources, {len(project_sources)} project-source rows -> {out}")


if __name__ == "__main__":
    main()
