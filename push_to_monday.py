import os
import requests
import json

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = "https://api.monday.com/v2"
BOARD_ID = 2014579172

headers = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json"
}

def push_to_monday(data: dict, group_id: str, qualified: bool, tags: list, ipinfo_text: str) -> dict:
    def safe(val):
        return val if val is not None else ""

    column_values = {
        "email_mkrjhbqe": safe(data.get("email")),
        "phone_mkrj1e0m": safe(data.get("phone")),
        "date": safe(data.get("dob")),
        "text9": safe(data.get("city_state")),
        "single_select": safe(data.get("tbi_year")),
        "single_select3": safe(data.get("memory_issues")),
        "single_select1": safe(data.get("english_fluent")),
        "single_select7": safe(data.get("handedness")),
        "single_select0": safe(data.get("can_exercise")),
        "single_select9": safe(data.get("can_mri")),
        "single_select__1": safe(data.get("future_study_consent")),
        "boolean_mks56vyg": qualified,
        "dropdown": {"labels": tags},
        "text": safe(data.get("source", "Hey Trial Bot")),
        "long_text_mks58x7v": {"text": ipinfo_text}
    }

    mutation = {
        "query": f'''
        mutation {{
          create_item (
            board_id: {BOARD_ID},
            group_id: "{group_id}",
            item_name: "{safe(data.get("name", "TBI Submission"))}",
            column_values: {json.dumps(column_values)}
          ) {{
            id
          }}
        }}
        '''
    }

    try:
        response = requests.post(MONDAY_API_URL, headers=headers, json=mutation)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print("❌ Failed to push to Monday:", e)
        print("Response:", response.text)
        return {"error": str(e)}
