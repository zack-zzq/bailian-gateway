"""Configuration management for Bailian Gateway."""

import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self) -> None:
        self.api_key: str = os.environ.get("OPENAI_API_KEY", "")
        self.base_url: str = os.environ.get(
            "OPENAI_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        # Ensure base_url does not end with a slash
        self.base_url = self.base_url.rstrip("/")

        # Model priority list (comma-separated), highest priority first
        model_priority_str = os.environ.get("MODEL_PRIORITY", "")
        self.model_priority: list[str] = [
            m.strip() for m in model_priority_str.split(",") if m.strip()
        ]

        self.port: int = int(os.environ.get("PORT", "8000"))
        self.host: str = os.environ.get("HOST", "0.0.0.0")

    def validate(self) -> None:
        """Validate required settings."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        if not self.model_priority:
            raise ValueError(
                "MODEL_PRIORITY environment variable is required "
                "(comma-separated list of model IDs)"
            )


settings = Settings()
