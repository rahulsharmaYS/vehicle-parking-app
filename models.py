from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Name = db.Column(db.String(100), nullable=False)
    Email = db.Column(db.String(120), unique=True, nullable=False)
    Password = db.Column(db.String(200), nullable=False)
    Pincode = db.Column(db.String(10), nullable=False)
    Address = db.Column(db.Text, nullable=True)
    Phone = db.Column(db.String(15), nullable=True)
    Vehicle_Number = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now(ZoneInfo("Asia/Kolkata")))

    reservations = db.relationship('Reservation', backref='user')

    def __repr__(self):
        return f'<User {self.Email}>'
    
    @property
    def vehicle_number(self):
        return self.Vehicle_Number if self.Vehicle_Number else "No Vehicle"


class Contact(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    First_Name = db.Column(db.String(100), nullable=False)
    Last_Name = db.Column(db.String(100), nullable=True)
    Email = db.Column(db.String(120), nullable=False)
    Phone = db.Column(db.String(15), nullable=True)
    Subject = db.Column(db.String(200), nullable=False)
    Message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(ZoneInfo("Asia/Kolkata")))

    def __repr__(self):
        return f'<Contact {self.Name} - {self.Email}>'


class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    Location = db.Column(db.String(200), nullable=False)
    Address = db.Column(db.Text, nullable=False)
    Pincode = db.Column(db.String(10), nullable=False)
    Price = db.Column(db.Float, nullable=False)
    Max_Spots = db.Column(db.Integer, nullable=False)
    Created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    Created_at = db.Column(db.DateTime, default=datetime.now(ZoneInfo("Asia/Kolkata")))
    Max_Time = db.Column(db.Integer, nullable=True)  # in minutes
    
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ParkingLot {self.Location}>'

    @property
    def available_spots(self):
        return len([spot for spot in self.spots if spot.status == 'A'])

    @property
    def occupied_spots(self):
        return len([spot for spot in self.spots if spot.status == 'O'])

    @property
    def occupancy_percentage(self):
        if self.Max_Spots == 0:
            return 0
        return (self.occupied_spots / self.Max_Spots) * 100

class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    status = db.Column(db.String(1), nullable=False, default='A')
    created_at = db.Column(db.DateTime, default=datetime.now(ZoneInfo("Asia/Kolkata")))
    updated_at = db.Column(db.DateTime, default=datetime.now(ZoneInfo("Asia/Kolkata")), onupdate=datetime.now(ZoneInfo("Asia/Kolkata")))
    reservations = db.relationship('Reservation', backref='spot', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<ParkingSpot {self.id} - {self.status}>'


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    in_time = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))
    out_time = db.Column(db.DateTime(timezone=True), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo("Asia/Kolkata")), onupdate=lambda: datetime.now(ZoneInfo("Asia/Kolkata")))

    total_cost = db.Column(db.Float, nullable=True)
    status = db.Column(db.String(20), default='active')  # active, completed
    def __init__(self, spot_id, user_id):
        self.spot_id = spot_id
        self.user_id = user_id
        self.in_time = datetime.now(ZoneInfo("Asia/Kolkata"))
        self.status = 'active'
    def complete_reservation(self, out_time=None, total_cost=None):
        if out_time is None:
            out_time = datetime.now(ZoneInfo("Asia/Kolkata"))
        self.out_time = out_time
        self.total_cost = total_cost
        self.status = 'completed'
        db.session.commit()
    def cancel_reservation(self):
        self.status = 'cancelled'
        db.session.commit()
    def is_active(self):
        return self.status == 'active'
    def is_completed(self):
        return self.status == 'completed'
    def is_cancelled(self):
        return self.status == 'cancelled'

    def __repr__(self):
        return f'<Reservation {self.id} - User {self.user_id}>'
    

    @property
    def duration_hours(self):
        if self.out_time:
            adjusted_out_time = self.out_time + timedelta(hours=5, minutes=30)
            duration = adjusted_out_time - self.in_time
            return round(duration.total_seconds() / 3600, 2)
        return
