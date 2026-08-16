"""
Populates the database with sample hospital data so the chatbot has
something real to answer questions about. Run once after the tables
are created (app.py does this automatically on first run).
"""

from models import db, Hospital, Department, Doctor, DoctorSchedule


def seed():
    if Hospital.query.first():
        return  # already seeded

    hospital = Hospital(
        name="Sunrise General Hospital",
        address="12 MG Road, Kolkata",
        phone="+91-33-1234-5678",
        opening_time="08:00",
        closing_time="20:00",
        emergency_open_24_7=True,
    )
    db.session.add(hospital)

    departments = {
        "Cardiology": "Heart and cardiovascular care",
        "Dermatology": "Skin, hair, and nail conditions",
        "Orthopedics": "Bones, joints, and muscles",
        "Pediatrics": "Child and infant health",
        "General Medicine": "General checkups and common illnesses",
    }
    dept_objs = {}
    for name, desc in departments.items():
        d = Department(name=name, description=desc)
        db.session.add(d)
        dept_objs[name] = d
    db.session.flush()  # get IDs

    doctors = [
        ("Dr. Anjali Rao", "Interventional Cardiologist", "Cardiology",
         [(0, "09:00", "13:00"), (2, "09:00", "13:00"), (4, "09:00", "13:00")]),
        ("Dr. Rohan Mehta", "Cardiac Surgeon", "Cardiology",
         [(1, "10:00", "14:00"), (3, "10:00", "14:00")]),
        ("Dr. Sana Iyer", "Dermatologist", "Dermatology",
         [(0, "11:00", "15:00"), (3, "11:00", "15:00"), (5, "10:00", "13:00")]),
        ("Dr. Karan Bose", "Orthopedic Surgeon", "Orthopedics",
         [(1, "09:00", "12:00"), (2, "09:00", "12:00"), (4, "14:00", "17:00")]),
        ("Dr. Meera Nair", "Pediatrician", "Pediatrics",
         [(0, "10:00", "16:00"), (1, "10:00", "16:00"), (2, "10:00", "16:00"),
          (3, "10:00", "16:00"), (4, "10:00", "16:00")]),
        ("Dr. Vivek Shah", "General Physician", "General Medicine",
         [(0, "08:30", "12:30"), (1, "08:30", "12:30"), (2, "08:30", "12:30"),
          (3, "08:30", "12:30"), (4, "08:30", "12:30"), (5, "09:00", "12:00")]),
    ]

    for name, specialization, dept_name, schedule in doctors:
        doc = Doctor(name=name, specialization=specialization,
                     department_id=dept_objs[dept_name].id)
        db.session.add(doc)
        db.session.flush()
        for day, start, end in schedule:
            db.session.add(DoctorSchedule(doctor_id=doc.id, day_of_week=day,
                                           start_time=start, end_time=end))

    db.session.commit()
    print("Seeded sample hospital data.")