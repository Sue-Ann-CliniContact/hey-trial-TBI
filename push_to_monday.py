import os
import requests
import json
import datetime # Import datetime for date formatting

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = "https://api.monday.com/v2"

headers = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json"
}

def push_to_monday(data: dict, group_id: str, qualified: bool, tags: list, ipinfo_text: str, board_id: int) -> dict:
    """
    Pushes data to Monday.com board.
    Args:
        data (dict): Dictionary containing user data.
        group_id (str): The Monday.com group ID to add the item to.
        qualified (bool): Whether the applicant qualified.
        tags (list): A list of tags to apply (e.g., ["Too far", "Left-handed"]).
                     Only valid tags for the 'dropdown' column should be passed.
        ipinfo_text (str): Formatted IP information text.
        board_id (int): The Monday.com board ID.
    Returns:
        dict: The JSON response from Monday.com API or an error dictionary.
    """
    def safe(val):
        return val if val is not None else ""

    def status_label(val):
        return {"label": val} if val else None

    # Define allowed tags for Monday.com 'dropdown' column
    # IMPORTANT: These tags MUST exist as labels in your Monday.com dropdown column!
    allowed_tags = ["Too far", "Left-handed", "fraudulent", "TBI", "Diabetes", "Depression", "Asthma"]
    
    study_interest_str = data.get("study_interest_keywords", "")
    if study_interest_str:
        interest_keywords = [
            keyword.strip() for keyword in study_interest_str.split(',') if keyword.strip()
        ]
        tags.extend(interest_keywords)

    filtered_tags = [tag for tag in tags if tag in allowed_tags]

    # --- FIX: Format DOB to YYYY-MM-DD for Monday.com 'date' column ---
    formatted_dob_for_monday = None
    dob_from_data = data.get("dob")
    if dob_from_data:
        try:
            # Parse MM/DD/YYYY
            date_obj = datetime.datetime.strptime(dob_from_data, "%m/%d/%Y").date()
            # Format to YYYY-MM-DD
            formatted_dob_for_monday = date_obj.strftime("%Y-%m-%d")
        except ValueError:
            print(f"WARNING: Could not parse DOB '{dob_from_data}' into MM/DD/YYYY for Monday.com formatting.")
            # If parsing fails, send as is or skip, Monday will likely reject
            formatted_dob_for_monday = dob_from_data
    # --- END FIX ---

    column_values = {
        "email": {
            "email": safe(data.get("email")),
            "text": safe(data.get("email"))
        },
        "phone": {
            "phone": safe(data.get("phone")),
            "text": safe(data.get("phone"))
        },
        "date": formatted_dob_for_monday, # USE THE FORMATTED DOB HERE
        "text9": safe(data.get("city_state")),
        "single_select": status_label(data.get("tbi_year")),
        "single_select3": status_label(data.get("memory_issues")),
        "single_select1": status_label(data.get("english_fluent")),
        "single_select7": status_label(data.get("handedness")),
        "single_select0": status_label(data.get("can_exercise")),
        "single_select9": status_label(data.get("can_mri")),
        "single_select__1": status_label(data.get("future_study_consent")),
        "boolean_mks56vyg": {"checked": qualified},
        "dropdown": {"labels": filtered_tags},
        "text": safe(data.get("source", "Form Submission")),
        "long_text_mks58x7v": {"text": ipinfo_text}
    }

    # Monday.com API requires JSON string for column_values
    # Double-encode the JSON string to be a valid GraphQL string literal
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
        # Monday.com can return 200 OK even with errors in the 'errors' array
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