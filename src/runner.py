from agent.agent import root_agent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

APP_NAME = "frateto"

session_service = InMemorySessionService()
runner = Runner(agent=root_agent, session_service=session_service, app_name=APP_NAME)

async def run_agent(session_id: str, user_id: str, user_message: str):
    """Simple function to run the agent and return the response"""

    session = await session_service.get_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )
    if not session:
        await session_service.create_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )

    content = types.Content(
        role='user',
        parts=[types.Part(text=user_message)]
    )

    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if not event.is_final_response() and event.content:
            # check if message is text for the user
            if event.content and event.content.parts and event.content.parts[0].text:
                yield event.content.parts[0].text
            # check if message is a function call
            elif event.content and event.content.parts and event.content.parts[0].function_response:
                yield f"*{event.content.parts[0].function_response.name}*"
        elif event.is_final_response() and event.content:
            if event.content.parts and event.content.parts[0].text:
                # return the query text and finish conversation
                yield event.content.parts[0].text
                break
