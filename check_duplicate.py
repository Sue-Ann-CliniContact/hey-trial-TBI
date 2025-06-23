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
          boards(ids: {BOARD_ID}) {{
            items_page(limit: 100) {{
              items {{
                id
                name
                column_values {{
                  id
                  text
                }}
              }}
            }}
          }}
        }}
        '''
    }

    try:
        response = requests.post(MONDAY_API_URL, headers=headers, json=query)
        response.raise_for_status()
        data = response.json()

        items = data.get("data", {}).get("boards", [])[0].get("items_page", {}).get("items", [])
        for item in items:
            for column in item.get("column_values", []):
                if column["id"] == "email" and column.get("text", "").lower() == email.lower():
                    return True
        return False
    except Exception as e:
        print(f"Error checking duplicates: {e}")
        if response is not None:
            print("Response:", response.text)
        return False