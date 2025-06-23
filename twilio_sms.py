from twilio.rest import Client
import os

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

client = Client(TWILIO_SID, TWILIO_AUTH)

def send_verification_sms(to_number: str, code: str) -> tuple[bool, str]:
    if not to_number.startswith("+1"):
        return False, "⚠️ That doesn't look like a US number. Please provide a valid US number starting with +1."

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
        return False, "⚠️ We couldn't send the confirmation code. Please double-check your number and try again."

