import os
import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config['SECRET_KEY'] = 'change-this-to-a-real-secret-key'
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

    def __repr__(self):
        return f'<User {self.email}>'


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
    date_added = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # This connects each lead to a specific user
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    def __repr__(self):
        return f'<Lead {self.name}>'


# -----------------------------
# Helper Functions
# -----------------------------
def get_current_user():
    user_id = session.get('user_id')

    if user_id is None:
        return None

    user = User.query.filter_by(id=user_id).first()
    return user

def login_required(route_function):
    @wraps(route_function)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'error')
            return redirect(url_for('login'))
        return route_function(*args, **kwargs)
    return wrapper


# -----------------------------
# Message Generation Functions
# -----------------------------
def generate_message_1(lead):
    return f"""
Hello {lead.name.title()},

Thank you for your inquiry about finding a {lead.property_type} in {lead.location} with a budget of {lead.budget}. My name is {lead.agent_name}, and I'm a real estate agent specializing in properties in Lagos.

I am reviewing your request and will get back to you shortly with some initial options that match your criteria.

In the meantime, you can view some of our available properties on our website: [Your Website Link]

Best regards,
{lead.agent_name}
"""


def generate_message_2(lead):
    return f"""
Hello {lead.name.title()},

This is {lead.agent_name} following up on your property inquiry. I hope you had a chance to look at the initial options I sent over.

I would love to schedule a brief 10-15 minute call to better understand your needs and discuss how I can help you find the perfect {lead.property_type} in {lead.location}.

Are you available for a quick chat tomorrow around 11am or 2pm?

Best regards,
{lead.agent_name}
"""


def generate_call_script(lead):
    return f"""
Lead Name: {lead.name.title()}
Phone: {lead.phone}
Inquiry: {lead.property_type} in {lead.location}, Budget: {lead.budget}

Opener:
Hi {lead.name.title()}, this is {lead.agent_name} calling from [Your Agency Name]. I'm following up on your inquiry about a {lead.property_type} in {lead.location}. Is now a good time to talk for a few minutes?

Discovery Questions:
1. To make sure I find the best options for you, could you tell me more about what you're looking for?
2. You mentioned a budget of {lead.budget}. Is this flexible for the right property?
3. What is your timeline for moving? You mentioned {lead.timeline}.
4. Have you seen any other properties that you liked?

Next Steps:
Thank you for sharing that with me. Based on what you've told me, I have a few properties in mind that I think you'll love. I will prepare a personalized list and send it to you via WhatsApp shortly.

Closing:
I look forward to helping you find your new property. Have a great day.
"""


# -----------------------------
# Auth Routes
# -----------------------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')

        if not full_name or not email or not password or not confirm_password:
            flash('Please fill out all fields.', 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return redirect(url_for('register'))

        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('An account with that email already exists.', 'error')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)

        new_user = User(
            full_name=full_name,
            email=email,
            password_hash=hashed_password
        )

        db.session.add(new_user)
        db.session.commit()

        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash('Please enter your email and password.', 'error')
            return redirect(url_for('login'))

        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password_hash, password):
            flash('Invalid email or password.', 'error')
            return redirect(url_for('login'))

        session['user_id'] = user.id
        session['user_name'] = user.full_name

        flash('You are now logged in.', 'success')
        return redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('login'))


# -----------------------------
# Lead Routes
# -----------------------------
@app.route('/')
@login_required
def index():
    current_user = get_current_user()
    return render_template('index.html', current_user=current_user)


@app.route('/add_lead', methods=['POST'])
@login_required
def add_lead():
    current_user = get_current_user()

    if current_user is None:
        flash('Session expired. Please log in again.', 'error')
        return redirect(url_for('login'))

    agent_name = request.form.get('agent_name')
    name = request.form.get('name')
    phone = request.form.get('phone')
    budget = request.form.get('budget')
    location = request.form.get('location')
    property_type = request.form.get('property_type')
    timeline = request.form.get('timeline')
    notes = request.form.get('notes')

    # DEBUG (temporary)
    print("DEBUG DATA:")
    print(agent_name, name, phone, budget, location, property_type, timeline)

    # Validation
    if not all([agent_name, name, phone, budget, location, property_type, timeline]):
        flash('Please fill out all required fields.', 'error')
        return redirect(url_for('index'))

    # Save to DB
    new_lead = Lead(
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

    db.session.add(new_lead)
    db.session.commit()

    return redirect(url_for('result', lead_id=new_lead.id))

@app.route('/result/<int:lead_id>')
@login_required
def result(lead_id):
    current_user = get_current_user()

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()
    if not lead:
        flash('Lead not found.', 'error')
        return redirect(url_for('leads'))

    message1 = generate_message_1(lead)
    message2 = generate_message_2(lead)
    call_script = generate_call_script(lead)

    return render_template(
        'result.html',
        lead=lead,
        message1=message1,
        message2=message2,
        call_script=call_script
    )


@app.route('/leads')
@login_required
def leads():
    current_user = get_current_user()
    all_leads = Lead.query.filter_by(user_id=current_user.id).order_by(Lead.date_added.desc()).all()
    return render_template('leads.html', leads=all_leads, current_user=current_user)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))