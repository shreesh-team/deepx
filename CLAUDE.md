# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Purpose

DeepX is an LLM observability platform. The core idea:

```
User → Chatbot UI → [SDK Wrapper] → LLM API
                         ↓
                  Ingestion API → Database
```

The FastAPI backend serves as the **Ingestion API** — receiving logs from the SDK wrapper, validating them, and persisting them to PostgreSQL. The schema should capture messages, sessions, and per-call metadata (latency, tokens, success/failure).

## Commands

This project uses `uv` as the package manager.

```bash
# Run dev server (auto-reload)
uv run fastapi dev main.py

# Run production server
uv run fastapi run main.py

# Add a dependency
uv add <package>

# Run a script/one-off
uv run python -c "..."
```

## Architecture

**Entry point**: `main.py` — defines the FastAPI `app` and the `lifespan` context manager. The lifespan runs a `SELECT 1` health check against PostgreSQL on startup (prints `[DB] PostgreSQL connection: OK` or a failure message) and disposes the connection pool on shutdown.

**Config** (`app/core/config.py`): `pydantic-settings` `Settings` class reads all config from `.env`. The `DATABASE_URL` must use the `postgresql+asyncpg://` scheme. Pool settings (`DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_PRE_PING`) are also configurable via env.

**Database** (`app/db/database.py`): Creates a SQLAlchemy 2.0 async engine and an `async_sessionmaker`. The `get_db()` async generator is the standard FastAPI dependency for per-request sessions.

## Environment

Copy `.env.example` to `.env` and fill in credentials before running:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/deepx
```

`.env` is gitignored. Never commit it.
