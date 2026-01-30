import os
import json
import smtplib
from email.mime.text import MIMEText
from groq import Groq
from pdfminer.high_level import extract_text
from config import Config

# Initialize Groq Client
try:
    client = Groq(api_key=Config.GROQ_API_KEY)
except Exception as e:
    print(f"Failed to initialize Groq client: {e}")
    client = None

def get_groq_completion(prompt_text, is_json=False):
    """
    Helper function to call the Groq API.
    Handles JSON parsing and error checking.
    """
    if not client:
        print("Groq client not initialized. Check API key.")
        return None

    try:
        chat_completion = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant. If the user asks for JSON, respond with ONLY the valid JSON object and nothing else."
                },
                {
                    "role": "user",
                    "content": prompt_text,
                }
            ],
            model="llama-3.1-8b-instant", # Using a fast model
            temperature=0.5,
        )
        response = chat_completion.choices[0].message.content.strip()
        
        if is_json:
            # Clean response to ensure it's valid JSON
            if response.startswith("```json"):
                response = response[7:-3].strip()
            
            try:
                return json.loads(response)
            except json.JSONDecodeError as e:
                print(f"JSON Decode Error: {e}")
                print(f"Raw response was: {response}")
                return None
        
        return response

    except Exception as e:
        print(f"Error calling Groq API: {e}")
        return None

# --- AGENT 1: Resume Parser Agent ---
def agent_1_parse_resume(pdf_path):
    """
    Extracts text from PDF and uses Groq to parse it into JSON.
    Returns: (resume_text, parsed_data_json)
    """
    try:
        resume_text = extract_text(pdf_path)
    except Exception as e:
        print(f"PDF Parsing Error: {e}")
        return None, None
    
    # Truncate text to fit context window
    truncated_text = resume_text[:6000]
    
    prompt = f"""
    Extract key details from this resume text. Respond with ONLY a valid JSON object.
    
    Resume Text:
    {truncated_text}

    JSON Schema:
    {{
      "name": "string (Candidate's full name)",
      "email": "string (Candidate's email address)",
      "skills": ["list", "of", "top 10 skills"],
      "experience_years": integer (Total years of professional experience, 0 if student),
      "summary": "string (A 2-3 sentence summary of their professional profile)"
    }}
    """
    
    parsed_data = get_groq_completion(prompt, is_json=True)
    return resume_text, parsed_data

# --- AGENT 2: Evaluator Agent ---
def agent_2_evaluate_resume(parsed_resume_json, job): # <-- MODIFIED: accepts job
    """
    Evaluates parsed resume data against a specific job.
    Returns: evaluation_data_json
    """
    
    # --- MODIFIED: The prompt is now dynamic ---
    prompt = f"""
    You are an AI HR Assistant. Evaluate this candidate for the following specific role:
    ROLE TITLE: {job.title}
    ROLE SKILLS/DESCRIPTION: {job.description}

    Evaluate the candidate based on their resume data:
    CANDIDATE DATA: {json.dumps(parsed_resume_json)}

    Give:
    1. skill_match_percent: How well do their skills match the ROLE? (0-100)
    2. experience_relevance_percent: How relevant is their experience to the ROLE? (0-100)
    3. ai_score: The average of the two percentages.
    4. feedback: A short, 1-2 sentence constructive feedback summary for the candidate *for this specific role*.

    Respond with ONLY a valid JSON object.
    """
    
    evaluation = get_groq_completion(prompt, is_json=True)
    
    # --- NEW ROBUST LOGIC ---
    if evaluation:
        try:
            # Get the individual scores, force them to be integers, default to 0
            skill_match = int(evaluation.get('skill_match_percent', 0) or 0)
            exp_relevance = int(evaluation.get('experience_relevance_percent', 0) or 0)
            
            # Check if ai_score was provided. If not, calculate it.
            if 'ai_score' not in evaluation or not evaluation.get('ai_score'):
                ai_score = (skill_match + exp_relevance) / 2
            else:
                ai_score = int(evaluation.get('ai_score', 0) or 0)

            # --- Save the cleaned data back into the dictionary ---
            evaluation['skill_match_percent'] = skill_match
            evaluation['experience_relevance_percent'] = exp_relevance
            evaluation['ai_score'] = ai_score

            # System logic to assign status
            if ai_score > 60:
                status = "Shortlisted"
            elif ai_score < 10:
                status = "Rejected"
            else:
                status = "Needs Review"
            evaluation['status'] = status
        
        except (ValueError, TypeError) as e:
            print(f"WORKER: Error converting AI scores to int: {e}")
            print(f"Raw evaluation data: {evaluation}")
            # Fallback in case of bad data
            evaluation['status'] = "Needs Review"
            evaluation['ai_score'] = 0
            evaluation['skill_match_percent'] = 0
            evaluation['experience_relevance_percent'] = 0
            
    return evaluation

# --- AGENT 3: Job Post Writer Agent ---
def agent_3_write_job_post(job_title, skills, description):
    """
    Generates a professional LinkedIn-style job post.
    Returns: job_post_string
    """
    prompt = f"""
    Create a professional, engaging, and inclusive LinkedIn-style job post.
    Do not use any emojis.
    
    Role: {job_title}
    Key Skills: {skills}
    Description: {description}
    Company: AgenCruit
    
    Format the post clearly with sections like "About Us", "The Role", "Requirements", and "What We Offer".
    Do not include any preamble, just the post itself.
    """
    return get_groq_completion(prompt)

# --- AGENT 4: Email Notifier Agent ---
def agent_4_send_email(candidate_name, candidate_email, status):
    """
    Generates personalized email content and sends it using smtplib.
    Returns: Boolean (True if sent, False if failed)
    """
    
    # 1. Generate Email Content
    prompt = f"""
    Generate a professional email template for a candidate.
    The candidate's name is: {candidate_name}
    Their application status is: '{status}'
    The company is: AgenCruit

    Respond with ONLY a valid JSON object:
    {{"subject": "string", "body": "string (Use \\n for new lines. Be polite and professional.)"}}
    """
    
    email_content = get_groq_completion(prompt, is_json=True)
    
    if not email_content or 'subject' not in email_content or 'body' not in email_content:
        print("Failed to generate email content from Groq.")
        return False

    # 2. Send Email using smtplib
    try:
        msg = MIMEText(email_content['body'])
        msg['Subject'] = email_content['subject']
        msg['From'] = Config.MAIL_USERNAME
        msg['To'] = candidate_email

        print(f"Connecting to mail server {Config.MAIL_SERVER}...")
        with smtplib.SMTP(Config.MAIL_SERVER, Config.MAIL_PORT) as server:
            server.set_debuglevel(1) # Show SMTP logs
            server.starttls()
            server.login(Config.MAIL_USERNAME, Config.MAIL_PASSWORD)
            server.sendmail(Config.MAIL_USERNAME, [candidate_email], msg.as_string())
        
        print(f"Email successfully sent to {candidate_email}")
        return True
    except Exception as e:
        print(f"Failed to send email: {e}")
        return False