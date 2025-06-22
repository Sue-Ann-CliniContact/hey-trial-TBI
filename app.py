from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from main import start_session, handle_input

app = FastAPI()

# Allow Webflow/frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict this to your Webflow domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/chat")
async def chat(request: Request):
    body = await request.json()
    session_id = body.get("session_id")
    message = body.get("message")
    response = handle_input(session_id, message)
    return {"reply": response}
