import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.utils import secure_filename
from functools import wraps
from datetime import datetime # <-- ADD THIS LINE
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from redis import Redis
from rq import Queue
from tasks import run_agentic_workflow 
import os
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify # <-- Add jsonify
from collections import Counter # <-- Add Counter
import json # <-- Add json
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory
from models import db, User, Application, Job
from config import Config
from agents import (
    agent_1_parse_resume,
    agent_2_evaluate_resume,
    agent_3_write_job_post,
    agent_4_send_email
)

# --- App Initialization ---

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'login'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    with app.app_context():
        # Create database tables if they don't exist
        db.create_all()
        
        # Create the default admin user if it doesn't exist
        if not User.query.filter_by(email='admin').first():
            print("Creating default admin user...")
            admin = User(email='admin', name='Admin User', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("Admin user created with email 'admin' and password 'admin123'")

    return app

app = create_app()

# --- Helper Decorators ---

def admin_required(f):
    """Custom decorator to restrict access to admin users."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin:
            flash('You do not have permission to access this page.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# --- Auth Routes (Login, Register, Logout) ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        # Special case for admin login as per project spec
        if email == 'admin' and password == 'admin123':
            user = User.query.filter_by(email='admin').first()
            if user:
                login_user(user)
                flash('Admin login successful!', 'success')
                return redirect(url_for('dashboard'))

        # Normal user login
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('dashboard'))
        else:
            flash('Login failed. Check email and password.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        password = request.form.get('password')

        if User.query.filter_by(email=email).first():
            flash('Email address already registered.', 'warning')
            return redirect(url_for('register'))

        new_user = User(email=email, name=name)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()

        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

# --- Core App Routes ---

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login')) # <-- Change to this
@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.is_admin:
        # Admin Dashboard Logic
        try:
            # Get filters
            status_filter = request.args.get('status', 'all')
            sort_by = request.args.get('sort', 'date_desc')

            query = Application.query.join(User).join(Job)

            if status_filter != 'all':
                query = query.filter(Application.status == status_filter)

            if sort_by == 'score_desc':
                query = query.order_by(Application.ai_score.desc())
            else:
                query = query.order_by(Application.created_at.desc())

            applications = query.all()
            
            # Dashboard stats
            stats = {
                'total': Application.query.count(),
                'shortlisted': Application.query.filter_by(status='Shortlisted').count(),
                'rejected': Application.query.filter_by(status='Rejected').count(),
                'pending': Application.query.filter_by(status='Pending').count(),
                'review': Application.query.filter_by(status='Needs Review').count()
            }
            
            return render_template('dashboard_admin.html', applications=applications, stats=stats)
        
        except Exception as e:
            flash(f"Error loading admin dashboard: {e}", "danger")
            return render_template('dashboard_admin.html', applications=[], stats={}, error=str(e))

    # ... inside your dashboard() function ...
    else:
    # User Dashboard Logic
     applications = Application.query.filter_by(user_id=current_user.id).order_by(Application.created_at.desc()).all()
    # --- NEW: Fetch all jobs ---
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('dashboard_user.html', applications=applications, jobs=jobs)

# --- USER PANEL ROUTES ---

@app.route('/upload_resume', methods=['POST'])
@login_required
def upload_resume():
    if 'resume' not in request.files:
        flash('No file part', 'danger')
        return redirect(url_for('dashboard'))

    file = request.files['resume']
    if file.filename == '' or not file.filename.endswith('.pdf'):
        flash('Valid PDF file is required', 'danger')
        return redirect(url_for('dashboard'))

    filename = secure_filename(f"{current_user.id}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.pdf")
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    file.save(filepath)

   # ... inside your upload_resume() function ...
    try:
    # --- NEW: Get the selected job_id from the form ---
        job_id = request.form.get('job_id')
        if not job_id:
            flash('You must select a job to apply for.', 'danger')
            return redirect(url_for('dashboard'))
    # --- END NEW ---

    # 1. Create the application entry in the database (with status "Pending")
        new_application = Application(
            user_id=current_user.id,
            resume_filename=filename,
            status='Pending', # Set status to Pending
            job_id=job_id  # --- NEW: Save the job_id ---
        )
        db.session.add(new_application)
        db.session.commit()

    # 2. Enqueue the task to run in the background
    # We pass the new application's ID and job_id to the worker
        q.enqueue(run_agentic_workflow, new_application.id, job_id)

        flash('Resume uploaded and is now being analyzed by our AI. Refresh in a moment to see results.', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'An error occurred: {e}', 'danger')

    return redirect(url_for('dashboard'))

# --- ADMIN PANEL ROUTES ---

@app.route('/admin/update_status/<int:app_id>', methods=['POST'])
@login_required
@admin_required
def update_status(app_id):
    application = Application.query.get_or_404(app_id)
    new_status = request.form.get('status')
    
    if new_status in ['Shortlisted', 'Rejected', 'Needs Review']:
        application.status = new_status
        db.session.commit()
        
        # Trigger Email Notifier Agent
        if request.form.get('send_email') == 'on':
            email_sent = agent_4_send_email(
                candidate_name=application.applicant.name,
                candidate_email=application.applicant.email,
                status=new_status
            )
            if email_sent:
                flash(f"Status updated to {new_status} and email sent.", 'success')
            else:
                flash(f"Status updated, but email sending failed. Check logs.", 'warning')
        else:
            flash(f"Status updated to {new_status}.", 'success')
            
    return redirect(url_for('dashboard'))


@app.route('/admin/generate_job_post', methods=['POST'])
@login_required
@admin_required
def generate_job_post():
    job_title = request.form.get('job_title')
    skills = request.form.get('skills')
    description = request.form.get('description')
    
    try:
        # Trigger Job Post Writer Agent
        job_post = agent_3_write_job_post(job_title, skills, description)

    # --- NEW: Save the job to the database ---
        new_job = Job(
        title=job_title,
        key_skills=skills,
        description=job_post
    )
        db.session.add(new_job)
        db.session.commit()        
        # We need to re-render the admin dashboard, so we fetch data again
        stats = {
            'total': Application.query.count(),
            'shortlisted': Application.query.filter_by(status='Shortlisted').count(),
            'rejected': Application.query.filter_by(status='Rejected').count(),
            'pending': Application.query.filter_by(status='Pending').count(),
            'review': Application.query.filter_by(status='Needs Review').count()        }
        applications = Application.query.join(User).order_by(Application.created_at.desc()).all()
        
        flash('Job post generated successfully!', 'success')
        return render_template('dashboard_admin.html', applications=applications, stats=stats, generated_post=job_post)
        
    except Exception as e:
        flash(f'Error generating job post: {e}', 'danger')
        return redirect(url_for('dashboard'))


@app.route('/uploads/resumes/<filename>')
@login_required
def view_resume(filename):
    """Allows admin to view uploaded resumes."""
    if not current_user.is_admin:
        flash('Access denied.', 'danger')
        return redirect(url_for('dashboard'))
        
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)
@app.route('/api/skill-stats')
@login_required
@admin_required
def skill_stats():
    """
    API endpoint to provide skill statistics for the admin dashboard.
    """
    try:
        applications = Application.query.filter(Application.parsed_skills.isnot(None)).all()

        all_skills = []
        for app in applications:
            try:
                # parsed_skills is stored as a JSON string, so we load it
                skills = json.loads(app.parsed_skills)
                if skills:
                    # Standardize to lowercase to avoid "Python" and "python" being different
                    all_skills.extend([skill.lower() for skill in skills])
            except (json.JSONDecodeError, TypeError):
                continue # Skip if skills are empty or malformed

        # Count the occurrences of each skill
        skill_counts = Counter(all_skills)

        # Get the top 10 most common skills
        top_10_skills = skill_counts.most_common(10)

        # Prepare data for Chart.js
        labels = [skill[0] for skill in top_10_skills]
        data = [skill[1] for skill in top_10_skills]

        return jsonify({'labels': labels, 'data': data})

    except Exception as e:
        print(f"Error in /api/skill-stats: {e}")
        return jsonify({'error': str(e)}), 500
# --- Main Run ---
if __name__ == '__main__':
    app.run(debug=True)