"""Environment settings for the HTTP service."""

import os


def cors_origins() -> list[str]:
    """Allow local development by default; deployments can specify their origins."""
    value = os.getenv("PLATEX_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")
    return [origin.strip() for origin in value.split(",") if origin.strip()]
