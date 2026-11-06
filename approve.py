"""
Step 3 of the notes process: a person approves the draft.

    python approve.py 2025-11 "Asef Chaklader"

Reads outputs/2025-11/notes_draft.md (with any edits you made), checks it,
and saves outputs/2025-11/notes_approved.md with your name and today's date.

The check: every number in the notes must match a figure the code calculated
for that month. If you typed a number that is not in the report, approval
stops and tells you which one, so a wrong number cannot go out.
"""

import json
import re
import sys
from datetime import date

import pandas as pd

from src.load import PROJECT_ROOT

NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def numbers_in(text):
    return {n.replace(",", "") for n in NUMBER.findall(text)}


def main():
    if len(sys.argv) != 3:
        sys.exit('Usage: python approve.py YYYY-MM "Your Name"')
    month, name = sys.argv[1], sys.argv[2].strip()
    if not name:
        sys.exit("Add your name in quotes, for example \"Asef Chaklader\".")
    folder = PROJECT_ROOT / "outputs" / month
    draft_md = folder / "notes_draft.md"
    draft_json = folder / "notes_draft.json"
    if not draft_md.exists():
        sys.exit(f"No draft for {month}. Run: python run_month.py {month}")

    record = json.loads(draft_json.read_text(encoding="utf-8"))
    bullets = [line[2:].strip() for line in draft_md.read_text(encoding="utf-8").splitlines()
               if line.startswith("- ")]
    if not bullets:
        sys.exit("The draft has no bullets. Each bullet must start with '- '.")

    # Every number must come from the code's figures, reasons or period labels
    allowed = set()
    for v in record["slots"].values():
        allowed |= numbers_in(str(v))
    for d in record["drivers"]:
        allowed |= numbers_in(d["text"])

    problems = []
    for i, b in enumerate(bullets, 1):
        if "{" in b or "}" in b:
            problems.append(f"Bullet {i} still has a slot in curly braces.")
        for n in numbers_in(b) - allowed:
            problems.append(f"Bullet {i}: '{n}' is not a figure in this month's report.")
    if problems:
        print("NOT APPROVED. Fix these in notes_draft.md and run approve again:")
        for p in problems:
            print(f"  - {p}")
        sys.exit(1)

    edited = bullets != record["rendered"]
    today = date.today().isoformat()
    month_label = pd.Period(month, "M").strftime("%B %Y")
    lines = [f"# Zorora monthly business review: {month_label}", ""]
    lines += [f"- {b}" for b in bullets]
    lines += ["", f"Approved by {name} on {today}. "
              f"Draft source: {'template' if record['source'] == 'template' else 'AI'}"
              f"{', edited by the approver' if edited else ''}."]
    (folder / "notes_approved.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (folder / "notes_approved.json").write_text(json.dumps({
        "month": month, "bullets": bullets, "approved_by": name, "approved_on": today,
        "draft_source": record["source"], "edited": edited}, indent=2, ensure_ascii=False),
        encoding="utf-8")
    print(f"APPROVED by {name} on {today}. Saved outputs/{month}/notes_approved.md")
    if edited:
        print("(Your edits were kept. All numbers matched the report.)")


if __name__ == "__main__":
    main()
