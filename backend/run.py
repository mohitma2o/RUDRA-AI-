"""Frozen/backend entry point for the Rudra FastAPI service."""

import multiprocessing
import os

import uvicorn

from app.main import app


def main() -> None:
    multiprocessing.freeze_support()
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("RUDRA_PORT", "8000")),
        log_level="info",
    )


if __name__ == "__main__":
    main()
