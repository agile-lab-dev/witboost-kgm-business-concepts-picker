"""
Application entry-point.

Creates the FastAPI app, registers middleware (CORS, request logging),
and includes all routers.
"""

import os
import sys

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from src.dependencies import get_settings
from src.routers import custom_url_picker_router

# ---------------------------------------------------------------------------
# Log level (default: DEBUG)
# ---------------------------------------------------------------------------

_log_level = os.environ.get("LOG_LEVEL", "DEBUG").upper()
logger.remove()
logger.add(sys.stderr, level=_log_level)

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Custom URL Picker",
    description="Witboost Custom URL Picker — serves drop-down options from an external service.",
    version="0.1.0",
)

# ---------------------------------------------------------------------------
# CORS — allow the Witboost UI to call this service
# ---------------------------------------------------------------------------

_settings = get_settings()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[_settings.custom_url_picker.cors.origin],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Request / response logging
# ---------------------------------------------------------------------------


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info("{} {}", request.method, request.url)
    response = await call_next(request)
    logger.info("Response status: {}", response.status_code)
    return response


# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(custom_url_picker_router.router)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
