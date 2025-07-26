from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from runner import run_agent

app = FastAPI()

app.add_middleware(CORSMiddleware, allow_origins=["*"])

class ChatRequest(BaseModel):
    messages: list
    user_id: str
    session_id: str

@app.post("/api/chat")
async def chat(request: ChatRequest):
    user_message = request.messages[-1]["content"]
    user_id = request.user_id
    session_id = request.session_id

    result = await run_agent(session_id, user_id, user_message)

    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": str(result)
                }
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
