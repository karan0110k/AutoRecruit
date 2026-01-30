# import os
# import json
# from models import db, Application, Job
# from agents import agent_1_parse_resume, agent_2_evaluate_resume
# # from app import create_app # Import create_app <-- DELETE THIS LINE

# def run_agentic_workflow(application_id, job_id):
    
#     from app import create_app # Import create_app <-- ADD THIS LINE

#     # We must create an app context for the database
#     app = create_app()
#     with app.app_context():
#         try:
#             print(f"WORKER: Starting workflow for app {application_id} for job {job_id}")
#             application = Application.query.get(application_id)
#             job = Job.query.get(job_id) # <-- Get the job
            
#             if not application or not job:
#                 print(f"WORKER: Application {application_id} or Job {job_id} not found.")
#                 return

#             # --- AGENT 1: PARSE ---
#             filepath = f"uploads/resumes/{application.resume_filename}"
#             resume_text, parsed_data = agent_1_parse_resume(filepath)
#             if not parsed_data:
#                 application.status = "Error: Failed to parse"
#                 db.session.commit()
#                 print("WORKER: Failed to parse resume.")
#                 return

#             # --- AGENT 2: EVALUATE ---
#             # This calls the robust agent_2 function from your Canvas
#             evaluation = agent_2_evaluate_resume(parsed_data, job) 
#             if not evaluation:
#                 application.status = "Error: Failed to evaluate"
#                 db.session.commit()
#                 print("WORKER: Failed to evaluate resume.")
#                 return

#             # --- SUCCESS: Update Database (with robust type conversion) ---
#             application.resume_text = resume_text
#             application.status = evaluation.get('status', 'Needs Review')
            
#             # --- THIS IS THE FIX ---
#             # Force all scores from the agent's evaluation to be integers
#             application.ai_score = int(evaluation.get('ai_score', 0) or 0)
#             application.ai_feedback = evaluation.get('feedback', 'No feedback available.')
#             application.skill_match = int(evaluation.get('skill_match_percent', 0) or 0)
#             application.experience_relevance = int(evaluation.get('experience_relevance_percent', 0) or 0)
            
#             application.parsed_skills = json.dumps(parsed_data.get('skills', []))
#             application.parsed_experience_years = int(parsed_data.get('experience_years', 0) or 0)
#             application.parsed_summary = parsed_data.get('summary', '')
#             # --- END OF FIX ---

#             db.session.commit()
#             print(f"WORKER: Successfully processed app {application_id}")

#         except Exception as e:
#             print(f"WORKER: Error processing {application_id}: {e}")
#             db.session.rollback()


import os
import json
from models import db, Application, Job
from agents import agent_1_parse_resume, agent_2_evaluate_resume


def run_agentic_workflow(application_id, job_id):
    from app import create_app  # Import create_app inside the function

    # Create Flask app context for DB
    app = create_app()
    with app.app_context():
        try:
            print(f"WORKER: Starting workflow for Application {application_id}, Job {job_id}")

            # Fetch application & job data
            application = Application.query.get(application_id)
            job = Job.query.get(job_id)
            if not application or not job:
                print(f"WORKER: Application {application_id} or Job {job_id} not found.")
                return

            # --- AGENT 1: PARSE RESUME ---
            filepath = f"uploads/resumes/{application.resume_filename}"
            resume_text, parsed_data = agent_1_parse_resume(filepath)
            if not parsed_data:
                application.status = "Error: Failed to parse"
                db.session.commit()
                print("WORKER: Failed to parse resume.")
                return

            # --- AGENT 2: EVALUATE RESUME ---
            evaluation = agent_2_evaluate_resume(parsed_data, job)
            if not evaluation:
                application.status = "Error: Failed to evaluate"
                db.session.commit()
                print("WORKER: Failed to evaluate resume.")
                return

            # --- Extract & normalize scores ---
            raw_score = float(evaluation.get('ai_score', 0) or 0)
            skill_match = float(evaluation.get('skill_match_percent', 0) or 0)
            exp_rel = float(evaluation.get('experience_relevance_percent', 0) or 0)
            feedback = evaluation.get('feedback', 'No feedback available.')

            # --- Intelligent scoring adjustment ---
            # If some skills match, ensure a base score (30–40 range)
            if 20 < skill_match < 50 and raw_score < 30:
                adjusted_score = 45
                status = "Needs Review"
            elif skill_match >= 50 and raw_score < 50:
                adjusted_score = max(raw_score, 50)
                status = "Shortlisted"
            elif raw_score >= 70:
                adjusted_score = raw_score
                status = "Shortlisted"
            elif raw_score < 20:
                adjusted_score = raw_score
                status = "Rejected"
            else:
                adjusted_score = max(raw_score, 30)
                status = "Needs Review"

            # --- Update application record ---
            application.resume_text = resume_text
            application.status = status
            application.ai_score = int(adjusted_score)
            application.ai_feedback = feedback
            application.skill_match = int(skill_match)
            application.experience_relevance = int(exp_rel)
            application.parsed_skills = json.dumps(parsed_data.get('skills', []))
            application.parsed_experience_years = int(parsed_data.get('experience_years', 0) or 0)
            application.parsed_summary = parsed_data.get('summary', '')

            db.session.commit()
            print(f"WORKER: ✅ Successfully processed Application {application_id} (Score: {adjusted_score}, Status: {status})")

        except Exception as e:
            print(f"WORKER: ❌ Error processing Application {application_id}: {e}")
            db.session.rollback()