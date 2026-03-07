"""Core gateway logic: proxy requests to Bailian with model fallback."""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
from fastapi import HTTPException
from fastapi.responses import StreamingResponse

from .config import settings

logger = logging.getLogger("bailian_gateway")

# In-memory set of models whose free quota has been exhausted.
# Free quota exhaustion is irreversible, so we persist this to a file.
DATA_DIR = Path("data")
EXHAUSTED_MODELS_FILE = DATA_DIR / "exhausted_models.json"

def _load_exhausted_models() -> set[str]:
    """Load the set of exhausted models from disk."""
    if EXHAUSTED_MODELS_FILE.exists():
        try:
            with open(EXHAUSTED_MODELS_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception as e:
            logger.error(f"Failed to load exhausted models from {EXHAUSTED_MODELS_FILE}: {e}")
    return set()

def _save_exhausted_models() -> None:
    """Save the set of exhausted models to disk."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(EXHAUSTED_MODELS_FILE, "w", encoding="utf-8") as f:
            json.dump(list(exhausted_models), f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save exhausted models to {EXHAUSTED_MODELS_FILE}: {e}")

exhausted_models: set[str] = _load_exhausted_models()

# Shared async HTTP client (created lazily)
_client: httpx.AsyncClient | None = None

QUOTA_ERROR_CODE = "AllocationQuota.FreeTierOnly"


def get_client() -> httpx.AsyncClient:
    """Get or create the shared httpx async client."""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(timeout=httpx.Timeout(300.0, connect=10.0))
    return _client


async def close_client() -> None:
    """Close the shared httpx client."""
    global _client
    if _client is not None and not _client.is_closed:
        await _client.aclose()
        _client = None


def _get_available_models() -> list[str]:
    """Return the list of models that still have quota, in priority order."""
    return [m for m in settings.model_priority if m not in exhausted_models]


def _is_quota_exhausted_error(status_code: int, body: bytes) -> bool:
    """Check if the response indicates a free quota exhaustion error."""
    if status_code != 403:
        return False
    try:
        data = json.loads(body)
        error = data.get("error", {})
        code = error.get("code", "")
        return code == QUOTA_ERROR_CODE
    except (json.JSONDecodeError, AttributeError):
        return False


def _is_quota_exhausted_error_str(status_code: int, text: str) -> bool:
    """Check if a text response indicates quota exhaustion."""
    if status_code != 403:
        return False
    try:
        data = json.loads(text)
        error = data.get("error", {})
        code = error.get("code", "")
        return code == QUOTA_ERROR_CODE
    except (json.JSONDecodeError, AttributeError):
        return False


def _build_headers() -> dict[str, str]:
    """Build headers for the upstream request."""
    return {
        "Authorization": f"Bearer {settings.api_key}",
        "Content-Type": "application/json",
    }


async def proxy_chat_completions(request_body: dict[str, Any]) -> Any:
    """
    Proxy a chat completions request with automatic model fallback.

    For non-streaming requests, tries each model in priority order.
    For streaming requests, peeks at the first response to detect errors
    before committing to streaming back to the client.
    """
    available_models = _get_available_models()
    if not available_models:
        raise HTTPException(
            status_code=503,
            detail={
                "error": {
                    "message": "All configured models have exhausted their free quota.",
                    "type": "service_unavailable",
                    "code": "all_models_exhausted",
                    "exhausted_models": list(exhausted_models),
                }
            },
        )

    is_stream = request_body.get("stream", False)

    if is_stream:
        return await _proxy_streaming(request_body, available_models)
    else:
        return await _proxy_non_streaming(request_body, available_models)


async def _proxy_non_streaming(
    request_body: dict[str, Any], models: list[str]
) -> dict[str, Any]:
    """Try each model for a non-streaming request."""
    client = get_client()
    url = f"{settings.base_url}/chat/completions"
    headers = _build_headers()

    last_error: dict[str, Any] | None = None

    for model_id in models:
        body = {**request_body, "model": model_id}
        logger.info(f"Trying model: {model_id}")

        response = await client.post(url, json=body, headers=headers)

        if _is_quota_exhausted_error(response.status_code, response.content):
            logger.warning(f"Model {model_id} quota exhausted, trying next model...")
            exhausted_models.add(model_id)
            _save_exhausted_models()
            continue

        # For any other response (success or non-quota error), return it
        result = response.json()
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=result)

        return result

    # All models exhausted
    raise HTTPException(
        status_code=503,
        detail={
            "error": {
                "message": "All configured models have exhausted their free quota.",
                "type": "service_unavailable",
                "code": "all_models_exhausted",
                "exhausted_models": list(exhausted_models),
            }
        },
    )


async def _proxy_streaming(
    request_body: dict[str, Any], models: list[str]
) -> StreamingResponse:
    """Try each model for a streaming request.

    For each model, we start a streaming request. We read the initial bytes
    to check if it's a quota error. If so, we close that stream and try the next.
    Once we find a working model, we stream the response back to the client.
    """
    client = get_client()
    url = f"{settings.base_url}/chat/completions"
    headers = _build_headers()

    for model_id in models:
        body = {**request_body, "model": model_id, "stream": True}
        logger.info(f"Trying model (streaming): {model_id}")

        req = client.build_request("POST", url, json=body, headers=headers)
        response = await client.send(req, stream=True)

        # For non-2xx responses, read the full body to check for quota error
        if response.status_code != 200:
            body_bytes = await response.aread()
            await response.aclose()

            if _is_quota_exhausted_error(response.status_code, body_bytes):
                logger.warning(
                    f"Model {model_id} quota exhausted, trying next model..."
                )
                exhausted_models.add(model_id)
                _save_exhausted_models()
                continue

            # Non-quota error, return it to the client
            try:
                error_data = json.loads(body_bytes)
            except json.JSONDecodeError:
                error_data = {"error": {"message": body_bytes.decode(errors="replace")}}
            raise HTTPException(status_code=response.status_code, detail=error_data)

        # Success! Stream the response back
        logger.info(f"Model {model_id} responded successfully, streaming to client...")

        async def stream_generator(resp: httpx.Response) -> AsyncIterator[bytes]:
            try:
                async for chunk in resp.aiter_bytes():
                    yield chunk
            finally:
                await resp.aclose()

        return StreamingResponse(
            stream_generator(response),
            status_code=200,
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # All models exhausted
    raise HTTPException(
        status_code=503,
        detail={
            "error": {
                "message": "All configured models have exhausted their free quota.",
                "type": "service_unavailable",
                "code": "all_models_exhausted",
                "exhausted_models": list(exhausted_models),
            }
        },
    )
