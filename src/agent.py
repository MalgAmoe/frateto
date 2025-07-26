#!/usr/bin/env python3
"""
Frateto Parliament Agent with LoopAgent using only custom SQL queries
Run with: adk web
"""

from dotenv import load_dotenv
from google.adk.agents import Agent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
import sqlite3

load_dotenv()

DB_PATH = "./db_stuff/parliament_votes.db"

def execute_custom_sql(sql_query: str) -> dict:
    """Execute a custom SQL query against the European Parliament database.

    Args:
        sql_query: A SELECT SQL query to execute. Must be a valid SELECT statement.
                  Should include appropriate JOINs and LIMIT clauses for performance.

    Returns:
        Dict containing query results, column names, and metadata

    Security Note: Only SELECT queries are allowed. No INSERT, UPDATE, DELETE, or DDL operations.
    """
    try:
        # Basic security check - only allow SELECT statements
        query_upper = sql_query.strip().upper()
        if not query_upper.startswith('SELECT'):
            return {
                "error": "Only SELECT queries are allowed",
                "query": sql_query
            }

        # Check for dangerous keywords
        dangerous_keywords = ['INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE', 'ALTER', 'TRUNCATE']
        for keyword in dangerous_keywords:
            if keyword in query_upper:
                return {
                    "error": f"Query contains forbidden keyword: {keyword}",
                    "query": sql_query
                }

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Execute the query
        cursor.execute(sql_query)
        results = cursor.fetchall()

        # Get column names
        column_names = [description[0] for description in cursor.description] if cursor.description else []

        conn.close()

        # Format results as list of dictionaries for easier processing
        formatted_results = []
        for row in results:
            formatted_results.append(dict(zip(column_names, row)))

        return {
            "success": True,
            "query": sql_query,
            "results": formatted_results,
            "column_names": column_names,
            "row_count": len(results),
            "explanation": f"Custom SQL query returned {len(results)} rows with columns: {', '.join(column_names)}"
        }

    except sqlite3.Error as e:
        return {
            "error": f"SQL error: {str(e)}",
            "query": sql_query
        }
    except Exception as e:
        return {
            "error": f"Database error: {str(e)}",
            "query": sql_query
        }

def update_analysis_state(current_step: int, analysis_complete: bool, findings: str = "") -> dict:
    """Update the analysis state variables.

    Args:
        current_step: The current step number (increment by 1 each call)
        analysis_complete: True if analysis is complete, False if more steps needed
        findings: Summary of current findings

    Returns:
        Dict confirming the state update
    """
    return {
        "success": True,
        "step": current_step,
        "complete": analysis_complete,
        "message": f"Updated to step {current_step}, complete: {analysis_complete}"
    }

# SQL-only iterative analysis agent
sql_analyzer = Agent(
    name="sql_analyzer",
    model=LiteLlm(
        model="fireworks_ai/accounts/fireworks/models/kimi-k2-instruct",
    ),
    description="Performs iterative analysis of European Parliament data using custom SQL queries",
    instruction="""
    You are Frateto, a European Parliament data analyst. You analyze voting data using ONLY custom SQL queries.

    DATABASE STRUCTURE:
    European Parliament Voting Database (2019-2025): 21,371 votes by 1,266 MEPs from 28 countries.

    === CORE ENTITIES ===

    1. VOTES (21,371 rows) - The parliamentary votes
       Columns: id, timestamp, display_title, procedure_title, procedure_type,
               count_for, count_against, count_abstention, count_did_not_vote, result, is_main

    2. MEMBERS (1,266 rows) - The MEPs (Members of European Parliament)
       Columns: id, first_name, last_name, country_code, date_of_birth

    3. MEMBER_VOTES (15M rows) - How each MEP voted on each vote
       Columns: vote_id, member_id, position, country_code, group_code
       Position values: 'FOR', 'AGAINST', 'ABSTENTION', 'DID_NOT_VOTE'
       Note: group_code here = political group MEP belonged to AT TIME OF VOTE

    === REFERENCE TABLES ===

    4. COUNTRIES (28 rows) - EU member states
       Columns: code, label
       Example: 'DEU' → 'Germany', 'FRA' → 'France'

    5. GROUPS (10 rows) - Political groups/parties
       Columns: code, label, short_label
       Example: 'EPP' → 'European People's Party', 'SD' → 'Progressive Alliance of Socialists and Democrats'

    6. EUROVOC_CONCEPTS (1,730 rows) - Policy topic classifications
       Columns: id, label
       Example: topics like 'climate change', 'agriculture', 'digital policy'

    7. COMMITTEES (24 rows) - Parliamentary committees
       Columns: code, label
       Example: 'ENVI' → 'Environment Committee', 'ECON' → 'Economic Committee'

    === RELATIONSHIP TABLES (Many-to-Many Links) ===

    8. EUROVOC_CONCEPT_VOTES - Links votes to policy topics
       Columns: vote_id, eurovoc_concept_id
       (One vote can have multiple topics, one topic appears in multiple votes)

    9. RESPONSIBLE_COMMITTEE_VOTES - Links votes to responsible committee
       Columns: vote_id, committee_code

    10. GROUP_MEMBERSHIPS - Historical record of MEP political group membership
        Columns: member_id, group_code, start_date, end_date, term
        (MEPs can change groups over time)

    === KEY RELATIONSHIPS & HOW TO JOIN ===

    🔗 MEP Voting History:
    members → member_votes → votes
    SELECT m.first_name, m.last_name, mv.position, v.display_title
    FROM members m
    JOIN member_votes mv ON m.id = mv.member_id
    JOIN votes v ON mv.vote_id = v.id

    🔗 Vote Topics:
    votes → eurovoc_concept_votes → eurovoc_concepts
    SELECT v.display_title, ec.label as topic
    FROM votes v
    JOIN eurovoc_concept_votes ecv ON v.id = ecv.vote_id
    JOIN eurovoc_concepts ec ON ecv.eurovoc_concept_id = ec.id

    🔗 Political Group Analysis (TWO WAYS):
    Option A - Current group at time of vote (RECOMMENDED):
    Use group_code directly from member_votes table

    Option B - Historical membership tracking:
    members → group_memberships → groups

    🔗 Country Voting Patterns:
    Use country_code directly from member_votes table, or:
    member_votes → members → countries

    🔗 Committee Responsibility:
    votes → responsible_committee_votes → committees

    === STEP MANAGEMENT ===
    You have up to 3 steps for complex analysis:
    - Check current step: ctx.session.state.get("current_step", 0)
    - Increment step: ctx.session.state["current_step"] = current_step + 1
    - Mark analysis complete: ctx.session.state["analysis_complete"] = True
    - Store findings: ctx.session.state["findings"] = your_findings_list

    Build understanding through 1-3 SQL queries. Stop early if you have sufficient data.

    === IMPORTANT TECHNICAL NOTES ===
    - Always use LIMIT for large result sets
    - Use ABS(count_for - count_against) for vote margins
    - Timestamp format: 'YYYY-MM-DD HH:MM:SS'
    - group_code in member_votes = political group at time of vote (most reliable)
    - One vote can have multiple topics (use JOINs carefully)

    === STEP MANAGEMENT ===
        At the start of each response, call: update_analysis_state(current_step + 1, False)
        At the end of each response, if done, call: update_analysis_state(current_step, True)

        Available tools:
        - execute_custom_sql: For database queries
        - update_analysis_state: For updating step tracking (MUST USE)

    Remember:
        Only state what is important for the user, there is no need to repeat again and again the same thing.
        Make detailed and helpful answers.
        model maximum context length: 32767
    """,
    tools=[
        execute_custom_sql,
        update_analysis_state
    ],
    output_key="step_analysis"
)

# Create the LoopAgent with max 3 iterations
frateto_sql_agent = LoopAgent(
    name="frateto_sql_parliament_agent",
    max_iterations=3,
    sub_agents=[
        sql_analyzer,
    ]
)

# This is the agent that ADK will use when you run `adk web`
root_agent = frateto_sql_agent
