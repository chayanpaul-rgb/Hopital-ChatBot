from flask import Flask, request, jsonify, render_template
from datetime import datetime

from models import db, Hospital, Department, Doctor, DoctorSchedule, Patient, Appointment
import nlu
import seed_data

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///hospital.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    seed_data.seed()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_department_names():
    return [d.name for d in Department.query.all()]


def get_doctor_names():
    return [d.name for d in Doctor.query.all()]


def find_doctor_by_name(name):
    if not name:
        return None
    return Doctor.query.filter(Doctor.name.ilike(f"%{name.split('.')[-1].strip()}%")).first()


def find_department_by_name(name):
    if not name:
        return None
    return Department.query.filter(Department.name.ilike(name)).first()


def format_schedule(doctor: Doctor) -> str:
    if not doctor.schedules:
        return f"{doctor.name} has no listed availability right now."
    parts = [f"{s.DAY_NAMES[s.day_of_week]} {s.start_time}-{s.end_time}" for s in doctor.schedules]
    return f"{doctor.name} ({doctor.specialization}, {doctor.department.name}) is available: " + "; ".join(parts)


# ---------------------------------------------------------------------------
# Intent handlers
# ---------------------------------------------------------------------------

def handle_hospital_timing():
    h = Hospital.query.first()
    msg = f"{h.name} is open from {h.opening_time} to {h.closing_time}, every day."
    if h.emergency_open_24_7:
        msg += " The emergency department is open 24/7."
    return {"reply": msg, "data": h.to_dict()}


def handle_doctor_timing(entities):
    doctor = find_doctor_by_name(entities.get("doctor"))
    if not doctor:
        return {
            "reply": "Which doctor would you like the timing for? You can say, "
                      "for example, 'When is Dr. Anjali Rao available?'",
            "data": None,
        }
    return {"reply": format_schedule(doctor), "data": doctor.to_dict(include_schedule=True)}


def handle_doctor_by_department(entities):
    dept = find_department_by_name(entities.get("department"))
    if not dept:
        names = ", ".join(get_department_names())
        return {
            "reply": f"Which department do you need? We have: {names}.",
            "data": None,
        }
    doctors = Doctor.query.filter_by(department_id=dept.id).all()
    if not doctors:
        return {"reply": f"No doctors are currently listed for {dept.name}.", "data": None}
    lines = [f"{d.name} ({d.specialization})" for d in doctors]
    reply = f"Doctors in {dept.name}: " + "; ".join(lines) + \
            ". Tell me a name and a preferred day to check their timing or book."
    return {"reply": reply, "data": [d.to_dict() for d in doctors]}


def handle_book_appointment(entities, message):
    doctor = find_doctor_by_name(entities.get("doctor"))
    dept = find_department_by_name(entities.get("department"))

    if not doctor and dept:
        doctors = Doctor.query.filter_by(department_id=dept.id).all()
        if len(doctors) == 1:
            doctor = doctors[0]
        elif doctors:
            names = ", ".join(d.name for d in doctors)
            return {
                "reply": f"We have a few doctors in {dept.name}: {names}. "
                         f"Which one would you like to book with?",
                "data": None,
            }

    if not doctor:
        return {
            "reply": "Who would you like to book an appointment with? You can name a "
                      "doctor directly, or a department (e.g. 'Cardiology').",
            "data": None,
        }

    date = entities.get("date")
    time = entities.get("time")
    missing = []
    if not date:
        missing.append("a date (e.g. 'tomorrow', 'next Monday', '2026-08-20')")
    if not time:
        missing.append("a preferred time (e.g. '10:30' or '4pm')")
    if missing:
        return {
            "reply": f"Booking with {doctor.name}. Please also share " + " and ".join(missing) + ".",
            "data": {"doctor": doctor.to_dict()},
        }

    # NOTE: in production, verify the slot against doctor.schedules for that
    # weekday and check for existing conflicting appointments before booking.
    return {
        "reply": f"To confirm: book {doctor.name} ({doctor.department.name}) on {date} at {time}? "
                  f"Reply with your name and phone number to confirm.",
        "data": {"doctor": doctor.to_dict(), "date": date, "time": time, "status": "pending_confirmation"},
    }


# ---------------------------------------------------------------------------
# Chat endpoint - this is the main "understand the patient" entry point
# ---------------------------------------------------------------------------

@app.route("/api/chat", methods=["POST"])
def chat():
    body = request.get_json(silent=True) or {}
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"reply": "Please type your question.", "intent": None}), 400

    intent = nlu.detect_intent(message)
    entities = nlu.extract_entities(message, get_department_names(), get_doctor_names())

    if intent == "greeting":
        result = {"reply": "Hello! I can help with hospital timings, doctor availability, "
                            "finding a doctor by department, or booking an appointment. "
                            "How can I help?", "data": None}
    elif intent == "hospital_timing":
        result = handle_hospital_timing()
    elif intent == "doctor_timing":
        result = handle_doctor_timing(entities)
    elif intent == "doctor_by_department":
        result = handle_doctor_by_department(entities)
    elif intent == "book_appointment":
        result = handle_book_appointment(entities, message)
    else:
        result = {
            "reply": "I didn't quite catch that. I can help with hospital timings, "
                      "a doctor's availability, finding a doctor by department, or "
                      "booking an appointment. Could you rephrase?",
            "data": None,
        }

    return jsonify({
        "intent": intent,
        "entities": entities,
        "reply": result["reply"],
        "data": result["data"],
    })


# ---------------------------------------------------------------------------
# Direct REST API (for a front-end app, not just the chat box)
# ---------------------------------------------------------------------------

@app.route("/api/hospital", methods=["GET"])
def api_hospital():
    return jsonify(Hospital.query.first().to_dict())


@app.route("/api/departments", methods=["GET"])
def api_departments():
    return jsonify([d.to_dict() for d in Department.query.all()])


@app.route("/api/doctors", methods=["GET"])
def api_doctors():
    department = request.args.get("department")
    query = Doctor.query
    if department:
        dept = find_department_by_name(department)
        if not dept:
            return jsonify([])
        query = query.filter_by(department_id=dept.id)
    return jsonify([d.to_dict() for d in query.all()])


@app.route("/api/doctors/<int:doctor_id>/schedule", methods=["GET"])
def api_doctor_schedule(doctor_id):
    doctor = Doctor.query.get_or_404(doctor_id)
    return jsonify(doctor.to_dict(include_schedule=True))


@app.route("/api/appointments", methods=["POST"])
def api_book_appointment():
    """
    Expected JSON body:
    {
      "patient_name": "John Doe", "patient_phone": "9876543210",
      "doctor_id": 1, "date": "2026-08-20", "time": "10:30"
    }
    """
    body = request.get_json(silent=True) or {}
    required = ["patient_name", "patient_phone", "doctor_id", "date", "time"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    doctor = Doctor.query.get(body["doctor_id"])
    if not doctor:
        return jsonify({"error": "Doctor not found"}), 404

    try:
        datetime.strptime(body["date"], "%Y-%m-%d")
    except ValueError:
        return jsonify({"error": "date must be in YYYY-MM-DD format"}), 400

    # Reuse an existing patient record by phone number, or create a new one.
    patient = Patient.query.filter_by(phone=body["patient_phone"]).first()
    if not patient:
        patient = Patient(name=body["patient_name"], phone=body["patient_phone"],
                           email=body.get("patient_email"))
        db.session.add(patient)
        db.session.flush()

    existing = Appointment.query.filter_by(
        doctor_id=doctor.id, appointment_date=body["date"],
        appointment_time=body["time"], status="confirmed",
    ).first()
    if existing:
        return jsonify({"error": "That slot is already booked. Please choose another time."}), 409

    appt = Appointment(patient_id=patient.id, doctor_id=doctor.id,
                        appointment_date=body["date"], appointment_time=body["time"])
    db.session.add(appt)
    db.session.commit()

    return jsonify({"message": "Appointment confirmed", "appointment": appt.to_dict()}), 201


@app.route("/api/appointments/<int:patient_id>", methods=["GET"])
def api_patient_appointments(patient_id):
    appts = Appointment.query.filter_by(patient_id=patient_id).all()
    return jsonify([a.to_dict() for a in appts])


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True)