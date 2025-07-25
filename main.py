from dotenv import load_dotenv
import asyncio
from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

load_dotenv()

APP_NAME = "frateto"
USER_ID = "user_001"
SESSION_ID = "session_001"

async def main():
    agent = Agent(
        name="fireworks_agent",
        model=LiteLlm(model="fireworks_ai/accounts/fireworks/models/kimi-k2-instruct"),
        instruction="""
        You are Frateto, you are curious about all things about the European Union.
        You want to help gather resources and extract informations to help citizens understand what the institution are doing.
        You are not political, just really curious to understand and explain everything you can about the European institutions, what has been done in the past, what is planned, and the impact of those choices and actions.
        """
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )
    print("got session service")

    runner = Runner(agent=agent, session_service=session_service, app_name=APP_NAME)

    message = types.Content(role="user", parts=[types.Part(text="Hello, what are you doing?")])

    print("sending question")

    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=message):
        if event.is_final_response() and event.content:
            if event.content.parts:
                print(event.content.parts[0].text)
            break


if __name__ == "__main__":
    asyncio.run(main())
