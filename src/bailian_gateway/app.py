"""FastAPI application with OpenAI-compatible endpoints."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import settings
from .gateway import (
    close_client,
    exhausted_models,
    proxy_chat_completions,
)

logger = logging.getLogger("bailian_gateway")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    settings.validate()
    logger.info(
        f"Bailian Gateway starting with {len(settings.model_priority)} models: "
        f"{', '.join(settings.model_priority)}"
    )
    yield
    await close_client()
    logger.info("Bailian Gateway shut down.")


app = FastAPI(
    title="Bailian Gateway",
    description="OpenAI-compatible gateway for Alibaba Cloud Bailian with automatic model fallback",
    version="0.1.0",
    lifespan=lifespan,
)


@app.post("/v1/chat/completions")
async def chat_completions(request: Request) -> Any:
    """Proxy chat completions with automatic model fallback."""
    body = await request.json()
    return await proxy_chat_completions(body)


@app.get("/v1/models")
async def list_models() -> JSONResponse:
    """List available models (excluding exhausted ones)."""
    available = [m for m in settings.model_priority if m not in exhausted_models]
    models_data = [
        {
            "id": model_id,
            "object": "model",
            "created": int(time.time()),
            "owned_by": "bailian-gateway",
        }
        for model_id in available
    ]
    return JSONResponse(
        content={
            "object": "list",
            "data": models_data,
        }
    )


@app.get("/health")
async def health_check() -> JSONResponse:
    """Health check endpoint."""
    available = [m for m in settings.model_priority if m not in exhausted_models]
    return JSONResponse(
        content={
            "status": "ok",
            "total_models": len(settings.model_priority),
            "available_models": len(available),
            "exhausted_models": list(exhausted_models),
        }
    )
