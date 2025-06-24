import uuid
import random
import math
import datetime
import requests
import os
import re
import traceback
from typing import Dict, Any

# --- CHANGE START ---
from openai import OpenAI
#import google.generativeai as genai # Added Google Generative AI import#
# --- CHANGE END ---

from twilio_sms import send_verification_sms, is_us_number, format_us_number
from push_to_monday import push_to_monday
from check_duplicate import check_duplicate_email

# Constants and API keys
KESSLER_COORDS = (40.8255, -74.3594)
DISTANCE_THRESHOLD_MILES = 50
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")
Maps_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

# --- CHANGE START ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") # Removed OpenAI API key variable
#GEMINI_API_KEY = os.getenv("GEMINI_API_KEY") # Added Gemini API key variable
MONDAY_BOARD_ID = 2014579172 # Centralized Monday.com Board ID

# --- CHANGE START ---
client = OpenAI(api_key=OPENAI_API_KEY) # Removed OpenAI client initialization
#genai.configure(api_key=GEMINI_API_KEY) # Configured Gemini API
# --- CHANGE END ---

# Session storage
sessions: Dict[str, Dict[str, Any]] = {}

questions = [
    "name", "email", "phone", "dob", "city_state",
    "tbi_year", "memory_issues", "english_fluent",
    "handedness", "can_exercise", "can_mri", "future_study_consent"
]

question_prompts = {
    "name": "Can I have your full name?",
    "email": "Okay, {name}. What’s your email address?",
    "phone": "Thanks, {name}. What’s the best phone number to reach you? (10-digit US number, e.g. 5551234567)",
    "dob": "And your date of birth? (YYYY-MM-DD)",
    "city_state": "Where are you currently located? (City and State)",
    "tbi_year": "Have you experienced a traumatic brain injury at least one year ago? (Yes/No)",
    "memory_issues": "Do you have persistent memory problems? (Yes/No)",
    "english_fluent": "Are you able to read and speak English well? (Yes/No)",
    "handedness": "Are you left or right-handed?",
    "can_exercise": "Are you willing and able to exercise? (Yes/No)",
    "can_mri": "Are you able to undergo an MRI? (Yes/No)",
    "future_study_consent": "Would you like us to contact you about future studies? (Yes/No)"
}

STUDY_SUMMARY = """
This clinical research study is led by Kessler Foundation in East Hanover, New Jersey. It aims to understand how exercise may improve memory and brain function in individuals with a history of moderate to severe traumatic brain injury (TBI).

To qualify, participants must:
- Be age 18 or older
- Have experienced a moderate to severe TBI at least one year ago
- Be experiencing persistent memory issues
- Be fluent in English
- Be physically able and willing to exercise
- Be able to undergo MRI brain scans
- Live within 50 miles of East Hanover, NJ

Participants will attend in-person visits, complete memory tests, undergo MRI scans, and engage in supervised exercise sessions.

Compensation is provided for time and transportation.

The study is IRB approved and participation is voluntary.
"""

def generate_session_id() -> str:
    return str(uuid.uuid4())

def start_session() -> str:
    session_id = generate_session_id()
    sessions[session_id] = {
        "step": -1,
        "data": {},
        "verified": False,
        "code": generate_verification_code(),
        "ip": None
    }
    return session_id

def generate_verification_code() -> str:
    return str(random.randint(1000, 9999))

def calculate_age(dob: str) -> int:
    """Calculates age from a `YYYY-MM-DD` date string. Raises ValueError if format is incorrect."""
    try:
        birth_date = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
        today = datetime.date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except ValueError as e:
        print(f"Error calculating age for DOB '{dob}': {e}")
        raise ValueError("Invalid date of birth format. Please use `YYYY-MM-DD`.")


def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    """Calculates Haversine distance between two sets of coordinates in miles."""
    R = 3958.8
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_location_from_ip(ip_address: str) -> Dict[str, Any]:
    """Fetches location information from an IP address using ipinfo.io."""
    if not ip_address:
        return {}
    url = f"https://ipinfo.io/{ip_address}?token={IPINFO_TOKEN}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        loc = data.get("loc", "").split(",")
        if len(loc) == 2:
            data["latitude"], data["longitude"] = float(loc[0]), float(loc[1])
        return data
    except Exception as e:
        print(f"Error getting location from IP '{ip_address}': {e}")
        return {}

def get_coords_from_city_state(city_state: str) -> Dict[str, float]:
    """Gets geographical coordinates for a given city and state using Google Maps Geocoding API."""
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={city_state}&key={Maps_API_KEY}" # Corrected variable name
    try:
        response = requests.get(url)
        response.raise_for_status()
        results = response.json().get("results")
        if results and len(results) > 0:
            location = results[0]["geometry"]["location"]
            return {"latitude": location["lat"], "longitude": location["lng"]}
        else:
            print(f"No geocoding results found for city/state: {city_state}")
            return {}
    except Exception as e:
        print(f"Error getting coordinates for '{city_state}': {e}")
        return {}

def is_within_distance(user_lat: float, user_lon: float) -> bool:
    """Checks if user's location is within the defined distance threshold from Kessler."""
    distance = haversine_distance(user_lat, user_lon, *KESSLER_COORDS)
    return distance <= DISTANCE_THRESHOLD_MILES

def normalize_fields(data: dict) -> dict:
    """Normalizes specific fields in the data dictionary (Yes/No, handedness, consent)."""
    def normalize_yes_no(value):
        val = str(value).strip().lower()
        if val in ["yes", "y"]:
            return "Yes"
        elif val in ["no", "n"]:
            return "No"
        return value

    def normalize_handedness(value):
        val = str(value).strip().lower()
        if "left" in val:
            return "Left-handed"
        elif "right" in val:
            return "Right-handed"
        return value

    def normalize_consent(value):
        val = str(value).strip().lower()
        if val == "yes":
            return "I, confirm"
        elif val == "no":
            return "I, do not confirm"
        return value

    normalized_data = data.copy()

    for key, val in normalized_data.items():
        if key in ["tbi_year", "memory_issues", "english_fluent", "can_exercise", "can_mri"]:
            normalized_data[key] = normalize_yes_no(val)
        elif key == "handedness":
            normalized_data[key] = normalize_handedness(val)
        elif key == "future_study_consent":
            normalized_data[key] = normalize_consent(val)

    return normalized_data

# --- CHANGE START (Reverting to OpenAI) ---
def ask_gpt(question: str) -> str: # Renamed back to ask_gpt
    """Asks the AI model (OpenAI GPT-4) a question about the study summary."""
    try:
        response = client.chat.completions.create(
            model="gpt-4", # Or "gpt-3.5-turbo" if preferred
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a helpful, friendly, and smart AI assistant for a clinical trial recruitment platform.

Below is a study summary written in IRB-approved language. Your job is to answer any natural-language question about the study accurately and supportively.
If the user asks about location, purpose, visits, eligibility, MRI, compensation, or logistics — answer with clear, friendly language based only on what is in the summary.

If the user expresses interest or says something like “I want to participate”, invite them to start the pre-qualifier right here in the chat.

Always end your answers with:
"Would you like to complete the quick pre-qualifier here in the chat to see if you're a match?"

STUDY DETAILS:
{STUDY_SUMMARY}
"""
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.6,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e) # Changed log message
        return "I'm here to help you learn more about the study or see if you qualify. Would you like to begin the quick pre-qualifier now?"
# --- CHANGE END ---

def handle_input(session_id: str, user_input: str, ip_address: str = None) -> str:
    """Handles incoming user input, processes questions, and manages session state."""
    session = sessions.get(session_id)
    if not session:
        print(f"❌ Session ID {session_id} not found. (Current time: {datetime.datetime.now()})")
        return "⚠️ Unable to start session. Please refresh and try again."

    if ip_address and not session["ip"]:
        session["ip"] = ip_address

    step = session["step"]
    data = session["data"]
    text = user_input.strip()

    # Start of conversation (step -1)
    if step == -1:
        lowered = text.lower()
        if any(p in lowered for p in ["yes", "start", "begin", "qualify", "participate", "sign me up", "ready"]):
            session["step"] = 0
            return question_prompts[questions[0]]
        return ask_gpt(text)

    # --- SMS Verification and Final Submission Logic (After all questions are answered) ---
    if session["step"] == len(questions): # This ensures this block is primarily for the final stage
        if not session["verified"]: # SMS not sent or needs re-sending
            print("DEBUG: All questions answered. Attempting to send SMS for the first time.")
            phone_number = data.get("phone", "")
            if not phone_number:
                print("❌ Error: Phone number missing before SMS verification attempt.")
                return "⚠️ A required piece of information (phone number) is missing for verification. Please restart the qualification."

            formatted_phone_number = format_us_number(phone_number)
            success, error_msg = send_verification_sms(formatted_phone_number, session["code"])
            
            if success:
                session["verified"] = True # Mark as SMS sent
                return "Thanks! Please check your phone and enter the 4-digit code we just sent you to confirm your submission."
            else:
                # SMS sending failed. Reset state to allow re-entry of phone number.
                session["step"] = questions.index("phone") # Go back to phone question
                data["phone"] = "" # Clear phone number
                session["verified"] = False # Ensure not verified
                print(f"SMS sending failed for {formatted_phone_number}: {error_msg}. Resetting for phone re-entry.")
                return f"❌ {error_msg} Please enter a new 10-digit US phone number."
        else: # session["verified"] is True, meaning SMS was previously sent, now waiting for code
            print(f"DEBUG: Session verified, expecting code input. User input: '{text}'")
            if text == session["code"]:
                # Correct code, proceed to final submission
                try:
                    data = normalize_fields(data)

                    dob_value = data.get("dob", "")
                    if not dob_value:
                        raise ValueError("Date of birth is missing.")
                    age = calculate_age(dob_value)

                    city_state_value = data.get("city_state", "")
                    if not city_state_value:
                        raise ValueError("City and State information is missing.")
                    
                    coords = get_coords_from_city_state(city_state_value)
                    if not coords or not coords.get("latitude") or not coords.get("longitude"):
                        print(f"❌ Geocoding failed for '{city_state_value}' during final submission.")
                        return "⚠️ Sorry, we couldn't determine your location for qualification. Please enter your city and state again like 'Newark, NJ'."

                    distance_ok = is_within_distance(coords.get("latitude", 0.0), coords.get("longitude", 0.0))
                    
                    qualified = (
                        age >= 18 and
                        data.get("tbi_year") == "Yes" and
                        data.get("memory_issues") == "Yes" and
                        data.get("english_fluent") == "Yes" and
                        data.get("can_exercise") == "Yes" and
                        data.get("can_mri") == "Yes" and
                        distance_ok
                    )

                    group = "new_group58505__1" if qualified else "new_group__1"
                    tags = []
                    if not distance_ok:
                        tags.append("Too far")
                    if data.get("handedness") == "Left-handed":
                        tags.append("Left-handed")

                    ip_data = get_location_from_ip(session.get("ip", ""))
                    ipinfo_text = "\n".join([f"{k}: {v}" for k, v in ip_data.items()]) if ip_data else ""

                    push_to_monday(data, group, qualified, tags, ipinfo_text, MONDAY_BOARD_ID)
                    return "✅ Your submission is now confirmed and has been received. Thank you!"
                except ValueError as ve:
                    print(f"❌ Qualification data error (ValueError): {ve}")
                    traceback.print_exc()
                    return f"⚠️ There was an issue with your provided information: {ve}. Please try again."
                except Exception as e:
                    print("❌ Final submission error (within handle_input verification block):", e)
                    traceback.print_exc()
                    return "⚠️ Something went wrong while confirming your submission. Please try again."
            else: # Input is NOT the verification code
                if is_us_number(text): # User might be trying to provide a new phone number
                    session["step"] = questions.index("phone") # Go back to phone question
                    data["phone"] = "" # Clear phone number
                    session["verified"] = False # Reset verified status
                    print("DEBUG: User provided a number instead of code. Resetting to phone number question.")
                    return "❌ That wasn't the code. If you wish to change your number, please enter a valid 10-digit US phone number."
                
                return "❌ That code doesn't match. Please check your SMS and enter the correct 4-digit code."
    
    # --- Process answers to questions step-by-step (If not in SMS/final submission phase) ---
    current_question_index = step
    try:
        current_question = questions[current_question_index]
        user_value = text
        
        print(f"DEBUG: Processing '{current_question}' (step {current_question_index}) with value '{user_value}'")

        if current_question == "phone":
            # Add basic email validation for phone field if user re-enters
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if re.match(email_regex, user_value): # This is a check for email in phone field
                return "⚠️ That looks like an email address, but I need a 10-digit US phone number."

            if not is_us_number(user_value):
                return "⚠️ That doesn't look like a valid US phone number. Please enter a 10-digit US number (e.g. 5551234567)."

        if current_question == "email":
            # Add basic email validation here
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_regex, user_value):
                return "⚠️ That doesn't look like a valid email address. Please provide a valid email (e.g., example@domain.com)."           
            # FIX: Corrected indentation for the duplicate check
            if check_duplicate_email(user_value, MONDAY_BOARD_ID):
                session["step"] = len(questions)
                push_to_monday({"email": user_value, "name": "Duplicate"}, "group_mkqb9ps4", False, ["Duplicate"], "", MONDAY_BOARD_ID)
                return "⚠️ It looks like you’ve already submitted an application for this study. We’ll be in touch if you qualify!"
 
        # FIX: Removed the duplicated normalization lines. This block runs AFTER email validation.
        # normalized_data_for_current = normalize_fields({current_question: user_value})
        # data[current_question] = normalized_data_for_current.get(current_question, user_value)
 
        # Moved the normalization and data storage here to ensure it applies after all validations
        # within the current_question processing block.
        normalized_data_for_current = normalize_fields({current_question: user_value})
        data[current_question] = normalized_data_for_current.get(current_question, user_value)

        session["step"] += 1
        print(f"DEBUG: Session step after increment: {session['step']}")

        if session["step"] == len(questions):
            print(f"DEBUG: All questions answered. Next input will trigger SMS/Verification. (Current time: {datetime.datetime.now()})")
            return "Thank you for answering all the questions. Please wait while we prepare your verification."

        next_question_index = session["step"]
        print(f"DEBUG: About to get next question. Next step index: {next_question_index}")
        next_question_key = questions[next_question_index]

        first_name = data.get("name", "").split(" ")[0] if data.get("name") else ""
        formatted_prompt = question_prompts[next_question_key].format(name=first_name) if "{name}" in question_prompts[next_question_key] else question_prompts[next_question_key]

        print(f"DEBUG: Next question key: {next_question_key}, Formatted prompt: {formatted_prompt}")
        return formatted_prompt

    except IndexError:
        print(f"❌ IndexError: Session step {session['step']} out of bounds for questions list. (Current time: {datetime.datetime.now()})")
        traceback.print_exc()
        return "⚠️ An unexpected error occurred with the question sequence. Please try again."
    except Exception as e:
        print(f"❌ General error processing input for question '{current_question}' (step {current_question_index}) with value '{user_value}': {e} (Current time: {datetime.datetime.now()})")
        traceback.print_exc()
        return "⚠️ Something went wrong. Please try again."