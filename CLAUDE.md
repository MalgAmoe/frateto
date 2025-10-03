# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Structure

This repository contains a reference implementation (`frateto/`) and a refactoring directory (`frateto-refactor/`):

- **`frateto/`** - Complete reference implementation of the Frateto application (EU Parliament voting analysis AI agent)
- **`frateto-refactor/`** - Work directory for refactoring and new development

**IMPORTANT**: The `frateto/` directory is read-only and serves as the reference. All new code and modifications should be done in `frateto-refactor/`.

## What is Frateto?

Frateto is an AI agent that analyzes European Parliament voting data and EU legislation using Google's Agent Development Kit (ADK). It combines parliamentary voting records with actual EU legislation research to provide comprehensive political analysis.

### Key Features
- Query 21,371 European Parliament votes from 1,266 MEPs across 28 countries
- Cross-reference parliamentary votes with EU legislation (EUR-Lex)
- Analyze voting patterns by country, political group, and policy topic
- Research EU laws using SPARQL queries
- Multi-step iterative analysis with state management

## Technology Stack

### Backend
- **Python 3.12** with `uv` for dependency management
- **FastAPI** server with streaming responses
- **Google ADK** (Agent Development Kit) for agent orchestration
- **Fireworks.ai** (Kimi K2 model) for LLM inference
- **SQLite** database with EU Parliament voting data from [HowTheyVote](https://github.com/HowTheyVote/data)

### Frontend
- **React 19** with TypeScript
- **Vite** build system
- **Tailwind CSS** for styling
- **@ai-sdk/react** for streaming chat interface
- **@llamaindex/chat-ui** for chat components

## Working Directory

Always work from the repository root: `/home/malg/dev/agents/frateto/frateto-ref/`

Reference implementation files are in `frateto/`, but **do not modify them**. Use them for understanding the architecture.

## Common Commands

### Initial Setup

```bash
# Navigate to reference implementation
cd frateto/

# Create Python virtual environment
uv venv

# Install Python dependencies
uv sync

# Install frontend dependencies
cd chat && npm install && cd ..

# Set up environment variables
cp .env.example .env
# Edit .env and add FIREWORKS_API_KEY from https://fireworks.ai/
```

### Build and Run

```bash
# Build frontend and run server (from frateto/ directory)
./build_front.sh && uv run src/main.py

# Alternative: build and run separately
./build_front.sh
uv run src/main.py

# Access the application
# Open browser to http://localhost:8000
```

### Frontend Development

```bash
# Run frontend dev server (from frateto/chat/)
cd chat
npm run dev

# Build frontend for production
npm run build

# Run linter
npm run lint
```

### Database Operations

```bash
# Download and populate the database (from frateto/ directory)
uv run db_stuff/howTheyVote.py

# Inspect database structure
uv run db_stuff/db_query_for_prompt.py

# Database location
# ./db_stuff/parliament_votes.db
```

## Application Architecture

### Core Components

1. **FastAPI Server** (`src/main.py`)
   - Serves static frontend from `static/` directory
   - Provides `/api/chat` endpoint with streaming responses
   - In-memory session management (max 20 concurrent users, 15-minute timeout)
   - Injects session ID via `window.FRATETO_SESSION` in HTML

2. **Agent System** (`src/agent/agent.py`)
   - `frateto_analyzer`: Main SQL analysis agent with tools
   - `frateto_agent`: LoopAgent wrapper (max 3 iterations)
   - Uses Fireworks.ai Kimi K2 model via LiteLLM
   - Comprehensive system prompt with database schema and SPARQL examples

3. **Runner** (`src/runner.py`)
   - Google ADK Runner with InMemorySessionService
   - Streams events from agent to FastAPI endpoint
   - Handles session creation and message routing

4. **Database Tools** (in `src/agent/agent.py`)
   - `execute_custom_sql()`: Query SQLite voting database (SELECT only)
   - `execute_eurlex_sparql()`: Query EU legislation via SPARQL
   - `update_analysis_state()`: Track multi-step analysis progress
   - `get_current_date()`: Provide temporal context

### Database Schema

The SQLite database contains 14 tables with rich relational data:

**Core Tables:**
- `votes` (21,371 rows) - Parliamentary votes with metadata
- `members` (1,266 rows) - MEP profiles
- `member_votes` (15,117,795 rows) - How each MEP voted on each vote

**Reference Tables:**
- `countries`, `groups`, `committees`, `eurovoc_concepts`, `oeil_subjects`, `geo_areas`

**Junction Tables:**
- `eurovoc_concept_votes`, `responsible_committee_votes`, `group_memberships`, `geo_area_votes`, `oeil_subject_votes`

All tables have foreign key relationships and indexes on commonly queried columns (vote_id, member_id, timestamp, procedure_type).

### Data Sources

**Parliamentary Voting Data:**
- Source: HowTheyVote GitHub releases (https://github.com/HowTheyVote/data)
- Scraper: `db_stuff/howTheyVote.py`
- Coverage: European Parliament 2019-2025
- Update: Run scraper to download latest release

**EU Legislation Data:**
- Source: EUR-Lex SPARQL endpoint (http://publications.europa.eu/webapi/rdf/sparql)
- Access: Via `execute_eurlex_sparql()` tool
- Limitations: Metadata only (CELEX numbers, dates), no full text
- Notes: Recent legislation may have database lag

### Agent Workflow

1. User sends message via chat interface
2. FastAPI validates session and creates streaming response
3. Runner executes agent with user message
4. Agent uses tools to query databases:
   - `execute_custom_sql` for voting patterns
   - `execute_eurlex_sparql` for legislation
   - `update_analysis_state` for multi-step analysis
5. Agent streams responses back through runner
6. Frontend displays streamed responses in real-time

### Frontend Structure

The frontend is built with Vite and served as static files:

```
chat/
├── src/           # React components and logic
├── dist/          # Built output (copied to static/)
├── package.json   # Dependencies
└── vite.config.ts # Build configuration
```

After `npm run build`, the `dist/` directory is copied to `static/` by `build_front.sh`.

## Model Configuration

The agent uses Fireworks.ai's Kimi K2 model:

```python
model = LiteLlm(
    model="fireworks_ai/accounts/fireworks/models/kimi-k2-instruct-0905"
)
```

**To change the model:**
1. Modify `src/agent/agent.py` line 231
2. Update LiteLLM model identifier
3. Update `.env` with appropriate API key

**Alternative models:**
- OpenAI: `model="gpt-4"` with `OPENAI_API_KEY`
- Google: `model="gemini-pro"` with `GOOGLE_API_KEY`

## Development Notes

### Session Management
- In-memory sessions (not persistent across restarts)
- Max 20 concurrent users (line 82 in `src/main.py`)
- 15-minute timeout for inactive sessions
- Session ID injected via inline script in HTML

### Security
- SQL injection protection: Only SELECT queries allowed
- Dangerous keywords blocked: INSERT, UPDATE, DELETE, DROP, etc.
- SPARQL queries restricted to read-only operations

### Performance Considerations
- Agent has 200,000 token context limit
- Always use LIMIT clauses in SQL queries (recommended: 100-1000 max)
- Database has indexes on vote_id, member_id, timestamp, procedure_type
- SPARQL queries should include LIMIT to avoid timeouts

### Build Process
The `build_front.sh` script:
1. Runs `npm run build` in `chat/` directory
2. Removes old `static/` directory
3. Copies `chat/dist/` to `static/`
4. Verifies `static/index.html` exists

**Must run before starting server** - FastAPI serves from `static/` directory.

## Environment Variables

Required in `.env` file:
```bash
FIREWORKS_API_KEY=your_key_here
PORT=8000  # Optional, defaults to 8000
```

## Troubleshooting

**Frontend not loading:**
- Ensure `build_front.sh` was run successfully
- Check that `static/index.html` exists
- Verify FastAPI started without errors

**Database errors:**
- Run `uv run db_stuff/howTheyVote.py` to populate database
- Check that `db_stuff/parliament_votes.db` exists
- Verify SQLite version compatibility

**SPARQL timeouts:**
- Reduce LIMIT clause in queries (try 5-10)
- Use FILTER(BOUND(?celex)) to exclude null results
- EUR-Lex endpoint can be unreliable for very recent legislation

**Session capacity reached:**
- Adjust concurrent user limit in `src/main.py` line 82
- Consider implementing persistent session storage

## Key Files Reference

- `src/main.py:31-66` - Chat API endpoint with streaming
- `src/agent/agent.py:228-641` - Agent definition with comprehensive prompt
- `src/agent/agent.py:28-93` - SQL query tool
- `src/agent/agent.py:95-206` - SPARQL query tool
- `src/runner.py:11-43` - Agent execution and streaming
- `build_front.sh` - Frontend build script
- `db_stuff/howTheyVote.py` - Database scraper
