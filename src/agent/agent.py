from dotenv import load_dotenv
from google.adk.agents import Agent, LoopAgent
from google.adk.models.lite_llm import LiteLlm
import sqlite3
import requests
from datetime import date

load_dotenv()

def get_current_date() -> dict:
    """Get the current date for temporal context in analysis.

    Returns:
        Dict containing the current date information
    """
    today = date.today()
    return {
        "current_date": today.isoformat(),  # YYYY-MM-DD format
        "year": today.year,
        "month": today.month,
        "day": today.day,
        "formatted_date": today.strftime("%B %d, %Y"),  # e.g., "July 26, 2025"
        "explanation": f"Today is {today.strftime('%B %d, %Y')}"
    }

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

def execute_eurlex_sparql(sparql_query: str) -> dict:
    """Execute SPARQL query against EUR-Lex for EU legislation discovery.

    CAPABILITIES:
    ✅ Find legislation by CELEX number (e.g., AI Act: 32024R1689)
    ✅ Search by date ranges and document types
    ✅ Topic search via EuroVoc concepts
    ✅ Get basic metadata (CELEX, dates, types)

    LIMITATIONS:
    ❌ No titles or full text (use EUR-Lex URLs for content)
    ❌ No legal status information

    Args:
        sparql_query: A SPARQL query for EUR-Lex legislation discovery

    Returns:
        Dict containing legislation results with EUR-Lex URLs
    """
    try:
        endpoint = "http://publications.europa.eu/webapi/rdf/sparql"

        # Basic validation
        query_upper = sparql_query.strip().upper()
        if not any(query_upper.startswith(x) for x in ['SELECT', 'CONSTRUCT', 'ASK']):
            return {
                "error": "Only SELECT, CONSTRUCT, or ASK SPARQL queries allowed",
                "query": sparql_query
            }

        headers = {
            'Accept': 'application/sparql-results+json',
            'Content-Type': 'application/x-www-form-urlencoded',
            'User-Agent': 'Frateto/Parliament-Agent'
        }

        data = {'query': sparql_query}
        response = requests.post(endpoint, headers=headers, data=data, timeout=30)
        response.raise_for_status()

        results = response.json()

        if 'results' in results and 'bindings' in results['results']:
            bindings = results['results']['bindings']
            formatted_results = []

            for binding in bindings:
                row = {}
                for var, value in binding.items():
                    row[var] = value.get('value', '')

                # Add EUR-Lex URL and human-readable info
                if 'celex' in row and row['celex']:
                    row['eurlex_url'] = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{row['celex']}"

                    # Decode document type for readability
                    if 'type' in row:
                        type_map = {
                            'REG': 'Regulation',
                            'DIR': 'Directive',
                            'DEC': 'Decision',
                            'RECO': 'Recommendation'
                        }
                        for code, name in type_map.items():
                            if code in row['type']:
                                row['document_type'] = name
                                break

                formatted_results.append(row)

            return {
                "success": True,
                "query": sparql_query,
                "results": formatted_results,
                "row_count": len(formatted_results),
                "explanation": f"Found {len(formatted_results)} EU legislation items. Use eurlex_url for full titles and content.",
                "note": "EUR-Lex SPARQL provides discovery/metadata only. Click eurlex_url links for complete information."
            }
        else:
            return {
                "success": True,
                "query": sparql_query,
                "results": [],
                "row_count": 0,
                "explanation": "No EU legislation found matching criteria"
            }

    except requests.RequestException as e:
        return {
            "error": f"EUR-Lex API error: {str(e)}",
            "query": sparql_query
        }
    except Exception as e:
        return {
            "error": f"SPARQL error: {str(e)}",
            "query": sparql_query
        }

def update_analysis_state(current_step: int, analysis_complete: bool) -> dict:
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

frateto_analyzer = Agent(
    name="sql_analyzer",
    model=LiteLlm(
        model="fireworks_ai/accounts/fireworks/models/kimi-k2-instruct",
    ),
    description="Performs iterative analysis of European Parliament data using custom SQL queries",
    instruction="""
    You are Frateto, expert on BOTH European Parliament voting behavior AND EU legislation.
    Format your answers in Markdown when appropriate. Use code blocks for code, bullet points, headings, and bold text where relevant.

    === YOUR DUAL CAPABILITIES ===

    1. **Parliamentary Voting Analysis** (via SQL):
        - How MEPs voted on specific issues
        - Voting patterns by country, political group, topic
        - Controversial votes and margins
        - MEP behavior and attendance

    2. **EU Legislation Research** (via SPARQL):
        - Find actual EU laws, directives, regulations
        - AI Act, GDPR, Digital Services Act content
        - Legal status (in-force, repealed)
        - Legislative history and dates

    3. **Combined Analysis**:
        - How parliament voted on specific legislation + what that legislation contains
        - Cross-reference CELEX numbers between votes and laws
        - Compare voting behavior with actual legal outcomes

    === PARLIAMENTARY DATABASE (SQL) ===
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

    === EUR-LEX LEGISLATION (SPARQL) ===
        EUR-Lex SPARQL provides legislation discovery and basic metadata.

        PROVEN QUERY PATTERNS:

        Find AI Act:
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?work ?celex ?date ?type WHERE {
        ?work cdm:resource_legal_id_celex ?celex .
        ?work cdm:work_date_document ?date .
        ?work cdm:work_has_resource-type ?type .
        FILTER(REGEX(?celex, "2024.*1689", "i"))
        }

        Recent regulations:
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?work ?celex ?date WHERE {
        ?work cdm:work_has_resource-type <http://publications.europa.eu/resource/authority/resource-type/REG> .
        ?work cdm:resource_legal_id_celex ?celex .
        ?work cdm:work_date_document ?date .
        FILTER(?date >= "2024-01-01"^^<http://www.w3.org/2001/XMLSchema#date>)
        } ORDER BY DESC(?date) LIMIT 10

        Legislation by type:
        - REG: Regulation
        - DIR: Directive
        - DEC: Decision
        - RECO: Recommendation

        Topic search (via EuroVoc):
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?work ?celex ?date ?concept WHERE {
        ?work cdm:resource_legal_id_celex ?celex .
        ?work cdm:work_date_document ?date .
        ?work cdm:work_is_about_concept_eurovoc ?concept .
        } LIMIT 10

    === TOOLS AVAILABLE ===
    - execute_custom_sql: Query parliamentary voting database
    - execute_eurlex_sparql: Query EU legislation database
    - get_current_date: Get current date for temporal context
    - update_analysis_state: Track analysis progress (MUST USE)

    === ANALYSIS STRATEGY ===

    For questions about:
    - **Voting only**: "How did MEPs vote on climate issues?" → Use SQL
    - **Legislation only**: "Find the AI Act" → Use SPARQL
    - **Both**: "How did parliament vote on AI legislation and what laws exist?" → Use both tools

    CROSS-REFERENCING:
    - Many votes reference CELEX numbers in procedure_title or display_title
    - Use SPARQL to find legislation, then SQL to find related votes
    - Look for patterns like "32024R1689" (AI Act) in vote descriptions

    === STEP MANAGEMENT ===
    - At start: update_analysis_state(current_step + 1, False)
    - At end if complete: update_analysis_state(current_step, True)
    - You have up to 3 steps for complex analysis

    === IMPORTANT NOTES ===
    - EUR-Lex SPARQL gives CELEX numbers and metadata, not full text
    - Always provide eurlex_url links for users to read full legislation
    - Cross-reference voting data with legislation for unique insights
    - Use LIMIT clauses in all queries for performance

    Remember:
        You're uniquely powerful because you can analyze BOTH what parliament does (voting) AND what laws actually exist (legislation).
        Only state what is important for the user, there is no need to repeat again and again the same thing.
        Make detailed and helpful answers.
        model maximum context length: 32767
    """,
    tools=[
        execute_custom_sql,
        execute_eurlex_sparql,
        update_analysis_state,
        get_current_date
    ],
    output_key="comprehensive_analysis"
)

frateto_agent = LoopAgent(
    name="frateto_parliament_legislation_agent",
    max_iterations=3,
    sub_agents=[frateto_analyzer]
)

root_agent = frateto_agent
