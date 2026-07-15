# OilChem Agent — Frontend (Step 0)

Minimal React + Vite + TypeScript scaffold.

## Scope (Step 0)

- Vite-powered dev server (port `5173`)
- React 18 + TypeScript
- TailwindCSS configured (utility classes available)
- Home page renders the literal text **OilChem Agent**
- `/api/*` proxied to the FastAPI backend at `http://localhost:8000`

No chat, no component library, no business logic.

## Quick start

```bash
cd frontend
npm install
npm run dev
```

The dev server will be available at http://localhost:5173.

## Build

```bash
npm run build      # type-check + production bundle into dist/
npm run preview    # serve the production bundle locally
```
