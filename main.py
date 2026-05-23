from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db.database import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Verify database connectivity on startup
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("[DB] PostgreSQL connection: OK")
    except Exception as e:
        print(f"[DB] PostgreSQL connection FAILED: {e}")

    yield

    await engine.dispose()
    print("[DB] Database connections closed")


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello From FastAPI"}
