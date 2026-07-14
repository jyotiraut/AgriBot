"""
KrishiMitra - FastAPI Application Entry Point
"""
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.mongo import connect_db, disconnect_db
from api.routes import router
from api.auth_routes import router as auth_router
from notifications import start_schedular, stop_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger   = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────────
    logger.info("KrishiMitra starting up — connecting to MongoDB...")

    if settings.jwt_secret_is_default:
        logger.warning(
            "JWT_SECRET is the insecure default — set a strong JWT_SECRET "
            "environment variable before deploying to production."
        )

    await connect_db()

    # Start the Phase 4 Notification Cron Job
    start_schedular()

    yield

    # ── Shutdown ──────────────────────────────────────────────────────────────
    stop_scheduler()
    await disconnect_db()
    logger.info("KrishiMitra shutting down.")


app = FastAPI(
    title="KrishiMitra API",
    description=(
        "AI-powered agricultural advisory system for smallholder farmers in Nepal.\n\n"
        "Phase 1 — Foundation & Rule Engine:\n"
        "- Farmer profile management (Type A active / Type B planning)\n"
        "- District → Zone classification (Terai / Hills / Mountains)\n"
        "- DAS / GDD growth stage calculator\n"
        "- Crop suitability engine\n"
        "- Safety guardrails (fertilizer / pesticide limits)\n"
        "- LangGraph advisory pipeline with LLM synthesis"
    ),
    version="1.0.0",
    lifespan=lifespan,
)

_cors_origins = settings.cors_origins_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Credentials cannot be combined with a wildcard origin (browsers reject it).
    allow_credentials=_cors_origins != ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router,      prefix="/api/v1",      tags=["KrishiMitra"])
app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])


@app.get("/", tags=["Health"])
def root():
    return {"status": "ok", "service": "KrishiMitra", "phase": 1}


@app.get("/health", tags=["Health"])
def health():
    return {"status": "healthy"}