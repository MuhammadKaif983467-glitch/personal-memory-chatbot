"""Module-level FastAPI app for uvicorn (``uvicorn app.main:app``).

The heavy lifting lives in :mod:`app.factory` so tests can import
``create_app`` without building the default development database.
"""

from app.factory import create_app

app = create_app()