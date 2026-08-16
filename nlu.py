"""
Lightweight rule-based NLU for understanding patient requests.

No external ML model needed — this is intent classification by keyword
matching plus entity extraction (department name, doctor name, date)
against what's actually in the database. This keeps the system fully
explainable and easy for clinical/compliance staff to audit, which
matters a lot more for a hospital bot than raw NLU accuracy.

For a production system you could swap detect_intent()'s internals for
a proper NLU engine (Rasa, Dialogflow, or an LLM call) while keeping the
same function signature — the rest of the app doesn't need to change.
"""

import re
from datetime import datetime, timedelta
from dateutil import parser as dateparser

INTENTS = {
    "hospital_timing": [
        "hospital timing", "hospital hours", "hospital open", "hospital close",
        "opening hour", "opening time", "closing time", "closing hour",
        "when do you open", "when does the hospital open", "what time do you open",
        "what time does the hospital open", "visiting hours", "what time do you close",
        "what time does the hospital close", "are you open", "your timing", "your hours",
    ],
    "doctor_timing": [
        "doctor timing", "doctor available", "doctor availability",
        "when is dr", "what time is dr", "dr available", "doctor schedule",
        "when is doctor", "doctor's timing", "doctor time",
    ],
    "doctor_by_department": [
        "doctor for", "doctors for", "which doctor", "who is the doctor",
        "specialist for", "doctor in", "department doctor", "doctor of","doctor",
    ],
    "book_appointment": [
        "book an appointment", "book appointment", "schedule an appointment",
        "schedule appointment", "i want to see", "i need an appointment",
        "make an appointment", "fix an appointment", "set up an appointment",
        "book a slot", "book with dr",
    ],
}

# Words that, combined with a doctor/department mention, strongly imply a
# timing question even without an exact phrase match above.
TIMING_WORDS = {"time", "timing", "timings", "hours", "available", "availability", "when"}

GREETING_WORDS = {"hi", "hello", "hey", "good morning", "good evening"}


def detect_intent(message: str) -> str:
    """Return the best-matching intent for a raw patient message."""
    text = message.lower().strip()

    if any(g in text for g in GREETING_WORDS) and len(text.split()) <= 3:
        return "greeting"

    # Score each intent by how many of its trigger phrases appear.
    scores = {intent: 0 for intent in INTENTS}
    for intent, phrases in INTENTS.items():
        for phrase in phrases:
            if phrase in text:
                scores[intent] += 1

    best_intent = max(scores, key=scores.get)
    if scores[best_intent] > 0:
        return best_intent

    # Fallback: no exact phrase matched. Use a looser heuristic based on
    # timing-related words plus whether "hospital" or a doctor mention
    # appears, so paraphrases like "what time does the hospital open" or
    # "doctor time for cardiology" still resolve correctly.
    words = set(re.findall(r"[a-z]+", text))
    if words & TIMING_WORDS:
        if "hospital" in words:
            return "hospital_timing"
        if "dr" in words or "doctor" in words:
            return "doctor_timing"

    return "unknown"


def extract_department(message: str, department_names) -> str | None:
    """Fuzzy-match a department name mentioned in the message."""
    text = message.lower()
    for name in department_names:
        if name.lower() in text:
            return name
    # loose match: singular/plural or partial word (e.g. "cardio" -> "Cardiology")
    for name in department_names:
        stem = name.lower()[:5]
        if stem and stem in text:
            return name
    return None


def extract_doctor_name(message: str, doctor_names) -> str | None:
    """Match a doctor's name mentioned in the message (with or without 'Dr.')."""
    text = message.lower()
    for name in doctor_names:
        bare = name.lower().replace("dr.", "").replace("dr ", "").strip()
        if bare in text:
            return name
    return None


def extract_date(message: str) -> str | None:
    """
    Extract a date from natural language and return it as 'YYYY-MM-DD'.
    Understands: 'tomorrow', 'today', 'next monday', '20 august', '2026-08-20', etc.
    Returns None if no date-like text is found.
    """
    text = message.lower()
    today = datetime.now()

    if "today" in text:
        return today.strftime("%Y-%m-%d")
    if "tomorrow" in text:
        return (today + timedelta(days=1)).strftime("%Y-%m-%d")

    weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    for i, day in enumerate(weekdays):
        if day in text:
            days_ahead = (i - today.weekday() + 7) % 7
            days_ahead = days_ahead or 7  # "monday" said on a monday means next monday
            return (today + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    # Try to find an explicit date substring like "20 august" or "2026-08-20"
    match = re.search(
        r"(\d{4}-\d{1,2}-\d{1,2})|(\d{1,2}(st|nd|rd|th)?\s+[a-zA-Z]+)|([a-zA-Z]+\s+\d{1,2}(st|nd|rd|th)?)",
        text,
    )
    if match:
        try:
            parsed = dateparser.parse(match.group(0), fuzzy=True, default=today)
            return parsed.strftime("%Y-%m-%d")
        except (ValueError, OverflowError):
            return None
    return None


def extract_time(message: str) -> str | None:
    """Extract a clock time like '10:30', '10 am', '4pm' and normalize to HH:MM 24h."""
    match = re.search(r"(\d{1,2})(:(\d{2}))?\s*(am|pm)?", message.lower())
    if not match:
        return None
    hour = int(match.group(1))
    minute = int(match.group(3)) if match.group(3) else 0
    meridiem = match.group(4)
    if meridiem == "pm" and hour != 12:
        hour += 12
    if meridiem == "am" and hour == 12:
        hour = 0
    if not (0 <= hour <= 23):
        return None
    return f"{hour:02d}:{minute:02d}"


def extract_entities(message: str, department_names, doctor_names) -> dict:
    """Run all extractors and return a single entity dict."""
    return {
        "department": extract_department(message, department_names),
        "doctor": extract_doctor_name(message, doctor_names),
        "date": extract_date(message),
        "time": extract_time(message),
    }