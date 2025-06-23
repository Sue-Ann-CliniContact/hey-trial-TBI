import uuid
import random
import math
import datetime
import requests
import os
import re
import traceback # Import traceback for detailed error logging
from typing import Dict, Any
from openai import OpenAI
from twilio_sms import send_verification_sms, is_us_number, format_us_number
from push_to_monday import push_to_monday
from check_duplicate import check_duplicate_email

# Constants and API keys
KESSLER_COORDS = (40.8255, -74.3594)
DISTANCE_THRESHOLD_MILES = 50
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")
# CORRECTED: Ensure this matches your environment variable name and is used consistently
Maps_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONDAY_BOARD_ID = 2014579172 # Centralized Monday.com Board ID

client = OpenAI(api_key=OPENAI_API_KEY)

# Session storage
sessions: Dict[str, Dict[str, Any]] = {}

questions = [
    "name", "email", "phone", "dob", "city_state",
    "tbi_year", "memory_issues", "english_fluent",
    "handedness", "can_exercise", "can_mri", "future_study_consent"
]

question_prompts = {
    "name": "Can I have your full name?",
    "email": "What’s your email address?",
    "phone": "What’s the best phone number to reach you? (10-digit US number, e.g. 5551234567)",
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
        "ip": None # Initialize IP in session data
    }
    return session_id

def generate_verification_code() -> str:
    return str(random.randint(1000, 9999))

def calculate_age(dob: str) -> int:
    """Calculates age from a YYYY-MM-DD date string. Raises ValueError if format is incorrect."""
    try:
        birth_date = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
        today = datetime.date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    except ValueError as e:
        print(f"Error calculating age for DOB '{dob}': {e}")
        raise ValueError("Invalid date of birth format. Please use YYYY-MM-DD.")


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
    # CORRECTED: Use the Maps_API_KEY variable
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={city_state}&key={Maps_API_KEY}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        results = response.json().get("results")
        if results and len(results) > 0: # Ensure results exist and are not empty
            location = results[0]["geometry"]["location"]
            return {"latitude": location["lat"], "longitude": location["lng"]}
        else:
            print(f"No geocoding results found for city/state: {city_state}")
            return {}
    except Exception as e:
        print(f"Error getting coordinates for '{city_state}': {e}")
        return {} # Ensure an empty dict is always returned on error

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

def ask_gpt(question: str) -> str:
    """Asks GPT-4 a question about the study summary."""
    try:
        response = client.chat.completions.create(
            model="gpt-4",
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
        print("OpenAI error:", e)
        return "I'm here to help you learn more about the study or see if you qualify. Would you like to begin the quick pre-qualifier now?"

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

    # Initial conversation step (user asks to start qualifier or general question)
    if step == -1:
        lowered = text.lower()
        if any(p in lowered for p in ["yes", "start", "begin", "qualify", "participate", "sign me up", "ready"]):
            session["step"] = 0
            return question_prompts[questions[0]]
        return ask_gpt(text)

    # --- Handle verification code entry for final submission ---
    if step == len(questions) and not session["verified"]:
        if text == session["code"]:
            session["verified"] = True
            try:
                # Normalize all fields one final time before qualification check and Monday push
                data = normalize_fields(data)

                # Qualification logic
                # Safely get DOB, handling potential missing key
                dob_value = data.get("dob", "")
                if not dob_value: # Basic check for empty DOB before calculating age
                    raise ValueError("Date of birth is missing.")
                age = calculate_age(dob_value) # calculate_age now handles ValueError internally

                # Safely get city_state, handling potential missing key
                city_state_value = data.get("city_state", "")
                if not city_state_value: # Basic check for empty city_state
                    raise ValueError("City and State information is missing.")
                
                coords = get_coords_from_city_state(city_state_value)
                if not coords or not coords.get("latitude") or not coords.get("longitude"):
                    # This return statement is only hit *after* verification code, not during step-by-step
                    print(f"❌ Geocoding failed for '{city_state_value}' during final submission.")
                    return "⚠️ Sorry, we couldn't determine your location for qualification. Please enter your city and state again like 'Newark, NJ'."

                # Use .get with default 0.0 for safety
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

                group = "new_group58505__1" if qualified else "new_group__1" # Qualified vs. Not Qualified group IDs
                tags = []
                if not distance_ok:
                    tags.append("Too far")
                if data.get("handedness") == "Left-handed":
                    tags.append("Left-handed")

                ip_data = get_location_from_ip(session.get("ip", ""))
                ipinfo_text = "\n".join([f"{k}: {v}" for k, v in ip_data.items()]) if ip_data else ""

                push_to_monday(data, group, qualified, tags, ipinfo_text, MONDAY_BOARD_ID)
                return "✅ Your submission is now confirmed and has been received. Thank you!"
            except ValueError as ve: # Catch specific value errors from e.g. calculate_age or missing data
                print(f"❌ Qualification data error (ValueError): {ve}")
                traceback.print_exc() # Print full traceback for qualification errors
                return f"⚠️ There was an issue with your provided information: {ve}. Please try again."
            except Exception as e:
                print("❌ Final submission error (within handle_input verification block):", e)
                traceback.print_exc() # Print full traceback for general final submission errors
                return "⚠️ Something went wrong while confirming your submission. Please try again."
        else:
            return "❌ That code doesn't match. Please check your SMS and enter the correct 4-digit code."
    
    # --- Process answers to questions step-by-step ---
    current_question_index = step # Use a clear variable for current index
    try: # General try-except for processing each question
        current_question = questions[current_question_index]
        user_value = text
        
        # DEBUG PRINTS to pinpoint issue
        print(f"DEBUG: Processing '{current_question}' (step {current_question_index}) with value '{user_value}'")

        # Specific validation for phone number
        if current_question == "phone":
            if not is_us_number(user_value):
                return "⚠️ That doesn't look like a valid US phone number. Please enter a 10-digit US number (e.g. 5551234567)."

        # Validate DOB format here (YYYY-MM-DD)
        if current_question == "dob":
            try:
                datetime.datetime.strptime(user_value, "%Y-%m-%d")
            except ValueError:
                return "⚠️ That doesn't look like a valid date format. Please use YYYY-MM-DD (e.g., 1990-01-20)."
        
        # Normalize just the current input before storing
        normalized_data_for_current = normalize_fields({current_question: user_value})
        # Use .get with a fallback to user_value in case normalization somehow fails or returns None/empty
        data[current_question] = normalized_data_for_current.get(current_question, user_value)
        
        print(f"DEBUG: Data stored for '{current_question}': {data.get(current_question)}")
        print(f"DEBUG: Current session step before increment: {session['step']}")

        # Handle duplicate email check (only if current_question is email)
        if current_question == "email":
            if check_duplicate_email(user_value, MONDAY_BOARD_ID):
                session["step"] = len(questions) # Skip to end if duplicate
                # Push duplicate to a specific Monday.com group/board if needed
                # Ensure this Monday.com group_id ('group_mkqb9ps4') exists on your board
                push_to_monday({"email": user_value, "name": "Duplicate"}, "group_mkqb9ps4", False, ["Duplicate"], "", MONDAY_BOARD_ID)
                return "⚠️ It looks like you’ve already submitted an application for this study. We’ll be in touch if you qualify!"
        
        # Increment step to move to the next question
        session["step"] += 1
        print(f"DEBUG: Session step after increment: {session['step']}")


        # Check if all questions are answered and initiate SMS verification
        if session["step"] == len(questions):
            print("DEBUG: Entering SMS verification block.")
            phone_number = data.get("phone", "")
            if not phone_number: # Edge case: if phone number is somehow missing
                print("❌ Error: Phone number missing before SMS verification.")
                return "⚠️ A required piece of information (phone number) is missing for verification. Please restart the qualification."

            formatted_phone_number = format_us_number(phone_number)
            success, error_msg = send_verification_sms(formatted_phone_number, session["code"])
            if success:
                return "Thanks! Please check your phone and enter the 4-digit code we just sent you to confirm your submission."
            else:
                session["step"] -= 1 # Stay on the current step if SMS fails
                print(f"SMS sending failed: {error_msg}")
                return error_msg
        
        # Return the next question prompt
        next_question_index = session["step"]
        print(f"DEBUG: About to get next question. Next step index: {next_question_index}")
        next_question_key = questions[next_question_index]
        print(f"DEBUG: Next question key: {next_question_key}")
        return question_prompts[next_question_key]

    except IndexError: # Catch if questions[session["step"]] goes out of bounds unexpectedly
        print(f"❌ IndexError: Session step {session['step']} out of bounds for questions list. (Current time: {datetime.datetime.now()})")
        traceback.print_exc() # Print full traceback for IndexErrors
        return "⚠️ An unexpected error occurred with the question sequence. Please try again."
    except Exception as e:
        # This is the crucial log for the "Something went wrong" at intermediate steps
        print(f"❌ General error processing input for question '{current_question}' (step {current_question_index}) with value '{user_value}': {e} (Current time: {datetime.datetime.now()})")
        traceback.print_exc() # Print full traceback for general errors
        return "⚠️ Something went wrong. Please try again."