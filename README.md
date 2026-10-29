# Zorora Monthly Business Review Pipeline

A monthly reporting pipeline for Zorora Academy, a study abroad consultancy in Dhaka.
It turns lead, pipeline and revenue data into the monthly numbers, a draft commentary
and a one-page memo for leadership. Code calculates every number, AI only drafts the
wording, and a person approves it, with checks at each step.

**Built with:** Python (pandas), Claude API, Power BI, SQL (SQLite), Word.
**Status:** built and tested on 29 months of data (January 2024 to May 2026).
**One-page summary:** [docs/writeup.md](docs/writeup.md)

## What it produces each month
- `outputs/<month>/metrics.csv`: every figure, against last month and the same month last year
- `outputs/<month>/notes_draft.md`: 4 to 6 bullets drafted by Claude and checked by code
- `outputs/<month>/notes_approved.md`: the notes after a person signs them off
- `outputs/<month>/Zorora_MBR_<month>.docx` and `.pdf`: the one-page memo
- `outputs/powerbi_*.csv`: three tables for the Power BI page

## How the AI is used
1. **Code calculates every number.** Claude never types a figure: it writes placeholders such as `{close_rate}` and code fills them in.
2. **Claude drafts the wording.** Code rejects any bullet that types a number, gives a reason the data does not support, puts a reason next to a figure it is not tied to, mixes a count and a rate in one sentence, or uses cause-and-effect wording. Up to 3 attempts, each told exactly what failed. Failing bullets are then removed, never loosened, and a plain template note is the last resort.
3. **A person approves it.** Approval checks every number in the final text against the report, and the memo re-checks it again before it is built.

Only aggregated figures are sent to Claude, never individual leads.

## Controls
| Check | What it proves |
|---|---|
| 26 locked-number checks (`run_checks.py`) | The code reproduces Zorora's verified figures from raw data |
| 9 replay checks (`run_all.py`) | The 29 monthly reports add back to the raw totals: 103 paid clients, BDT 4,645,000 |
| Note checks (`src/notes.py`) | No typed numbers, no unsupported reasons, no overloaded bullets |
| Approval and memo re-check | Nothing goes out unsigned or with a number that no longer matches |
| SQL cross-check (`sql/cross_check.sql`) | Key figures match when recomputed independently in SQLite |
| Privacy check (`privacy_check.py`) | No keys, personal columns or staff names in the repository |

## How the figures are measured
- Each month's report is measured as of that month's last day, using only what was known then.
- Counts (leads, MQLs, calls, paid clients, revenue) use the month each thing happened.
- Rates use rolling 3-month windows by the month leads arrived. Close rate uses the 3 months ending last month, because every paid client in the data paid within 38 days of first contact.
- Each figure is compared with the same month last year and last month, as those earlier reports showed it. 2024 is the first comparison year (2023 was the launch phase).
- A rate with fewer than 10 behind it is shown as "too few to call", never as a number.

## Run it
```
pip install -r requirements.txt
python run_checks.py                     # locked-number checks
python run_all.py                        # all 29 months, totals checks, Power BI tables
python run_month.py 2025-11              # one month: figures and an AI draft (needs an API key in .env)
python run_month.py 2025-11 --no-ai      # same, with the plain template note (free)
python approve.py 2025-11 "Your Name"    # sign off the draft
python make_memo.py 2025-11              # one-page memo, Word and PDF
python test_notes.py                     # AI notes on 6 months at once, one test report
python privacy_check.py                  # run before publishing
```
To use the AI step, copy `.env.example` to `.env` and add an Anthropic API key, or run `python save_api_key.py`.
Power BI steps: [docs/powerbi_steps.md](docs/powerbi_steps.md).

## Data
A **reconstructed operating dataset calibrated to Zorora's real patterns**, not a CRM export:
1,458 leads from June 2023 to May 2026. Names are removed, and operators appear only as roles.
Version 3.1 adds one calibration (the early-2025 US demand dip) without changing any locked figure.
Dated real-world events the notes may refer to are in `config/events_log.csv`.

## Folders
- `src/`: `load.py` (read and clean), `metrics.py` (as-of view), `locked_checks.py`, `report.py` (one month's figures), `drivers.py` (allowed reasons), `notes.py` (AI draft and checks), `powerbi.py`
- `config/`: settings and the events log
- `data/reconstructed/`: the dataset
- `sql/`: the independent cross-check
- `docs/`: one-page write-up, Power BI steps, recording script
- `outputs/`: what each run produces

## Change log
- 2026-10-27: Session 1. Data layer, as-of logic, 26 locked-number checks. Corrected label: 30 paid clients covers Jan–Jun 2026, not Jan–May.
- 2026-10-27: Dataset v3.1. Calibrated to one known event: the US demand dip after the January 2025 inauguration. Six pairs of unpaid 2025 leads swapped destination (US leads from Feb–Apr 2025 with Australia/UK leads from Jul–Sep 2025). Only the contacts file changed (12 rows). Yearly destination shares, all paid clients, the revenue file and all 26 locked numbers are unchanged. v3 contacts file retired.
- 2026-10-27: Events log added (`config/events_log.csv`). Only events marked `citable = yes` may be given as a reason in the monthly notes, and only if the data moves the way the event predicts.
- 2026-10-28: Session 2. Monthly reports with last-month and last-year comparisons, 29-month replay with 9 checks, allowed-reasons list, AI notes with checks and fallback, approval step.
- 2026-10-28: Notes rules tightened after a 6-month test: a reason must sit next to a figure it relates to (enforced), each reason used once, no typed currency, no judging words, the watch bullet gives the current value. No comparisons with 2023 (launch phase).
- 2026-10-28: Reasons tied to exact figures and only offered where the figure moved the way the reason predicts (channel mix judged by each channel's triage rate). No reason may explain itself. Every reason must follow "coincides with" or "came alongside".
- 2026-10-28: Session 3. Memo (Word and PDF) with a re-check of the approved note, Power BI tables, SQL cross-check, privacy check. Names removed from the data; operators shown as roles. CAD shown for scale at 1 CAD = BDT 86.
