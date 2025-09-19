from streamlit import user
from flask import render_template, jsonify, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
from zoneinfo import ZoneInfo
from datetime import timezone
from collections import Counter
from sqlalchemy.orm import joinedload
from functools import wraps
from models import db, Contact, Reservation, User, ParkingLot, ParkingSpot
from datetime import datetime, timedelta

def routes(app):

    
    ############################################## Basic Quick Routes ##########################################


    @app.route('/')
    def index():
        return render_template('index.html')
    @app.route('/docs')
    def docs():
        return render_template('docs.html')
    @app.route('/about')
    def about():
        return render_template('about.html')
    @app.route('/contact', methods=['GET', 'POST'])
    def contact():
        if request.method == 'POST':
            name = request.form['Name']
            email = request.form['email']
            phone = request.form['phone']
            subject = request.form['subject']
            message = request.form['message']

            print(f'Contact form submitted by {name} ({email}, {phone}): {subject} - {message}')

            user = User.query.filter_by(Email=email).first()
            contact_message = Contact(
                First_Name=name,
                Email=email,
                Phone=phone,
                Subject=subject,
                Message=message
            )
            db.session.add(contact_message)
            db.session.commit()

            if user:
                print(f'Message from {user.Name}: {message}')
            else:
                print(f'Message from unregistered user: {name}')

            return redirect(url_for('contact'))

        return render_template('contact.html')


########################################## User Routes ##########################################

    # User Register
    @app.route('/register', methods=['GET', 'POST'])
    def user_register():
        if request.method == 'POST':
            if User.query.filter_by(Email=request.form['email']).first():
                print(f'User with email {request.form["email"]} already exists!')
                return redirect(url_for('user_login'))
            else:
                try:
                    user = User(
                        Name=request.form['name'],
                        Email=request.form['email'],
                        Password=generate_password_hash(request.form['password']),
                        Pincode=request.form['pincode'],
                        Address=request.form.get('address', ''),
                        Phone=request.form.get('phone', ''),
                        Vehicle_Number=request.form.get('vehicle_number', '')
                    )
                    db.session.add(user)
                    db.session.commit()
                    print(f'User {user.Email} registered successfully!')
                    return redirect(url_for('user_login'))
                except Exception as e:
                    db.session.rollback()
                    print(f'Error registering user: {e}')
                    return redirect(url_for('user_register'))        
        return render_template('user/register.html')

    # User Login
    @app.route('/login', methods=['GET', 'POST'])
    def user_login():
        if request.method == 'POST':
            email = request.form['email']
            username = request.form['email']
            if not email and not username:
                return redirect(url_for('user_login'))
            user = User.query.filter((User.Email == email) | (User.Name == username)).first()

            if user and check_password_hash(user.Password, request.form['password']):
                session['user_id'] = user.id
                session['user_name'] = user.Name
                session['user_email'] = user.Email
                return redirect(url_for('user_dashboard'))
            else:
                print(f'Login failed for {request.form["email"]}')
                return render_template('user/login.html', error='Invalid credentials')        
        return render_template('user/login.html')

    # User Logout
    @app.route('/logout')
    def user_logout():
        session.pop('user_id', None)
        session.pop('user_name', None)
        session.pop('user_email', None)
        return redirect(url_for('index'))

    # User Dashboard
    @app.route('/dashboard')
    def user_dashboard():
        if not session.get('user_id'):
            return redirect(url_for('user_login'))
        user = User.query.get(session['user_id'])
        print('user:', user)
        active_reservations = Reservation.query.filter_by(
            user_id=user.id,
            status='active'
        ).join(ParkingSpot).join(ParkingLot).all()

        # will show *all* lots in that pincode prefix that have at least one avail spot
        query = (
            db.session.query(ParkingLot)
            .join(ParkingSpot)
            .filter(ParkingLot.Pincode.startswith(user.Pincode[:2]))
            .filter(ParkingSpot.status == 'A')
            .distinct()
        )
        nearby_lots = query.all()
        print('nearby_lots:', nearby_lots)
        return render_template('user/dashboard.html',
                            user=user,
                            active_reservations=active_reservations,
                            nearby_lots=nearby_lots)

    # User Book Spot
    @app.route('/book/<int:lot_id>')
    def user_book_spot(lot_id):
        if not session.get('user_id'):
            return redirect(url_for('user_login'))
        lot = ParkingLot.query.get_or_404(lot_id)
        available = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').first()
        if not available:
            return redirect(url_for('user_dashboard'))
        try:
            reservation = Reservation(spot_id=available.id, user_id=session['user_id'])
            available.status = 'O'
            db.session.add(reservation)
            db.session.commit()
            print(f'Successfully booked spot: {available.id}')
        except Exception as e:

            db.session.rollback()
            print(f'Error booking spot: {e}')
            return redirect(url_for('user_dashboard'))
        return redirect(url_for('user_dashboard'))

    # User Release Spot
    @app.route('/release/<int:reservation_id>', methods=['POST'])
    def user_release_spot(reservation_id):
        if not session.get('user_id'):
            return redirect(url_for('user_login'))
        res = Reservation.query.get_or_404(reservation_id)
        if res.user_id != session['user_id']:
            return redirect(url_for('user_dashboard'))
        try:
            res.out_time = datetime.utcnow()
            duration_hours = max(1, (res.out_time - res.in_time).total_seconds() / 3600)
            res.total_cost = duration_hours * res.spot.lot.Price
            res.status = 'completed'
            res.spot.status = 'A'
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print(f'Error releasing spot: {e}')
        return redirect(url_for('user_dashboard'))

    # User Summary
    @app.route('/summary')
    def user_summary():
        if not session.get('user_id'):
            return redirect(url_for('user_login'))
        
        reservations = Reservation.query.filter_by(
            user_id=session['user_id']
        ).order_by(
            Reservation.in_time.desc()
        ).all()
        for res in reservations:
            if res.out_time:
                if res.out_time.tzinfo is None:
                    res.out_time = res.out_time.replace(tzinfo=timezone.utc)
                res.out_time_display = res.out_time.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                res.out_time_display = None

            if res.in_time:
                if res.in_time.tzinfo is None:
                    res.in_time = res.in_time.replace(tzinfo=timezone.utc)
                res.in_time_display = res.in_time.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                res.in_time_display = None

        total_bookings = len(reservations)
        total_spent = sum(r.total_cost or 0 for r in reservations if r.status == 'completed')
        total_hours = sum(r.duration_hours for r in reservations if r.status == 'completed')

        return render_template(
            'user/summary.html',
            reservations=reservations,
            total_bookings=total_bookings,
            total_spent=total_spent,
            total_hours=total_hours
        )

    # User Profile
    @app.route('/profile', methods=['GET', 'POST'])
    def user_profile():
        if not session.get('user_id'):
            return redirect(url_for('user_login'))

        user = User.query.get(session['user_id'])
        session['user_name'] = user.Name
        session['user_email'] = user.Email
        session['user_phone'] = user.Phone
        session['user_address'] = user.Address
        session['user_pincode'] = user.Pincode
        session['user_vehicle_number'] = user.Vehicle_Number
        session['user_created_at'] = user.created_at.strftime('%Y-%m-%d')
        print('session:', session)
        print('user:', user)
        if not user:
            print('User not found!')
            return redirect(url_for('user_login'))

        if request.method == 'POST':
            try:
                user.Name = request.form['name']
                user.Email = request.form['email']
                user.Address = request.form.get('address', '')
                user.Phone = request.form.get('phone', '')
                user.Vehicle_Number = request.form.get('vehicle_number', '')
                session['user_created_at'] = user.created_at.strftime('%Y-%m-%d')
                print(user.created_at, user.vehicle_number, user.Phone, user.Address, user.Pincode)
                if request.form['pincode']:
                    user.Pincode = request.form['pincode']

                db.session.commit()
                session['user_name'] = user.Name
                print(f'Profile updated for {user.Name}')
            except Exception as e:
                db.session.rollback()
                print(f'Error updating profile: {str(e)}')

        return render_template('user/profile.html', user=user)



########################################### Admin Routes ##########################################


    # Admin Login
    @app.route('/admin/login', methods=['GET', 'POST'])
    def admin_login():
        if request.method == 'POST':
            email = request.form['email']
            username = request.form['email']
            password = request.form['password']
            print('data:', email, username, password)
            user = User.query.filter((User.Email == email) | (User.Name == username)).first()
            print('user:', user)
            if user and (user.Email == 'admin@admin.com' or user.Name == 'admin') and check_password_hash(user.Password, password):
                session['admin_logged_in'] = True

                return redirect(url_for('admin_dashboard'))

            else:
                return render_template('admin/login.html', error='Invalid credentials')
        return render_template('admin/login.html')  

    # Admin Logout
    @app.route('/admin/logout')
    def admin_logout():
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        session.pop('admin_logged_in', None)
        return redirect(url_for('index'))

    # to prevent unauthorized access to admin dashbaord
    def admin_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not session.get('admin_logged_in'):
                return redirect(url_for('admin_login'))
            return f(*args, **kwargs)
        return decorated_function

    # Admin Dashboard
    @app.route('/admin/dashboard')
    @admin_required
    def admin_dashboard():
        lots = ParkingLot.query.all()
        total_spots = sum(len([spot for spot in lot.spots if spot.status == 'A']) for lot in lots)
        print('total_spots:', total_spots)
        occupied_spots = sum(lot.occupied_spots for lot in lots)
        print('occupied_spots:', occupied_spots)
        available_spots = total_spots - occupied_spots
        search = request.args.get('search', '')
        
        if search:
            lots = ParkingLot.query.filter(
                (ParkingLot.Location.contains(search)) | 
                (ParkingLot.Pincode.contains(search))
            ).all()
        else:
            lots = ParkingLot.query.all()
        
        return render_template('admin/dashboard.html', 
                            lots=lots, 
                            total_spots=total_spots,
                            occupied_spots=occupied_spots,
                            available_spots=available_spots,
                            search=search)

    # Admin Add Lot
    @app.route('/admin/add-lot', methods=['GET', 'POST'])
    @admin_required
    def add_lot():
     if request.method == 'POST':
        print('form data:', request.form)
        try:
            lot = ParkingLot(
                Location=request.form['Location'],
                Address=request.form['Address'],
                Pincode=request.form['Pincode'],
                Price=float(request.form['Price']),
                Max_Spots=int(request.form['Max_Spots']),
                Created_by=session.get('user_id'),
                Max_Time=int(request.form.get('Max_Time', 60))  #defaulting to 60 mins if not provided
            )
            db.session.add(lot)
            db.session.commit()

            for _ in range(lot.Max_Spots):
                spot = ParkingSpot(lot_id=lot.id, status='A')
                db.session.add(spot)
            
            db.session.commit()
            return redirect(url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
    
     return render_template('admin/add_lot.html')

    # Admin Edit Lot
    @app.route('/admin/parking_edit/<int:lot_id>', methods=['GET', 'POST'])
    @admin_required
    def admin_parking_edit(lot_id):
        lot = ParkingLot.query.get(lot_id)
        print('lot:', lot)
        if request.method == 'POST':
            previous_max_spots = lot.Max_Spots
            new_max_spots = int(request.form['Max_Spots'])
            try:
                lot.Location = request.form['Location']
                lot.Address = request.form['Address']
                lot.Pincode = request.form['Pincode']
                lot.Price = float(request.form['Price'])
                lot.Max_Spots = new_max_spots
                print('form data:', request.form)

                spot_diff = lot.Max_Spots - previous_max_spots

                if new_max_spots != previous_max_spots:
                    ParkingSpot.query.filter_by(lot_id=lot.id, status='A').delete(synchronize_session=False)

                    for _ in range(new_max_spots):
                        new_spot = ParkingSpot(lot_id=lot.id, status='A')
                        db.session.add(new_spot)

                # lot.Max_Time = int(request.form.get('Max_Time', 60))  #default here too
                db.session.commit()
                return redirect(url_for('admin_dashboard'))
            except Exception as e:
                db.session.rollback()
    
        return render_template('admin/parking_edit.html', lot=lot)

    # Admin Delete Lot
    @app.route('/admin/delete-lot/<int:lot_id>')
    @admin_required
    def admin_delete_lot(lot_id):
        lot = ParkingLot.query.get_or_404(lot_id)
        
        try:
            db.session.delete(lot)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
        
        return redirect(url_for('admin_dashboard'))

    # Admin User Management
    @app.route('/admin/users')
    @admin_required
    def admin_users():
        users = User.query.filter(User.Name != 'admin').all()
        return render_template('admin/users.html', users=users)

    # Admin Delete User
    @app.route('/admin/delete_user/<int:user_id>', methods=['POST', 'GET'])
    @admin_required
    def admin_delete_user(user_id):
        user = User.query.get_or_404(user_id)
        if user.reservations and len(user.reservations) > 0:
            return redirect(url_for('admin_users'))

        try:
            db.session.delete(user)
            db.session.commit()
            print(f"User {user.Name} has been deleted.")
        except Exception as e:
            db.session.rollback()
        return redirect(url_for('admin_users'))

    # Admin Summary
    @app.route('/admin/summary')
    @admin_required
    def admin_summary():
        reservations = Reservation.query.order_by(Reservation.in_time.desc()).all()
        status_counts = Counter([res.status for res in reservations])
        monthly_counts = Counter()
        for res in reservations:
            if res.in_time:
                month_str = res.in_time.strftime('%b %Y')
                monthly_counts[month_str] += 1

        sorted_months = sorted(monthly_counts.keys(), key=lambda m: datetime.strptime(m, '%b %Y'))
        monthly_data = {
            'labels': sorted_months,
            'data': [monthly_counts[month] for month in sorted_months]
        }
        print('monthly_data:', monthly_data)
        for res in reservations:
            if res.out_time:
                if res.out_time.tzinfo is None:
                    res.out_time = res.out_time.replace(tzinfo=timezone.utc)
                res.out_time_display = res.out_time.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                res.out_time_display = None

            if res.in_time:
                if res.in_time.tzinfo is None:
                    res.in_time = res.in_time.replace(tzinfo=timezone.utc)
                res.in_time_display = res.in_time.astimezone(ZoneInfo("Asia/Kolkata"))
            else:
                res.in_time_display = None

        return render_template(
            'admin/summary.html',
            reservations=reservations,
            status_counts=status_counts,
            monthly_data=monthly_data
        )


########################################### THE END ##########################################
