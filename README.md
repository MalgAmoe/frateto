# Frateto

Frateto is an AI agent that analyzes European Parliament voting data and EU legislation using Google's Agent Development Kit (ADK).

## Features

- Query European Parliament voting records (reusing the work from HowTheyVote https://github.com/HowTheyVote/data)
- Cross-reference parliamentary votes with actual EU legislation
- Analyze voting patterns by country, political group, and policy topic
- Research EU laws using EUR-Lex SPARQL queries
- Multi-step iterative analysis with state management

## Architecture

- Python (I am using v3.12)
- Google ADK
- Fastapi
- sqlite
- Kimi K2 llm (serverless calls deployed by fireworks.ai)

## Usage

To use it locally, you'll need an API key from https://fireworks.ai/ (FIREWORKS_API_KEY in .env file).
You can replace the model used and use openai or google gemini, but you'll need to replace it in the agent(look for model="fireworks_ai/accounts/fireworks/models/kimi-k2-instruct" in the code).

Other that that:
- python
- uv (for dependencies)
- node and npm to build the frontend

### Steps

Create venv
```
uv venv
```

Get the dependencies
```
uv sync
```

Compile frontend
```
./build_front.sh
```

Run
```
uv run src/main.py
```

Go to `http://localhost:8000`

## Thoughts

With the help of my buddy Claudinho de Antropicão we build this weird machinery.
I tried to make it as self contained as possible, it's all served by fastapi, with a pretty shitty in memory session management. As it's my first python project I am sure I did some weird things.
Concurrency is limited to 20. Maybe it's even too much?
It's pretty slow overall.
The front could be served by vercel, I could have used google-adk generated fastapi, postgres, etc... But I made it small to mess around and understand what is going on.

## License

MIT
