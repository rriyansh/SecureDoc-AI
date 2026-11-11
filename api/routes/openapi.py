"""Custom OpenAPI enrichment."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi


def register(app: FastAPI) -> None:
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        schema["info"]["x-logo"] = {"url": "https://example.com/logo.png"}
        schema["servers"] = [{"url": "http://localhost:8000", "description": "local"}]
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
