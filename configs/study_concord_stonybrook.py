# configs/study_concord_stonybrook.py

from typing import Dict, Any, List, Optional

# --- Study-Specific Constants ---
# Coordinates for 100 Nicolls Rd, Stony Brook, NY 11794, United States
# Looked up using Google Maps (approximate center)
CONCORD_COORDS = (40.9142, -73.1250)
DISTANCE_THRESHOLD_MILES = 50

# Monday.com Board and Group IDs for this specific study
MONDAY_BOARD_ID = 2030248088 # Provided in your query
# Group IDs from the Monday.com query response are for STATUS column labels, not actual groups.
# You need to get the actual GROUP IDs from your Monday.com board (e.g., "Qualified Leads", "Disqualified Leads")
# For now, using placeholders. Please REPLACE these with actual group IDs from your Monday.com board.
QUALIFIED_GROUP_ID = "new_group58505__1" # Common default group for new items, or get actual 'Qualified' group ID
DISQUALIFIED_GROUP_ID = "new_group__1" # Example: an actual group ID for disqualified leads on your board
DUPLICATE_GROUP_ID = "group_mkqb9ps4" # Example: an actual group ID for duplicate leads on your board

# --- Form Field Definitions ---
FORM_FIELDS = [
    {"name": "name", "label": "Full Name", "type": "text", "placeholder": "John Doe", "required": True},
    {"name": "email", "label": "Email Address", "type": "email", "placeholder": "john.doe@example.com", "required": True, "validation": "email"},
    {"name": "phone", "label": "Phone Number (10-digit US)", "type": "tel", "placeholder": "5551234567", "required": True, "validation": "phone"},
    {"name": "dob", "label": "Date of Birth", "type": "text", "placeholder": "MM/DD/YYYY", "required": True, "validation": "dob_age", "description": "Format: Month/Day/Year (e.g., 01/15/1990)"},
    {"name": "city_state", "label": "City and State", "type": "text", "placeholder": "Stony Brook, NY", "required": True},
    {"name": "ckd_gfr", "label": "Do you have chronic kidney disease (CKD) at stage 3b, 4, or 5, or have you had a kidney transplant with a GFR less than 45?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "kidney_transplant_6months", "label": "If you have a kidney transplant, has it been at least 6 months since your transplantation?", "type": "radio", "options": ["Yes", "No", "Not Applicable"], "required": True, "conditional_on": {"field": "ckd_gfr", "value": "Yes"}},
    {"name": "gfr_less_45", "label": "Is your most recent kidney filtration rate (GFR) less than 45?", "type": "radio", "options": ["Yes", "No"], "required": True, "conditional_on": {"field": "ckd_gfr", "value": "Yes"}},
    {"name": "previous_bupropion", "label": "Have you ever been treated with bupropion (Wellbutrin)?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "current_depression_medication", "label": "Are you currently taking medication for depression?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "untreatable_cancer", "label": "Do you have terminal lung disease, untreatable cancer or are you receiving chemotherapy or radiation for cancer?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "liver_disease", "label": "Do you have liver disease?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "seizure_disorder", "label": "Do you have a seizure disorder?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "dialysis", "label": "Are you currently receiving hemodialysis or peritoneal dialysis?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "current_depression_therapy", "label": "Are you currently receiving therapy for depression?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "medications_list", "label": "Please list all medications you are currently taking:", "type": "text", "placeholder": "e.g., Lisinopril, Metformin", "required": False}, # Not required by qualifications, so made optional
    {"name": "future_study_consent", "label": "Contact for future studies?", "type": "radio", "options": ["Yes", "No"], "required": True},
    {"name": "study_interest_keywords", "label": "What types of studies would you be interested in?", "type": "text", "placeholder": "e.g., Kidney disease, Depression, Diabetes", "description": "List comma separated keywords", "conditional_on": {"field": "future_study_consent", "value": "Yes"}}
]

# --- QUALIFICATION RULES ---
QUALIFICATION_RULES = [
    {"field": "age", "operator": "greater_than_or_equal", "value": 18, "type": "age", "disqual_message": "you are under 18 years old"},
    {"field": "distance", "operator": "less_than_or_equal", "value": "threshold", "type": "distance", "disqual_message": "you are located outside the eligible distance from our research site"},

    # Exclusionary criteria (simple checks)
    {"field": "previous_bupropion", "operator": "equals", "value": "No", "disqual_message": "you have previously been treated with bupropion"},
    {"field": "current_depression_medication", "operator": "equals", "value": "No", "disqual_message": "you are currently taking antidepressant medication"},
    {"field": "untreatable_cancer", "operator": "equals", "value": "No", "disqual_message": "you have untreatable cancer"},
    {"field": "liver_disease", "operator": "equals", "value": "No", "disqual_message": "you suffer from liver disease"},
    {"field": "seizure_disorder", "operator": "equals", "value": "No", "disqual_message": "you have a seizure disorder"},
    {"field": "dialysis", "operator": "equals", "value": "No", "disqual_message": "you are currently receiving hemodialysis or peritoneal dialysis"},
    {"field": "current_depression_therapy", "operator": "equals", "value": "No", "disqual_message": "you are currently receiving therapy for depression"},

    # CKD/GFR Complex Logic - Represented as a sequence of dependent rules
    # Rule 1: Must have CKD stage 3b, 4, or 5 OR kidney transplant with GFR < 45
    {"field": "ckd_gfr", "operator": "equals", "value": "Yes", "disqual_message": "you do not have chronic kidney disease (CKD) at the required stage or a kidney transplant with the specified GFR", "rule_id": "ckd_main_check"},

    # Rule 2: If ckd_gfr is Yes, and kidney_transplant_6months is NOT "Not Applicable", then it must be "Yes"
    # This rule is conditional on 'ckd_main_check' being true.
    # And its application depends on the 'kidney_transplant_6months' answer
    {"field": "kidney_transplant_6months", "operator": "equals", "value": "Yes", "disqual_message": "your kidney transplant has not been at least 6 months ago", "depends_on": {"rule_id": "ckd_main_check", "value_of": "ckd_gfr", "is": "Yes", "skip_if_field": "kidney_transplant_6months", "skip_value": "Not Applicable"}},

    # Rule 3: If ckd_gfr is Yes, then gfr_less_45 must be Yes
    # This rule is conditional on 'ckd_main_check' being true.
    {"field": "gfr_less_45", "operator": "equals", "value": "Yes", "disqual_message": "your most recent kidney filtration rate (GFR) is not less than 45", "depends_on": {"rule_id": "ckd_main_check", "value_of": "ckd_gfr", "is": "Yes"}}
]

# --- Monday.com Column Mappings ---
MONDAY_COLUMN_MAPPINGS = {
    "email": "email",
    "phone": "phone",
    "dob": "date", # Maps to "Your Date of Birth" column ID: date
    "city_state": "text9", # Maps to "City" column ID: text9
    "ckd_gfr": "single_select", # Maps to "Do you have chronic kidney disease (CKD)..." column ID: single_select
    "kidney_transplant_6months": "single_select3", # Maps to "If you have a kidney transplant..." column ID: single_select3
    "gfr_less_45": "single_select1", # Maps to "Is your most recent kidney filtration rate (GFR)..." column ID: single_select1
    "previous_bupropion": "single_select0", # Maps to "Have you ever been treated with bupropion..." column ID: single_select0
    "current_depression_medication": "color_mksegmrh", # Maps to "Are you currently taking medication for depression?" column ID: color_mksegmrh
    "untreatable_cancer": "color_mksekj8m", # Maps to "Do you have terminal lung disease..." column ID: color_mksekj8m
    "liver_disease": "color_mkse8bj6", # Maps to "Do you have liver disease?" column ID: color_mkse8bj6
    "seizure_disorder": "color_mksezh83", # Maps to "Do you have a seizure disorder?" column ID: color_mksezh83
    "dialysis": "color_mkseyk6t", # Maps to "Are you currently receiving hemodialysis or peritoneal dialysis?" column ID: color_mkseyk6t
    "current_depression_therapy": "single_select7", # Maps to "Are you currently receiving therapy for depression?" column ID: single_select7
    "medications_list": "text_mksed511", # Maps to "Please list all medications you are currently taking:" column ID: text_mksed511
    "future_study_consent": "single_select__1", # Maps to "Consent Request for Future Studies" column ID: single_select__1
    "stony_brook_qualified": "boolean_mks56vyg", # Maps to "Stony Brook Study Qualified" checkbox
    "study_interest_keywords": "text_mksew3kd" # Maps to "Other Studies" column ID: text_mksew3kd (If source is 'text', then 'study_interest_keywords' should go here)
}

# --- Monday.com Dropdown Tags (for the 'dropdown' column) ---
# Labels from your provided Monday.com dropdown column JSON: "Too far", "Left-handed", "fraudulent"
MONDAY_DROPDOWN_ALLOWED_TAGS = ["Too far", "Stony Brook Study", "fraudulent"] # Added new tag

# --- General Study Information ---
STUDY_SUMMARY = """
This study focuses on individuals with chronic kidney disease (CKD) at specific stages (3b, 4, or 5 with GFR under 45), or those who have had a kidney transplant with a GFR under 45 for at least 6 months. It excludes individuals previously treated with bupropion, currently on antidepressant medication, suffering from untreatable cancer or liver disease, seizure disorder, or receiving dialysis. Participants should be 18 years or older. There are 2 in-person visits required at the research site near Stony Brook, NY.
"""

FORM_TITLE = "Concord Study Qualification - Stony Brook"

# --- Study-Specific SMS Messages ---
SMS_MESSAGES = {
    "qualified": "✅ Congratulations! Based on your answers, you may qualify for the Concord study.",
    "future_consent": "Thank you for your interest. Based on your answers, you do not meet the current Concord study criteria, but since you opted for future studies, we will verify your contact information.",
    "sms_prompt": "Your confirmation code for the Concord Study is {}. Please enter this code to confirm your submission." # CHANGE THIS LINE
}