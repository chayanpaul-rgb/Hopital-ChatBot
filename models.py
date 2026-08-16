
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Hospital(db.Model):
    """General hospital info: name, address, opening hours, phone."""
    __tablename__ = "hospital"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.String(250))
    phone = db.Column(db.String(30))
    opening_time = db.Column(db.String(10), nullable=False)   # "08:00"
    closing_time = db.Column(db.String(10), nullable=False)   # "20:00"
    emergency_open_24_7 = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "name": self.name,
            "address": self.address,
            "phone": self.phone,
            "opening_time": self.opening_time,
            "closing_time": self.closing_time,
            "emergency_open_24_7": self.emergency_open_24_7,
        }


class Department(db.Model):
    """Hospital department, e.g. Cardiology, Dermatology, Orthopedics."""
    __tablename__ = "department"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(255))

    doctors = db.relationship("Doctor", backref="department", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "description": self.description}


class Doctor(db.Model):
    """A doctor belonging to a department, with a weekly schedule."""
    __tablename__ = "doctor"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    specialization = db.Column(db.String(150))
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)

    schedules = db.relationship("DoctorSchedule", backref="doctor", lazy=True,
                                 cascade="all, delete-orphan")
    appointments = db.relationship("Appointment", backref="doctor", lazy=True)

    def to_dict(self, include_schedule=False):
        data = {
            "id": self.id,
            "name": self.name,
            "specialization": self.specialization,
            "department": self.department.name if self.department else None,
        }
        if include_schedule:
            data["schedule"] = [s.to_dict() for s in self.schedules]
        return data


class DoctorSchedule(db.Model):
    """One weekly availability block for a doctor."""
    __tablename__ = "doctor_schedule"

    id = db.Column(db.Integer, primary_key=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)
    # 0=Monday ... 6=Sunday (Python's weekday() convention)
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time = db.Column(db.String(10), nullable=False)   # "09:00"
    end_time = db.Column(db.String(10), nullable=False)     # "13:00"

    DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
                 "Friday", "Saturday", "Sunday"]

    def to_dict(self):
        return {
            "day": self.DAY_NAMES[self.day_of_week],
            "start_time": self.start_time,
            "end_time": self.end_time,
        }


class Patient(db.Model):
    """Minimal patient identity record for booking appointments."""
    __tablename__ = "patient"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(30), nullable=False)
    email = db.Column(db.String(120))

    appointments = db.relationship("Appointment", backref="patient", lazy=True)

    def to_dict(self):
        return {"id": self.id, "name": self.name, "phone": self.phone, "email": self.email}


class Appointment(db.Model):
    """A booked appointment linking a patient to a doctor at a date/time."""
    __tablename__ = "appointment"

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey("patient.id"), nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey("doctor.id"), nullable=False)
    appointment_date = db.Column(db.String(10), nullable=False)  # "2026-08-20"
    appointment_time = db.Column(db.String(10), nullable=False)  # "10:30"
    status = db.Column(db.String(20), default="confirmed")       # confirmed/cancelled
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "patient": self.patient.name if self.patient else None,
            "doctor": self.doctor.name if self.doctor else None,
            "department": self.doctor.department.name if self.doctor and self.doctor.department else None,
            "date": self.appointment_date,
            "time": self.appointment_time,
            "status": self.status,
        }