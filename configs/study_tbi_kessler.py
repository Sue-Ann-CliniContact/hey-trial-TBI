# configs/study_tbi_kessler.py

# Import necessary types for type hinting
from typing import Dict, Any, List, Optional

# --- Study-Specific Constants ---
# These are specific to the Kessler TBI study's location
KESSLER_COORDS = (40.8255, -74.3594)
DISTANCE_THRESHOLD_MILES = 50

# Monday.com Board and Group IDs for this specific study
MONDAY_BOARD_ID = 2014579172
QUALIFIED_GROUP_ID = "new_group58505__1" # Group for qualified leads
DISQUALIFIED_GROUP_ID = "new_group__1" # Group for disqualified leads (no future consent)
DUPLICATE_GROUP_ID = "group_mkqb9ps4" # Group for duplicate emails

# --- Form Field Definitions ---
# This defines the structure and validation rules for the HTML form
FORM_FIELDS = [
    {"name": "name", "label": "Full Name", "type": "text", "placeholder": "John Doe", "required": True},
    {"name": "email", "label": "Email Address", "type": "email", "placeholder": "john.doe@example.com", "required": True, "validation": "email"},
    {"name": "phone", "label": "Phone Number (10-digit US)", "type": "tel", "placeholder": "5551234567", "required": True, "validation": "phone"},
    {"name": "dob", "label": "Date of Birth", "type": "text", "placeholder": "MM/DD/YYYY", "required": True, "validation": "dob_age", "description": "Format: Month/Day/Year (e.g., 01/15/1990)"},
    {"name": "city_state", "label": "City and State", "type": "text", "placeholder": "Newark, NJ", "required": True},
    {"name": "tbi_year", "label": "Experienced TBI at least one year ago?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "memory_issues", "label": "Persistent memory problems?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "english_fluent", "label": "Fluent in English?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "handedness", "label": "Handedness", "type": "radio", "options": ["Left-handed", "Right-handed"], "required": True},
    {"name": "can_exercise", "label": "Willing and able to exercise?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "can_mri", "label": "Able to undergo an MRI?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "future_study_consent", "label": "Contact for future studies?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "study_interest_keywords", "label": "What types of studies would you be interested in?", "type": "text", "placeholder": "e.g., Diabetes, Depression, Asthma, TBI", "description": "List comma separated keywords", "conditional_on": {"field": "future_study_consent", "value": "Yes"}}
]

# --- Monday.com Column Mappings ---
# Maps form field names to Monday.com column IDs
MONDAY_COLUMN_MAPPINGS = {
    "email": "email",
    "phone": "phone",
    "dob": "date", # Monday.com 'Date' column
    "city_state": "text9", # Assuming this is the correct column ID for City/State
    "tbi_year": "single_select",
    "memory_issues": "single_select3",
    "english_fluent": "single_select1",
    "handedness": "single_select7",
    "can_exercise": "single_select0",
    "can_mri": "single_select9",
    "future_study_consent": "single_select__1",
    # "study_interest_keywords" will be mapped to the 'text' column (Source) in push_to_monday
}

# --- Qualification Criteria ---
# Defines the specific rules for a 'qualified' lead for this study
QUALIFICATION_CRITERIA = {
    "min_age": 18,
    "tbi_year": "Yes",
    "memory_issues": "Yes",
    "english_fluent": "Yes",
    "can_exercise": "Yes",
    "can_mri": "Yes",
    "distance_check_required": True, # Set to True if distance check is needed
    "target_coords": KESSLER_COORDS, # The coordinates for distance check
    "distance_threshold_miles": DISTANCE_THRESHOLD_MILES # Max distance allowed
}

# --- Monday.com Dropdown Tags (for the 'dropdown' column) ---
# These tags MUST exist as labels in your Monday.com dropdown column!
MONDAY_DROPDOWN_ALLOWED_TAGS = ["Too far", "Left-handed", "fraudulent"] # Add any other fixed tags here

# --- General Study Information for AI (if AI chatbot is integrated) ---
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

FORM_TITLE = "Kessler TBI Study Qualification" # Example title for this specific form