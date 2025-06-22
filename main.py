import uuid
import random
import math
import datetime
import requests
import os
from typing import Dict, Any
from openai import OpenAI
from twilio_sms import send_verification_sms
from push_to_monday import push_to_monday
from check_duplicate import check_duplicate_email

# Constants and API keys
KESSLER_COORDS = (40.8255, -74.3594)
DISTANCE_THRESHOLD_MILES = 50
IPINFO_TOKEN = os.getenv("IPINFO_TOKEN")
GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

# Session storage
sessions: Dict[str, Dict[str, Any]] = {}

questions = [
    "name", "email", "phone", "dob", "city_state",
    "tbi_year", "memory_issues", "english_fluent",
    "handedness", "can_exercise", "can_mri", "future_study_consent"
]

question_prompts = {
    "name": "Can I have your full name?",
    "email": "What’s your email address?",
    "phone": "What’s the best phone number to reach you?",
    "dob": "And your date of birth? (YYYY-MM-DD)",
    "city_state": "Where are you currently located? (City and State)",
    "tbi_year": "Have you experienced a traumatic brain injury at least one year ago? (Yes/No)",
    "memory_issues": "Do you have persistent memory problems? (Yes/No)",
    "english_fluent": "Are you able to read and speak English well? (Yes/No)",
    "handedness": "Are you left or right-handed?",
    "can_exercise": "Are you willing and able to exercise? (Yes/No)",
    "can_mri": "Are you able to undergo an MRI? (Yes/No)",
    "future_study_consent": "Would you like us to contact you about future studies? (Yes/No)"
}

STUDY_SUMMARY = """
This clinical research study is led by Kessler Foundation in East Hanover, New Jersey. It aims to understand how exercise may improve memory and brain function in individuals with a history of moderate to severe traumatic brain injury (TBI).

To qualify, participants must:
- Be age 18 or older
- Have experienced a moderate to severe TBI at least one year ago
- Be experiencing persistent memory issues
- Be fluent in English
- Be physically able and willing to exercise
- Be able to undergo MRI brain scans
- Live within 50 miles of East Hanover, NJ

Participants will attend in-person visits, complete memory tests, undergo MRI scans, and engage in supervised exercise sessions.

Compensation is provided for time and transportation.

The study is IRB approved and participation is voluntary.
"""

def generate_session_id() -> str:
    return str(uuid.uuid4())

def start_session() -> str:
    session_id = generate_session_id()
    sessions[session_id] = {
        "step": -1,
        "data": {},
        "verified": False,
        "code": generate_verification_code()
    }
    return session_id

def generate_verification_code() -> str:
    return str(random.randint(1000, 9999))

def calculate_age(dob: str) -> int:
    birth_date = datetime.datetime.strptime(dob, "%Y-%m-%d").date()
    today = datetime.date.today()
    return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))

def haversine_distance(lat1, lon1, lat2, lon2) -> float:
    R = 3958.8
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (math.sin(d_lat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(d_lon/2)**2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def get_location_from_ip(ip_address: str) -> Dict[str, Any]:
    url = f"https://ipinfo.io/{ip_address}?token={IPINFO_TOKEN}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        loc = data.get("loc", "").split(",")
        if len(loc) == 2:
            data["latitude"], data["longitude"] = float(loc[0]), float(loc[1])
        return data
    return {}

def get_coords_from_city_state(city_state: str) -> Dict[str, float]:
    url = f"https://maps.googleapis.com/maps/api/geocode/json?address={city_state}&key={GOOGLE_MAPS_API_KEY}"
    response = requests.get(url)
    if response.status_code == 200:
        results = response.json().get("results")
        if results:
            location = results[0]["geometry"]["location"]
            return {"latitude": location["lat"], "longitude": location["lng"]}
    return {}

def is_within_distance(user_lat: float, user_lon: float) -> bool:
    distance = haversine_distance(user_lat, user_lon, *KESSLER_COORDS)
    return distance <= DISTANCE_THRESHOLD_MILES

def ask_gpt(question: str) -> str:
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"""
You are a helpful, friendly, and smart AI assistant for a clinical trial recruitment platform.

Below is a study summary written in IRB-approved language. Your job is to answer any natural-language question about the study accurately and supportively. 
If the user asks about location, purpose, visits, eligibility, MRI, compensation, or logistics — answer with clear, friendly language based only on what is in the summary.

If the user expresses interest or says something like “I want to participate”, invite them to start the pre-qualifier right here in the chat.

Always end your answers with:  
"Would you like to complete the quick pre-qualifier here in the chat to see if you're a match?"

STUDY DETAILS:
{STUDY_SUMMARY}
"""
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.6,
            max_tokens=300
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI error:", e)
        return "I'm here to help you learn more about the study or see if you qualify. Would you like to begin the quick pre-qualifier now?"

def handle_input(session_id: str, user_input: str) -> str:
    session = sessions.get(session_id)
    if not session:
        return "Session not found. Please refresh and try again."

    step = session["step"]
    data = session["data"]
    text = user_input.strip().lower()

    # Chat mode before screener
    if step == -1:
        # If user says yes or expresses intent → move to screener
        if any(p in text for p in ["yes", "start", "begin", "qualify", "participate", "sign me up", "ready"]):
            session["step"] = 0
            return question_prompts[questions[0]]

        # Otherwise, answer the question using GPT
        reply = ask_gpt(user_input)
        return reply

    # SMS verification step
    if step == len(questions) and not session["verified"]:
        if text == session["code"]:
            session["verified"] = True
            age = calculate_age(data["dob"])
            coords = get_coords_from_city_state(data["city_state"])
            distance_ok = is_within_distance(coords.get("latitude", 0), coords.get("longitude", 0))

            qualified = (
                age >= 18 and
                data["tbi_year"].lower() == "yes" and
                data["memory_issues"].lower() == "yes" and
                data["english_fluent"].lower() == "yes" and
                data["can_exercise"].lower() == "yes" and
                data["can_mri"].lower() == "yes" and
                distance_ok
            )

            group = "new_group58505__1" if qualified else "new_group__1"
            tags = ["Validated"]
            if not qualified:
                tags.append("Disqualified")
            if not distance_ok:
                tags.append("Far Location")

            ip_data = get_location_from_ip(data.get("ip", ""))
            ipinfo_text = "\n".join([f"{k}: {v}" for k, v in ip_data.items()])

            push_to_monday(data, group, qualified, tags, ipinfo_text)
            return "✅ Your submission is now confirmed and has been received. Thank you!"
        else:
            return "❌ That code doesn't match. Please check your SMS and enter the correct 4-digit code."

    # Screener flow
    current_question = questions[step]
    user_value = user_input.strip()

    if current_question == "email":
        if check_duplicate_email(user_value):
            session["step"] = len(questions)
            push_to_monday({"email": user_value, "name": "Duplicate"}, "group_mkqb9ps4", False, ["Duplicate"], "")
            return "It looks like you’ve already submitted an application for this study. We’ll be in touch if you qualify!"

    data[current_question] = user_value
    session["step"] += 1

    if session["step"] == len(questions):
        phone_number = data.get("phone", "")
        success = send_verification_sms(phone_number, session["code"])
        if success:
            return "Thanks! Please check your phone and enter the 4-digit code we just sent you to confirm your submission."
        else:
            return "There was an issue sending the SMS. Please double-check your number or try again later."

    next_question = questions[session["step"]]
    return question_prompts[next_question]
