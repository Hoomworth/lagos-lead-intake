import os
import datetime
from functools import wraps

from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text, inspect
from openai import OpenAI

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'super-secret-key-123')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
if app.config['SQLALCHEMY_DATABASE_URI'] and app.config['SQLALCHEMY_DATABASE_URI'].startswith("postgres://"):
    app.config['SQLALCHEMY_DATABASE_URI'] = app.config['SQLALCHEMY_DATABASE_URI'].replace("postgres://", "postgresql://", 1)
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=30)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

api_key = os.environ.get("OPENAI_API_KEY")

if not api_key:
    print("ERROR: OPENAI_API_KEY not set")
    api_key = "dummy-key-to-prevent-crash-during-migrations"

client = OpenAI(api_key=api_key)

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# -----------------------------
# Database Models
# -----------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    credits = db.Column(db.Integer, default=5)

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
    contacted_at = db.Column(db.DateTime, nullable=True)
    closed_at = db.Column(db.DateTime, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)


# -----------------------------
# Helpers
# -----------------------------
def analyze_lead(lead):
    score = 0

    # Timeline
    timeline = (lead.timeline or "").lower()
    if "urgent" in timeline:
        score += 30
        intent = "Urgent Buyer"
    elif "month" in timeline:
        score += 20
        intent = "Active Buyer"
    else:
        score += 10
        intent = "Exploring"

    # Budget
    try:
        budget_value = int(''.join(filter(str.isdigit, lead.budget)))
        if budget_value > 50000000:
            score += 30
        elif budget_value > 20000000:
            score += 20
        else:
            score += 10
    except:
        score += 10

    # Property Type
    if "land" in (lead.property_type or "").lower():
        score += 10
    else:
        score += 20

    # Final classification
    if score >= 70:
        quality = "Hot"
        action = "Call immediately"
        timing = "Immediate"
    elif score >= 40:
        quality = "Warm"
        action = "Send WhatsApp first"
        timing = "Soon"
    else:
        quality = "Cold"
        action = "Nurture with follow-up message"
        timing = "Later"

    objections = "May worry about price or location fit"

    return {
        "score": score,
        "quality": quality,
        "intent": intent,
        "action": action,
        "timing": timing,
        "risk": objections
    }

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

Thank you for reaching out regarding your interest in acquiring a {lead.property_type} in {lead.location} within your specified budget of {lead.budget}. I have received your details and I am thrilled to assist you in finding the perfect match.

My name is {lead.agent_name}, and I am a specialized real estate consultant focusing on verified, premium listings within this specific area. I have carefully noted your requirements, and my team is already checking our exclusive inventory for options that perfectly align with your vision.

The real estate market in {lead.location} is highly dynamic right now, offering some fantastic opportunities whether you are looking for long-term appreciation, rental yield, or a beautiful place to call home. Having the right insights will give you a significant advantage.

To ensure I do not overwhelm you with the wrong listings, I would love to quickly confirm a few finer details. Are you primarily buying for personal use or investment? Do you prefer brand-new modern builds or something with room for custom renovations?

Additionally, how important is proximity to major roads, and is your budget slightly flexible if we find an off-market property that truly checks every single box on your wishlist?

Once you provide these quick details, I will handpick 2 to 3 of the most solid, verified options and send them over for your review. I look forward to working closely with you to secure the best possible deal.

Looking forward to your response.

Best regards,  
{lead.agent_name}
"""


def generate_message_2(lead):
    return f"""
Hello {lead.name.title()},

Just checking back with you regarding your request for a {lead.property_type} in {lead.location}.

I have shortlisted a few options that could match what you’re looking for, but I need a bit more clarity before sending them so I don’t waste your time.

Are you still actively searching or just exploring options for now?

Also, would you prefer:
- A quick WhatsApp walkthrough
- Or a short call to explain the best available options

Let me know what works best for you.

Best regards,  
{lead.agent_name}
"""


def generate_call_script(lead):
    return f"""
LEAD SUMMARY
Name: {lead.name}
Phone: {lead.phone}
Interest: {lead.property_type} in {lead.location}
Budget: {lead.budget}
Timeline: {lead.timeline}

[OPENING - PARAGRAPH 1]
Hello {lead.name}, my name is {lead.agent_name} calling from Hoomworth CRM. I am reaching out regarding the inquiry you made about acquiring a {lead.property_type} in {lead.location}. Am I catching you at a good time to speak for just two minutes?

[CONTEXT - PARAGRAPH 2]
Great! The reason for my call today is that I’ve personally reviewed your request, and I wanted to make sure I introduce myself. Our agency specializes in securing premium properties in that exact neighborhood, and I want to ensure we find exactly what you need.

[QUALIFYING - PARAGRAPH 3]
To help me filter out the noise and only present you with the best matches, I have a quick question: Are you looking to purchase this property primarily for your own personal use, or is this going to be an investment for rental income?

[TIMELINE & BUDGET - PARAGRAPH 4]
Understood. I also see you mentioned a budget of {lead.budget} and a timeline of {lead.timeline}. If we happen to find a property that completely blows you away but sits just slightly above that budget, is there any flexibility, or is that a hard ceiling?

[POSITIONING - PARAGRAPH 5]
That makes perfect sense. Based on everything you’ve shared with me right now, I actually have two specific properties in mind that recently became available. They haven't been heavily marketed yet, and they align beautifully with your criteria.

[CLOSING - PARAGRAPH 6]
Here is my proposed next step: I am going to compile the details, photos, and exact locations of these properties and send them directly to your WhatsApp. Please review them at your convenience, and if one catches your eye, we can immediately schedule a private viewing. Does that sound like a fair plan to you?
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
        session.permanent = True

        if user.credits is None:
            user.credits = 5
            db.session.commit()
        

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
        return redirect(url_for('leads'))

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
    session['last_lead_id'] = lead_id
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

    ai_whatsapp = session.pop('ai_whatsapp', None)
    ai_sms = session.pop('ai_sms', None)
    ai_email_subject = session.pop('ai_email_subject', None)
    ai_email_body = session.pop('ai_email_body', None)
    analysis = session.pop('ai_analysis', None)
    ai_followup = session.pop('ai_followup', None)
    ai_script = session.pop('ai_script', None)

    message2 = ai_followup if ai_followup else None
    call_script = ai_script if ai_script else None

    # fallback if AI not used
    if not analysis:
        analysis = analyze_lead(lead)


    return render_template(
        'result.html',
        lead=lead,
        current_user=current_user,
        analysis=analysis,
        message1=ai_whatsapp if ai_whatsapp else generate_message_1(lead),
        is_ai_message1=bool(ai_whatsapp),
        message2=message2,
        call_script=call_script,
        phone=phone,

        sms=ai_sms,
        email_subject=ai_email_subject,
        email_body=ai_email_body,


    )


@app.route('/leads')
@login_required
def leads():
    current_user = get_current_user()

    if not current_user:
        return redirect(url_for('login'))

    # ✅ GET FILTER FROM URL
    status = request.args.get('status')
    search = request.args.get('search')

    # ✅ BASE QUERY
    query = Lead.query.filter_by(user_id=current_user.id)

    # ✅ APPLY STATUS FILTER
    if status:
        query = query.filter_by(status=status)

    # ✅ APPLY SEARCH FILTER
    if search:
        query = query.filter(
            (Lead.name.ilike(f"%{search}%")) |
            (Lead.phone.ilike(f"%{search}%"))
        )

    # ✅ FINAL DATA
    all_leads = query.all()

    # ADD THIS
    leads_with_analysis = []

    for lead in all_leads:
        analysis = analyze_lead(lead)
        leads_with_analysis.append({
            "lead": lead,
            "analysis": analysis
        })

    # Sort the leads outside of the loop for correctness and performance
    priority_order = {
            "Hot": 1,
            "Warm": 2,
            "Cold": 3
    }
    leads_with_analysis.sort(
        key=lambda x: (
            priority_order.get(x["analysis"]["quality"], 4),
                -x["lead"].date_added.timestamp() if x["lead"].date_added else 0
            )
    )

    # ✅ COUNTS
    total_leads = Lead.query.filter_by(user_id=current_user.id).count()
    new_leads = Lead.query.filter_by(user_id=current_user.id, status='New').count()
    contacted_leads = Lead.query.filter_by(user_id=current_user.id, status='Contacted').count()
    closed_leads = Lead.query.filter_by(user_id=current_user.id, status='Closed').count()

    print("USER CREDITS:", current_user.credits)

    return render_template(
        'leads.html',
        leads=leads_with_analysis,
        current_user=current_user,
        total_leads=total_leads,
        new_leads=new_leads,
        contacted_leads=contacted_leads,
        closed_leads=closed_leads,
        credits=current_user.credits
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
        if not lead.closed_at:
            lead.closed_at = datetime.datetime.utcnow()
        db.session.commit()

    return redirect(url_for('leads'))    


@app.route('/mark_contacted/<int:lead_id>', methods=['POST'])
@login_required
def mark_contacted(lead_id):
    current_user = get_current_user()

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    if lead:
        lead.status = 'Contacted'
        if not lead.contacted_at:
            lead.contacted_at = datetime.datetime.utcnow()
        db.session.commit()

    return '', 200


@app.route('/generate_ai/<int:lead_id>')
@login_required
def generate_ai(lead_id):
    current_user = get_current_user()

    if current_user.credits <= 0:
        flash("No credits left. Please upgrade.", "error")
        return redirect(url_for('result', lead_id=lead_id))

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    if not lead:
        return redirect(url_for('leads'))

    prompt = f"""
You are a professional Lagos real estate sales expert.

Analyze this lead and generate outreach messages.

Lead Details:
Name: {lead.name}
Location: {lead.location}
Budget: {lead.budget}
Property Type: {lead.property_type}
Timeline: {lead.timeline}

Return ONLY valid JSON in this format:

{{
  "quality": "Hot/Warm/Cold",
  "intent": "Type of buyer",
  "score": number between 1-100,
  "action": "Best next step",
  "timing": "When to follow up",
  "objection": "Likely concern",

  "whatsapp": "Write a highly detailed, 6-paragraph WhatsApp follow-up. Separate each paragraph with a double line break (\\n\\n). Do NOT write less than 6 complete paragraphs.",
  "sms": "Short SMS under 160 characters",
  "email_subject": "Email subject line",
  "email_body": "Write a highly detailed, 6-paragraph professional email. Separate each paragraph with a double line break (\\n\\n) for perfect spacing. Do NOT write less than 6 complete paragraphs."
}}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "user", "content": prompt}
            ]
        )

        import json
        ai_data = json.loads(response.choices[0].message.content)

        # Save to session
        session['ai_whatsapp'] = ai_data.get("whatsapp")
        session['ai_sms'] = ai_data.get("sms")
        session['ai_email_subject'] = ai_data.get("email_subject")
        session['ai_email_body'] = ai_data.get("email_body")

        session['ai_analysis'] = {
            "quality": ai_data.get("quality", "Warm"),
            "intent": ai_data.get("intent", "Buyer"),
            "score": ai_data.get("score", 50),
            "action": ai_data.get("action", "Follow up"),
            "timing": ai_data.get("timing", "Soon"),
            "risk": ai_data.get("objection", "No major concern")
        }

        # deduct credit
        current_user.credits -= 1
        db.session.commit()

        flash("AI analysis generated!", "success")

    except Exception as e:
        print("AI ERROR:", e)
        flash("AI failed. Try again.", "error")

    return redirect(url_for('result', lead_id=lead.id))


@app.route('/generate_first_contact/<int:lead_id>')
@login_required
def generate_first_contact(lead_id):
    current_user = get_current_user()

    if current_user.credits <= 0:
        flash("No credits left.", "error")
        return redirect(url_for('result', lead_id=lead_id))

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    prompt = f"Write a highly detailed, 6-paragraph WhatsApp first-contact message for a real estate client named {lead.name} inquiring about a {lead.property_type} in {lead.location} with a budget of {lead.budget}. Separate each paragraph with a double line break (\\n\\n). Do NOT write less than 6 complete paragraphs."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    session['ai_whatsapp'] = response.choices[0].message.content

    current_user.credits -= 1
    db.session.commit()

    return redirect(url_for('result', lead_id=lead_id))


@app.route('/generate_sms/<int:lead_id>')
@login_required
def generate_sms(lead_id):
    current_user = get_current_user()

    if current_user.credits <= 0:
        flash("No credits left.", "error")
        return redirect(url_for('result', lead_id=lead_id))

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    prompt = f"Generate a short SMS under 160 characters for this lead: {lead.name}, {lead.property_type} in {lead.location}, budget {lead.budget}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    sms = response.choices[0].message.content

    session['ai_sms'] = sms

    current_user.credits -= 1
    db.session.commit()

    return redirect(url_for('result', lead_id=lead_id))


@app.route('/generate_email/<int:lead_id>')
@login_required
def generate_email(lead_id):
    current_user = get_current_user()

    if current_user.credits <= 0:
        flash("No credits left.", "error")
        return redirect(url_for('result', lead_id=lead_id))

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    prompt = f"Write a highly detailed, professional real estate email for {lead.name} about a {lead.property_type} in {lead.location}, budget {lead.budget}. You MUST write exactly 6 complete paragraphs. Separate each paragraph with a double line break (\\n\\n) for perfect spacing and alignment."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    email_body = response.choices[0].message.content

    session['ai_email_subject'] = f"{lead.property_type} in {lead.location}"
    session['ai_email_body'] = email_body

    current_user.credits -= 1
    db.session.commit()

    return redirect(url_for('result', lead_id=lead_id))


@app.route('/generate_followup/<int:lead_id>')
@login_required
def generate_followup(lead_id):
    current_user = get_current_user()

    if current_user.credits <= 0:
        flash("No credits left.", "error")
        return redirect(url_for('result', lead_id=lead_id))

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    prompt = f"Write a highly detailed follow-up WhatsApp message for a real estate client named {lead.name} who showed interest in a {lead.property_type} in {lead.location}. You MUST write exactly 6 complete paragraphs. Separate each paragraph with a double line break (\\n\\n)."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    followup = response.choices[0].message.content

    session['ai_followup'] = followup

    current_user.credits -= 1
    db.session.commit()

    return redirect(url_for('result', lead_id=lead_id))


@app.route('/generate_script/<int:lead_id>')
@login_required
def generate_script(lead_id):
    current_user = get_current_user()

    if current_user.credits <= 0:
        flash("No credits left.", "error")
        return redirect(url_for('result', lead_id=lead_id))

    lead = Lead.query.filter_by(id=lead_id, user_id=current_user.id).first()

    prompt = f"Write a comprehensive phone call script for a real estate agent speaking to {lead.name} about a {lead.property_type} in {lead.location}. You MUST write exactly 6 complete paragraphs. Separate each paragraph with a double line break (\\n\\n) to ensure proper spacing."

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )

    script = response.choices[0].message.content

    session['ai_script'] = script

    current_user.credits -= 1
    db.session.commit()

    return redirect(url_for('result', lead_id=lead_id))



@app.route('/insights')
@login_required
def insights():
    current_user = get_current_user()
    if not current_user:
        return redirect(url_for('login'))

    # Fetch all leads for the current user
    leads = Lead.query.filter_by(user_id=current_user.id).all()

    # Calculate status counts
    total_leads = len(leads)
    new_leads = sum(1 for l in leads if l.status == 'New')
    contacted_leads = sum(1 for l in leads if l.status == 'Contacted')
    closed_leads = sum(1 for l in leads if l.status == 'Closed')

    # Calculate quality counts
    hot_leads = warm_leads = cold_leads = 0
    response_times = []
    close_times = []
    for lead in leads:
        analysis = analyze_lead(lead)
        if analysis['quality'] == 'Hot':
            hot_leads += 1
        elif analysis['quality'] == 'Warm':
            warm_leads += 1
        else:
            cold_leads += 1
            
        if lead.contacted_at and lead.date_added:
            diff = (lead.contacted_at - lead.date_added).total_seconds()
            if diff >= 0:
                response_times.append(diff)
                
        if lead.closed_at and lead.date_added:
            diff = (lead.closed_at - lead.date_added).total_seconds()
            if diff >= 0:
                close_times.append(diff)
            
    # Calculate Conversion Rate
    conversion_rate = round((closed_leads / total_leads * 100), 1) if total_leads > 0 else 0

    # Calculate Averages (Response Time & Lead Close Days)
    avg_response_time = 'N/A'
    if response_times:
        avg_sec = sum(response_times) / len(response_times)
        if avg_sec < 3600:
            avg_response_time = f"{int(avg_sec // 60)} mins"
        elif avg_sec < 86400:
            avg_response_time = f"{round(avg_sec / 3600, 1)} hours"
        else:
            avg_response_time = f"{round(avg_sec / 86400, 1)} days"
            
    lead_close_days = 'N/A'
    if close_times:
        avg_sec = sum(close_times) / len(close_times)
        lead_close_days = f"{round(avg_sec / 86400, 1)} days"

    return render_template('insights.html',
                           total_leads=total_leads, new_leads=new_leads,
                           contacted_leads=contacted_leads, closed_leads=closed_leads,
                           hot_leads=hot_leads, warm_leads=warm_leads, cold_leads=cold_leads,
                           conversion_rate=conversion_rate,
                           avg_response_time=avg_response_time,
                           lead_close_days=lead_close_days)
   

@app.route('/prospect')
@login_required
def open_prospect():
    lead_id = session.get('last_lead_id')

    # If no last lead, get latest lead from DB
    if not lead_id:
        current_user = get_current_user()

        last_lead = Lead.query.filter_by(user_id=current_user.id)\
            .order_by(Lead.date_added.desc())\
            .first()

        if not last_lead:
            return redirect(url_for('leads'))

        return redirect(url_for('result', lead_id=last_lead.id))

    return redirect(url_for('result', lead_id=lead_id))


# -----------------------------
# RUN
# -----------------------------
with app.app_context():
    db.create_all()

    # Auto-upgrade database specifically for Render production
    try:
        inspector = inspect(db.engine)
        if 'lead' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('lead')]
            if 'contacted_at' not in columns:
                db.session.execute(text('ALTER TABLE lead ADD COLUMN contacted_at TIMESTAMP'))
                db.session.commit()
                print("Successfully added contacted_at to Render database.")
            if 'closed_at' not in columns:
                db.session.execute(text('ALTER TABLE lead ADD COLUMN closed_at TIMESTAMP'))
                db.session.commit()
                print("Successfully added closed_at to Render database.")
    except Exception as e:
        print(f"Migration check skipped: {e}")
        db.session.rollback()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))