from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse # New import for serving HTML
from pydantic import BaseModel
from typing import Dict, Any, Optional # Added Dict, Any for dynamic form data

# Import necessary functions from main.py
from main import (
    process_qualification_submission_from_form, # For new smart form
    load_study_config, # To load study configs
    sessions # For SMS verification
)

# FIX: Import generate_html_form from html_generator.py
from html_generator import generate_html_form

# Import push_to_monday and check_duplicate_email (still used by process_qualification_submission_from_form)
from push_to_monday import push_to_monday # This is used by verify_code directly
from check_duplicate import check_duplicate_email # This is used by process_qualification_submission_from_form

# NEW: Import StaticFiles for serving images (logo, favicon)
from fastapi.staticfiles import StaticFiles

import os
import requests
import json
import traceback

app = FastAPI()

# NEW: Mount static files directory for images (clini-logo.png, favicon.png)
app.mount("/static", StaticFiles(directory="static"), name="static")

# CORS for frontend (e.g. your Monday.com App, or Webflow)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust for production: e.g., ["https://your-monday-app.cdn.monday.app", "https://your-webflow-domain.com"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for incoming form data (flexible for dynamic fields)
class DynamicQualificationForm(BaseModel):
    # These are the common fields you expect from any form submission
    name: str
    email: str
    phone: str
    dob: str # MM/DD/YYYY
    city_state: str
    tbi_year: str # Yes/No
    memory_issues: str # Yes/No
    english_fluent: str # Yes/No
    handedness: str # Left-handed/Right-handed
    can_exercise: str # Yes/No
    can_mri: str # Yes/No
    future_study_consent: str # Yes/No
    study_interest_keywords: Optional[str] = None # New optional field
    
    # Crucial: The study_id to identify which form/config this submission belongs to
    study_id: str 

    # Use extra=Extra.allow to allow for additional, dynamic fields from the form
    # This captures any unique_client_q1, etc. that are not explicitly defined above
    class Config:
        extra = "allow"

# Pydantic Model for SMS Verification Input
class SMSVerificationInput(BaseModel):
    submission_id: str
    code: str

# --- CHANGE START: Removed Chatbot Endpoints ---
# @app.post("/start")
# async def start():
#     session_id = generate_session_id() # From main.py
#     welcome = "👋 Hi! I’m your AI Assistant for clinical research studies. You can ask questions or begin screening when you’re ready."
#     return {"session_id": session_id, "message": welcome}

# @app.post("/chat")
# async def chat(request: Request):
#     body = await request.json()
#     session_id = body.get("session_id")
#     message = body.get("message")
#     ip_address = request.client.host if request.client else None
#     response = handle_input(session_id, message, ip_address) # From main.py
#     return {"reply": response}
# --- CHANGE END ---

# --- NEW ENDPOINT: Dynamically serve HTML form ---
@app.get("/form/{study_id}", response_class=HTMLResponse)
async def get_study_form(study_id: str):
    """
    Serves a dynamically generated HTML qualification form for a given study_id.
    """
    study_config = load_study_config(study_id)
    if not study_config:
        raise HTTPException(status_code=404, detail=f"Study form '{study_id}' not found or configured.")
    
    html_content = generate_html_form(study_config, study_id) # Use the imported function
    return HTMLResponse(content=html_content)

# --- ENDPOINT: For Smart Form Submission ---
@app.post("/qualify_form")
async def qualify_form_submit(form_data: Dict[str, Any], request: Request): # FIX: Accept Dict[str, Any]
    # Extract study_id from the form_data payload
    study_id = form_data.get("study_id")
    if not study_id:
        raise HTTPException(status_code=400, detail="Missing study_id in form submission.")

    print(f"Received form submission for study '{study_id}':", form_data)
    try:
        ip_address = request.client.host if request.client else None
        
        # Call the new processing function from main.py
        result = process_qualification_submission_from_form(form_data, study_id, ip_address)
        
        return result # This will be a dict like {"status": "...", "message": "..."}
    except Exception as e:
        print(f"Error in /qualify_form_submit endpoint for study '{study_id}': {e}")
        traceback.print_exc() # Added traceback for this endpoint
        return {"status": "error", "message": "An unexpected server error occurred. Please try again."}

# --- ENDPOINT: For SMS Code Verification ---
@app.post("/verify_code")
async def verify_code(sms_input: SMSVerificationInput):
    print(f"Received verification attempt for submission_id: {sms_input.submission_id}, code: {sms_input.code}")
    submission_data = sessions.get(sms_input.submission_id)

    if not submission_data:
        return {"status": "error", "message": "Verification session expired or not found. Please resubmit the form."}

    if sms_input.code == submission_data["code"]:
        try:
            # Extract necessary data from the temporary session storage
            data_to_push = submission_data["data"]
            group = submission_data["group"]
            qualified = submission_data["qualified"]
            tags = submission_data["tags"]
            ip_info_text = submission_data["ip_info_text"]
            monday_board_id = submission_data["monday_board_id"] # Get board ID from stored data

            # Only push to Monday.com if flag is set (based on qualification/future consent)
            if submission_data["push_to_monday_flag"]:
                # The push_to_monday function now needs the dropdown_allowed_tags from the config.
                # However, the study_config is NOT stored in the session for verify_code.
                # We need to load it here or pass it through the session.
                # For simplicity, we'll hardcode the allowed tags here for the verify_code path,
                # or assume push_to_monday handles it robustly without needing the full list.
                # Given the previous push_to_monday.py, it expects it.
                # The safest is to retrieve it from the config based on study_id if available in session data.
                
                # FIX: Retrieve study_config to get MONDAY_DROPDOWN_ALLOWED_TAGS
                # This requires study_id to be stored in the session data from qualify_form_submit
                # Let's assume study_id is part of submission_data['data'] for now.
                study_id_for_verify = data_to_push.get("study_id")
                verify_study_config = load_study_config(study_id_for_verify)
                
                if not verify_study_config:
                    print(f"❌ Error: Study config not found for study_id {study_id_for_verify} during verification.")
                    return {"status": "error", "message": "Verification failed: Study configuration missing."}

                push_to_monday(data_to_push, group, qualified, tags, ip_info_text, monday_board_id, verify_study_config["MONDAY_COLUMN_MAPPINGS"], verify_study_config["MONDAY_DROPDOWN_ALLOWED_TAGS"])
            else:
                print(f"DEBUG: Not pushing to Monday.com for submission_id {sms_input.submission_id} as push_to_monday_flag was False.")
            
            # Clean up temporary session data
            del sessions[sms_input.submission_id]
            
            # Formulate final success message based on original qualification
            if qualified:
                message = "✅ Your submission is confirmed! Based on your answers, you may qualify for a TBI study. We will contact you soon with more details."
            else: # Not qualified but consented for future studies
                message = "✅ Your submission is confirmed! Based on your answers, you do not meet the current study criteria, but your information has been saved for future studies you may qualify for."
            
            return {"status": "success", "message": message}
        
        except Exception as e:
            print(f"Error during final Monday push after code verification: {e}")
            traceback.print_exc()
            return {"status": "error", "message": "An error occurred during final submission. Please try again."}
    else:
        # Code did not match
        return {"status": "invalid_code", "message": "❌ That code doesn't match. Please try again."}