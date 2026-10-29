"""
Session 1 command. Run from the project folder:

    python run_checks.py

It loads the data, checks every locked number, and saves two files in outputs/:
  locked_checks.csv     - every check with expected vs actual
  monthly_activity.csv  - leads, MQLs, calls, paid clients and revenue per month
"""

import sys

from src.load import PROJECT_ROOT, load_data, load_settings
from src.locked_checks import FULL_DATA_AS_OF, run_locked_checks
from src.metrics import monthly_activity, snapshot


def main():
    settings = load_settings()
    leads, revenue = load_data(settings)
    print(f"Loaded {len(leads)} leads and {len(revenue)} paid clients. Names removed.\n")

    results = run_locked_checks(leads, revenue)
    out = PROJECT_ROOT / "outputs"
    out.mkdir(exist_ok=True)
    results.to_csv(out / "locked_checks.csv", index=False)

    print(results.to_string(index=False))
    failed = results[results["result"] == "FAIL"]
    print()
    if len(failed):
        print(f"STOPPED: {len(failed)} of {len(results)} checks failed. Send Claude the FAIL lines.")
        sys.exit(1)
    print(f"ALL {len(results)} CHECKS PASSED.")

    # Preview: monthly counts for the report window
    snap = snapshot(leads, FULL_DATA_AS_OF)
    activity = monthly_activity(snap, revenue, FULL_DATA_AS_OF)
    start, end = settings["report_start_month"], settings["report_end_month"]
    window = activity.loc[start:end]
    window.to_csv(out / "monthly_activity.csv")
    print(f"\nSaved monthly_activity.csv: {len(window)} months, {start} to {end}.")
    print(f"Paid clients in window: {window['paid_clients'].sum()}  "
          f"Revenue in window (BDT): {window['revenue_bdt'].sum():,}")
    print("Note: the window revenue is not the locked lifetime figure of 5,285,000.")


if __name__ == "__main__":
    main()
