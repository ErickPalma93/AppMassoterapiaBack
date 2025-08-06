# src/models/booking.py
from src.models.user import db
from datetime import datetime
from sqlalchemy import UniqueConstraint  # <-- 1. IMPORTE AQUI


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('customer.id'), nullable=False)
    service_id = db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False)
    booking_date = db.Column(db.Date, nullable=False)
    booking_time = db.Column(db.Time, nullable=False)

    status = db.Column(db.String(20), default='confirmed', nullable=False)  # Adicionado nullable=False para garantir
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    customer = db.relationship('Customer', backref='bookings', lazy=True)
    service = db.relationship('Service', backref='bookings')

    # <-- 2. ADICIONE ESSA LINHA
    # Garante que não pode haver duas linhas com a mesma data, hora e status.
    # Essencial para impedir agendamentos 'confirmed' duplicados.
    __table_args__ = (UniqueConstraint('booking_date', 'booking_time', 'status', name='_booking_date_time_status_uc'),)

    def __repr__(self):
        return f'<Booking {self.id} - {self.booking_date} {self.booking_time}>'

    def to_dict(self):
        data = {
            'id': self.id,
            'customer_id': self.customer_id,
            'service_id': self.service_id,
            'booking_date': self.booking_date.isoformat() if self.booking_date else None,
            'booking_time': self.booking_time.strftime('%H:%M') if self.booking_time else None,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'customer': self.customer.to_dict() if self.customer else None,
            'service': self.service.to_dict() if self.service else None
        }

        if hasattr(self, 'blocked_time_entry') and self.blocked_time_entry:
            data['blocked_time_entry'] = self.blocked_time_entry.to_dict()
        return data