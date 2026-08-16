# Hospital Helpline Chatbot (Flask + SQLite)

A working backend for a hospital helpline chatbot that understands patient
requests about hospital timings, a specific doctor's availability, doctors
by department, and appointment booking — backed by a custom SQLite database.

## Project structure

```
hospital_chatbot/
├── app.py            Flask app: /api/chat endpoint + REST API routes
├── models.py          SQLAlchemy models (Hospital, Department, Doctor,
│                       DoctorSchedule, Patient, Appointment)
├── nlu.py             Rule-based intent detection + entity extraction
├── seed_data.py        Populates sample hospital/department/doctor data
├── templates/
│   └── index.html      Simple browser chat UI for testing
└── hospital.db         SQLite database (created automatically on first run)
```

## Setup

```bash
pip install flask flask_sqlalchemy python-dateutil
python app.py
```

Then open **http://127.0.0.1:5000** in a browser for the test chat UI,
or call the API directly (see below). The database and sample data
(1 hospital, 5 departments, 6 doctors with weekly schedules) are created
automatically the first time you run the app.

## How "understanding the patient" works (`nlu.py`)

This is intentionally **rule-based, not a black-box ML model** — for a
hospital chatbot you want every decision to be explainable and auditable
by non-engineers (compliance, clinical staff). The flow:

1. **`detect_intent(message)`** — scores the message against keyword/phrase
   lists for four intents (`hospital_timing`, `doctor_timing`,
   `doctor_by_department`, `book_appointment`), with a fallback heuristic
   for paraphrases that don't hit an exact phrase.
2. **`extract_entities(message, ...)`** — pulls out a department name and
   doctor name by matching against what's actually in the database (so it
   stays correct as you add doctors), plus a date (`tomorrow`, `next
   monday`, `2026-08-20`, ...) and a time (`10am`, `14:30`, ...).
3. **`app.py`** routes the (intent, entities) pair to a handler function
   that queries the database and returns a natural-language reply plus
   structured data.

To swap in a real NLU/LLM engine later, you only need to change what
`detect_intent` and `extract_entities` return — the rest of the app
(routing, database queries, booking logic) stays the same.

## API

### `POST /api/chat` — the chatbot endpoint
```json
// Request
{ "message": "When is Dr. Anjali Rao available?" }

// Response
{
  "intent": "doctor_timing",
  "entities": {"department": null, "doctor": "Dr. Anjali Rao", "date": null, "time": null},
  "reply": "Dr. Anjali Rao (Interventional Cardiologist, Cardiology) is available: Monday 09:00-13:00; ...",
  "data": { "...doctor + schedule..." }
}
```

Example messages it understands:
- "What time does the hospital open?"
- "When is Dr. Anjali Rao available?"
- "Which doctor for Dermatology?"
- "Book an appointment with Dr. Karan Bose tomorrow at 10am"

### Direct REST endpoints
| Method | Path | Purpose |
|---|---|---|
| GET | `/api/hospital` | Hospital name, address, hours |
| GET | `/api/departments` | List all departments |
| GET | `/api/doctors?department=Cardiology` | Doctors, optionally filtered |
| GET | `/api/doctors/<id>/schedule` | One doctor's weekly schedule |
| POST | `/api/appointments` | Book an appointment (see body below) |
| GET | `/api/appointments/<patient_id>` | A patient's appointments |

```json
// POST /api/appointments body
{
  "patient_name": "John Doe",
  "patient_phone": "9876543210",
  "doctor_id": 1,
  "date": "2026-08-20",
  "time": "10:30"
}
```
Booking checks for an existing confirmed appointment at the same
doctor/date/time and returns `409 Conflict` if the slot is taken.

## Things to add before this goes anywhere near production

- **Slot validation against the doctor's actual weekly schedule** (currently
  only checks for double-booking, not whether the doctor works that day/time).
- **Patient identity verification** before returning or booking anything
  tied to a real patient record.
- **Emergency/red-flag detection** — if a message mentions symptoms like
  chest pain or breathing difficulty, the bot should immediately show
  emergency instructions instead of continuing the booking flow.
- **HTTPS, authentication, and rate limiting** on the API.
- **A real database** (Postgres/MySQL) instead of SQLite for concurrent
  production traffic — just change `SQLALCHEMY_DATABASE_URI` in `app.py`.
- **Audit logging** of conversations for compliance review.
