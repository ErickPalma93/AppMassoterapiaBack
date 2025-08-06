# src/models/blocked_time.py
from src.models.user import db
from datetime import datetime, date, time

class BlockedTime(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    blocked_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time)
    end_time = db.Column(db.Time)
    reason = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    booking_id = db.Column(db.Integer, db.ForeignKey('booking.id'), nullable=True, unique=True)
    booking = db.relationship('Booking', backref=db.backref('blocked_time_entry', uselist=False))

    def __repr__(self):
        return f'<BlockedTime {self.blocked_date}>'

    def to_dict(self):
        return {
            'id': self.id,
            'blocked_date': self.blocked_date.isoformat() if self.blocked_date else None,
            'start_time': self.start_time.strftime('%H:%M') if self.start_time else None,
            'end_time': self.end_time.strftime('%H:%M') if self.end_time else None,
            'reason': self.reason,
            'booking_id': self.booking_id, # Inclua para debug, se quiser ver o ID do agendamento associado
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'active': self.active
        }