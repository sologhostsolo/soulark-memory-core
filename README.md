# SoulArk Memory Core

`SoulArk Memory Core` is the first runnable scaffold for the shared memory foundation described in the product roadmap.

Current scope is intentionally narrow:

- `write`
- `search`
- `date_recall`
- `daily_recall`
- `delete`
- `export`
- SQLite persistence
- minimal Flask web surface

This scaffold does not include persona, prompt orchestration, project-state prompting, ambient logic, or any channel connectors.

## Quick Start

```bash
pip install -r requirements.txt
python run.py
```

Default service address: `http://127.0.0.1:8765`

## Personal Integration Sample

Run a minimal `Personal -> Core` HTTP sample against a running local service:

```bash
python examples/personal_core_integration_sample.py
```

The sample writes one memory item through HTTP, then verifies `search`, `daily_recall`, and `export` from the same service.

## Endpoints

- `GET /health`
- `GET /`
- `GET /demo`
- `POST /api/v1/write`
- `POST /api/v1/search`
- `POST /api/v1/date-recall`
- `POST /api/v1/daily-recall`
- `POST /api/v1/delete`
- `GET /api/v1/export`

## Docker

```bash
docker build -t soulark-memory-core .
docker run --rm -p 8765:8765 -v memory-core-data:/data soulark-memory-core
```

The database path defaults to `/data/memory_core.db` in Docker and `data/memory_core.db` locally.

For a one-command Docker acceptance flow on Windows PowerShell:

```powershell
./scripts/verify_docker_acceptance.ps1
```