
import os
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with a real secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///leads.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Define the Lead model for the database
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

    def __repr__(self):
        return f'<Lead {self.name}>'

# --- Message Generation Functions ---
def generate_message_1(lead):
    """Generates the initial WhatsApp reply."""
    return f"""
Hello {lead.name},

Thank you for your inquiry about finding a {lead.property_type} in {lead.location} with a budget of {lead.budget}. My name is {lead.agent_name}, and I'm a real estate agent specializing in properties in Lagos.

I am reviewing your request and will get back to you shortly with some initial options that match your criteria.

In the meantime, you can view some of our available properties on our website: [Your Website Link]

Best regards,
{lead.agent_name}
"""

def generate_message_2(lead):
    """Generates the 24-hour follow-up message."""
    return f"""
Hello {lead.name},

This is {lead.agent_name} following up on your property inquiry. I hope you had a chance to look at the initial options I sent over.

I would love to schedule a brief 10-15 minute call to better understand your needs and discuss how I can help you find the perfect {lead.property_type} in {lead.location}.

Are you available for a quick chat tomorrow around [Suggest a Time]?

Best regards,
{lead.agent_name}
"""

def generate_call_script(lead):
    """Generates a short call script."""
    return f"""
**Lead Name:** {lead.name}
**Phone:** {lead.phone}
**Inquiry:** {lead.property_type} in {lead.location}, Budget: {lead.budget}

---

**Opener:**
"Hi {lead.name}, this is {lead.agent_name} calling from [Your Agency Name]. I'm following up on your WhatsApp inquiry about a {lead.property_type} in {lead.location}. Is now a good time to talk for a few minutes?"

**Discovery Questions:**
1. "To make sure I find the best options for you, could you tell me a bit more about what you're looking for? Are there any specific features that are must-haves?"
2. "You mentioned a budget of {lead.budget}. Is this flexible for the right property?"
3. "What is your timeline for moving? Are you looking to move in the next {lead.timeline}?"
4. "Have you seen any other properties that you liked? What stood out about them?"

**Next Steps:**
"Thank you for sharing that with me. Based on what you've told me, I have a few properties in mind that I think you'll love. I will prepare a personalized list and send it to you via WhatsApp shortly. From there, we can schedule some viewings."

**Closing:**
"I look forward to helping you find your new property. Have a great day!"
"""

@app.route('/')
def index():
    """Renders the lead intake form."""
    return render_template('index.html')

@app.route('/add_lead', methods=['POST'])
def add_lead():
    """Handles form submission, saves the lead, and shows the results page."""
    agent_name = request.form.get('agent_name')
    name = request.form.get('name')
    phone = request.form.get('phone')
    budget = request.form.get('budget')
    location = request.form.get('location')
    property_type = request.form.get('property_type')
    timeline = request.form.get('timeline')
    notes = request.form.get('notes')

    # Basic validation
    if not all([agent_name, name, phone, budget, location, property_type, timeline]):
        flash('Please fill out all required fields.', 'error')
        return redirect(url_for('index'))

    try:
        new_lead = Lead(
            agent_name=agent_name,
            name=name,
            phone=phone,
            budget=budget,
            location=location,
            property_type=property_type,
            timeline=timeline,
            notes=notes
        )
        db.session.add(new_lead)
        db.session.commit()
        flash('Lead saved successfully!', 'success')
        return redirect(url_for('result', lead_id=new_lead.id))
    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {e}', 'error')
        return redirect(url_for('index'))

@app.route('/result/<int:lead_id>')
def result(lead_id):
    """Displays the generated messages for a specific lead."""
    lead = Lead.query.get_or_404(lead_id)
    message1 = generate_message_1(lead)
    message2 = generate_message_2(lead)
    call_script = generate_call_script(lead)
    return render_template('result.html', lead=lead, message1=message1, message2=message2, call_script=call_script)

@app.route('/leads')
def leads():
    """Displays the dashboard with a list of all saved leads."""
    all_leads = Lead.query.order_by(Lead.date_added.desc()).all()
    return render_template('leads.html', leads=all_leads)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
