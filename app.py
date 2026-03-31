import os
import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)


# -----------------------------
# Database Models
# -----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    leads = db.relationship('Lead', backref='owner', lazy=True)


class Lead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    agent_name = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    budget = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(100), nullable=False)
    property_type = db.Column(db.String(50), nullable=False)
    timeline = db.Column(db.String(50), nullable=False)
    notes = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='New')
    date_added = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    status = db.Column(db.String(20), default='New')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# -----------------------------
# Helpers
# -----------------------------
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return None
    return User.query.filter_by(id=user_id).first()


def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return route_function(*args, **kwargs)
    return wrapper


# -----------------------------
# Message Generators
# -----------------------------
def generate_message_1(lead):
    return f"""
Hello {lead.name.title()},

Thank you for your inquiry about finding a {lead.property_type} in {lead.location} with a budget of {lead.budget}. My name is {lead.agent_name}.

I am reviewing your request and will get back to you shortly.

Best regards,
{lead.agent_name}
"""


def generate_message_2(lead):
    return f"""
Hello {lead.name.title()},

This is {lead.agent_name} following up on your property inquiry.

Are you available for a quick call tomorrow?

Best regards,
{lead.agent_name}
"""


def generate_call_script(lead):
    return f"""
Lead: {lead.name}
Phone: {lead.phone}

Hi {lead.name}, this is {lead.agent_name}. I'm calling about your request for a {lead.property_type} in {lead.location}.
"""


# -----------------------------
# Auth Routes
# -----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name')
        email = request.form.get('email').lower()
        password = request.form.get('password')
        confirm = request.form.get('confirm_password')

        if not full_name or not email or not password or not confirm:
            flash('Fill all fields', 'error')
            return redirect(url_for('register'))

        if password != confirm:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email already exists', 'error')
            return redirect(url_for('register'))

        user = User(
            full_name=full_name,
            email=email,
            password_hash=generate_password_hash(password)
        )

        db.session.add(user)
        db.session.commit()

        flash('Account created. Login now.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email').lower()
        password = request.form.get('password')

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password', 'error')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        session['user_name'] = user.full_name

        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# -----------------------------
# Lead Routes
# -----------------------------
@app.route('/')
@login_required
def index():
    return render_template('index.html')


@app.route('/add_lead', methods=['POST'])
@login_required
def add_lead():
    current_user = get_current_user()

    if not current_user:
        return redirect(url_for('login'))

    agent_name = request.form.get('agent_name')
    name = request.form.get('name')
    phone = request.form.get('phone')
    budget = request.form.get('budget')
    location = request.form.get('location')
    property_type = request.form.get('property_type')
    timeline = request.form.get('timeline')
    notes = request.form.get('notes')

    if not all([agent_name, name, phone, budget, location, property_type, timeline]):
        flash('Fill all fields', 'error')
        return redirect(url_for('index'))

    lead = Lead(
        agent_name=agent_name,
        name=name,
        phone=phone,
        budget=budget,
        location=location,
        property_type=property_type,
        timeline=timeline,
        notes=notes,
        user_id=current_user.id
    )

    db.session.add(lead)
    db.session.commit()

    return redirect(url_for('result', lead_id=lead.id))


@app.route('/result/<int:lead_id>')
@login_required
def result(lead_id):
    current_user = get_current_user()

    if not current_user:
        return redirect(url_for('login'))

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    if not lead:
        return redirect(url_for('leads'))

    # FORMAT PHONE FOR WHATSAPP
    phone = lead.phone.strip()

    if phone.startswith('0'):
        phone = '234' + phone[1:]

    if phone.startswith('+'):
        phone = phone[1:]

    return render_template(
        'result.html',
        lead=lead,
        message1=generate_message_1(lead),
        message2=generate_message_2(lead),
        call_script=generate_call_script(lead),
        phone=phone
    )


@app.route('/leads')
@login_required
def leads():
    current_user = get_current_user()

    if not current_user:
        return redirect(url_for('login'))

    # ✅ GET FILTER FROM URL
    status = request.args.get('status')

    # ✅ BASE QUERY
    query = Lead.query.filter_by(user_id=current_user.id)

    # ✅ APPLY FILTER IF EXISTS
    if status:
        query = query.filter_by(status=status)

    # ✅ FINAL DATA
    all_leads = query.order_by(Lead.date_added.desc()).all()

    # ✅ COUNTS
    total_leads = Lead.query.filter_by(user_id=current_user.id).count()
    new_leads = Lead.query.filter_by(user_id=current_user.id, status='New').count()
    contacted_leads = Lead.query.filter_by(user_id=current_user.id, status='Contacted').count()
    closed_leads = Lead.query.filter_by(user_id=current_user.id, status='Closed').count()

    return render_template(
        'leads.html',
        leads=all_leads,
        current_user=current_user,
        total_leads=total_leads,
        new_leads=new_leads,
        contacted_leads=contacted_leads,
        closed_leads=closed_leads
    )

# ✅ DELETE ROUTE (FIXED)
@app.route('/delete_lead/<int:lead_id>', methods=['POST'])
@login_required
def delete_lead(lead_id):
    current_user = get_current_user()

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    if not lead:
        return redirect(url_for('leads'))

    db.session.delete(lead)
    db.session.commit()

    flash('Deleted successfully', 'success')
    return redirect(url_for('leads'))


@app.route('/mark_closed/<int:lead_id>')
@login_required
def mark_closed(lead_id):
    current_user = get_current_user()

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    if lead:
        lead.status = 'Closed'
        db.session.commit()

    return redirect(url_for('leads'))    


@app.route('/mark_contacted/<int:lead_id>', methods=['POST'])
@login_required
def mark_contacted(lead_id):
    current_user = get_current_user()

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    if lead:
        lead.status = 'Contacted'
        db.session.commit()

    return '', 200


# -----------------------------
# RUN
# -----------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))