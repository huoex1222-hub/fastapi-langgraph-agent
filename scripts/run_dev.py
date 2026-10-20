"""Run the FastAPI app with a Windows-compatible event loop.

uvicorn's default ProactorEventLoop on Windows cannot run the psycopg async
pool used by LangGraph. ``--reload`` switches uvicorn to a selector loop in its
child process, but debugpy needs the app to run in the parent process. This
wrapper installs the selector policy before starting uvicorn without reload.
"""

import asyncio
import os
import sys
from pathlib import Path

import uvicorn

# Running a script sets sys.path[0] to scripts/, not the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


def main() -> None:
    """Start uvicorn on the configured host and port."""
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    uvicorn.run(
        "app.main:app",
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "8000")),
        env_file=os.getenv("ENV_FILE", ".env.development"),
    )


if __name__ == "__main__":
    main()
