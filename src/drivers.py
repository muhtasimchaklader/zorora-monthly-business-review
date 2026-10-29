"""
The allowed reasons ("drivers") for one month's notes.

Claude may only point to a reason from this list, and only next to a figure the
reason is tied to. Code builds the list from two sources:

  1. Events from config/events_log.csv marked citable = yes, that the data
     confirms, and that had started by the first month of the window they explain.
  2. Channel mix: a channel's share of leads moved by at least driver_shift_points
     against the same window last year. Tied to the MQL rate and MQL count, never
     to the channel's own share (that would be the figure explaining itself).

Each reason is tied to exact figures with an expected direction. A reason is
only offered beside a figure that moved that way this month. Example: more
Facebook leads (low triage pass) can sit beside a falling MQL rate, never a
rising one.

The driver text is written by code, not by Claude, so any number in it comes
from the data.
"""

import pandas as pd

from src.load import PROJECT_ROOT
from src.report import figure_name, slug


# ---------- 1. Events ----------
def _event_value(leads, revenue, metric, first, last):
    """The value an event's metric had over a window of months (whole dataset)."""
    m = leads["inquiry_date"].dt.to_period("M")
    win = leads[(m >= first) & (m <= last)]
    if metric.startswith("share_leads_"):
        kind, value = metric[len("share_leads_"):].split(":")
        col = {"channel": "channel_source", "destination": "destination_country"}[kind]
        return (win[col] == value).mean() if len(win) else None
    if metric.startswith("leads_count_"):
        kind, value = metric[len("leads_count_"):].split(":")
        col = {"channel": "channel_source", "student_type": "student_type"}[kind]
        return int((win[col] == value).sum())
    if metric == "revenue_per_client":
        rm = revenue["close_date"].dt.to_period("M")
        r = revenue[(rm >= first) & (rm <= last)]
        return r["total_revenue_bdt"].mean() if len(r) else None
    if metric == "close_rate":
        return win["closed_won"].mean() if len(win) else None
    if metric == "diag_to_close":
        d = win[win["reached_opp"]]
        return d["closed_won"].mean() if len(d) else None
    raise ValueError(f"Unknown event metric: {metric}")


def check_events(leads, revenue):
    """Read the events log and mark which citable events the data confirms.

    Each event is compared with a window of the same length just before it.
    """
    log = pd.read_csv(PROJECT_ROOT / "config" / "events_log.csv", dtype=str)
    log["confirmed"] = False
    for i, e in log.iterrows():
        if e["citable"] != "yes":
            continue
        first, last = pd.Period(e["start_month"], "M"), pd.Period(e["end_month"], "M")
        n = (last - first).n + 1
        before = _event_value(leads, revenue, e["metric"], first - n, first - 1)
        during = _event_value(leads, revenue, e["metric"], first, last)
        if before is None or during is None:
            continue
        moved_up = during > before
        log.at[i, "confirmed"] = moved_up if e["expected_direction"] == "up" else not moved_up
    return log


UP, DOWN, ANY = "up", "down", "any"


def _flip(direction, sign):
    return direction if sign > 0 else {UP: DOWN, DOWN: UP}[direction]


def channel_quality(leads):
    """+1 if a channel's leads pass triage more often than average, -1 if less."""
    overall = leads["reached_mql"].mean()
    rates = leads.groupby("channel_source")["reached_mql"].mean()
    return {ch: (1 if r > overall else -1) for ch, r in rates.items()}


def figure_directions(report):
    """Which way each figure moved: against last year if both are known,
    otherwise against last month. Returns {figure name: 'up' | 'down' | 'flat'}."""
    out = {}
    for _, r in report.iterrows():
        if r["status"] != "ok":
            continue
        for prefix in ("last_year_", "last_month_"):
            if r[f"{prefix}status"] == "ok":
                diff = r["value"] - r[f"{prefix}value"]
                out[figure_name(r["metric"], r["segment"])] = (
                    UP if diff > 0 else DOWN if diff < 0 else "flat")
                break
    return out


def _event_figures(metric, direction, quality, lost_reasons):
    """(window start for report month M, [(figure, expected direction)])."""
    if metric.startswith("share_leads_channel:"):
        ch = metric.split(":", 1)[1]
        mix = _flip(direction, quality.get(ch, 1))
        return (lambda m: m - 2), [(f"lead_share_channel_{slug(ch)}", direction),
                                   ("mql_rate", mix), ("mqls", mix)]
    if metric.startswith("share_leads_destination:"):
        dest = metric.split(":", 1)[1]
        return (lambda m: m - 2), [(f"lead_share_destination_{slug(dest)}", direction)]
    if metric.startswith("leads_count_channel:"):
        ch = metric.split(":", 1)[1]
        return (lambda m: m - 2), [("leads", direction),
                                   (f"lead_share_channel_{slug(ch)}", direction)]
    if metric.startswith("leads_count_"):
        return (lambda m: m - 2), [("leads", direction)]
    if metric in ("close_rate", "diag_to_close"):
        return (lambda m: m - 3), ([("close_rate", direction), ("diag_to_close", direction)]
                                   + [(f"lost_reason_share_{slug(r)}", ANY)
                                      for r in lost_reasons])
    if metric == "revenue_per_client":
        return (lambda m: m - 2), [("revenue_per_client", direction),
                                   ("revenue_by_tier_full_mentorship", direction)]
    raise ValueError(f"Unknown event metric: {metric}")


def _keep_matching(figures, moved):
    """Keep only the figures that moved the way the reason predicts."""
    return [f for f, d in figures if f in moved and (d == ANY or moved[f] == d)]


def _driver(id_, text, figures):
    return {"id": id_, "text": text, "figures": figures,
            "relates_to": ", ".join(figures)}


# ---------- all drivers for one month ----------
def drivers_for_month(report, month, events, settings, leads):
    """Return the allowed reasons for one month as a list of dicts:
    id, text (inserted into the note as written), figures (the exact figures it
    may sit next to, already filtered to those that moved the predicted way)."""
    shift = settings["driver_shift_points"] / 100
    moved = figure_directions(report)
    quality = channel_quality(leads)
    lost_reasons = sorted(leads["lost_reason"].dropna().unique())
    out = []

    # 1. Events, started by the first month of the window they explain
    for _, e in events.iterrows():
        if e["citable"] != "yes" or not e["confirmed"]:
            continue
        first, last = pd.Period(e["start_month"], "M"), pd.Period(e["end_month"], "M")
        window_start, figures = _event_figures(e["metric"], e["expected_direction"],
                                               quality, lost_reasons)
        if not first <= window_start(month) <= last:
            continue
        figures = _keep_matching(figures, moved)
        if figures:
            text = f"{e['event']} (from {first.strftime('%b %Y')})"
            out.append(_driver(e["event_id"], text, figures))

    # 2. Channel mix shifts against the same window last year
    rows = report[(report["metric"] == "lead_share_channel") & (report["status"] == "ok")
                  & (report["last_year_status"] == "ok")]
    for _, r in rows.iterrows():
        diff = r["value"] - r["last_year_value"]
        if abs(diff) < shift:
            continue
        direction = UP if diff > 0 else DOWN
        mix = _flip(direction, quality.get(r["segment"], 1))
        figures = _keep_matching([("mql_rate", mix), ("mqls", mix)], moved)
        if figures:
            word = "rise" if diff > 0 else "fall"
            text = (f"a {word} in the {r['segment']} share of leads, from "
                    f"{r['last_year_value'] * 100:.1f}% ({r['last_year_window']}) "
                    f"to {r['value'] * 100:.1f}% ({r['window']})")
            out.append(_driver(f"mix:{r['segment']}", text, figures))
    return out
