from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError

from app.api.routes import health as health_routes
from app.config import get_settings
from app.core.database import get_engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = get_settings()
    except ValidationError as exc:
        sys.exit(f"configuration error — cannot start:\n{exc}")

    engine = get_engine()
    # fail fast: verify the database is reachable before accepting traffic
    with engine.connect():
        pass

    app.state.engine = engine
    app.state.settings = settings

    yield

    engine.dispose()


app = FastAPI(title="nl2sql-real-estate", version="0.1.0", lifespan=lifespan)

app.include_router(health_routes.router)

# TODO: restrict allow_origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
