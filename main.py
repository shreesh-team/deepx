from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.core.config import settings
from app.db.database import engine
from app.models import Base
from app.routers.auth import router as auth_router
from app.routers.conversations import router as conversations_router
from app.routers.ingestion import router as ingestion_router


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

_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    missing = [e["loc"][-1] for e in exc.errors() if e["type"] == "missing"]
    if missing:
        message = f"Missing required field(s): {', '.join(missing)}"
    else:
        message = str(exc.errors()[0].get("msg", "Invalid request"))
    return JSONResponse(
        status_code=400,
        content={"error": {"code": "MISSING_FIELD", "message": message}},
    )


app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(ingestion_router)


@app.get("/")
async def root():
    return {"message": "Hello From FastAPI"}
