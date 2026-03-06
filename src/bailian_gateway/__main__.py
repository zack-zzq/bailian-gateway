"""Entry point for running the gateway directly with `python -m bailian_gateway`."""

import logging

import uvicorn

from .config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

if __name__ == "__main__":
    uvicorn.run(
        "bailian_gateway.app:app",
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
