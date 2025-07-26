from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import json

from runner import run_agent

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: str

@app.post("/api/chat")
async def chat(request: ChatRequest):
    print("request: ", request)
    user_message = request.message
    user_id = request.user_id
    session_id = request.session_id
    result = await run_agent(session_id, user_id, user_message)

    def generate_stream():
        # Properly escape the content for JSON
        escaped_result = json.dumps(result)
        yield f'0:{escaped_result}\n'

        # Send finish signal
        word_count = len(result.split())
        yield f'd:{{"finishReason":"stop","usage":{{"promptTokens":10,"completionTokens":{word_count}}}}}\n'

    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"X-Vercel-AI-Data-Stream": "v1"}
    )
    return StreamingResponse(
        generate_stream(),
        media_type="text/plain",
        headers={"X-Vercel-AI-Data-Stream": "v1"}
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
