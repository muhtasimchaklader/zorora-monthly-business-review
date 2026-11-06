"""
Session 2 command. Builds one month's report and a draft of the notes:

    python run_month.py 2025-11

Saves in outputs/2025-11/:
  metrics.csv        every figure for the month (this month, last month, last year)
  notes_draft.md     the draft notes, numbers filled in, for a person to read
  notes_draft.json   the record behind the draft (slots, reasons, every attempt)

Add --no-ai to skip Claude and use the plain template note (costs nothing).
"""

import sys

import pandas as pd

from src.drivers import check_events, drivers_for_month
from src.load import PROJECT_ROOT, load_data, load_settings
from src.locked_checks import run_locked_checks
from src.notes import draft_notes, write_draft
from src.report import MonthBuilder


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    use_ai = "--no-ai" not in sys.argv
    if len(args) != 1:
        sys.exit("Usage: python run_month.py YYYY-MM   (for example 2025-11)")
    settings = load_settings()
    try:
        month = pd.Period(args[0], "M")
    except ValueError:
        sys.exit(f"'{args[0]}' is not a month. Use the form 2025-11.")
    start = pd.Period(settings["report_start_month"], "M")
    end = pd.Period(settings["report_end_month"], "M")
    if not start <= month <= end:
        sys.exit(f"Pick a month from {start} to {end}.")

    leads, revenue = load_data(settings)
    checks = run_locked_checks(leads, revenue)
    if (checks["result"] == "FAIL").any():
        sys.exit("STOPPED: locked checks failed. Run python run_checks.py to see which.")
    print(f"Locked checks: all {len(checks)} passed.")

    builder = MonthBuilder(leads, revenue, settings)
    report = builder.report(month)
    folder = PROJECT_ROOT / "outputs" / str(month)
    folder.mkdir(parents=True, exist_ok=True)
    report.to_csv(folder / "metrics.csv", index=False, encoding="utf-8")

    events = check_events(leads, revenue)
    drivers = drivers_for_month(report, month, events, settings, leads)
    print(f"Report month {month}. Gate version live: {builder.gate_version(month)}. "
          f"Allowed reasons: {len(drivers)}.")

    if use_ai:
        print("Asking Claude for a draft (costs about 2-5 cents)...")
    result = draft_notes(report, month, drivers, settings, use_ai=use_ai)
    write_draft(result, folder)

    for i, a in enumerate(result["attempts"], 1):
        status = "passed" if not a["problems"] else f"failed {len(a['problems'])} checks"
        print(f"  Attempt {i}: {status}")
        for p in a["problems"]:
            print(f"    - {p}")
    print({
        "ai": "Draft: written by Claude, passed all checks.",
        "ai_trimmed": f"Draft: written by Claude. {result.get('removed_bullets', 0)} bullet(s) "
                      "that failed checks were removed; the rest passed.",
        "template": "Draft: plain template note (Claude's draft did not pass, or --no-ai was used).",
    }[result["source"]])

    print(f"\nSaved outputs/{month}/notes_draft.md. Open it, read it, edit if needed, then run:")
    print(f'  python approve.py {month} "Your Name"')


if __name__ == "__main__":
    main()
