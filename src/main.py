from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json
import os

from runner import run_agent

app = FastAPI(title="Frateto Chat API", version="1.0.0")

# CORS configuration for production
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
CORS_ORIGINS = [
    FRONTEND_URL,  # Production frontend
    "https://*.vercel.app",  # Vercel deployments
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: str

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    print("request: ", request)
    user_message = request.message
    user_id = request.user_id
    session_id = request.session_id

    async def generate_stream():
        word_count = 0
        try:
            async for message in run_agent(session_id, user_id, user_message):
                # add "\n\n" to separate messages in the frontend
                escaped_message = json.dumps(message + "\n\n")
                word_count += len(escaped_message.split())
                yield f'0:{escaped_message}\n'

            # Send finish signal after all messages
            yield f'd:{{"finishReason":"stop","usage":{{"promptTokens":10,"completionTokens":{word_count}}}}}\n'

        except Exception as e:
            print(f"Streaming error: {e}")
            error_msg = json.dumps(f"Error: {str(e)}")
            yield f'0:{error_msg}\n'
            yield 'd:{{"finishReason":"error","usage":{{"promptTokens":0,"completionTokens":0}}}}\n'

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"X-Vercel-AI-Data-Stream": "v1"}
    )

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
