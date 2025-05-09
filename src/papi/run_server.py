"""
Application entry point for launching the FastAPI server using Uvicorn
with unified logging (Loguru).
"""

import uvicorn
from core.logger import setup_logging
from core.settings import get_config

setup_logging()


config = get_config()


def main() -> None:
    uvicorn.run(
        "core.server:pAPI",
        host=config.server.host,
        port=config.server.port,
        reload=True,
        log_config=None,
        log_level=None,
    )


if __name__ == "__main__":
    main()
