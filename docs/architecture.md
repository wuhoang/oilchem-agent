# OilChem Agent — Architecture (Step 0)

## High-level

```
┌────────────────────┐    HTTP    ┌────────────────────┐
│  React + Vite SPA  │ ─────────▶ │  FastAPI backend   │
│  (frontend/)       │ ◀───────── │  (backend/app/)    │
└────────────────────┘   JSON     └────────────────────┘
                                       │
                                       ▼
                              ┌────────────────────┐
                              │  Loguru logs       │
                              │  (logs/app.log)    │
                              └────────────────────┘
```

## Backend layout

| Layer          | Path                          | Step 0 state           |
|----------------|-------------------------------|------------------------|
| Entry point    | `app/main.py`                 | Implemented            |
| Config         | `app/core/config.py`          | Implemented            |
| Logging        | `app/core/logger.py`          | Implemented            |
| API root       | `app/api/v1/router.py`        | Implemented (empty)    |
| Agent          | `app/agent/`                  | Placeholder            |
| Tools          | `app/tools/`                  | Placeholder            |
| LLM            | `app/llm/`                    | Placeholder            |
| Database       | `app/database/`               | Placeholder            |
| Guardrails     | `app/guardrails/`             | Placeholder            |
| MCP            | `app/mcp/`                    | Placeholder            |

## Branching

- `main`    — stable, releasable
- `develop` — integration branch
- feature/* — short-lived topic branches off `develop`
