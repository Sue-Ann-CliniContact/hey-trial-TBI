from twilio.rest import Client
import os
import re

# Load from environment variables (Render)
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_SID, TWILIO_AUTH)

def send_verification_sms(to_number: str, code: str) -> tuple[bool, str]:
    """
    Sends a 4-digit confirmation code via SMS using Twilio.
    Returns (True, "") if successful, or (False, error message) if failed.
    """

    # Check if the number is a valid US number (E.164 format: +1XXXXXXXXXX)
    if not re.fullmatch(r"\+1\d{10}", to_number):
        return False, "⚠️ That doesn’t look like a valid US phone number. Please enter a number starting with +1 followed by 10 digits."

    try:
        message = client.messages.create(
            body=f"Hi! Your confirmation code for the Kessler Study is {code}. Please enter this code in the chat to confirm your submission.",
            from_=TWILIO_NUMBER,
            to=to_number
        )
        print(f"SMS sent: SID {message.sid}")
        return True, ""
    except Exception as e:
        print(f"Failed to send SMS: {e}")
        return False, "⚠️ There was a problem sending the SMS. Please double-check your number or try again later."
