import uuid
import random
import math
import datetime
import requests
import os
import re
import traceback
from typing import Dict, Any, Optional
import importlib.util # For dynamic module loading

# --- CHANGE START: Removed OpenAI import as chatbot/AI code is removed ---
# from openai import OpenAI
# --- CHANGE END ---

from twilio_sms import send_verification_sms, is_us_number, format_us_number
from push_to_monday import push_to_monday
from check_duplicate import check_duplicate_email

# --- GLOBAL CONSTANTS (API Keys, not study-specific) ---
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")
# User confirmed Maps_API_KEY is the env var name, so use it consistently
Maps_API_KEY = os.getenv("Maps_API_KEY") 

# --- CHANGE START: Removed OpenAI client initialization as chatbot/AI code is removed ---
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
# client = OpenAI(api_key=OPENAI_API_KEY)
# --- CHANGE END ---

# Session storage (for SMS verification temporary data)
sessions: Dict[str, Dict[str, Any]] = {}

# --- DYNAMIC CONFIGURATION LOADING ---
# This dictionary will store loaded study configurations
STUDY_CONFIGS: Dict[str, Dict[str, Any]] = {}

def load_study_config(study_id: str) -> Optional[Dict[str, Any]]:
    """
    Dynamically loads a study configuration from the 'configs' folder.
    Caches loaded configurations for efficiency.
    """
    if study_id in STUDY_CONFIGS:
        return STUDY_CONFIGS[study_id]

    try:
        # Construct the path to the config file
        # Assumes config files are named like study_<study_id>.py
        config_file_name = f"study_{study_id}.py"
        config_file_path = os.path.join(os.path.dirname(__file__), "configs", config_file_name)
        
        if not os.path.exists(config_file_path):
            print(f"❌ Config file not found for study_id: {study_id} at {config_file_path}")
            return None

        # Dynamically import the module
        spec = importlib.util.spec_from_file_location(f"configs.{study_id}", config_file_path)
        if spec is None:
            print(f"❌ Could not load module spec for study_id: {study_id}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Extract relevant constants from the loaded module
        config = {
            "KESSLER_COORDS": getattr(module, "KESSLER_COORDS", None),
            "DISTANCE_THRESHOLD_MILES": getattr(module, "DISTANCE_THRESHOLD_MILES", None),
            "MONDAY_BOARD_ID": getattr(module, "MONDAY_BOARD_ID", None),
            "QUALIFIED_GROUP_ID": getattr(module, "QUALIFIED_GROUP_ID", None),
            "DISQUALIFIED_GROUP_ID": getattr(module, "DISQUALIFIED_GROUP_ID", None),
            "DUPLICATE_GROUP_ID": getattr(module, "DUPLICATE_GROUP_ID", None),
            "FORM_FIELDS": getattr(module, "FORM_FIELDS", []),
            "MONDAY_COLUMN_MAPPINGS": getattr(module, "MONDAY_COLUMN_MAPPINGS", {}),
            "QUALIFICATION_CRITERIA": getattr(module, "QUALIFICATION_CRITERIA", {}),
            "MONDAY_DROPDOWN_ALLOWED_TAGS": getattr(module, "MONDAY_DROPDOWN_ALLOWED_TAGS", []),
            "STUDY_SUMMARY": getattr(module, "STUDY_SUMMARY", "No study summary provided."),
            "FORM_TITLE": getattr(module, "FORM_TITLE", "Qualification Form") # New: Form title from config
        }
        
        # Store for future use
        STUDY_CONFIGS[study_id] = config
        return config

    except Exception as e:
        print(f"❌ Error loading configuration for study_id '{study_id}': {e}")
        traceback.print_exc()
        return None

# --- Re-used Helper Functions (no change needed here) ---
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
    """Calculates age from a `MM/DD/YYYY` date string. Raises ValueError if format is incorrect or under 18."""
    try:
        birth_date = datetime.datetime.strptime(dob, "%m/%d/%Y").date()
        today = datetime.date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        
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
    # FIX: Use Maps_API_KEY as per user's environment variable name
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

def is_within_distance(user_lat: float, user_lon: float, target_coords: tuple, distance_threshold_miles: float) -> bool:
    """Checks if user's location is within the defined distance threshold from target coordinates."""
    distance = haversine_distance(user_lat, user_lon, *target_coords)
    return distance <= distance_threshold_miles

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
        # 'study_interest_keywords' is a new field and typically just stored as text, no normalization needed

    return normalized_data

# --- CHANGE START: Removed ask_gpt and chatbot specific questions/prompts ---
# Removed ask_gpt function
# Removed questions list
# Removed question_prompts dictionary
# Removed handle_input function
# --- CHANGE END ---

# --- NEW FUNCTION START: For Smart Form Submission ---
def process_qualification_submission_from_form(form_data: Dict[str, Any], study_id: str, ip_address: Optional[str] = None) -> Dict[str, Any]:
    """
    Processes all qualification data from a single form submission for a specific study.
    Performs validation, qualification, conditional SMS/Monday.com push,
    and returns a structured result.

    Args:
        form_data (Dict[str, Any]): A dictionary containing all submitted form fields.
        study_id (str): The ID of the study to load configuration for.
        ip_address (Optional[str]): User's IP address if captured from frontend.

    Returns:
        Dict[str, Any]: A dictionary with result status (e.g., 'sms_required', 'qualified', 'disqualified'),
                        and a message for the user.
    """
    # Load the specific study configuration
    study_config = load_study_config(study_id)
    if not study_config:
        return {"status": "error", "message": f"⚠️ Study configuration for '{study_id}' not found."}

    try:
        # 1. Normalize fields (uses existing normalize_fields function)
        data = normalize_fields(form_data)
        
        # Add IP to data if available (for Monday.com push)
        if ip_address:
            data['ip'] = ip_address

        # 2. Perform comprehensive validation on all fields received from the form
        
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
            age = calculate_age(dob_value) 
            if age < study_config["QUALIFICATION_CRITERIA"]["min_age"]:
                raise ValueError(f"Age must be {study_config['QUALIFICATION_CRITERIA']['min_age']} years or older for these studies.")
        except ValueError as e:
            return {"status": "error", "message": f"⚠️ {e}"}

        # City/State validation
        city_state_value = data.get("city_state", "")
        if not city_state_value:
            return {"status": "error", "message": "⚠️ City and State information is missing."}

        # 3. Check for duplicate email (uses study_config's board ID)
        if check_duplicate_email(data.get("email", ""), study_config["MONDAY_BOARD_ID"]):
            duplicate_info = {"email": data.get("email"), "name": data.get("name", "Duplicate Form"), "source": "Form Submission"}
            # FIX: Pass MONDAY_DROPDOWN_ALLOWED_TAGS for duplicate push
            push_to_monday(duplicate_info, study_config["DUPLICATE_GROUP_ID"], False, ["Duplicate"], "", study_config["MONDAY_BOARD_ID"], study_config["MONDAY_DROPDOWN_ALLOWED_TAGS"])
            return {"status": "duplicate", "message": "⚠️ It looks like you’ve already submitted an application for this platform. We’ll be in touch if you qualify!"}

        # 4. Perform qualification logic (uses study_config criteria)
        coords = get_coords_from_city_state(city_state_value)
        if not coords or not coords.get("latitude") or not coords.get("longitude"):
            return {"status": "error", "message": "⚠️ Sorry, we couldn't determine your location from the provided City/State. Please ensure it's correct (e.g., 'Newark, NJ')."}

        distance_ok = True
        if study_config["QUALIFICATION_CRITERIA"].get("distance_check_required", False):
            distance_ok = is_within_distance(coords.get("latitude", 0.0), coords.get("longitude", 0.0), 
                                             study_config["QUALIFICATION_CRITERIA"]["target_coords"], 
                                             study_config["QUALIFICATION_CRITERIA"]["distance_threshold_miles"])
        
        qualified = (
            data.get("tbi_year") == study_config["QUALIFICATION_CRITERIA"].get("tbi_year", "Yes") and
            data.get("memory_issues") == study_config["QUALIFICATION_CRITERIA"].get("memory_issues", "Yes") and
            data.get("english_fluent") == study_config["QUALIFICATION_CRITERIA"].get("english_fluent", "Yes") and
            data.get("can_exercise") == study_config["QUALIFICATION_CRITERIA"].get("can_exercise", "Yes") and
            data.get("can_mri") == study_config["QUALIFICATION_CRITERIA"].get("can_mri", "Yes") and
            (distance_ok if study_config["QUALIFICATION_CRITERIA"].get("distance_check_required", False) else True) # Only check if required
        )

        group = study_config["QUALIFIED_GROUP_ID"] if qualified else study_config["DISQUALIFIED_GROUP_ID"]
        tags = []
        if not distance_ok: tags.append("Too far")
        if data.get("handedness") == "Left-handed": tags.append("Left-handed")
        
        disqualification_reasons = []
        if not distance_ok: disqualification_reasons.append("you are located outside the eligible distance from our research site")
        if age < study_config["QUALIFICATION_CRITERIA"]["min_age"]: disqualification_reasons.append(f"you are under {study_config['QUALIFICATION_CRITERIA']['min_age']} years old")
        if data.get("tbi_year") != study_config["QUALIFICATION_CRITERIA"].get("tbi_year", "Yes"): disqualification_reasons.append("you have not experienced a TBI at least one year ago")
        if data.get("memory_issues") != study_config["QUALIFICATION_CRITERIA"].get("memory_issues", "Yes"): disqualification_reasons.append("you do not have persistent memory problems")
        if data.get("english_fluent") != study_config["QUALIFICATION_CRITERIA"].get("english_fluent", "Yes"): disqualification_reasons.append("you are not fluent in English")
        if data.get("can_exercise") != study_config["QUALIFICATION_CRITERIA"].get("can_exercise", "Yes"): disqualification_reasons.append("you are not willing or able to exercise")
        if data.get("can_mri") != study_config["QUALIFICATION_CRITERIA"].get("can_mri", "Yes"): disqualification_reasons.append("you are not able to undergo an MRI")
        
        # 5. Conditional SMS and Monday.com Push based on qualification and future_study_consent
        final_message_for_sms = "" # Message to show before SMS code entry
        push_to_monday_flag = False
        sms_required_flag = False
        
        # Scenario 1: Qualified - Always SMS and Push
        if qualified:
            sms_required_flag = True
            push_to_monday_flag = True
            final_message_for_sms = "✅ Thank you! Based on your answers, you may qualify for a TBI study."

        # Scenario 2: Not Qualified, but consented for future studies - SMS and Push
        elif not qualified and data.get("future_study_consent") == "I, confirm":
            sms_required_flag = True
            push_to_monday_flag = True # Even if disqualified, push if they want future studies
            final_message_for_sms = "Thank you for your interest. Based on your answers, you do not meet the current study criteria, but since you opted for future studies, we will verify your contact information."

        # Scenario 3: Not Qualified AND NO consent for future studies - No SMS, No Push
        else: # not qualified and data.get("future_study_consent") == "I, do not confirm"
            push_to_monday_flag = False
            sms_required_flag = False
            if len(disqualification_reasons) > 0:
                reasons_str = ", and ".join([", ".join(disqualification_reasons[:-1]), disqualification_reasons[-1]]) if len(disqualification_reasons) > 1 else disqualification_reasons[0]
                final_message_for_sms = f"Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria because {reasons_str}. We appreciate your time."
            else:
                final_message_for_sms = "Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria. We appreciate your time."
            
            # If no SMS/push, this is the final message.
            return {"status": "disqualified_no_capture", "message": final_message_for_sms}

        # If SMS is required, we proceed to send it and return specific status to frontend
        if sms_required_flag:
            verification_code = generate_verification_code()
            submission_id = str(uuid.uuid4())
            sessions[submission_id] = { # Store data and config for verification step
                "data": data,
                "code": verification_code,
                "push_to_monday_flag": push_to_monday_flag,
                "group": group,
                "qualified": qualified,
                "tags": tags,
                "ip_info_text": "\n".join([f"{k}: {v}" for k, v in get_location_from_ip(ip_address).items()]) if ip_address else "",
                "monday_board_id": study_config["MONDAY_BOARD_ID"] # Store board ID for verification step
            }
            
            phone_number = data.get("phone", "")
            formatted_phone_number = format_us_number(phone_number)
            sms_success, sms_error_msg = send_verification_sms(formatted_phone_number, verification_code)
            
            if sms_success:
                return {"status": "sms_required", "submission_id": submission_id, "message": final_message_for_sms + " Please check your phone for a 4-digit verification code."}
            else:
                del sessions[submission_id] # Clean up temporary session data if SMS fails
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