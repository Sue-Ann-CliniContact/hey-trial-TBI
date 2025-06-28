import os
import requests
import json
import datetime
from typing import Dict

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = "https://api.monday.com/v2"

headers = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json"
}

# FIX: Add monday_column_mappings and dropdown_allowed_tags to function signature
def push_to_monday(data: dict, group_id: str, qualified: bool, tags: list, ipinfo_text: str, board_id: int,
                   monday_column_mappings: Dict[str, str], dropdown_allowed_tags: list) -> dict:
    """
    Pushes data to Monday.com board using dynamic column mappings.
    Args:
        data (dict): Dictionary containing user data (form fields).
        group_id (str): The Monday.com group ID to add the item to.
        qualified (bool): Whether the applicant qualified.
        tags (list): A list of tags (e.g., ["Too far", "Left-handed"]).
        ipinfo_text (str): Formatted IP information text.
        board_id (int): The Monday.com board ID.
        monday_column_mappings (Dict[str, str]): Mapping of form field names to Monday.com column IDs.
        dropdown_allowed_tags (list): List of allowed labels for the 'dropdown' column on Monday.com.
    Returns:
        dict: The JSON response from Monday.com API or an error dictionary.
    """
    def safe(val):
        return val if val is not None else ""

    def status_label(val):
        return {"label": val} if val else None

    # Filter tags based on the allowed tags from the config
    filtered_dropdown_tags = [tag for tag in tags if tag in dropdown_allowed_tags]

    # --- Process study_interest_keywords for the 'text' (Source) column ---
    study_interest_keywords_from_data = data.get("study_interest_keywords", "").strip()
    source_field_value = study_interest_keywords_from_data if study_interest_keywords_from_data else "Form Submission"

    # --- Format DOB to YYYY-MM-DD for Monday.com 'date' column ---
    formatted_dob_for_monday = None
    dob_from_data = data.get("dob")
    if dob_from_data:
        try:
            date_obj = datetime.datetime.strptime(dob_from_data, "%m/%d/%Y").date()
            formatted_dob_for_monday = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            print(f"WARNING: Could not parse DOB '{dob_from_data}' into MM/DD/YYYY for Monday.com formatting. Sending original string.")
            formatted_dob_for_monday = dob_from_data

    # --- Dynamically build column_values using monday_column_mappings ---
    column_values = {}
    for form_field, monday_column_id in monday_column_mappings.items():
        value = data.get(form_field)
        
        # Handle specific column types as per Monday.com API requirements
        if monday_column_id == "email":
            column_values[monday_column_id] = {
                "email": safe(value),
                "text": safe(value)
            }
        elif monday_column_id == "phone":
            column_values[monday_column_id] = {
                "phone": safe(value),
                "text": safe(value)
            }
        elif monday_column_id == "date":
            # This is handled separately by formatted_dob_for_monday
            column_values[monday_column_id] = formatted_dob_for_monday
        elif monday_column_id.startswith("single_select"): # For single select columns
            column_values[monday_column_id] = status_label(value)
        elif monday_column_id == "boolean_mks56vyg": # For the qualified checkbox
            column_values[monday_column_id] = {"checked": qualified}
        # FIX: Map 'study_interest_keywords' to the 'text' column if specified in mappings
        elif monday_column_id == "text" and form_field == "study_interest_keywords":
            column_values[monday_column_id] = safe(source_field_value)
        # Handle the dropdown column for general tags
        elif monday_column_id == "dropdown":
            column_values[monday_column_id] = {"labels": filtered_dropdown_tags}
        elif monday_column_id == "long_text_mks58x7v": # For IP info
            column_values[monday_column_id] = {"text": ipinfo_text}
        else:
            # Default for other text/number columns not explicitly handled
            column_values[monday_column_id] = safe(value)
    
    # Ensure mandatory fields like 'text' (source) and 'long_text_mks58x7v' (IP) are always included
    # even if not explicitly in MONDAY_COLUMN_MAPPINGS for this study.
    # This assumes 'text' is the source column and 'long_text_mks58x7v' is the IP column.
    if "text" not in monday_column_mappings.values():
        column_values["text"] = safe(source_field_value)
    if "long_text_mks58x7v" not in monday_column_mappings.values():
        column_values["long_text_mks58x7v"] = {"text": ipinfo_text}

    # Monday.com API requires JSON string for column_values
    column_values_json_escaped = json.dumps(json.dumps(column_values))

    mutation = {
        "query": f'''
        mutation {{
          create_item (
            board_id: {board_id},
            group_id: "{group_id}",
            item_name: "{safe(data.get("name", "TBI Submission"))}",
            column_values: {column_values_json_escaped}
          ) {{
            id
          }}
        }}
        '''
    }

    try:
        print(f"DEBUG: Attempting to push to Monday.com Board ID: {board_id}, Group ID: {group_id}")
        print(f"DEBUG: Monday.com Mutation Payload: {json.dumps(mutation, indent=2)}")
        
        response = requests.post(MONDAY_API_URL, headers=headers, json=mutation)
        response.raise_for_status()
        
        monday_response = response.json()
        if monday_response.get("errors"):
            print(f"❌ MONDAY.COM API RETURNED ERRORS (but HTTP 200 OK): {json.dumps(monday_response.get('errors'), indent=2)}")
        else:
            print(f"✅ SUCCESS: Pushed to Monday.com. Response: {json.dumps(monday_response, indent=2)}")
        return monday_response
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP ERROR pushing to Monday: {http_err}")
        if response is not None:
            print("❌ Monday API Error Response (HTTPError):", response.text)
        return {"error": str(http_err), "response_content": response.text if response else ""}
    except Exception as e:
        print(f"❌ GENERAL ERROR pushing to Monday: {e}")
        return {"error": str(e)}