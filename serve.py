"""Production-style server (waitress). Use instead of `python app.py` for deployment.

    python serve.py            ->  http://127.0.0.1:8000   (HOST / PORT env vars override)
See docs/deployment.md (HTTPS, APP_ENV=production, reverse proxy).
"""
import os

from waitress import serve

from app import create_app

if __name__ == "__main__":
    serve(create_app(), host=os.environ.get("HOST", "127.0.0.1"), port=int(os.environ.get("PORT", "8000")),
          threads=8)
