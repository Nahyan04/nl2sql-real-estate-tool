from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.routes import examples as examples_routes
from app.api.routes import health as health_routes
from app.api.routes import query as query_routes
from app.api.routes import schema as schema_routes
from app.config import get_settings
from app.models.contracts import ErrorResponse
from app.core.database import get_engine
from app.services.product_schema import introspect_product_schema

API_PREFIX = "/api/v1"

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
    introspect_product_schema(engine)

    app.state.engine = engine
    app.state.settings = settings

    yield

    engine.dispose()


app = FastAPI(title="nl2sql-real-estate", version="0.1.0", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def invalid_request_handler(request, exc: RequestValidationError):
    request_id = uuid4().hex
    logger.info("invalid request request_id=%s path=%s", request_id, request.url.path)
    return JSONResponse(
        status_code=422,
        content=ErrorResponse(
            error="INVALID_REQUEST",
            detail="Check the question, provider and request format.",
            request_id=request_id,
        ).model_dump(),
        headers={"X-Request-ID": request_id},
    )

app.include_router(health_routes.router)
app.include_router(query_routes.router, prefix=API_PREFIX)
app.include_router(examples_routes.router, prefix=API_PREFIX)
app.include_router(schema_routes.router, prefix=API_PREFIX)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in get_settings().cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)
