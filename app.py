# app.py

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel
from typing import Dict, Any, Optional

# Import necessary functions from main.py
from main import (
    process_qualification_submission_from_form,
    load_study_config,
    sessions
)

from html_generator import generate_html_form
from push_to_monday import push_to_monday
from check_duplicate import check_duplicate_email

from fastapi.staticfiles import StaticFiles

import os
import requests
import json
import traceback

app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# NEW ENDPOINT: Dynamic Thank You Page
@app.get("/form/{study_id}/thank-you", response_class=HTMLResponse)
async def thank_you_page(study_id: str, status: Optional[str] = "qualified", message: Optional[str] = "Your submission has been received."):
    """
    Serves a dynamic thank you page after successful form submission or SMS verification.
    The 'status' and 'message' query parameters can be used to alleviate content.
    """
    # Basic check for valid status
    valid_statuses = ["qualified", "disqualified_no_capture", "duplicate", "error"]
    if status not in valid_statuses:
        status = "qualified" # Default to qualified for safety

    # Load study config to get form title for branding
    study_config = load_study_config(study_id)
    form_title = study_config.get("FORM_TITLE", "Qualification Status") if study_config else "Qualification Status"

    # Define message and icon based on status
    icon_html = ""
    display_message = message

    if status == "qualified":
        icon_html = '<svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-green-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>'
    elif status == "disqualified_no_capture":
        icon_html = '<svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-yellow-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" /></svg>'
    elif status == "duplicate":
        icon_html = '<svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-blue-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" /></svg>'
    elif status == "error":
        icon_html = '<svg xmlns="http://www.w3.org/2000/svg" class="h-16 w-16 text-red-500 mx-auto mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>'

    backend_base_url = os.getenv('RENDER_EXTERNAL_URL', "http://localhost:8000")

    html_content = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{form_title} - Status</title>
        <link rel="icon" href="{backend_base_url}/static/images/favicon.png" type="image/png">
        <script src="https://cdn.tailwindcss.com"></script>
        <style>
            .fade-in {{ animation: fadeIn 0.5s ease-in-out; }}
            @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
        </style>
        <script async src="https://www.googletagmanager.com/gtag/js?id=G-S2CHKR5MYY"></script>
        <script>
          window.dataLayer = window.dataLayer || [];
          function gtag(){{dataLayer.push(arguments);}}
          gtag('js', new Date());
          gtag('config', 'G-S2CHKR5MYY');
          // Send a conversion event based on status
          gtag('event', 'form_submission_status', {{
            'event_category': 'form_submission',
            'event_label': '{status}', // e.g., 'qualified', 'disqualified_no_capture', 'duplicate'
            'value': 1 // Or a monetary value if applicable
          }});
        </script>
        <script>
          !function(f,b,e,v,n,t,s)
          {{if(f.fbq)return;n=f.fbq=function(){{n.callMethod?
          n.callMethod.apply(n,arguments):n.queue.push(arguments)}};
          if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
          n.queue=[];t=b.createElement(e);t.async=!0;
          t.src=v;s=b.getElementsByTagName(e)[0];
          s.parentNode.insertBefore(t,s)}}(window, document,'script',
          'https://connect.facebook.net/en_US/fbevents.js');
          fbq('init', '156500797479357');
          fbq('track', 'PageView');
          // Send a custom conversion event
          fbq('trackCustom', 'FormSubmit', {{status: '{status}'}});
        </script>
        <noscript><img height="1" width="1" style="display:none"
          src="https://www.facebook.com/tr?id=156500797479357&ev=PageView&noscript=1"
        /></noscript>
    </head>
    <body class="bg-gray-50 flex items-center justify-center min-h-screen p-4">
        <div class="bg-white p-8 rounded-xl shadow-2xl w-full max-w-lg text-center fade-in">
            <div class="mb-6">
                <img src="{backend_base_url}/static/images/clini-logo.png" alt="CliniContact Logo" class="mx-auto h-16 mb-4">
            </div>
            <h2 class="text-3xl font-extrabold text-gray-900 mb-6">{form_title}</h2>
            {icon_html}
            <p class="text-gray-800 text-lg mb-6">{display_message}</p>
            <button onclick="window.location.href='/form/{study_id}'" class="w-full py-3 px-4 rounded-lg bg-blue-600 text-white font-semibold hover:bg-blue-700 transition duration-300 ease-in-out shadow-lg">
                Start New Qualification
            </button>
            <div class="text-center mt-6 text-sm text-gray-500">
                <p>By submitting this form, you agree to our <a href="https://www.clinicontact.com/privacy-policy" target="_blank" class="text-blue-600 hover:underline">Privacy Policy</a>.</p>
            </div>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# --- ENDPOINT: For Smart Form Submission ---
@app.post("/qualify_form")
async def qualify_form_submit(form_data: Dict[str, Any], request: Request): # Accept Dict[str, Any]
    # Extract study_id from the form_data payload
    study_id = form_data.get("study_id")
    if not study_id:
        raise HTTPException(status_code=400, detail="Missing study_id in form submission.")

    print(f"Received form submission for study '{study_id}':", form_data)
    try:
        ip_address = request.client.host if request.client else None
        
        # Call the new processing function from main.py
        result = process_qualification_submission_from_form(form_data, study_id, ip_address)
        
        # If SMS is required, return SMS prompt to frontend as before
        if result.get("status") == "sms_required":
            return result
        
        # FIX: For immediate statuses (qualified, disqualified, duplicate), redirect to thank-you page
        # Encode the message to pass it as a URL parameter
        encoded_message = quote(result.get("message", "Submission received."))
        return RedirectResponse(
            url=f"/form/{study_id}/thank-you?status={result.get('status')}&message={encoded_message}",
            status_code=303 # Use 303 See Other for POST-redirect-GET pattern
        )
    except Exception as e:
        print(f"Error in /qualify_form_submit endpoint for study '{study_id}': {e}")
        traceback.print_exc()
        # For general errors, redirect to an error state on the thank-you page
        encoded_error_message = quote("An unexpected server error occurred. Please try again.")
        return RedirectResponse(
            url=f"/form/{study_id}/thank-you?status=error&message={encoded_error_message}",
            status_code=303
        )

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
            monday_board_id = submission_data["monday_board_id"]
            
            study_id_for_verify = data_to_push.get("study_id")
            verify_study_config = load_study_config(study_id_for_verify)
            
            if not verify_study_config:
                print(f"❌ Error: Study config not found for study_id {study_id_for_verify} during verification.")
                return {"status": "error", "message": "Verification failed: Study configuration missing."}

            if submission_data["push_to_monday_flag"]:
                push_to_monday(data_to_push, group, qualified, tags, ip_info_text, monday_board_id, verify_study_config["MONDAY_COLUMN_MAPPINGS"], verify_study_config["MONDAY_DROPDOWN_ALLOWED_TAGS"]) 
            else:
                print(f"DEBUG: Not pushing to Monday.com for submission_id {sms_input.submission_id} as push_to_monday_flag was False.")
            
            # Clean up temporary session data
            del sessions[sms_input.submission_id]
            
            # FIX: Formulate final success message dynamically using study_config
            study_title = verify_study_config.get("FORM_TITLE", "a study")
            
            if qualified:
                message = f"✅ Your submission is confirmed! Based on your answers, you may qualify for the {study_title}. We will contact you soon with more details."
            else: # Not qualified but consented for future studies
                message = "✅ Your submission is confirmed! Based on your answers, you do not meet the current study criteria, but your information has been saved for future studies you may qualify for."
            
            # FIX: Redirect to thank-you page after successful verification
            # The message is generated here, then encoded and passed
            encoded_message = quote(message)
            return RedirectResponse(
                url=f"/form/{study_id_for_verify}/thank-you?status={'qualified' if qualified else 'disqualified_no_capture'}&message={encoded_message}",
                status_code=303
            )
        
        except Exception as e:
            print(f"Error during final Monday push after code verification: {e}")
            traceback.print_exc()
            # For verification errors, redirect to error state on thank-you page
            encoded_error_message = quote("An error occurred during final submission. Please try again.")
            return RedirectResponse(
                url=f"/form/{study_id_for_verify}/thank-you?status=error&message={encoded_error_message}",
                status_code=303
            )
    else:
        # Code did not match
        return {"status": "invalid_code", "message": "❌ That code doesn't match. Please try again."}