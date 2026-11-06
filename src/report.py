"""
Step 3 of the pipeline: build one month's report.

For a report month M, everything is measured as of the last day of M,
using only what was known on that day (see snapshot() in metrics.py).

  A. Activity   counts of things that happened in month M
  B. Quality    rates over rolling 3-month windows of leads, by the month they arrived
                - MQL rate, triage pass, lead mix: leads that arrived M-2 to M
                  (triage is decided within 5 days, so these leads are settled)
                - close rate, diagnostic-to-close: leads that arrived M-3 to M-1
                  (every paid client in the data paid within 38 days, so leads
                  from month M have not had time to pay yet)
  C. Money      revenue in month M, and 3-month averages
  D. Losses     why leads were lost, for leads that arrived M-3 to M-1

Every figure is shown three ways: this month, last month (M-1), and the same
month last year (M-12). Each comparison is what that earlier report showed on
its own month end, so like is compared with like.

A rate whose denominator is below min_denominator is marked "too_few" and is
never quoted as a number.
"""

import re

import pandas as pd

from src.metrics import snapshot

THIS, LAST_MONTH, LAST_YEAR = "this_month", "last_month", "last_year"


def slug(text):
    """Name used in slots, e.g. 'Educator Referral' -> 'educator_referral'."""
    return re.sub(r"[^a-z]+", "_", str(text).lower()).strip("_")


def figure_name(metric, segment):
    return metric if segment == "all" else f"{metric}_{slug(segment)}"


def month_end(period):
    return period.end_time.normalize()


def window_label(first, last):
    if first == last:
        return first.strftime("%b %Y")
    if first.year == last.year:
        return f"{first.strftime('%b')}-{last.strftime('%b %Y')}"
    return f"{first.strftime('%b %Y')}-{last.strftime('%b %Y')}"


class MonthBuilder:
    """Computes the figures for any month. Results are cached per month."""

    def __init__(self, leads, revenue, settings):
        self.leads = leads
        self.revenue = revenue.merge(
            leads[["lead_id"]], on="lead_id", how="inner")  # paid clients only
        self.settings = settings
        self.min_den = settings["min_denominator"]
        self.data_start = pd.Period(settings["data_start_month"], "M")
        # 2023 was the launch phase (5-8 leads a month), so no report is compared with it
        self.comparison_start = pd.Period(settings["comparison_start_month"], "M")
        # Fixed segment lists, so every month has the same rows
        self.channels = sorted(leads["channel_source"].unique())
        self.destinations = sorted(leads["destination_country"].unique())
        self.categories = sorted(revenue["service_category"].unique())
        self.reasons = sorted(leads["lost_reason"].dropna().unique())
        self._cache = {}

    # ---------- helpers ----------
    def _rate(self, num, den):
        if den < self.min_den:
            return None, "too_few"
        return num / den, "ok"

    def _row(self, section, metric, segment, value, num, den, status, unit, window):
        return {"section": section, "metric": metric, "segment": segment,
                "value": value, "numerator": num, "denominator": den,
                "status": status, "unit": unit, "window": window}

    # ---------- one month ----------
    def compute(self, month):
        """All figures for one month, as a DataFrame (one row per metric and segment)."""
        if month in self._cache:
            return self._cache[month]

        as_of = month_end(month)
        snap = snapshot(self.leads, as_of)
        snap = snap.assign(inq_m=snap["inquiry_date"].dt.to_period("M"))
        rows = []

        def in_month(dates):
            return dates.dt.to_period("M") == month

        # ---------- A. Activity (things that happened in month M) ----------
        w = window_label(month, month)
        rows.append(self._row("A", "leads", "all", int((snap["inq_m"] == month).sum()),
                              None, None, "ok", "count", w))
        rows.append(self._row("A", "mqls", "all",
                              int((snap["mql"] & in_month(snap["mql_date"])).sum()),
                              None, None, "ok", "count", w))
        rows.append(self._row("A", "diagnostic_calls", "all",
                              int((snap["diag"] & in_month(snap["diag_date"])).sum()),
                              None, None, "ok", "count", w))
        paid_m = snap[snap["won"] & in_month(snap["close_date"])]
        rows.append(self._row("A", "paid_clients", "all", len(paid_m),
                              None, None, "ok", "count", w))
        rev_known = self.revenue[self.revenue["close_date"] <= as_of]
        rev_m = rev_known[rev_known["close_date"].dt.to_period("M") == month]
        rows.append(self._row("A", "revenue", "all", int(rev_m["total_revenue_bdt"].sum()),
                              None, None, "ok", "bdt", w))

        # ---------- B. Quality ----------
        mql_first, mql_last = month - 2, month
        close_first, close_last = month - 3, month - 1
        mql_w = window_label(mql_first, mql_last)
        close_w = window_label(close_first, close_last)

        mql_win = snap[(snap["inq_m"] >= mql_first) & (snap["inq_m"] <= mql_last)]
        close_win = snap[(snap["inq_m"] >= close_first) & (snap["inq_m"] <= close_last)]

        v, s = self._rate(int(mql_win["mql"].sum()), len(mql_win))
        rows.append(self._row("B", "mql_rate", "all", v, int(mql_win["mql"].sum()),
                              len(mql_win), s, "rate", mql_w))
        for ch in self.channels:
            g = mql_win[mql_win["channel_source"] == ch]
            v, s = self._rate(int(g["mql"].sum()), len(g))
            rows.append(self._row("B", "triage_pass", ch, v, int(g["mql"].sum()), len(g), s,
                                  "rate", mql_w))
            v, s = self._rate(len(g), len(mql_win))
            rows.append(self._row("B", "lead_share_channel", ch, v, len(g), len(mql_win), s,
                                  "rate", mql_w))
        for dest in self.destinations:
            g = mql_win[mql_win["destination_country"] == dest]
            v, s = self._rate(len(g), len(mql_win))
            rows.append(self._row("B", "lead_share_destination", dest, v, len(g), len(mql_win),
                                  s, "rate", mql_w))

        won = int(close_win["won"].sum())
        v, s = self._rate(won, len(close_win))
        rows.append(self._row("B", "close_rate", "all", v, won, len(close_win), s, "rate", close_w))
        diag = int(close_win["diag"].sum())
        v, s = self._rate(won, diag)
        rows.append(self._row("B", "diag_to_close", "all", v, won, diag, s, "rate", close_w))

        # ---------- C. Money ----------
        for cat in self.categories:
            g = rev_m[rev_m["service_category"] == cat]
            rows.append(self._row("C", "revenue_by_tier", cat, int(g["total_revenue_bdt"].sum()),
                                  len(g), None, "ok", "bdt", w))
        rev3 = rev_known[(rev_known["close_date"].dt.to_period("M") >= month - 2)
                         & (rev_known["close_date"].dt.to_period("M") <= month)]
        n3 = len(rev3)
        if n3 < self.min_den:
            v, s = None, "too_few"
        else:
            v, s = rev3["total_revenue_bdt"].sum() / n3, "ok"
        rows.append(self._row("C", "revenue_per_client", "all", v,
                              int(rev3["total_revenue_bdt"].sum()), n3, s, "bdt",
                              window_label(month - 2, month)))
        rev_by_lead = close_win.merge(rev_known[["lead_id", "total_revenue_bdt"]],
                                      on="lead_id", how="left")
        rev_by_lead["total_revenue_bdt"] = rev_by_lead["total_revenue_bdt"].fillna(0)
        for ch in self.channels:
            g = rev_by_lead[rev_by_lead["channel_source"] == ch]
            if len(g) < self.min_den:
                v, s = None, "too_few"
            else:
                v, s = g["total_revenue_bdt"].sum() / len(g), "ok"
            rows.append(self._row("C", "revenue_per_lead", ch, v,
                                  int(g["total_revenue_bdt"].sum()), len(g), s, "bdt", close_w))

        # ---------- D. Losses (leads at least 30 days old, not paid) ----------
        lost = close_win[~close_win["won"] & close_win["lost_reason"].notna()]
        for reason in self.reasons:
            n = int((lost["lost_reason"] == reason).sum())
            v, s = self._rate(n, len(lost))
            rows.append(self._row("D", "lost_reason_share", reason, v, n, len(lost), s,
                                  "rate", close_w))

        df = pd.DataFrame(rows)
        self._cache[month] = df
        return df

    def gate_version(self, month):
        g = self.leads[self.leads["inquiry_date"].dt.to_period("M") == month]["gate_version"]
        return g.mode().iloc[0] if len(g) else None

    # ---------- report: this month vs last month vs last year ----------
    def report(self, month):
        base = self.compute(month).copy()
        keys = ["metric", "segment"]
        for label, other in [(LAST_MONTH, month - 1), (LAST_YEAR, month - 12)]:
            if other < self.comparison_start:
                base[f"{label}_value"] = None
                base[f"{label}_denominator"] = None
                base[f"{label}_status"] = "launch_phase"
                base[f"{label}_window"] = None
                continue
            o = self.compute(other)[keys + ["value", "denominator", "status", "window"]].rename(
                columns={"value": f"{label}_value", "denominator": f"{label}_denominator",
                         "status": f"{label}_status", "window": f"{label}_window"})
            base = base.merge(o, on=keys, how="left", validate="one_to_one")
        base.insert(0, "report_month", str(month))
        return base


def fmt(value, unit):
    """Format a figure the way it appears in the report."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if unit == "rate":
        return f"{value * 100:.1f}%"
    if unit == "bdt":
        return f"BDT {round(value):,}"
    return f"{int(value):,}"
