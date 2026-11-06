"""
The written notes for one month, using the 3-step process:

  1. Code calculates every number (report.py) and the allowed reasons (drivers.py).
  2. Claude drafts 4-6 bullets. It never types a number: it writes slot names such
     as {close_rate}, and code fills them in. Code checks the draft. If it fails,
     Claude gets up to two retries with the exact errors. If every attempt fails,
     bullets that fail are removed; if too few good ones remain, a plain template
     note is used, so the report never breaks.
  3. A person reads the draft, edits it if needed, and approves it (approve.py).

Only aggregated figures are sent to Claude, never individual leads.
"""

import json
import re
from datetime import datetime

import anthropic
import pandas as pd

from src.apikey import get_api_key
from src.report import figure_name, fmt, slug

# Figures offered to Claude, by section
COUNT_METRICS = ["leads", "mqls", "diagnostic_calls", "paid_clients", "revenue"]
RATE_METRICS = ["mql_rate", "close_rate", "diag_to_close", "triage_pass",
                "lead_share_channel", "lead_share_destination", "lost_reason_share"]
MONEY_METRICS = ["revenue_per_client", "revenue_by_tier", "revenue_per_lead"]

DESCRIPTIONS = {
    "leads": "new leads that arrived in the month",
    "mqls": "leads that passed triage (MQL) in the month",
    "diagnostic_calls": "diagnostic calls held in the month",
    "paid_clients": "clients who paid in the month",
    "revenue": "revenue booked in the month",
    "mql_rate": "share of leads that passed triage",
    "triage_pass": "share of this channel's leads that passed triage",
    "lead_share_channel": "this channel's share of all leads",
    "lead_share_destination": "this destination's share of all leads",
    "close_rate": "share of leads that became paid clients",
    "diag_to_close": "share of diagnostic calls that became paid clients",
    "revenue_per_client": "average revenue per paid client",
    "revenue_by_tier": "revenue booked in the month for this service category",
    "revenue_per_lead": "revenue per lead for this channel",
    "lost_reason_share": "this reason's share of lost leads",
}

BANNED_CAUSAL = ["because", "due to", "caused", "causing", "drove", "driven by",
                 "led to", "as a result", "resulted", "thanks to", "owing to", "since",
                 "explains", "explained by"]
BANNED_NUMBER_WORDS = ["two", "three", "four", "five", "six", "seven", "eight", "nine",
                       "ten", "eleven", "twelve", "twenty", "thirty", "forty", "fifty",
                       "hundred", "thousand", "million", "lakh", "crore", "percent",
                       "double", "doubled", "twice", "triple", "tripled", "half", "halved"]

PERSUASION_WORDS = ["sharp", "sharply", "strong", "strongly", "significant",
                    "significantly", "dramatic", "dramatically", "impressive", "impressively",
                    "notable", "notably", "huge", "massive", "remarkable", "remarkably",
                    "substantial", "substantially", "steep", "steeply", "robust", "healthy",
                    "encouraging", "worrying", "alarming", "excellent"]
CURRENCY_WORDS = ["bdt", "tk", "taka"]

FORECAST_WORDS = ["will", "expect", "expected", "likely", "should", "recover", "recovers",
                  "ease", "eases", "improve", "improves", "worsen", "worsens", "rebound",
                  "rebounds", "continue", "continues"]
MAX_FIGURES_PER_BULLET = 4
MAX_ATTEMPTS = 3

SLOT_PATTERN = re.compile(r"\{([^{}]+)\}")


# ---------- Step 1: slots (every figure Claude may use) ----------
def build_slots(report, month):
    """Return (slots, facts_text, figures).

    slots:     slot name -> formatted figure (or period label)
    facts:     the facts table shown to Claude
    figures:   figure slot name -> {"kind": "count" or "rate", "metric": metric name}
               (period labels are not figures)
    """
    slots, figures, lines = {}, {}, []
    month_label = month.strftime("%B %Y")
    slots["month"] = month_label
    slots["month_ly"] = (month - 12).strftime("%B %Y")
    slots["month_lm"] = (month - 1).strftime("%B %Y")

    for _, r in report.iterrows():
        if r["metric"] not in COUNT_METRICS + RATE_METRICS + MONEY_METRICS:
            continue
        name = figure_name(r["metric"], r["segment"])
        kind = "count" if r["metric"] in COUNT_METRICS else "rate"
        window_slot = f"{slug(r['metric'])}_window"
        parts = []
        for suffix, prefix in [("", ""), ("_lm", "last_month_"), ("_ly", "last_year_")]:
            status = r[f"{prefix}status"] if prefix else r["status"]
            value = r[f"{prefix}value"] if prefix else r["value"]
            win = r[f"{prefix}window"] if prefix else r["window"]
            label = {"": "this month", "_lm": "last month", "_ly": "same month last year"}[suffix]
            if status == "ok":
                slots[name + suffix] = fmt(value, r["unit"])
                figures[name + suffix] = {"kind": kind, "metric": r["metric"], "base": name}
                parts.append(f"{label} {{{name + suffix}}} = {slots[name + suffix]} [{win}]")
            else:
                parts.append(f"{label}: {STATUS_WORDS.get(status, status)}")
            if r["segment"] == "all" and isinstance(win, str):
                slots[window_slot + suffix] = win
        seg = "" if r["segment"] == "all" else f" ({r['segment']})"
        lines.append(f"- {r['metric']}{seg}: {DESCRIPTIONS[r['metric']]}. " + "; ".join(parts))

    window_lines = [f"- {{{k}}} = {v}" for k, v in slots.items()
                    if k.endswith(("_window", "_window_lm", "_window_ly"))
                    or k.startswith("month")]
    facts = "PERIOD SLOTS\n" + "\n".join(window_lines) + "\n\nFIGURES\n" + "\n".join(lines)
    return slots, facts, figures


STATUS_WORDS = {"too_few": "too few to call",
                "launch_phase": "no comparison (2023 was the launch phase)"}


# ---------- Step 2a: checks on a draft ----------
def bullet_problems(b, slots, drivers, figures, is_last):
    """Problems with one bullet. An empty list means the bullet passes."""
    problems = []
    by_id = {d["id"]: d for d in drivers}
    driver_ids = set(by_id)
    names = SLOT_PATTERN.findall(b)
    for n in names:
        if n.startswith("driver:"):
            if n[len("driver:"):] not in driver_ids:
                problems.append(f"{{{n}}} is not an allowed reason.")
        elif n not in slots:
            problems.append(f"{{{n}}} is not an available slot.")
    plain = SLOT_PATTERN.sub(" ", b)
    if re.search(r"\d", plain):
        problems.append("contains a typed number. Use slots only.")
    low = plain.lower()
    for w in BANNED_NUMBER_WORDS:
        if re.search(rf"\b{w}\b", low):
            problems.append(f"contains the number word '{w}'. Use slots only.")
    for w in BANNED_CAUSAL:
        if re.search(rf"\b{w}\b", low):
            problems.append(f"uses '{w}'. Say 'coincides with' instead.")
    for w in PERSUASION_WORDS:
        if re.search(rf"\b{w}\b", low):
            problems.append(f"uses '{w}'. State the figures plainly, without judging them.")
    for w in CURRENCY_WORDS:
        if re.search(rf"\b{w}\b", low):
            problems.append("types the currency. Money slots already include BDT.")
    if len(plain.split()) > 55:
        problems.append("too long. Keep it under 40 words.")
    for sentence in re.split(r"(?<=[.;])\s+", b):
        kinds = {figures[n]["kind"] for n in SLOT_PATTERN.findall(sentence) if n in figures}
        if kinds == {"count", "rate"}:
            problems.append("one sentence mixes a count and a rate. Use two sentences.")
    used = [n for n in names if n in figures]
    if len(used) > MAX_FIGURES_PER_BULLET:
        problems.append(f"has {len(used)} figures. One idea per bullet, "
                        f"at most {MAX_FIGURES_PER_BULLET} figures.")
    used_bases = {figures[n]["base"] for n in used}
    for n in names:
        d = by_id.get(n[len("driver:"):]) if n.startswith("driver:") else None
        if d and not used_bases & set(d["figures"]):
            problems.append(f"{{{n}}} sits next to figures it is not tied to. Put it in a "
                            f"bullet with one of: {d['relates_to']}.")
    for m in re.finditer(r"\{driver:[^{}]+\}", b):
        before = b[:m.start()].rstrip().lower()
        if not before.endswith(("coincides with", "came alongside")):
            problems.append(f"{m.group(0)} must follow 'coincides with' or 'came alongside'.")
    if is_last:
        if not b.lower().startswith("watch"):
            problems.append("the last bullet must start with 'Watch'.")
        if "{driver:" in b:
            problems.append("the last bullet names a figure to watch. It must not give a reason.")
        for w in FORECAST_WORDS:
            if re.search(rf"\b{w}\b", low):
                problems.append(f"the last bullet uses '{w}'. Name the figure to watch "
                                "without predicting which way it will move.")
        if not used:
            problems.append("the last bullet must include the current value of the figure "
                            "to watch, as a slot.")
    return problems


def _drivers_in(b):
    return [n for n in SLOT_PATTERN.findall(b) if n.startswith("driver:")]


def check_draft(bullets, slots, drivers, figures):
    """Return a list of problems. An empty list means the draft passes."""
    problems = []
    if not 4 <= len(bullets) <= 6:
        problems.append(f"Write 4 to 6 bullets, not {len(bullets)}.")
    seen = set()
    for i, b in enumerate(bullets, 1):
        for p in bullet_problems(b, slots, drivers, figures, is_last=(i == len(bullets))):
            problems.append(f"Bullet {i}: {p}")
        for n in _drivers_in(b):
            if n in seen:
                problems.append(f"Bullet {i}: {{{n}}} was already used. Use each reason once.")
            seen.add(n)
    return problems


def watch_fallback(slots):
    """A plain watch bullet with the current value of one figure."""
    if "close_rate" in slots:
        return "Watch next month: the close rate, now {close_rate} for {close_rate_window}."
    if "mql_rate" in slots:
        return "Watch next month: the MQL rate, now {mql_rate} for {mql_rate_window}."
    return "Watch next month: paid clients, at {paid_clients} in {month}."


def salvage(bullets, slots, drivers, figures):
    """Keep the bullets that pass on their own; drop the ones that fail.

    Used only after every attempt has failed. A bad bullet never ships: it is
    removed, not loosened. Returns the kept bullets, or None if fewer than three
    good main bullets survive (then the template note is used).
    """
    if not bullets:
        return None
    body, last = bullets[:-1], bullets[-1]
    kept, seen = [], set()
    for b in body:
        reasons = set(_drivers_in(b))
        if bullet_problems(b, slots, drivers, figures, is_last=False) or reasons & seen:
            continue  # failed a check, or repeats a reason already used
        kept.append(b)
        seen |= reasons
    if len(kept) < 3:
        return None
    if bullet_problems(last, slots, drivers, figures, is_last=True):
        last = watch_fallback(slots)
    result = kept[:5] + [last]
    return result if not check_draft(result, slots, drivers, figures) else None


def render(bullets, slots, drivers):
    """Replace slots with the real figures and driver ids with their text."""
    driver_text = {d["id"]: d["text"] for d in drivers}

    def fill(m):
        name = m.group(1)
        if name.startswith("driver:"):
            return driver_text[name[len("driver:"):]]
        return slots[name]
    # Safety net: never print the currency twice
    return [re.sub(r"\bBDT\s+BDT\b", "BDT", SLOT_PATTERN.sub(fill, b)) for b in bullets]


# ---------- Step 2b: Claude's draft ----------
SYSTEM_PROMPT = """You write the commentary for Zorora Academy's monthly business review. \
Zorora is a study abroad consultancy in Dhaka. The reader is the leadership team.

Rules you must follow:
1. Write 4 to 6 bullets. Plain English, short sentences. One idea per bullet, with at \
most four figures in it (for example two figures, each against last year). Under 40 words each.
2. Never type a number, not as digits and not as words. Every figure and every period \
must be a slot name in curly braces, exactly as listed, for example {close_rate} or \
{close_rate_window}. Code fills them in. Money slots already include "BDT", so never \
type the currency.
3. Compare with the same month last year first. Mention last month only when it adds \
something. If a comparison is listed as "no comparison (2023 was the launch phase)", \
do not compare with last year; you may compare with last month.
4. Never put a count (leads, MQLs, calls, paid clients, revenue) and a rate in the same \
sentence. Use two sentences.
5. Reasons: you may only point to reasons from the ALLOWED REASONS list, written as \
{driver:ID}. Each reason lists the exact figures it is tied to (slot names without \
_ly or _lm); put it only in a bullet that contains one of those figures. Use each reason at most once. The reason text is inserted \
into your sentence as written, so write for example "This coincides with {driver:E11}." \
Never claim one thing caused another, and never use: because, due to, caused, drove, \
driven by, led to, as a result, thanks to, owing to, since.
6. If a figure is listed as "too few", do not quote it. You may say there were too few \
leads to call it.
7. Lead with the most important change.
8. The last bullet starts with "Watch" and names one or two figures to track next month, \
with their current value as a slot. It gives no reason and does not predict which way \
they will move.
9. State figures plainly. Do not judge them with words such as sharp, strong, \
significant, dramatic, notable or huge.
10. Do not mention people by name."""

NOTES_SCHEMA = {
    "type": "object",
    "properties": {"bullets": {"type": "array", "items": {"type": "string"}}},
    "required": ["bullets"],
    "additionalProperties": False,
}
JSON_INSTRUCTION = ('\n\nReply with JSON only, in exactly this shape and nothing else: '
                    '{"bullets": ["first bullet", "second bullet"]}')


def _parse_bullets(text):
    """Pull the bullets out of Claude's JSON reply."""
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return []
    bullets = data.get("bullets", []) if isinstance(data, dict) else []
    return [str(b).strip() for b in bullets if str(b).strip()]


def _reply_text(reply):
    return "".join(getattr(b, "text", "") or "" for b in reply.content
                   if getattr(b, "type", None) == "text")


# Request options, tried in order. Newer models think before answering, which
# uses output tokens, so effort is kept low and there is room for the thinking.
# If the model refuses an option, the next, simpler request is tried.
REQUEST_OPTIONS = [
    {"output_config": {"format": {"type": "json_schema", "schema": NOTES_SCHEMA},
                       "effort": "low"}},
    {"output_config": {"format": {"type": "json_schema", "schema": NOTES_SCHEMA}}},
    {},
]
MAX_TOKENS = 8000


def _ask_claude(client, model, user_text):
    """Ask for the bullets as JSON. Returns (bullets, info about the reply)."""
    messages = [{"role": "user", "content": user_text + JSON_INSTRUCTION}]
    last_error = None
    for options in REQUEST_OPTIONS:
        try:
            reply = client.messages.create(model=model, max_tokens=MAX_TOKENS,
                                           system=SYSTEM_PROMPT, messages=messages, **options)
        except anthropic.BadRequestError as e:
            last_error = e
            continue
        text = _reply_text(reply)
        info = {"stop_reason": getattr(reply, "stop_reason", None),
                "blocks": [getattr(b, "type", "?") for b in reply.content],
                "text_start": text[:300]}
        return _parse_bullets(text), info
    raise last_error


def template_bullets(slots):
    """Plain fallback note, built from slots only. Always passes the checks."""
    def compare(name, what, window=None):
        w = f" for leads that arrived {{{window}}}" if window else " in {month}"
        if name in slots and name + "_ly" in slots:
            wl = f" for {{{window}_ly}}" if window else " in {month_ly}"
            return f"{what}{w}: {{{name}}}, against {{{name}_ly}}{wl}."
        if name in slots:
            return f"{what}{w}: {{{name}}}. No comparison with the same month last year."
        return f"{what}: too few leads to call this month."
    return [
        compare("paid_clients", "Paid clients"),
        compare("revenue", "Revenue"),
        compare("close_rate", "Close rate", "close_rate_window"),
        compare("mql_rate", "MQL rate", "mql_rate_window"),
        watch_fallback(slots),
    ]


def draft_notes(report, month, drivers, settings, use_ai=True):
    """Produce the draft. Returns a dict that is saved as notes_draft.json."""
    slots, facts, figures = build_slots(report, month)
    allowed = "\n".join(f"- {{driver:{d['id']}}} = {d['text']}  [tied to: {d['relates_to']}]"
                        for d in drivers) or "- (none)"
    user_text = (f"Report month: {{month}} = {slots['month']}\n\n{facts}\n\n"
                 f"ALLOWED REASONS\n{allowed}\n\nWrite the notes now.")

    result = {"month": str(month), "model": settings["model"], "source": None,
              "attempts": [], "slots": slots, "drivers": drivers,
              "created": datetime.now().isoformat(timespec="seconds")}

    if use_ai:
        try:
            client = anthropic.Anthropic(api_key=get_api_key())
            prompt = user_text
            for attempt in range(1, MAX_ATTEMPTS + 1):
                bullets, info = _ask_claude(client, settings["model"], prompt)
                problems = check_draft(bullets, slots, drivers, figures)
                if not bullets:
                    problems.append(f"Could not read bullets from the reply (stop reason: "
                                    f"{info['stop_reason']}; blocks: {info['blocks']}).")
                result["attempts"].append({"bullets": bullets, "problems": problems,
                                           "reply": info})
                if not problems:
                    result.update(source="ai", bullets=bullets)
                    break
                prompt = (user_text + "\n\nYour previous draft failed these checks. "
                          "Fix every one:\n" + "\n".join(f"- {p}" for p in problems)
                          + "\n\nPrevious draft:\n" + "\n".join(f"- {b}" for b in bullets))
        except (anthropic.APIError, SystemExit) as e:
            result["attempts"].append({"bullets": [], "problems": [f"API problem: {e}"]})

    if result["source"] is None and result["attempts"]:
        # Every attempt failed: keep the good bullets from the best attempt
        best = min(result["attempts"], key=lambda a: len(a["problems"]))
        kept = salvage(best["bullets"], slots, drivers, figures)
        if kept:
            removed = len(best["bullets"]) - len(kept)
            result.update(source="ai_trimmed", bullets=kept, removed_bullets=removed)

    if result["source"] is None:
        bullets = template_bullets(slots)
        assert not check_draft(bullets, slots, drivers, figures), "template failed checks"
        result.update(source="template", bullets=bullets)

    result["rendered"] = render(result["bullets"], slots, drivers)
    return result


# ---------- Files ----------
DRAFT_HEADER = "<!-- Edit the bullets below if needed. Keep each bullet on one line, "
APPROVE_HINT = "then run: python approve.py {month} \"Your Name\" -->"


def write_draft(result, folder):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "notes_draft.json").write_text(json.dumps(result, indent=2, ensure_ascii=False),
                                             encoding="utf-8")
    source = {
        "ai": "AI draft, passed all checks.",
        "ai_trimmed": "AI draft, passed all checks after removing bullets that failed.",
        "template": "Template note (AI draft did not pass checks or was not used).",
    }[result["source"]]
    month_label = pd.Period(result["month"], "M").strftime("%B %Y")
    lines = [f"# Zorora monthly business review: {month_label}",
             "", "**DRAFT, not approved.** " + source, "",
             DRAFT_HEADER + APPROVE_HINT.format(month=result["month"]), ""]
    lines += [f"- {b}" for b in result["rendered"]]
    (folder / "notes_draft.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
