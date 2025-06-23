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
    Implements basic pagination to fetch up to 500 items across multiple pages.
    """
    # Max items per page is 100 on Monday.com API v2
    # We will fetch up to 5 pages (500 items) to reasonably check for duplicates.
    # For larger boards, a more robust pagination loop would be needed.
    page_limit = 5
    items_per_page = 100

    for page in range(page_limit):
        query = {
            "query": f'''
            query {{
              boards(ids: {board_id}) {{
                items_page(limit: {items_per_page}, query_params: {{ order_by: {{ column_id: "created_at", direction: asc }}, page: {page + 1} }}) {{
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

            if not items: # No more items on this page, or no items at all
                break

            for item in items:
                for column in item.get("column_values", []):
                    # Assuming 'email' is the column ID for email
                    if column["id"] == "email" and column.get("text", "").lower() == email.lower():
                        return True
            
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error checking duplicates on Monday.com (page {page + 1}): {http_err}")
            if response is not None:
                print("Monday API Error Response:", response.text)
            return False # Treat API errors as "no duplicate found" to allow submission
        except Exception as e:
            print(f"Error checking duplicates on Monday.com (page {page + 1}): {e}")
            return False # Treat other errors as "no duplicate found"

    return False