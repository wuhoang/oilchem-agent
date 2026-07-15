# OilChem Agent — API

All business endpoints are versioned under `/api/v1`. Bootstrap endpoints
remain at the root.

## Bootstrap endpoints

### `GET /`

Returns the application banner.

```json
{
  "name": "OilChem Agent",
  "version": "0.1.0",
  "status": "running"
}
```

### `GET /health`

Liveness probe.

```json
{ "status": "ok" }
```

## v1 endpoints

| Method | Path | Description |
|--------|------|-------------|
| _none_ | _none_ | Reserved for future releases |

The `/api/v1` prefix is mounted; business endpoints (chat, tools, …) will
be added in subsequent steps.
