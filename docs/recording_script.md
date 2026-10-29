# 2-minute screen recording: script

Record with the Windows Snipping Tool (Record) or Loom. Have VS Code's terminal,
the memo and Power BI open before you start. Speak plainly; read the lines below.

**0:00 to 0:15. What it is**
"This is a monthly business review pipeline for Zorora Academy, a study abroad
consultancy. One command turns lead and revenue data into the monthly numbers,
a draft commentary and a one-page memo for leadership."

**0:15 to 0:35. The checks**
Run `python run_all.py`.
"It rebuilds every month from January 2024 to May 2026. Before anything runs, it
reproduces 26 locked figures from the raw data, and then checks the monthly totals
add back up. If any figure is off, it stops."

**0:35 to 1:00. The AI draft**
Run `python run_month.py 2025-11` and open `notes_draft.md`.
"Code calculates every number. Claude only drafts the wording, using placeholders
that code fills in, so it cannot type a wrong number. Code rejects any bullet that
gives a reason the data does not support, and Claude gets up to three tries."

**1:00 to 1:15. Approval**
Run `python approve.py 2025-11 "Asef Chaklader"`.
"Nothing goes out until a person approves it. Approval checks every number in the
final text against the report."

**1:15 to 1:35. The memo**
Run `python make_memo.py 2025-11` and open the PDF.
"This is what leadership receives: key figures against last year and last month,
the approved notes, and who signed them off."

**1:35 to 2:00. Power BI**
Show the page and change the month picker.
"The same tables feed this Power BI page. The data is a reconstructed model of
Zorora's real operating patterns, so the method is the point: numbers from code,
wording from AI, sign-off from a person, with checks at every step."
