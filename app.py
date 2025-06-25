from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel # Already present
from typing import Optional # Already present

# Import the new processing function
from main import process_qualification_submission_from_form, ask_gpt, sessions, generate_verification_code, normalize_fields, calculate_age, MONDAY_BOARD_ID, push_to_monday # Added push_to_monday and MONDAY_BOARD_ID for clarity here

import os
import requests
import json # Ensure json is imported if send_messenger_message is in app.py
import traceback # Ensure traceback is imported for logging

app = FastAPI()

# CORS for frontend (e.g. Webflow)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic model for incoming form data
class QualificationForm(BaseModel):
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

# --- NEW Pydantic Model for SMS Verification Input ---
class SMSVerificationInput(BaseModel):
    submission_id: str
    code: str

# --- Existing /start and /chat endpoints (if you keep the chatbot for general questions) ---
@app.post("/start")
async def start():
    session_id = start_session() # From main.py
    welcome = "👋 Hi! I’m your AI Assistant for clinical research studies. You can ask questions or begin screening when you’re ready."
    return {"session_id": session_id, "message": welcome}

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    session_id = body.get("session_id")
    message = body.get("message")
    ip_address = request.client.host if request.client else None
    response = handle_input(session_id, message, ip_address) # From main.py
    return {"reply": response}

# --- ENDPOINT: For Smart Form Submission ---
@app.post("/qualify_form")
async def qualify_form_submit(form_data: QualificationForm, request: Request):
    print("Received form submission:", form_data.dict())
    try:
        ip_address = request.client.host if request.client else None
        
        # Call the new processing function from main.py
        result = process_qualification_submission_from_form(form_data.dict(), ip_address)
        
        return result # This will be a dict like {"status": "...", "message": "..."}
    except Exception as e:
        print(f"Error in /qualify_form_submit endpoint: {e}")
        traceback.print_exc() # Added traceback for this endpoint
        return {"status": "error", "message": "An unexpected server error occurred. Please try again."}

# --- ENDPOINT: For SMS Code Verification (after form submission) ---
@app.post("/verify_code")
async def verify_code(sms_input: SMSVerificationInput): # FIX: Accept Pydantic model
    print(f"Received verification attempt for submission_id: {sms_input.submission_id}, code: {sms_input.code}")
    submission_data = sessions.get(sms_input.submission_id) # Use sms_input.submission_id

    if not submission_data:
        return {"status": "error", "message": "Verification session expired or not found. Please resubmit the form."}

    if sms_input.code == submission_data["code"]: # Use sms_input.code
        # Code matched! Now push to Monday.com
        try:
            # Extract necessary data from the temporary session storage
            data_to_push = submission_data["data"]
            group = submission_data["group"]
            qualified = submission_data["qualified"]
            tags = submission_data["tags"]
            ip_info_text = submission_data["ip_info_text"] # Already processed IP info text

            # MONDAY_BOARD_ID is imported from main, push_to_monday also
            push_to_monday(data_to_push, group, qualified, tags, ip_info_text, MONDAY_BOARD_ID) 
            
            # Clean up temporary session data
            del sessions[sms_input.submission_id] # Use sms_input.submission_id
            
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