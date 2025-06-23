import os
import requests
import json

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

    # Validate tags against allowed Monday.com dropdown labels
    # This assumes "dropdown" column allows "Too far", "Left-handed", "fraudulent"
    allowed_tags = ["Too far", "Left-handed", "fraudulent"]
    filtered_tags = [tag for tag in tags if tag in allowed_tags]

    column_values = {
        "email": {
            "email": safe(data.get("email")),
            "text": safe(data.get("email"))
        },
        "phone": {
            "phone": safe(data.get("phone")),
            "text": safe(data.get("phone"))
        },
        "date": safe(data.get("dob")),
        "text9": safe(data.get("city_state")),
        "single_select": status_label(data.get("tbi_year")),
        "single_select3": status_label(data.get("memory_issues")),
        "single_select1": status_label(data.get("english_fluent")),
        "single_select7": status_label(data.get("handedness")),  # Use "Left-handed"/"Right-handed"
        "single_select0": status_label(data.get("can_exercise")),
        "single_select9": status_label(data.get("can_mri")),
        "single_select__1": status_label(data.get("future_study_consent")),  # Use "I, confirm" or "I, do not confirm"
        "boolean_mks56vyg": {"checked": qualified},
        "dropdown": {"labels": filtered_tags},
        "text": safe(data.get("source", "Hey Trial Bot")), # Default source
        "long_text_mks58x7v": {"text": ipinfo_text}
    }

    # Monday.com API requires JSON string for column_values
    column_values_json = json.dumps(column_values)

    mutation = {
        "query": f'''
        mutation {{
          create_item (
            board_id: {board_id},
            group_id: "{group_id}",
            item_name: "{safe(data.get("name", "TBI Submission"))}",
            column_values: {column_values_json}
          ) {{
            id
          }}
        }}
        '''
    }

    try:
        response = requests.post(MONDAY_API_URL, headers=headers, json=mutation)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as http_err:
        print(f"❌ HTTP error pushing to Monday: {http_err}")
        if response is not None:
            print("Response content:", response.text)
        return {"error": str(http_err), "response_content": response.text if response else ""}
    except Exception as e:
        print(f"❌ Failed to push to Monday: {e}")
        return {"error": str(e)}