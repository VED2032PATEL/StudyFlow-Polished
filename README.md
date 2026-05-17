# StudyFlow

StudyFlow is a Flask study planner with authentication, subject/topic tracking, adaptive scheduling, spaced repetition reviews, analytics, and Groq-powered AI study helpers.

## Features

| Feature | Where | What it does |
|---|---|---|
| Floating AI Chat | Every page | Ask for study help, concepts, planning, and motivation. |
| Topic AI Tools | Topics page | Suggest topic difficulty, deadlines, estimated hours, quizzes, and study tips. |
| Schedule Insights | Schedule page | Analyze workload and suggest improvements. |
| Dashboard AI Advisor | Dashboard | Generate a concise daily focus plan. |
| Spaced Repetition | Reviews page | Schedule review sessions with an SM-2 style algorithm. |

## Quick Start

1. Create and activate a virtual environment.

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Configure environment variables.

```bash
cp .env.example .env
```

Set `SECRET_KEY` and `GROQ_API_KEY` in `.env`. For production with Turso, also set `TURSO_DB_URL` and `TURSO_DB_TOKEN`.

4. Run the app.

```bash
python app.py
```

Open `http://localhost:5000`.

## AI Configuration

By default, StudyFlow uses Groq models:

```env
GROQ_FAST_MODEL=llama-3.1-8b-instant
GROQ_HEAVY_MODEL=llama-3.3-70b-versatile
```

Override these in `.env` if you want to use different Groq-hosted models.

## Deployment Notes

The app can run locally with a SQLite file through `libsql-client`. On Vercel or other serverless hosts, configure Turso so your database persists outside the ephemeral filesystem.
