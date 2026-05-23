from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.db.database import engine
from app.models import Base
from app.routers.auth import router as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        print("[DB] PostgreSQL connection: OK")
    except Exception as e:
        print(f"[DB] PostgreSQL connection FAILED: {e}")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    await engine.dispose()
    print("[DB] Database connections closed")


app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)


@app.get("/")
async def root():
    return {"message": "Hello From FastAPI"}
