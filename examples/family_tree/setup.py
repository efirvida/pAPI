import logging
import subprocess
from pathlib import Path

from papi.core.addons import AddonSetupHook

logger = logging.getLogger(__name__)


class BuildJSLib(AddonSetupHook):
    """
    Initializes the addon by building the family-chart.js library.
    """

    async def run(self) -> None:
        """
        Builds static/libs/family-chart using npm.

        Steps:
        1. Navigate to the library directory.
        2. Run `npm install` to install dependencies.
        3. Run `npm run build` to compile the library.
        """
        base_dir = Path(__file__).parent
        lib_dir = base_dir / "static" / "libs" / "family-chart"

        if not lib_dir.exists():
            logger.error(f"Directory not found: {lib_dir.resolve()}")
            raise FileNotFoundError(f"Required directory does not exist: {lib_dir}")

        try:
            logger.info("Installing dependencies for family-chart.js...")
            subprocess.run(["npm", "install"], cwd=lib_dir, check=True)

            logger.info("Building family-chart.js...")
            subprocess.run(["npm", "run", "build"], cwd=lib_dir, check=True)

            logger.info("family-chart.js built successfully.")

        except subprocess.CalledProcessError as e:
            logger.exception(f"Command failed with exit code {e.returncode}")
            raise RuntimeError("Failed to build family-chart.js") from e
