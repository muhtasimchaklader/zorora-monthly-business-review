"""
Tests the AI notes on several months in one go, so every problem shows up at once.

    python test_notes.py

Runs Claude on 6 months (a mix of peak, quiet and gate-change months) and saves
one file with every draft, every failed check and the final bullets:

    outputs/ai_test_report.md

Cost: about 20-40 cents in total. Drafts are written to each month's folder as usual.
"""

import pandas as pd

from src.drivers import check_events, drivers_for_month
from src.load import PROJECT_ROOT, load_data, load_settings
from src.locked_checks import run_locked_checks
from src.notes import draft_notes, write_draft
from src.report import MonthBuilder

TEST_MONTHS = ["2024-11", "2025-03", "2025-06", "2025-10", "2025-11", "2026-04"]


def main():
    settings = load_settings()
    leads, revenue = load_data(settings)
    checks = run_locked_checks(leads, revenue)
    if (checks["result"] == "FAIL").any():
        raise SystemExit("STOPPED: locked checks failed. Run python run_checks.py.")

    builder = MonthBuilder(leads, revenue, settings)
    events = check_events(leads, revenue)
    lines = ["# AI notes test report", ""]
    tally = {"ai": 0, "ai_trimmed": 0, "template": 0}

    for m in TEST_MONTHS:
        month = pd.Period(m, "M")
        print(f"{m}: asking Claude...", flush=True)
        report = builder.report(month)
        drivers = drivers_for_month(report, month, events, settings, leads)
        result = draft_notes(report, month, drivers, settings, use_ai=True)
        write_draft(result, PROJECT_ROOT / "outputs" / m)
        tally[result["source"]] += 1
        print(f"  -> {result['source']}, {len(result['attempts'])} attempt(s)")

        lines += [f"## {m}: {result['source']}", ""]
        for i, a in enumerate(result["attempts"], 1):
            lines.append(f"Attempt {i}: {'passed' if not a['problems'] else 'failed'}")
            lines += [f"  - {p}" for p in a["problems"]]
            if a["problems"]:
                lines += [f"    > {b}" for b in a["bullets"]]
        lines += ["", "Final bullets:"] + [f"- {b}" for b in result["rendered"]] + [""]

    summary = (f"Passed first time or after retry: {tally['ai']}. "
               f"Trimmed: {tally['ai_trimmed']}. Template: {tally['template']}. "
               f"Out of {len(TEST_MONTHS)}.")
    lines.insert(2, summary + "\n")
    (PROJECT_ROOT / "outputs" / "ai_test_report.md").write_text("\n".join(lines),
                                                              encoding="utf-8")
    print("\n" + summary)
    print("Saved outputs/ai_test_report.md. Send it to Claude.")


if __name__ == "__main__":
    main()
