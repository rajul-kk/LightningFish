"""
Modal deployment for Lightningfish service.

Deploy:   modal deploy lightningfish_service/modal_app.py
Serve:    modal serve lightningfish_service/modal_app.py
Secrets:  modal secret create lightningfish-secrets \
            ANTHROPIC_API_KEY=... \
            DATABASE_URL=... \
            REDDIT_CLIENT_ID=... \
            REDDIT_CLIENT_SECRET=... \
            REDDIT_USER_AGENT=... \
            GITHUB_TOKEN=... \
            SEC_EDGAR_USER_AGENT=... \
            ALLOWED_ORIGINS=https://your-vercel-app.vercel.app
"""
from __future__ import annotations

import modal

app = modal.App("lightningfish-service")

image = (
    modal.Image.debian_slim(python_version="3.10")
    .pip_install(
        "fastapi>=0.115",
        "uvicorn>=0.29",
        "anthropic>=0.50",
        "openai>=1.0",
        "slowapi>=0.1.9",
        "psycopg2-binary>=2.9",
        "pydantic>=2.7",
        "scipy>=1.12",
        "yfinance>=0.2",
        "praw>=7.7",
        "requests>=2.31",
        "sec-edgar-downloader>=5.0",
        "PyGithub>=2.0",
    )
    .add_local_dir(".", remote_path="/app", ignore=["__pycache__", "*.pyc", ".git"])
)


@app.function(
    image=image,
    secrets=[modal.Secret.from_name("lightningfish-secrets")],
    timeout=600,
)
@modal.asgi_app()
def fastapi_app():
    import sys
    sys.path.insert(0, "/app")
    from lightningfish_service.main import app as _app
    return _app
