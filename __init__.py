import os
from flask import Flask
from datetime import datetime
from werkzeug.security import generate_password_hash
from routes import routes
# from app import db
from models import db, User, ParkingLot, ParkingSpot, Reservation
from zoneinfo import ZoneInfo
from flask_migrate import Migrate


migrate = Migrate()
def create_app():
    app = Flask(__name__, instance_relative_config=True)
    app.config['SECRET_KEY'] = 'app_vehicle_parking'
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(app.instance_path, 'vehicle_parking.sqlite3')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['UPLOAD_FOLDER'] = os.path.join(basedir, 'instance', 'uploads')
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  #16mb limits for file uploads
    db.init_app(app)
    with app.app_context():
        init_db()
        create_admin()
        routes(app)
    return app

def init_db():
    db.create_all()
    print('database finally working yay!')

# admin creation
def create_admin():
    if not User.query.filter_by(Email='admin@admin.com').first():
        admin = User(
            Name='admin',
            Email='admin@admin.com',
            Password=generate_password_hash('123'),
            Pincode='111111',
            Address='admin address',
            Phone='1234567890',
            Vehicle_Number='DL01AB1234',
            created_at=datetime.now(tz=ZoneInfo('Asia/Kolkata'))
        )
        db.session.add(admin)
        db.session.commit()
        print('admin added too!')
