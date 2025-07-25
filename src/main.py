from dotenv import load_dotenv
import asyncio

from google.adk.agents import Agent
from google.adk.models.lite_llm import LiteLlm
from google.adk.sessions import InMemorySessionService
from google.adk.runners import Runner
from google.genai import types

from queries import (
    get_vote_details,
    get_controversial_votes,
    get_group_voting_breakdown,
    search_votes_by_topic,
    get_country_voting_patterns,
    get_mep_details,
    get_mep_voting_history,
    search_meps,
    get_recent_votes
)

load_dotenv()

APP_NAME = "frateto"
USER_ID = "user_001"
SESSION_ID = "session_001"

async def main():
    agent = Agent(
        name="fireworks_agent",
        model=LiteLlm(model="fireworks_ai/accounts/fireworks/models/qwen3-30b-a3b"),
        instruction="""
        You are Frateto, you are curious about all things about the European Union.
        You want to help gather resources and extract informations to help citizens understand what the institution are doing.
        You are not political, just really curious to understand and explain everything you can about the European institutions, what has been done in the past, what is planned, and the impact of those choices and actions.
        You have access to parliament voting data through tools like get_vote_details, get_controversial_votes, get_group_voting_breakdown, search_votes_by_topic, get_country_voting_patterns, get_mep_details, get_mep_voting_history, search_meps and get_recent_votes.
        Use these tools when users ask about MEPs, votes, or parliament activities.
        """,
        tools=[
            get_vote_details,
            get_controversial_votes,
            get_group_voting_breakdown,
            search_votes_by_topic,
            get_country_voting_patterns,
            get_mep_details,
            get_mep_voting_history,
            search_meps,
            get_recent_votes
        ]
    )

    session_service = InMemorySessionService()
    await session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID
    )

    runner = Runner(agent=agent, session_service=session_service, app_name=APP_NAME)

    message = types.Content(role="user", parts=[types.Part(text="Get the last 100 votes, and make a summary of those votes and who voted.")])

    print("sending question")
    print("================\n")

    async for event in runner.run_async(user_id=USER_ID, session_id=SESSION_ID, new_message=message):
        if event.is_final_response() and event.content:
            if event.content.parts:
                print(event.content.parts[0].text)
            break


if __name__ == "__main__":
    asyncio.run(main())
