# OilChem Agent — Backend (Step 0)

Step 0 bootstrap for the OilChem Agent backend.

## Scope (Step 0)

- FastAPI application skeleton
- Loguru-based logging (console + `logs/app.log`)
- Pydantic v2 settings loaded from `.env`
- Root banner endpoint: `GET /`
- Health probe:        `GET /health`
- v1 API mount point:  `/api/v1/...` (no business endpoints yet)
- Placeholder modules for future agent / tool / LLM / database work

No business logic is implemented in this step.

## Requirements

- Python 3.12
- Poetry (recommended) **or** `uv` or plain `pip`

## Quick start

```bash
# 1. install deps
poetry install
# or:
pip install -r requirements.txt

# 2. configure env
cp .env.example .env

# 3. run the API
poetry run python -m app.main
# or:
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## Endpoints

| Method | Path     | Description              |
|--------|----------|--------------------------|
| GET    | `/`      | Application banner JSON  |
| GET    | `/health`| Liveness probe           |
| GET    | `/docs`  | Swagger UI (auto)        |

## Project layout

```
backend/
├── app/
│   ├── api/v1/            # future /api/v1/...
│   ├── core/              # config, logger, security, constants
│   ├── agent/             # planner / memory / prompts / executor / manager
│   ├── tools/             # tool base / registry / manager / builtin
│   ├── llm/               # LLM client / provider / schemas
│   ├── models/            # SQLAlchemy ORM models (later)
│   ├── services/          # business services (later)
│   ├── schemas/           # API request/response schemas (later)
│   ├── middleware/        # custom middleware (later)
│   ├── database/          # session / base
│   ├── guardrails/        # input/output/permission guards
│   ├── mcp/               # MCP client/server (later)
│   ├── utils/             # shared utilities
│   └── main.py            # FastAPI entry point
├── tests/
├── scripts/
├── logs/                  # generated at runtime
├── requirements.txt
├── pyproject.toml
└── .env.example
```
