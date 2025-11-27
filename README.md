# Agricruit - AI-Powered Recruitment Platform

Agricruit is a Flask-based web application designed to streamline the recruitment process using AI. It allows candidates to apply for jobs by uploading their resumes and provides an admin interface for recruiters to manage applications, evaluate candidates with AI-driven insights, and generate job postings.

## Project Structure

The project is organized into the following directories and files:

- **`app.py`**: The main Flask application file. It contains the application factory, defines routes, and handles the core logic of the web application.
- **`models.py`**: Defines the database schema using SQLAlchemy. It includes models for `User`, `Job`, and `Application`.
- **`config.py`**: Contains the configuration for the Flask application, including secret keys, database URI, and other settings.
- **`agents.py`**: This file likely contains the core AI logic, with functions that interact with an AI model (e.g., Groq) to parse resumes, evaluate candidates, and generate job descriptions.
- **`tasks.py`**: This file is used to define background tasks that can be run asynchronously, such as processing a resume after it has been uploaded. This is often used with a task queue like Redis Queue (RQ).
- **`requirements.txt`**: A list of all the Python packages required to run the project.
- **`static/`**: This directory contains static files like CSS, JavaScript, and images.
  - **`style.css`**: The main stylesheet for the application.
- **`templates/`**: This directory contains the HTML templates for the application.
  - **`base.html`**: The base template that other templates extend.
  - **`login.html`**: The login page.
  - **`register.html`**: The user registration page.
  - **`dashboard_user.html`**: The dashboard for regular users (candidates).
  - **`dashboard_admin.html`**: The dashboard for admin users (recruiters).
- **`uploads/`**: This directory is used to store uploaded files, such as resumes.
- **`instance/`**: This directory is often used to store instance-specific data, such as the SQLite database file.

## Core Functionality

### User Authentication

- Users can register for an account or log in.
- There is a default admin user with the credentials `admin` and `admin123`.
- The `flask_login` extension is used to manage user sessions.

### Candidate Dashboard

- Candidates can view a list of available jobs.
- They can upload their resume (in PDF format) to apply for a job.
- After uploading a resume, the application status is set to "Pending" and an AI-powered analysis is triggered in the background.

### Admin Dashboard

- Admins can view all applications from all users.
- They can filter applications by status (e.g., "Shortlisted," "Rejected," "Pending").
- They can view AI-generated scores and feedback for each application.
- Admins can manually update the status of an application.
- They can generate new job postings by providing a title, skills, and a brief description. The AI then generates a full job post.

### AI Integration

- The application uses an AI model (likely a Large Language Model) to perform several tasks:
  - **Resume Parsing**: Extracts key information from resumes, such as skills and years of experience.
  - **Candidate Evaluation**: Scores candidates based on how well their resume matches the job requirements.
  - **Job Post Generation**: Creates detailed job descriptions from a few keywords.

### Background Tasks

- The application uses Redis Queue (RQ) to run long-running tasks in the background, such as the AI analysis of a resume. This prevents the web application from becoming unresponsive while waiting for the AI to finish.

## How to Run the Project

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Set Up Environment Variables**:
   - Create a `.env` file in the root of the project.
   - Add the following variables to the `.env` file:
     ```
     SECRET_KEY=your-secret-key
     GROQ_API_KEY=your-groq-api-key
     ```

3. **Run the Application**:
   ```bash
   flask run
   ```

4. **Access the Application**:
   - Open your web browser and go to `http://127.0.0.1:5000`.
   - You can log in as the admin user with the email `admin` and password `admin123`.