# Monthly business review pipeline for Zorora Academy

**Asef Chaklader** · Python, Power BI, Claude API · Built and tested on 29 months of data

## The task
Zorora Academy is a study abroad consultancy in Dhaka. Leadership needs the same
picture every month: how many leads came in, how many passed triage, how many paid,
what revenue was booked, and what changed against the same month last year. Done by
hand, that report takes hours, and the commentary can drift from the numbers.

## What I built
A pipeline that produces the monthly business review with one command per step:

1. **Numbers.** Python reads the lead, pipeline and revenue data and builds each
   month's figures as of that month's last day, so a November report never sees
   December. Counts use the month an event happened. Rates use rolling 3-month
   windows by the month leads arrived, and close rate only uses leads old enough
   to have paid. Each figure sits next to the same month last year and last month.
2. **Commentary.** Claude drafts 4 to 6 bullets. It never types a number: it writes
   placeholders and code fills in the figures. Code rejects a draft that types a
   number, gives a reason the data does not support, mixes a count and a rate in one
   claim, or uses cause-and-effect wording. Claude gets up to three tries; after that,
   failing bullets are removed, and a plain template note is the last resort.
3. **Sign-off.** A person approves the draft. Approval checks every number in the
   final text against the report.
4. **Outputs.** A one-page memo in Word and PDF, and three tables for a Power BI page.

## Controls
- 26 checks reproduce Zorora's locked figures from raw data before anything runs.
- 9 replay checks confirm the 29 monthly reports add back to the raw totals
  (103 paid clients, BDT 4,645,000 revenue from January 2024 to May 2026).
- A reason can only appear next to a figure it is tied to, and only when that figure
  moved the way the reason predicts.
- A rate with fewer than 10 behind it is shown as "too few to call".
- The memo re-checks the approved note against the data before it is built.
- An independent SQL cross-check in DB Browser matches the pipeline's key figures.

## Results
- 29 monthly reports from January 2024 to May 2026, all checks passing.
- AI commentary tested on 6 months covering peak, quiet and system-change months;
  every draft passed the checks, with retries catching typed numbers, overloaded
  bullets and reasons placed next to unrelated figures.
- November 2025 approved and issued as a one-page memo.

## What comes next
Connect the pipeline to Zorora's live monthly export and run it on a real month.

*Data: a reconstructed operating dataset calibrated to Zorora's real patterns, not a
CRM export. Names are removed, and operators appear only as roles.*
