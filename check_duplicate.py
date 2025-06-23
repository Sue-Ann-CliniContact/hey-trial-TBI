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
    page_limit = 5
    items_per_page = 100

    for page in range(page_limit):
        query = {
            "query": f'''
            query {{
              boards(ids: {board_id}) {{
                items_page(limit: {items_per_page}, page: {page + 1}) {{ # 'page' moved outside 'query_params'
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

        # NOTE: I've removed the `query_params` for `order_by` from the query in the fix above,
        # as it was not directly causing the error but was a separate parameter.
        # If you need specific ordering, it would be a separate argument like:
        # items_page(limit: {items_per_page}, page: {page + 1}, order_by: {{ column_id: "created_at", direction: asc }})

        try:
            response = requests.post(MONDAY_API_URL, headers=headers, json=query)
            response.raise_for_status()
            data = response.json()

            items = data.get("data", {}).get("boards", [])[0].get("items_page", {}).get("items", [])

            if not items:
                break

            for item in items:
                for column in item.get("column_values", []):
                    if column["id"] == "email" and column.get("text", "").lower() == email.lower():
                        return True

        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error checking duplicates on Monday.com (page {page + 1}): {http_err}")
            if response is not None:
                print("Monday API Error Response:", response.text)
            return False
        except Exception as e:
            print(f"Error checking duplicates on Monday.com (page {page + 1}): {e}")
            return False

    return False