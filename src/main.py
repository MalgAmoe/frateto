from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse, HTMLResponse
from pydantic import BaseModel
from datetime import datetime
import json
import os
import uuid

from runner import run_agent

app = FastAPI(title="Frateto Chat API", version="1.0.0")

active_sessions: dict[str, float] = {}

class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: str

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
    print("✅ Static files mounted from /static")
else:
    print("⚠️  Static files not found. Run ./build.sh first!")

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.post("/api/chat")
async def chat(request: ChatRequest):
    print("request: ", request)
    if request.user_id not in active_sessions:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user_message = request.message
    user_id = request.user_id
    session_id = request.session_id

    timestamp = datetime.now().timestamp()
    active_sessions[user_id] = timestamp

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

@app.get("/")
async def serve_index():
    """Serve the main React app."""
    if not os.path.exists("static/index.html"):
        raise HTTPException(status_code=404, detail="Frontend not built. Run ./build.sh first!")

    # remove session is not active for 15 min
    now = datetime.now().timestamp()
    to_delete = [user_id for user_id, stamp in active_sessions.items() if stamp + 60 * 15 < now]

    for user_id in to_delete:
        del active_sessions[user_id]

    # limit to 20 concurrent users
    if len(active_sessions) >= 20:
        html_content = """
            <html>
                <head>
                    <title>503 Service Unavailable</title>
                    <meta charset="UTF-8">
                </head>
                <body>
                    <h1>Service Unavailable</h1>
                    <p>The website is currently at full capacity. Please try again shortly.</p>
                    <button onclick="location.reload()">Retry</button>
                </body>
            </html>
        """
        return HTMLResponse(
            content=html_content,
            status_code=503,
            headers={
                "Cache-Control": "no-store"
            }
        )

    with open("static/index.html", "r") as f:
        html_content = f.read()

    user_id = str(uuid.uuid4())
    timestamp = datetime.now().timestamp()
    active_sessions[user_id] = timestamp

    session_script = f"""
        <script>
            window.FRATETO_SESSION = '{user_id}';
        </script>
        """

    # Insert the script before closing </head> tag
    if "</head>" in html_content:
        html_content = html_content.replace("</head>", f"{session_script}</head>")
    else:
        # Fallback: insert at the beginning of <body>
        html_content = html_content.replace("<body>", f"<body>{session_script}")

    return HTMLResponse(content=html_content)

@app.get("/{path:path}")
async def serve_frontend_routes(path: str):
    """Catch-all route for React Router (SPA routing)."""
    # Check if it's a static asset first
    static_file_path = f"static/{path}"
    if os.path.exists(static_file_path) and os.path.isfile(static_file_path):
        return FileResponse(static_file_path)

    # Otherwise, serve index.html for React Router
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    else:
        raise HTTPException(status_code=404, detail="Frontend not built. Run ./build.sh first!")


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
