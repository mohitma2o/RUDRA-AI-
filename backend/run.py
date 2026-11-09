"""Frozen/backend entry point for the Rudra FastAPI service."""

import multiprocessing
import os
import sys
from pathlib import Path


def main() -> None:
    multiprocessing.freeze_support()
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")

    backend_dir = str(Path(__file__).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    import uvicorn
    from app.main import app

    uvicorn.run(
        app,
        host="127.0.0.1",
        port=int(os.environ.get("RUDRA_PORT", "8000")),
        log_level="info",
        log_config=None,
    )


if __name__ == "__main__":
    main()
