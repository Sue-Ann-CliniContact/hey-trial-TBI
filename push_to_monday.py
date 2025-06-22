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
    column_values = {
        "name": data.get("name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "date": data.get("dob"),
        "text9": data.get("city_state"),
        "single_select": data.get("tbi_year"),
        "single_select3": data.get("memory_issues"),
        "single_select1": data.get("english_fluent"),
        "single_select7": data.get("handedness"),
        "single_select0": data.get("can_exercise"),
        "single_select9": data.get("can_mri"),
        "single_select__1": data.get("future_study_consent"),
        "boolean_mks56vyg": qualified,
        "dropdown": {"labels": tags},
        "text": data.get("source", "Hey Trial Bot"),
        "long_text_mks58x7v": {"text": ipinfo_text}
    }

    mutation = {
        "query": f'''
        mutation {{
          create_item (
            board_id: {BOARD_ID},
            group_id: "{group_id}",
            item_name: "{data.get("name")}",
            column_values: {json.dumps(column_values)}
          ) {{
            id
          }}
        }}
        '''
    }

    response = requests.post(MONDAY_API_URL, headers=headers, json=mutation)
    return response.json()
