from twilio.rest import Client
import os
import re

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_SID, TWILIO_AUTH)

def is_us_number(number: str) -> bool:
    """
    Validates if the number is a U.S. number (starts with +1 or is 10 digits).
    """
    cleaned = re.sub(r"[^\d]", "", number)
    return cleaned.startswith("1") and len(cleaned) == 11 or len(cleaned) == 10

def format_us_number(number: str) -> str:
    """
    Formats a valid US number to E.164 for Twilio.
    """
    cleaned = re.sub(r"[^\d]", "", number)
    if len(cleaned) == 10:
        return "+1" + cleaned
    elif len(cleaned) == 11 and cleaned.startswith("1"):
        return "+" + cleaned
    return number

def send_verification_sms(to_number: str, code: str) -> tuple[bool, str]:
    """
    Sends a verification code if the number is a valid U.S. number.
    Returns (True, "") if successful or (False, "error message") otherwise.
    """
    if not is_us_number(to_number):
        return False, "⚠️ The number you entered does not appear to be a U.S. phone number. Please enter a valid 10-digit U.S. number."

    try:
        formatted_number = format_us_number(to_number)
        message = client.messages.create(
            body=f"Hi! Your confirmation code for the Kessler Study is {code}. Please enter this code in the chat to confirm your submission.",
            from_=TWILIO_NUMBER,
            to=formatted_number
        )
        print(f"SMS sent: SID {message.sid}")
        return True, ""
    except Exception as e:
        print(f"Failed to send SMS: {e}")
        return False, "❌ Failed to send SMS. Please check your number and try again."

