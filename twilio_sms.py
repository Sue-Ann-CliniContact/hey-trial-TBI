from twilio.rest import Client
import os
import re

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_SID, TWILIO_AUTH)

def is_us_number(number: str) -> bool:
    # Accepts formats like: +1XXXXXXXXXX or 10-digit US numbers
    return bool(re.match(r"^\+1\d{10}$", number))

def send_verification_sms(to_number: str, code: str) -> (bool, str):
    if not is_us_number(to_number):
        return False, "⚠️ That number doesn’t appear to be a valid US phone number. Please enter a 10-digit US number starting with +1."

    try:
        message = client.messages.create(
            body=f"Hi! Your confirmation code for the Kessler Study is {code}. Please enter this code in the chat to confirm your submission.",
            from_=TWILIO_NUMBER,
            to=to_number
        )
        print(f"✅ SMS sent: SID {message.sid}")
        return True, ""
    except Exception as e:
        print(f"❌ Failed to send SMS: {e}")
        return False, "Something went wrong while sending the SMS. Please try again."


