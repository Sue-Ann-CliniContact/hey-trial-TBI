from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from main import start_session, handle_input

app = FastAPI()
sessions = {}

# Allow Webflow/frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your Webflow domain if needed
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/start")
async def start(request: Request):
    ip = request.client.host
    session_id = start_session(ip)
    sessions[session_id] = {"history": []}
    return {
        "session_id": session_id,
        "message": "Can I have your full name?"
    }

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    session_id = body.get("session_id")
    message = body.get("message")

    if session_id not in sessions:
        return {"reply": "Session not found. Please refresh and try again."}

    response = handle_input(session_id, message)
    return {"reply": response}
