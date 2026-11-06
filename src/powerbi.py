"""
Tables shaped for Power BI, built from the full replay table.

  outputs/powerbi_monthly.csv             one row per month: headline figures,
                                          with last year (_ly) and last month (_lm)
  outputs/powerbi_channels.csv            one row per month and channel
  outputs/powerbi_revenue_by_service.csv  one row per month and service category

A figure that is "too few to call", or has no comparison (2023 launch phase),
is left blank, so Power BI shows a blank and never a false zero.
"""

import pandas as pd

HEADLINE = ["leads", "mqls", "diagnostic_calls", "paid_clients", "revenue",
            "mql_rate", "close_rate", "diag_to_close", "revenue_per_client"]


def _pick(row, prefix):
    status = row[f"{prefix}status"]
    return row[f"{prefix}value"] if status == "ok" else None


def export_tables(table, settings, out_folder):
    rate = settings["bdt_per_cad"]
    months = sorted(table["report_month"].unique())

    # ---------- monthly headline table ----------
    rows = []
    for m in months:
        t = table[(table["report_month"] == m) & (table["segment"] == "all")].set_index("metric")
        period = pd.Period(m, "M")
        r = {"month": period.start_time.date(), "month_label": period.strftime("%b %Y")}
        for metric in HEADLINE:
            row = t.loc[metric]
            r[metric] = row["value"] if row["status"] == "ok" else None
            r[f"{metric}_ly"] = _pick(row, "last_year_")
            r[f"{metric}_lm"] = _pick(row, "last_month_")
        r["revenue_cad"] = round(r["revenue"] / rate) if r["revenue"] is not None else None
        r["mql_rate_window"] = t.loc["mql_rate", "window"]
        r["close_rate_window"] = t.loc["close_rate", "window"]
        rows.append(r)
    monthly = pd.DataFrame(rows)
    counts = ["leads", "mqls", "diagnostic_calls", "paid_clients", "revenue", "revenue_cad"]
    for c in [c for c in monthly.columns if c.split("_ly")[0].split("_lm")[0] in counts]:
        monthly[c] = monthly[c].astype("Int64")  # whole numbers, blanks kept blank
    monthly.to_csv(out_folder / "powerbi_monthly.csv", index=False, encoding="utf-8")

    # ---------- channels ----------
    ch = table[table["metric"].isin(["lead_share_channel", "triage_pass", "revenue_per_lead"])]
    ch = ch.assign(value=ch["value"].where(ch["status"] == "ok"))
    channels = (ch.pivot_table(index=["report_month", "segment"], columns="metric",
                               values="value", aggfunc="first", dropna=False)
                  .reset_index()
                  .rename(columns={"segment": "channel", "lead_share_channel": "lead_share"}))
    channels.insert(0, "month", channels.pop("report_month").map(
        lambda m: pd.Period(m, "M").start_time.date()))
    channels.to_csv(out_folder / "powerbi_channels.csv", index=False, encoding="utf-8")

    # ---------- revenue by service ----------
    rv = table[table["metric"] == "revenue_by_tier"][["report_month", "segment", "value"]]
    rv = rv.rename(columns={"segment": "service_category", "value": "revenue_bdt"})
    rv.insert(0, "month", rv.pop("report_month").map(
        lambda m: pd.Period(m, "M").start_time.date()))
    rv.to_csv(out_folder / "powerbi_revenue_by_service.csv", index=False, encoding="utf-8")
    return monthly, channels, rv
