import os
import requests

MONDAY_API_KEY = os.getenv("MONDAY_API_KEY")
MONDAY_API_URL = "https://api.monday.com/v2"

headers = {
    "Authorization": MONDAY_API_KEY,
    "Content-Type": "application/json"
}

def check_duplicate_email(email: str, board_id: int) -> bool:
    """
    Checks if an email already exists on the specified Monday.com board.
    Fetches the first 100 items to check for duplicates, as 'page' argument
    is causing an error with current Monday.com API version.
    For boards with more than 100 items, a 'cursor' based pagination
    would be required for full coverage.
    """
    # Removed page and simplified the query to fetch just the first page (up to 100 items)
    query = {
        "query": f'''
        query {{
          boards(ids: {board_id}) {{
            items_page(limit: 100) {{ # Removed 'page' argument and 'query_params'
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
        response.raise_for_status() # Raises an HTTPError for bad responses (4xx or 5xx)
        data = response.json()

        items = data.get("data", {}).get("boards", [])[0].get("items_page", {}).get("items", [])

        for item in items:
            for column in item.get("column_values", []):
                if column["id"] == "email" and column.get("text", "").lower() == email.lower():
                    print(f"Duplicate email '{email}' found for item ID: {item['id']}")
                    return True
        return False

    except requests.exceptions.HTTPError as http_err:
        print(f"HTTP error checking duplicates on Monday.com: {http_err}")
        if response is not None:
            print("Monday API Error Response:", response.text)
        return False
    except Exception as e:
        print(f"Error checking duplicates on Monday.com: {e}")
        return False