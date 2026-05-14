# SoulArk Memory Core

> Open-source long-term memory core for AI Agents: stop making your AI start from zero every time.

[中文说明](README.zh-CN.md)

SoulArk Memory Core is a self-hostable long-term memory foundation for AI agents, personal AI assistants, and digital twin products. It focuses on durable memory records, traceable evidence, deletion, export, and a small HTTP API that can sit behind your own agent layer.

## Why SoulArk Memory Core?

Most AI assistants are stateless: every new session feels like a fresh introduction. SoulArk Memory Core gives your agent a minimal memory API so it can write, recall, inspect, delete, and export memory with evidence.

It is designed for:

- long-term memory for AI agents
- self-hosted personal AI assistants
- model-agnostic memory infrastructure
- digital twin and second-brain products
- applications that need traceable evidence instead of opaque recall

SoulArk Memory Core does not promise perfect or permanent truth. Memory can become outdated or corrected over time, so the project emphasizes evidence, traceability, deletion, and export.

## Current Scope

The v0.1 scope is intentionally narrow:

- `write`
- `search`
- `date_recall`
- `daily_recall`
- `delete`
- `export`
- SQLite persistence
- minimal Flask web surface

This v0.1 scope does not include persona, prompt orchestration, project-state prompting, ambient logic, surprise recall, policy guard logic, or channel connectors. Those belong in the agent/product layer above Memory Core.

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

For a temporary online test environment on Linux:

```bash
docker compose up -d --build
bash scripts/verify_http_acceptance.sh http://127.0.0.1:8765
```

The compose file lives at `docker-compose.yml` and persists SQLite data under `./data`.

If you prefer `systemd` instead of Docker:

```bash
bash deploy/ubuntu/bootstrap.sh
cp deploy/ubuntu/env.example deploy/ubuntu/.env
sudo cp deploy/ubuntu/soulark-memory-core.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now soulark-memory-core@$(whoami)
```

This setup is intended for temporary validation, not direct public Internet exposure without an access control layer.

For a one-command Docker acceptance flow on Windows PowerShell:

```powershell
./scripts/verify_docker_acceptance.ps1
```
