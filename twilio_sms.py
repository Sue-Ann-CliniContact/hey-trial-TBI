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
    Handles common formatting like spaces, hyphens, and parentheses.
    """
    cleaned = re.sub(r"[^\d]", "", number) # Remove non-digits
    # A valid US number is 10 digits or 11 digits starting with '1'
    return len(cleaned) == 10 or (len(cleaned) == 11 and cleaned.startswith("1"))

def format_us_number(phone: str) -> str:
    """
    Formats a U.S. phone number to the E.164 standard (+1NPANXXXXXX).
    Assumes the input number has already been validated as a US number.
    """
    digits = re.sub(r"\D", "", phone) # Remove non-digits
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    # If for some reason it's not a standard US number by this point,
    # return as is, but this should be caught by is_us_number
    return phone

def send_verification_sms(to_number: str, message_body: str) -> tuple[bool, str]: # Changed from 'code' to 'message_body'
    """
    Sends an SMS with the provided message body.
    Returns (True, "") if successful or (False, "error message") otherwise.
    """
    if not is_us_number(to_number):
        return False, "⚠️ Internal error: Phone number not a valid U.S. number format for SMS."

    try:
        formatted_number = format_us_number(to_number)
        message = client.messages.create(
            body=message_body, # Use the dynamic message_body here
            from_=TWILIO_NUMBER,
            to=formatted_number
        )
        print(f"SMS sent: SID {message.sid}")
        return True, ""
    except Exception as e:
        print(f"Failed to send SMS: {e}")
        return False, "❌ Failed to send SMS. Please check your number and try again."