import uuid
import random
import math
import datetime
import requests
import os
import re
import traceback
from typing import Dict, Any, Optional

from openai import OpenAI # Or google.generativeai as genai

from twilio_sms import send_verification_sms, is_us_number, format_us_number
from push_to_monday import push_to_monday
from check_duplicate import check_duplicate_email

# Constants and API keys
KESSLER_COORDS = (40.8255, -74.3594)
DISTANCE_THRESHOLD_MILES = 50
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")
Maps_API_KEY = os.getenv("Maps_API_KEY") 

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
MONDAY_BOARD_ID = 2014579172 # Centralized Monday.com Board ID

client = OpenAI(api_key=OPENAI_API_KEY) # Or genai.configure(api_key=GEMINI_API_KEY)

# Session storage (less crucial for smart form, but might be needed if you integrate interim steps)
sessions: Dict[str, Dict[str, Any]] = {} # This will likely be simpler or removed for a pure form submit

questions = [
    "name", "email", "phone", "dob", "city_state",
    "tbi_year", "memory_issues", "english_fluent",
    "handedness", "can_exercise", "can_mri", "future_study_consent",
    "study_interest_keywords" # New question key for future study interest
]

question_prompts = { # These prompts are for the chatbot, less relevant for the form itself
    "name": "Can I have your full name?",
    "email": "Okay, {name}. What’s your email address?",
    "phone": "Thanks, {name}. What’s the best phone number to reach you? (10-digit US number, e.g. 5551234567)",
    "dob": "And your date of birth? (MM/DD/YYYY)", # Updated prompt for MM/DD/YYYY
    "city_state": "Where are you currently located? (City and State)",
    "tbi_year": "Have you experienced a traumatic brain injury at least one year ago? (Yes/No)",
    "memory_issues": "Do you have persistent memory problems? (Yes/No)",
    "english_fluent": "Are you able to read and speak English well? (Yes/No)",
    "handedness": "Are you left or right-handed?",
    "can_exercise": "Are you willing and able to exercise? (Yes/No)",
    "can_mri": "Are you able to undergo an MRI? (Yes/No)",
    "future_study_consent": "Would you like us to contact you about future studies? (Yes/No)",
    "study_interest_keywords": "Great! What types of studies would you be interested in? (e.g., Diabetes, Depression, Asthma, TBI). Please list comma separated:" # New prompt
}

STUDY_SUMMARY = """
This platform helps connect individuals with clinical research studies focused on traumatic brain injury (TBI) and related conditions. These studies aim to advance medical understanding, evaluate potential new treatments, and improve outcomes for individuals affected by TBI, particularly concerning memory and brain function.

To potentially qualify for these types of studies, participants typically need to meet certain general criteria. Common criteria include:
- Being age 18 or older
- Having experienced a moderate to severe TBI at least one year ago
- Experiencing persistent memory issues
- Being fluent in English
- Being physically able and willing to participate in study-related activities, which may include exercise-based interventions
- Being able to undergo advanced imaging, such as MRI brain scans
- Being able to commute to a research facility, which is often located in a specific area, for example, near East Hanover, New Jersey. (NOTE: This specific location is just an example of how location is often a factor, not a direct mention of THE study location. The bot should not emphasize this.)

Typical participation may involve:
- In-person visits to a research facility.
- Completing various assessments, such as memory tests.
- Undergoing advanced imaging procedures like MRI scans.
- Engaging in supervised activities, for example, exercise sessions.

Compensation is usually provided for a participant's time and travel expenses.

All clinical studies are reviewed and approved by independent ethical review boards (IRBs) to protect participant safety and rights. Participation is always voluntary.
"""

def generate_session_id() -> str:
    return str(uuid.uuid4())

# The start_session and handle_input functions would be kept if you maintain the initial chatbot functionality
# For a pure form-based approach, you might simplify or remove the chatbot entry points.
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
    """Calculates age from a `MM/DD/YYYY` date string. Raises ValueError if format is incorrect or under 18."""
    try:
        # FIX: Change strptime format to MM/DD/YYYY
        birth_date = datetime.datetime.strptime(dob, "%m/%d/%Y").date()
        today = datetime.date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
        # FIX: Immediate age validation check
        if age < 18:
            raise ValueError("Age must be 18 years or older for these studies.")
            
        return age
    except ValueError as e:
        print(f"Error calculating age for DOB '{dob}': {e}")
        raise ValueError(f"Invalid date of birth or age: {e}. Please use `MM/DD/YYYY` and ensure you are 18 or older.")


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
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={city_state}&key={Maps_API_KEY}"
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
        # Note: 'study_interest_keywords' is a new field and typically just stored as text, no normalization needed

    return normalized_data

def ask_gpt(question: str) -> str:
    """Asks the AI model (OpenAI GPT-4) a question about the study summary."""
    try:
        response = client.chat.completions.create(
            model="gpt-4", # Or "gpt-3.5-turbo" if preferred
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a helpful, friendly, and smart AI assistant for a clinical trial recruitment platform.
Your goal is to inform users about general clinical research studies related to traumatic brain injury (TBI) and guide them through a pre-qualification process.
Crucially, **do not mention any specific institution names (like Kessler Foundation) or specific study titles** when describing studies. Always speak in general terms about "TBI studies" or "clinical research."

Answer any natural-language question about the *general nature* of TBI studies, their typical purpose, what participation might involve, or typical qualification criteria, based *only* on the provided general study details.

If the user asks about location, explain that research facilities are often located in specific areas, using East Hanover, New Jersey as an *example* of a location type, but not as the specific current study's location.

If the user expresses interest or asks to participate, invite them to start the pre-qualification questionnaire directly in the chat.

Always end your answers with:
"Would you like to complete a quick pre-qualifier here in the chat to see if you might be a match for a TBI study?"

GENERAL TBI STUDY DETAILS:
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
        return "I'm here to help you learn more about TBI studies or see if you might qualify. Would you like to begin the quick pre-qualifier now?"

# handle_input function is for the chatbot.
# We will create a new function for the form submission logic.
def handle_input(session_id: str, user_input: str, ip_address: str = None) -> str:
    # KEEP this if you want to retain the initial chatbot functionality
    # The logic here remains for the chatbot flow.
    session = sessions.get(session_id)
    if not session:
        print(f"❌ Session ID {session_id} not found. (Current time: {datetime.datetime.now()})")
        return "⚠️ Unable to start session. Please refresh and try again."

    if ip_address and not session["ip"]:
        session["ip"] = ip_address

    step = session["step"]
    data = session["data"]
    text = user_input.strip()

    if step == -1:
        lowered = text.lower()
        if any(p in lowered for p in ["yes", "start", "begin", "qualify", "participate", "sign me up", "ready"]):
            session["step"] = 0
            return question_prompts[questions[0]]
        return ask_gpt(text)
    
    if session["step"] == len(questions):
        if not session["verified"]:
            print("DEBUG: All questions answered. Attempting to send SMS for the first time immediately. (Current time: {datetime.datetime.now()})")
            phone_number = data.get("phone", "")
            if not phone_number:
                print("❌ Error: Phone number missing before SMS verification attempt.")
                return "⚠️ A required piece of information (phone number) is missing for verification. Please restart the qualification."

            formatted_phone_number = format_us_number(phone_number)
            success, error_msg = send_verification_sms(formatted_phone_number, session["code"])
            
            if success:
                session["verified"] = True
                return "Thanks! Please check your phone and enter the 4-digit code we just sent you to confirm your submission."
            else:
                session["step"] = questions.index("phone")
                data["phone"] = ""
                session["verified"] = False
                print(f"SMS sending failed for {formatted_phone_number}: {error_msg}. Resetting for phone re-entry.")
                return f"❌ {error_msg} Please enter a new 10-digit US phone number."
        else: # session["verified"] is True, meaning SMS was previously sent, now waiting for code
            print(f"DEBUG: Session verified, expecting code input. User input: '{text}'")
            if text == session["code"]:
                try:
                    data = normalize_fields(data)

                    # --- Qualification logic (same as below in process_qualification_submission_from_form) ---
                    # THIS PART IS DUPLICATED FOR CHATBOT'S FINAL SUBMISSION
                    dob_value = data.get("dob", "")
                    if not dob_value: raise ValueError("Date of birth is missing.")
                    age = calculate_age(dob_value) # calculate_age now validates age >= 18

                    city_state_value = data.get("city_state", "")
                    if not city_state_value: raise ValueError("City and State information is missing.")
                    
                    coords = get_coords_from_city_state(city_state_value)
                    if not coords or not coords.get("latitude") or not coords.get("longitude"):
                        return "⚠️ Sorry, we couldn't determine your location for qualification. Please enter your city and state again like 'Newark, NJ'."

                    distance_ok = is_within_distance(coords.get("latitude", 0.0), coords.get("longitude", 0.0))
                    
                    qualified = (
                        age >= 18 and # Redundant check if calculate_age already enforces >=18
                        data.get("tbi_year") == "Yes" and
                        data.get("memory_issues") == "Yes" and
                        data.get("english_fluent") == "Yes" and
                        data.get("can_exercise") == "Yes" and
                        data.get("can_mri") == "Yes" and
                        distance_ok
                    )

                    group = "new_group58505__1" if qualified else "new_group__1"
                    tags = []
                    if not distance_ok: tags.append("Too far")
                    if data.get("handedness") == "Left-handed": tags.append("Left-handed")
                    
                    disqualification_reasons = []
                    if not distance_ok: disqualification_reasons.append("you are located outside the eligible distance from our research site")
                    if age < 18: disqualification_reasons.append("you are under 18 years old") # This should be caught by calculate_age now
                    if data.get("tbi_year") != "Yes": disqualification_reasons.append("you have not experienced a TBI at least one year ago")
                    if data.get("memory_issues") != "Yes": disqualification_reasons.append("you do not have persistent memory problems")
                    if data.get("english_fluent") != "Yes": disqualification_reasons.append("you are not fluent in English")
                    if data.get("can_exercise") != "Yes": disqualification_reasons.append("you are not willing or able to exercise")
                    if data.get("can_mri") != "Yes": disqualification_reasons.append("you are not able to undergo an MRI")
                    
                    ip_data = get_location_from_ip(session.get("ip", ""))
                    ipinfo_text = "\n".join([f"{k}: {v}" for k, v in ip_data.items()]) if ip_data else ""

                    # FIX: Conditional push to Monday.com based on future_study_consent
                    if qualified or data.get("future_study_consent") == "I, confirm":
                        push_to_monday(data, group, qualified, tags, ipinfo_text, MONDAY_BOARD_ID)
                    else: # Not qualified and no future study consent, so don't push
                        print("DEBUG: Not qualified and no future study consent. Skipping Monday.com push.")

                    final_message = ""
                    if qualified:
                        final_message = "✅ Thank you! Based on your answers, you may qualify for a TBI study. We will contact you soon with more details."
                    else:
                        if len(disqualification_reasons) > 0:
                            if len(disqualification_reasons) > 1:
                                reasons_str = ", ".join(disqualification_reasons[:-1]) + ", and " + disqualification_reasons[-1]
                            else:
                                reasons_str = disqualification_reasons[0]
                            final_message = f"Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria because {reasons_str}. We appreciate your time!"
                        else:
                            final_message = "Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria. We appreciate your time!"
                    
                    del sessions[session_id] # Reset session after final message
                    return final_message

                except ValueError as ve:
                    print(f"❌ Qualification data error (ValueError): {ve}")
                    traceback.print_exc()
                    return f"⚠️ There was an issue with your provided information: {ve}. Please try again."
                except Exception as e:
                    print("❌ Final submission error (within handle_input verification block):", e)
                    traceback.print_exc()
                    return "⚠️ Something went wrong while confirming your submission. Please try again."
            else: # Input is NOT the verification code
                if is_us_number(text):
                    session["step"] = questions.index("phone")
                    data["phone"] = ""
                    session["verified"] = False
                    print("DEBUG: User provided a number instead of code. Resetting to phone number question.")
                    return "❌ That wasn't the code. If you wish to change your number, please enter a valid 10-digit US phone number."
                
                return "❌ That code doesn't match. Please check your SMS and enter the correct 4-digit code."
    
    current_question_index = step
    try:
        current_question = questions[current_question_index]
        user_value = text
        
        print(f"DEBUG: Processing '{current_question}' (step {current_question_index}) with value '{user_value}'")

        if current_question == "phone":
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if re.match(email_regex, user_value):
                return "⚠️ That looks like an email address, but I need a 10-digit US phone number."

            if not is_us_number(user_value):
                return "⚠️ That doesn't look like a valid US phone number. Please enter a 10-digit US number (e.g. 5551234567)."

        if current_question == "email":
            email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
            if not re.match(email_regex, user_value):
                return "⚠️ That doesn't look like a valid email address. Please provide a valid email (e.g., example@domain.com)."           
            if check_duplicate_email(user_value, MONDAY_BOARD_ID):
                session["step"] = len(questions)
                push_to_monday({"email": user_value, "name": "Duplicate"}, "group_mkqb9ps4", False, ["Duplicate"], "", MONDAY_BOARD_ID)
                return "⚠️ It looks like you’ve already submitted an application for this platform. We’ll be in touch if you qualify!"
 
        normalized_data_for_current = normalize_fields({current_question: user_value})
        data[current_question] = normalized_data_for_current.get(current_question, user_value)

        session["step"] += 1
        print(f"DEBUG: Session step after increment: {session['step']}")

        if session["step"] == len(questions):
            print(f"DEBUG: All questions answered. Attempting to send SMS for the first time immediately. (Current time: {datetime.datetime.now()})")
            phone_number = data.get("phone", "")
            if not phone_number:
                print("❌ Error: Phone number missing before SMS verification attempt.")
                return "⚠️ A required piece of information (phone number) is missing for verification. Please restart the qualification."

            formatted_phone_number = format_us_number(phone_number)
            success, error_msg = send_verification_sms(formatted_phone_number, session["code"])
            
            if success:
                session["verified"] = True
                return "Thanks! Please check your phone and enter the 4-digit code we just sent you to confirm your submission."
            else:
                session["step"] = questions.index("phone")
                data["phone"] = ""
                session["verified"] = False
                print(f"SMS sending failed for {formatted_phone_number}: {error_msg}. Resetting for phone re-entry.")
                return f"❌ {error_msg} Please enter a new 10-digit US phone number."

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

# --- NEW FUNCTION START: For Smart Form Submission ---
def process_qualification_submission_from_form(form_data: Dict[str, Any], ip_address: Optional[str] = None) -> Dict[str, Any]:
    """
    Processes all qualification data from a single form submission.
    Performs validation, qualification, conditional SMS/Monday.com push,
    and returns a structured result.

    Args:
        form_data (Dict[str, Any]): A dictionary containing all submitted form fields.
        ip_address (Optional[str]): User's IP address if captured from frontend.

    Returns:
        Dict[str, Any]: A dictionary with result status (e.g., 'sms_required', 'qualified', 'disqualified'),
                        and a message for the user.
    """
    try:
        # 1. Normalize fields (uses existing normalize_fields function)
        data = normalize_fields(form_data)
        
        # Add IP to data if available (for Monday.com push)
        if ip_address:
            data['ip'] = ip_address

        # 2. Perform comprehensive validation on all fields received from the form
        # This returns validation errors immediately if any field is invalid.
        
        # Email validation
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, data.get("email", "")):
            return {"status": "error", "message": "⚠️ Invalid email address format. Please provide a valid email (e.g., example@domain.com)."}
        
        # Phone validation
        if not is_us_number(data.get("phone", "")):
            return {"status": "error", "message": "⚠️ Invalid US phone number format. Please enter a 10-digit US number (e.g. 5551234567)."}

        # DOB validation and age calculation (now handles MM/DD/YYYY and age >= 18)
        dob_value = data.get("dob", "")
        if not dob_value:
            return {"status": "error", "message": "⚠️ Date of birth is missing."}
        try:
            age = calculate_age(dob_value) # This function now raises ValueError if under 18 or bad format
        except ValueError as e:
            return {"status": "error", "message": f"⚠️ {e}"} # Return specific age/DOB error

        # City/State validation
        city_state_value = data.get("city_state", "")
        if not city_state_value:
            return {"status": "error", "message": "⚠️ City and State information is missing."}

        # 3. Check for duplicate email (if desired on initial form submit)
        if check_duplicate_email(data.get("email", ""), MONDAY_BOARD_ID):
            # If duplicate, assume they know and provide a specific message
            # You might still log this duplicate to a 'duplicate' group on Monday.com if you want to track attempts
            duplicate_info = {"email": data.get("email"), "name": data.get("name", "Duplicate Form"), "source": "Form Submission"}
            push_to_monday(duplicate_info, "group_mkqb9ps4", False, ["Duplicate"], "", MONDAY_BOARD_ID)
            return {"status": "duplicate", "message": "⚠️ It looks like you’ve already submitted an application for this platform. We’ll be in touch if you qualify!"}

        # 4. Perform qualification logic
        coords = get_coords_from_city_state(city_state_value)
        if not coords or not coords.get("latitude") or not coords.get("longitude"):
            return {"status": "error", "message": "⚠️ Sorry, we couldn't determine your location from the provided City/State. Please ensure it's correct (e.g., 'Newark, NJ')."}

        distance_ok = is_within_distance(coords.get("latitude", 0.0), coords.get("longitude", 0.0))
        
        qualified = (
            data.get("tbi_year") == "Yes" and
            data.get("memory_issues") == "Yes" and
            data.get("english_fluent") == "Yes" and
            data.get("can_exercise") == "Yes" and
            data.get("can_mri") == "Yes" and
            distance_ok
        )
        # Note: age >= 18 is now enforced by calculate_age directly

        group = "new_group58505__1" if qualified else "new_group__1" # Qualified vs. Not Qualified group IDs
        tags = []
        if not distance_ok: tags.append("Too far")
        if data.get("handedness") == "Left-handed": tags.append("Left-handed")
        
        disqualification_reasons = []
        if not distance_ok: disqualification_reasons.append("you are located outside the eligible distance from our research site")
        # Age check now implicitly handled by calculate_age, but can add here for explicit messaging if needed
        # if age < 18: disqualification_reasons.append("you are under 18 years old") 
        if data.get("tbi_year") != "Yes": disqualification_reasons.append("you have not experienced a TBI at least one year ago")
        if data.get("memory_issues") != "Yes": disqualification_reasons.append("you do not have persistent memory problems")
        if data.get("english_fluent") != "Yes": disqualification_reasons.append("you are not fluent in English")
        if data.get("can_exercise") != "Yes": disqualification_reasons.append("you are not willing or able to exercise")
        if data.get("can_mri") != "Yes": disqualification_reasons.append("you are not able to undergo an MRI")
        
        # 5. Conditional SMS and Monday.com Push
        final_message = ""
        push_to_monday_flag = False
        sms_required_flag = False
        
        # Scenario 1: Qualified - Always SMS and Push
        if qualified:
            sms_required_flag = True
            push_to_monday_flag = True
            final_message = "✅ Thank you! Based on your answers, you may qualify for a TBI study."
            # No final message here, will be sent after SMS confirmation

        # Scenario 2: Not Qualified, but consented for future studies - SMS and Push
        elif not qualified and data.get("future_study_consent") == "I, confirm":
            sms_required_flag = True
            push_to_monday_flag = True # Even if disqualified, push if they want future studies
            final_message = "Thank you for your interest. Based on your answers, you do not meet the current study criteria, but since you opted for future studies, we will verify your contact information."
            # No final message here, will be sent after SMS confirmation

        # Scenario 3: Not Qualified AND NO consent for future studies - No SMS, No Push
        else: # not qualified and data.get("future_study_consent") == "I, do not confirm"
            push_to_monday_flag = False
            sms_required_flag = False
            if len(disqualification_reasons) > 0:
                reasons_str = ", and ".join([", ".join(disqualification_reasons[:-1]), disqualification_reasons[-1]]) if len(disqualification_reasons) > 1 else disqualification_reasons[0]
                final_message = f"Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria because {reasons_str}. We appreciate your time."
            else:
                final_message = "Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria. We appreciate your time."
            
            # If no SMS/push, this is the final message.
            return {"status": "disqualified_no_capture", "message": final_message}

        # If SMS is required, we return a specific status to the frontend
        # The frontend will then prompt for the code, and send it to a *new* verification endpoint.
        if sms_required_flag:
            # Generate a verification code for this specific submission
            verification_code = generate_verification_code()
            # Store data and code temporarily, linked to a submission ID (can be user's email, or a UUID)
            submission_id = str(uuid.uuid4())
            sessions[submission_id] = { # Reusing session dict for temporary storage
                "data": data,
                "code": verification_code,
                "push_to_monday_flag": push_to_monday_flag,
                "group": group,
                "qualified": qualified,
                "tags": tags,
                "ip_info_text": "\n".join([f"{k}: {v}" for k, v in get_location_from_ip(ip_address).items()]) if ip_address else ""
            }
            
            phone_number = data.get("phone", "")
            formatted_phone_number = format_us_number(phone_number)
            sms_success, sms_error_msg = send_verification_sms(formatted_phone_number, verification_code)
            
            if sms_success:
                return {"status": "sms_required", "submission_id": submission_id, "message": final_message + " Please check your phone for a 4-digit verification code."}
            else:
                # If SMS fails, delete the temporary session data
                del sessions[submission_id]
                print(f"SMS sending failed for form submission {formatted_phone_number}: {sms_error_msg}")
                return {"status": "error", "message": f"❌ Failed to send SMS for verification: {sms_error_msg}. Please check your phone number and try again."}

    except ValueError as ve:
        print(f"❌ Form submission data error (ValueError): {ve}")
        traceback.print_exc()
        return {"status": "error", "message": f"⚠️ Data validation error: {ve}"}
    except Exception as e:
        print(f"❌ General error processing form submission: {e}")
        traceback.print_exc()
        return {"status": "error", "message": "An unexpected error occurred during qualification. Please try again."}

# --- NEW FUNCTION END: For Smart Form Submission ---