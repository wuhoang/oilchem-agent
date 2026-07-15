# OilChem Agent

Enterprise-grade Agent platform for the OilChem domain.

> **Status:** Step 0 — Project Bootstrap. No business logic implemented yet.

## Repository layout

```
oilchem-agent/
├── backend/          # FastAPI + Python 3.12
├── frontend/         # React + Vite + TypeScript
├── docs/             # architecture.md, roadmap.md, api.md
├── docker/           # Dockerfile.backend, Dockerfile.frontend, compose
├── assets/           # shared static assets (placeholder)
├── .gitignore
├── LICENSE
└── README.md
```

## Tech stack

- **Backend**  — Python 3.12, FastAPI, Uvicorn, Pydantic v2, Pydantic
  Settings, Loguru, HTTPX, SQLAlchemy, Alembic
- **Frontend** — Node.js 22 LTS, React, Vite, TypeScript, TailwindCSS
- **Tooling**  — Poetry / pip, npm

## Quick start

### Backend

```bash
cd backend
pip install -r requirements.txt
cp .env.example .env
python -m app.main
# → http://localhost:8000
```

Available routes:

| Method | Path      | Purpose                |
|--------|-----------|------------------------|
| GET    | `/`       | Application banner     |
| GET    | `/health` | Liveness probe         |
| GET    | `/docs`   | Swagger UI             |

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

The home page renders the literal text **OilChem Agent**.

### Docker

```bash
docker compose -f docker/docker-compose.yml up --build
# Backend:  http://localhost:8000
# Frontend: http://localhost:8080
```

## Git workflow

- `main`    — stable, production
- `develop` — integration branch
- `feature/*` — short-lived feature branches off `develop`

See [docs/roadmap.md](docs/roadmap.md) for the planned milestones and
[docs/architecture.md](docs/architecture.md) for the component map.
