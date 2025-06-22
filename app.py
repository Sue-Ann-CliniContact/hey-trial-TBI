from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from main import start_session, handle_input

app = FastAPI()

# CORS for frontend (e.g. Webflow)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/start")
async def start():
    session_id = start_session()
    welcome = "👋 Hi! I’m your Hey Trial AI Assistant for the Kessler TBI study. You can ask questions or begin screening when you’re ready."
    return {"session_id": session_id, "message": welcome}


@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    session_id = body.get("session_id")
    message = body.get("message")
    response = handle_input(session_id, message)
    return {"reply": response}
