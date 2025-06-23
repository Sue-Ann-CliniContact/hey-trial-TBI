import os
import requests

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = "https://api.monday.com/v2"
BOARD_ID = 2014579172  # Hey Trial - TBI board ID

headers = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json"
}

def check_duplicate_email(email: str) -> bool:
    query = {
        "query": f'''
        query {{
          items_by_column_values(
            board_id: {BOARD_ID},
            column_id: "email_mkrjhbqe",
            column_value: "{email}"
          ) {{
            id
            name
          }}
        }}
        '''
    }

    try:
        response = requests.post(MONDAY_API_URL, headers=headers, json=query)
        response.raise_for_status()
        data = response.json()
        items = data.get("data", {}).get("items_by_column_values", [])
        return len(items) > 0
    except Exception as e:
        print(f"Error checking duplicates: {e}")
        if response is not None:
            print("Response:", response.text)
        return False
