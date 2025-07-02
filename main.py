# main.py
import uuid
import random
import math
import datetime
import requests
import os
import re
import traceback
from typing import Dict, Any, Optional
import importlib.util

from twilio_sms import send_verification_sms, is_us_number, format_us_number
from push_to_monday import push_to_monday
from check_duplicate import check_duplicate_email

IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")
Maps_API_KEY = os.getenv("Maps_API_KEY") 

sessions: Dict[str, Dict[str, Any]] = {}
STUDY_CONFIGS: Dict[str, Dict[str, Any]] = {}

def load_study_config(study_id: str) -> Optional[Dict[str, Any]]:
    """
    Dynamically loads a study configuration from the 'configs' folder.
    Caches loaded configurations for efficiency.
    """
    if study_id in STUDY_CONFIGS:
        return STUDY_CONFIGS[study_id]

    try:
        config_file_name = f"study_{study_id}.py"
        config_file_path = os.path.join(os.path.dirname(__file__), "configs", config_file_name)
        
        if not os.path.exists(config_file_path):
            print(f"❌ Config file not found for study_id: {study_id} at {config_file_path}")
            return None

        spec = importlib.util.spec_from_file_location(f"configs.{study_id}", config_file_path)
        if spec is None:
            print(f"❌ Could not load module spec for study_id: {study_id}")
            return None

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        config = {
            "MONDAY_BOARD_ID": getattr(module, "MONDAY_BOARD_ID", None),
            "QUALIFIED_GROUP_ID": getattr(module, "QUALIFIED_GROUP_ID", None),
            "DISQUALIFIED_GROUP_ID": getattr(module, "DISQUALIFIED_GROUP_ID", None),
            "DUPLICATE_GROUP_ID": getattr(module, "DUPLICATE_GROUP_ID", None),
            "FORM_FIELDS": getattr(module, "FORM_FIELDS", []),
            "MONDAY_COLUMN_MAPPINGS": getattr(module, "MONDAY_COLUMN_MAPPINGS", {}),
            "QUALIFICATION_RULES": getattr(module, "QUALIFICATION_RULES", []),
            "MONDAY_DROPDOWN_ALLOWED_TAGS": getattr(module, "MONDAY_DROPDOWN_ALLOWED_TAGS", []),
            "STUDY_SUMMARY": getattr(module, "STUDY_SUMMARY", "No study summary provided."),
            "FORM_TITLE": getattr(module, "FORM_TITLE", "Qualification Form"),
            "SMS_MESSAGES": getattr(module, "SMS_MESSAGES", {}),
            "TARGET_COORDS": getattr(module, "KESSLER_COORDS", None) if study_id == "tbi_kessler" else getattr(module, "CONCORD_COORDS", None),
            "DISTANCE_THRESHOLD_MILES": getattr(module, "DISTANCE_THRESHOLD_MILES", None)
        }
        
        STUDY_CONFIGS[study_id] = config
        return config

    except Exception as e:
        print(f"❌ Error loading configuration for study_id '{study_id}': {e}")
        traceback.print_exc()
        return None

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
    """Calculates age from a `MM/DD/YYYY` date string."""
    try:
        birth_date = datetime.datetime.strptime(dob, "%m/%d/%Y").date()
        today = datetime.date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return age
    except ValueError:
        raise ValueError("Invalid date of birth format. Please use MM/DD/YYYY.")

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

def is_within_distance(user_lat: float, user_lon: float, target_coords: tuple, distance_threshold_miles: float) -> bool:
    """Checks if user's location is within the defined distance threshold from target coordinates."""
    distance = haversine_distance(user_lat, user_lon, *target_coords)
    return distance <= distance_threshold_miles

def normalize_fields(data: dict) -> dict:
    """Normalizes specific fields in the data dictionary (Yes/No, handedness, consent, Not Applicable)."""
    normalized_data = data.copy()

    # Define common normalization rules
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

    def normalize_not_applicable(value):
        val = str(value).strip().lower()
        if val in ["not applicable", "n/a"]:
            return "Not Applicable"
        return value

    for key, val in normalized_data.items():
        if key in ["tbi_year", "memory_issues", "english_fluent", "can_exercise", "can_mri",
                   "ckd_gfr", "previous_bupropion", "current_depression_medication",
                   "untreatable_cancer", "liver_disease", "seizure_disorder", "dialysis",
                   "current_depression_therapy", "gfr_less_45", "psychotherapy_treatment"]: # Added psychotherapy_treatment
            normalized_data[key] = normalize_yes_no(val)
        elif key == "handedness":
            normalized_data[key] = normalize_handedness(val)
        elif key == "future_study_consent":
            normalized_data[key] = normalize_consent(val)
        elif key == "kidney_transplant_6months":
            normalized_data[key] = normalize_not_applicable(normalize_yes_no(val))
    
    return normalized_data

def process_qualification_submission_from_form(form_data: Dict[str, Any], study_id: str, ip_address: Optional[str] = None) -> Dict[str, Any]:
    """
    Processes all qualification data from a single form submission for a specific study.
    Performs validation, qualification, conditional SMS/Monday.com push,
    and returns a structured result.
    """
    study_config = load_study_config(study_id)
    if not study_config:
        return {"status": "error", "message": f"⚠️ Study configuration for '{study_id}' not found."}

    try:
        data = normalize_fields(form_data)
        if ip_address:
            data['ip'] = ip_address

        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, data.get("email", "")):
            return {"status": "error", "message": "⚠️ Invalid email address format. Please provide a valid email (e.g., example@domain.com)."}
        
        if not is_us_number(data.get("phone", "")):
            return {"status": "error", "message": "⚠️ Invalid US phone number format. Please enter a 10-digit US number (e.g. 5551234567)."}

        age = None
        try:
            age = calculate_age(data.get("dob", ""))
        except ValueError as e:
            return {"status": "error", "message": f"⚠️ {e}"}

        city_state_value = data.get("city_state", "")
        if not city_state_value:
            return {"status": "error", "message": "⚠️ City and State information is missing."}

        if check_duplicate_email(data.get("email", ""), study_config["MONDAY_BOARD_ID"]):
            duplicate_info = {"email": data.get("email"), "name": data.get("name", "Duplicate Form"), "source": "Form Submission"}
            push_to_monday(duplicate_info, study_config["DUPLICATE_GROUP_ID"], False, ["Duplicate"], "", study_config["MONDAY_BOARD_ID"], study_config["MONDAY_COLUMN_MAPPINGS"], study_config["MONDAY_DROPDOWN_ALLOWED_TAGS"])
            return {"status": "duplicate", "message": "⚠️ It looks like you’ve already submitted an application for this platform. We’ll be in touch if you qualify!"}

        qualified = True
        disqualification_reasons = []
        tags = []
        
        for rule in study_config["QUALIFICATION_RULES"]:
            rule_met = False
            field_value = data.get(rule["field"])

            # Handle conditional rules BEFORE evaluating the rule itself
            is_conditional = rule.get("conditional")
            if is_conditional:
                controlling_field_value = data.get(is_conditional["field"])
                required_control_value = is_conditional["value"]
                skip_if_value = is_conditional.get("skip_if_value")

                if controlling_field_value != required_control_value:
                    # If the condition is NOT met, skip this rule. It doesn't disqualify if not applicable.
                    rule_met = True # Consider it 'met' (not disqualifying)
                    continue
                
                if skip_if_value is not None and field_value == skip_if_value:
                    # If the field's value matches a skip value (e.g., "Not Applicable"), skip this rule.
                    rule_met = True # Consider it 'met' (not disqualifying)
                    continue

            # Process different rule types
            if rule.get("type") == "age":
                if age is not None and age >= rule["value"]:
                    rule_met = True
            elif rule.get("type") == "distance":
                user_coords = get_coords_from_city_state(city_state_value)
                if not user_coords or not user_coords.get("latitude") or not user_coords.get("longitude"):
                    # If we can't get coords, this rule disqualifies if distance is required
                    rule_met = False # Will lead to disqualification below
                    disqualification_reasons.append(rule["disqual_message"]) # Add reason immediately
                    tags.append("Location unknown")
                else:
                    target_coords = study_config["TARGET_COORDS"]
                    distance_threshold_miles = study_config["DISTANCE_THRESHOLD_MILES"]
                    if target_coords and distance_threshold_miles is not None:
                        if is_within_distance(user_coords.get("latitude"), user_coords.get("longitude"), 
                                             target_coords, 
                                             distance_threshold_miles):
                            rule_met = True
                    else:
                        print(f"WARNING: Distance rule present but TARGET_COORDS or DISTANCE_THRESHOLD_MILES not found in config for {study_id}. Skipping distance check.")
                        rule_met = True # Consider met if configuration is incomplete
                
                if not rule_met: # Only add "Too far" tag if specifically disqualified by distance
                    if "Location unknown" not in tags: # Avoid double tag
                        tags.append("Too far")
            elif rule.get("type") == "complex":
                # Process sub-rules for complex types
                complex_block_qualified = True
                complex_block_reasons = []

                sub_rules = rule.get("complex_rules", [])
                for sub_rule in sub_rules:
                    sub_rule_field_value = data.get(sub_rule["field"])
                    sub_rule_met_internal = False

                    # Handle conditional logic for sub-rules
                    is_sub_rule_conditional = sub_rule.get("conditional")
                    if is_sub_rule_conditional:
                        controlling_field_sub_value = data.get(is_sub_rule_conditional["field"])
                        required_control_sub_value = is_sub_rule_conditional["value"]
                        skip_sub_value = is_sub_rule_conditional.get("skip_if_value")

                        if controlling_field_sub_value != required_control_sub_value:
                            sub_rule_met_internal = True # Rule is "met" because it's not applicable
                            continue
                        
                        if skip_sub_value is not None and sub_rule_field_value == skip_sub_value:
                            sub_rule_met_internal = True # Rule is "met" because it's not applicable
                            continue

                    # Evaluate the actual sub-rule
                    if sub_rule["operator"] == "equals":
                        if sub_rule_field_value == sub_rule["value"]:
                            sub_rule_met_internal = True
                    elif sub_rule["operator"] == "not_equals":
                        if sub_rule_field_value != sub_rule["value"]:
                            sub_rule_met_internal = True
                    elif sub_rule["operator"] == "in_list":
                        if sub_rule_field_value in sub_rule["value"]:
                            sub_rule_met_internal = True
                    # Add other operators as needed for sub-rules
                    
                    if not sub_rule_met_internal:
                        complex_block_qualified = False
                        complex_block_reasons.append(sub_rule.get("disqual_message", f"Rule for {sub_rule['field']} was not met."))
                        # Don't break here, collect all reasons in complex block
                
                rule_met = complex_block_qualified # The complex rule is met if all its sub-rules were met
                if not rule_met:
                    disqualification_reasons.extend(complex_block_reasons)
                    # If complex block has overall disqual_message and no specific reasons, add it
                    if not complex_block_reasons and rule.get("disqual_message"):
                        disqualification_reasons.append(rule["disqual_message"])
            else: # Standard field comparison rules (equals, not_equals, in_list etc.)
                if rule["operator"] == "equals":
                    if field_value == rule["value"]:
                        rule_met = True
                elif rule["operator"] == "not_equals":
                    if field_value != rule["value"]:
                        rule_met = True
                elif rule["operator"] == "in_list":
                    if field_value in rule["value"]:
                        rule_met = True
                # Add other operators as needed (greater_than, less_than etc.)

            # Final check for the current rule if it was processed and not met
            if not rule_met:
                qualified = False
                # If the disqualification reason was not already added by specific handlers (like distance/complex)
                if rule.get("disqual_message") and rule.get("type") not in ["age", "distance", "complex"]:
                    disqualification_reasons.append(rule["disqual_message"])
                # Also add reasons from complex_block_reasons if they are collected there

        # Handle handedness tag (general, not a disqualifier for now, just a tag)
        if data.get("handedness") == "Left-handed":
            tags.append("Left-handed")

        # 5. Determine final group, tags, and SMS/Monday.com push logic
        final_message_for_sms = ""
        push_to_monday_flag = False
        sms_required_flag = False
        
        sms_qualified_msg = study_config["SMS_MESSAGES"].get("qualified", "✅ Thank you! Based on your answers, you may qualify for a study.")
        sms_future_consent_msg = study_config["SMS_MESSAGES"].get("future_consent", "Thank you for your interest. Based on your answers, you do not meet the current study criteria, but since you opted for future studies, we will verify your contact information.")
        sms_prompt_msg = study_config["SMS_MESSAGES"].get("sms_prompt", "Your confirmation code is {}. Please enter this code to confirm your submission.")

        if qualified:
            sms_required_flag = True
            push_to_monday_flag = True
            group = study_config["QUALIFIED_GROUP_ID"]
            final_message_for_sms = sms_qualified_msg

        elif not qualified and data.get("future_study_consent") == "I, confirm":
            sms_required_flag = True
            push_to_monday_flag = True
            group = study_config["DISQUALIFIED_GROUP_ID"] # Still disqualified, but capture for future
            final_message_for_sms = sms_future_consent_msg

        else: # not qualified and data.get("future_study_consent") == "I, do not confirm"
            push_to_monday_flag = False
            sms_required_flag = False
            group = study_config["DISQUALIFIED_GROUP_ID"] # No push, but conceptually in disqualified group if we tracked it
            if len(disqualification_reasons) > 0:
                # Remove duplicates from reasons and format string
                unique_reasons = list(dict.fromkeys(disqualification_reasons))
                reasons_str = ", and ".join([", ".join(unique_reasons[:-1]), unique_reasons[-1]]) if len(unique_reasons) > 1 else unique_reasons[0]
                final_message_for_sms = f"Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria because {reasons_str}. We appreciate your time."
            else:
                final_message_for_sms = "Thank you for your interest. Unfortunately, based on your answers, you do not meet the current study criteria. We appreciate your time."
            
            return {"status": "disqualified_no_capture", "message": final_message_for_sms}

        ip_info_data = get_location_from_ip(ip_address) if ip_address else {}
        ip_info_text_parts = []
        if ip_info_data:
            ip_info_text_parts.append(f"IP: {ip_info_data.get('ip', 'N/A')}")
            if ip_info_data.get('city') and ip_info_data.get('region'):
                ip_info_text_parts.append(f"Location (IP): {ip_info_data['city']}, {ip_info_data['region']}, {ip_info_data.get('country', '')}")
            if ip_info_data.get('org'):
                ip_info_text_parts.append(f"Org: {ip_info_data['org']}")
        ip_info_text = "\n".join(ip_info_text_parts)

        if sms_required_flag:
            verification_code = generate_verification_code()
            submission_id = str(uuid.uuid4())
            
            full_sms_message_body = sms_prompt_msg.format(verification_code) # ONLY this part is sent via SMS

            sessions[submission_id] = {
                "data": data,
                "code": verification_code,
                "push_to_monday_flag": push_to_monday_flag,
                "group": group,
                "qualified": qualified,
                "tags": tags,
                "ip_info_text": ip_info_text,
                "monday_board_id": study_config["MONDAY_BOARD_ID"],
                "monday_column_mappings": study_config["MONDAY_COLUMN_MAPPINGS"],
                "monday_dropdown_allowed_tags": study_config["MONDAY_DROPDOWN_ALLOWED_TAGS"]
            }
            
            phone_number = data.get("phone", "")
            formatted_phone_number = format_us_number(phone_number)
            
            sms_success, sms_error_msg = send_verification_sms(formatted_phone_number, full_sms_message_body)
            
            if sms_success:
                return {"status": "sms_required", "submission_id": submission_id, "message": final_message_for_sms}
            else:
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