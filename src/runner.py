from agent.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

APP_NAME = "frateto"

session_service = InMemorySessionService()

async def run_agent(session_id: str, user_id: str, user_message: str) -> str:
    """Simple function to run the agent and return the response"""

    await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
    runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)

    content = types.Content(
        role='user',
        parts=[types.Part(text=user_message)]
    )

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response() and event.content:
            if event.content.parts and event.content.parts[0].text:
                return event.content.parts[0].text

    return "No response received"
