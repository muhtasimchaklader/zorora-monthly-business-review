"""
Session 2 command. Run from the project folder:

    python run_all.py

Builds the report for every month from the start to the end month in settings,
checks the totals, and saves one table for Power BI:

    outputs/mbr_metrics.csv   one row per month, metric and segment,
                              with this month, last month and last year side by side
"""

import sys

import pandas as pd

from src.load import PROJECT_ROOT, load_data, load_settings
from src.locked_checks import run_locked_checks
from src.powerbi import export_tables
from src.report import MonthBuilder


def main():
    settings = load_settings()
    leads, revenue = load_data(settings)

    # Step 0: locked numbers must pass before anything else runs
    checks = run_locked_checks(leads, revenue)
    failed = checks[checks["result"] == "FAIL"]
    if len(failed):
        print(failed.to_string(index=False))
        sys.exit(f"\nSTOPPED: {len(failed)} locked checks failed. Nothing was built.")
    print(f"Locked checks: all {len(checks)} passed.")

    start = pd.Period(settings["report_start_month"], "M")
    end = pd.Period(settings["report_end_month"], "M")
    months = pd.period_range(start, end, freq="M")

    builder = MonthBuilder(leads, revenue, settings)
    table = pd.concat([builder.report(m) for m in months], ignore_index=True)
    out = PROJECT_ROOT / "outputs"
    out.mkdir(exist_ok=True)
    table.to_csv(out / "mbr_metrics.csv", index=False, encoding="utf-8")
    print(f"Built {len(months)} monthly reports, {start} to {end}.")

    # ---------- Checks on the replay ----------
    def this_month(metric):
        rows = table[(table["metric"] == metric) & (table["segment"] == "all")]
        return int(rows["value"].sum())

    window_leads = leads[(leads["inquiry_date"].dt.to_period("M") >= start)
                         & (leads["inquiry_date"].dt.to_period("M") <= end)]
    window_paid = leads[leads["closed_won"]
                        & (leads["close_date"].dt.to_period("M") >= start)
                        & (leads["close_date"].dt.to_period("M") <= end)]
    window_rev = revenue[(revenue["close_date"].dt.to_period("M") >= start)
                         & (revenue["close_date"].dt.to_period("M") <= end)]

    results = []

    def check(name, expected, actual):
        results.append({"check": name, "expected": expected, "actual": actual,
                        "result": "PASS" if expected == actual else "FAIL"})

    check("Paid clients, all months added up", 103, this_month("paid_clients"))
    check("Paid clients match the raw file", len(window_paid), this_month("paid_clients"))
    check("Revenue (BDT), all months added up", 4_645_000, this_month("revenue"))
    check("Revenue matches the raw file", int(window_rev["total_revenue_bdt"].sum()),
          this_month("revenue"))
    check("Leads match the raw file", len(window_leads), this_month("leads"))
    in_2024 = table[table["report_month"].str.startswith("2024")]
    check("2024 never compared with 2023 (launch phase)", True,
          bool((in_2024["last_year_status"] == "launch_phase").all()))
    jan_2024 = table[table["report_month"] == "2024-01"]
    check("Jan 2024 not compared with Dec 2023", True,
          bool((jan_2024["last_month_status"] == "launch_phase").all()))
    later = table[~table["report_month"].str.startswith("2024")]
    check("2025-2026 always have a last-year comparison", True,
          bool((later["last_year_status"] != "launch_phase").all()))
    rates = table[table["status"] == "too_few"]
    check("No rate is shown when there are too few", True, bool(rates["value"].isna().all()))

    results = pd.DataFrame(results)
    print()
    print(results.to_string(index=False))
    if (results["result"] == "FAIL").any():
        sys.exit("\nSTOPPED: replay checks failed. Send Claude the FAIL lines.")
    print(f"\nALL {len(results)} REPLAY CHECKS PASSED.")

    # ---------- Short summary ----------
    def pick(metric):
        rows = table[(table["metric"] == metric) & (table["segment"] == "all")]
        return rows.set_index("report_month")["value"]

    summary = pd.DataFrame({
        "leads": pick("leads").astype(int),
        "paid": pick("paid_clients").astype(int),
        "revenue_bdt": pick("revenue").astype(int).map("{:,}".format),
        "close_rate_3m": pick("close_rate").map(
            lambda v: "too few" if pd.isna(v) else f"{v * 100:.1f}%"),
    })
    print("\nLast 6 months:")
    print(summary.tail(6).to_string())
    export_tables(table, settings, out)
    print("\nSaved outputs/mbr_metrics.csv (full table) and three tables for Power BI:")
    print("  powerbi_monthly.csv, powerbi_channels.csv, powerbi_revenue_by_service.csv")


if __name__ == "__main__":
    main()
