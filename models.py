from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

# Initialize database
db = SQLAlchemy()

class User(UserMixin, db.Model):
    """
    User model for both Applicants and Admins.
    """
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    # Relationship: A user can have many applications
    applications = db.relationship('Application', backref='applicant', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'

# --- NEW MODEL ---
class Job(db.Model):
    """
    Job model to store postings created by the admin.
    """
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False) # The AI-generated post
    key_skills = db.Column(db.String(300)) # The skills admin entered
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationship: A job can have many applications
    applications = db.relationship('Application', backref='job', lazy=True)

    def __repr__(self):
        return f'<Job {self.title}>'
# --- END NEW MODEL ---

class Application(db.Model):
    """
    Application model to store resume data and AI analysis.
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # --- MODIFIED: Link to the Job model ---
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=True) # nullable=True to not break old data
    
    # File and Text
    resume_filename = db.Column(db.String(300))
    resume_text = db.Column(db.Text)
    
    # Application Status
    status = db.Column(db.String(50), default='Pending') # Pending, Shortlisted, Rejected, Needs Review
    
    # AI Evaluation
    ai_score = db.Column(db.Integer, default=0)
    ai_feedback = db.Column(db.Text)
    skill_match = db.Column(db.Integer, default=0)
    experience_relevance = db.Column(db.Integer, default=0)
    
    # Parsed Data (stored as JSON string)
    parsed_skills = db.Column(db.Text)
    parsed_experience_years = db.Column(db.Integer)
    parsed_summary = db.Column(db.Text)
    
    # Timestamp
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Application {self.id} by User {self.user_id}>'