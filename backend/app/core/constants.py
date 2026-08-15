"""
Project-wide constants.

Keep this module dependency-free so it can be imported anywhere.
"""

from pathlib import Path

APP_NAME: str = "OilChem Agent"
APP_VERSION: str = "1.1.0"
API_V1_PREFIX: str = "/api/v1"

# Paths
# constants.py -> app/core/ -> app/ -> backend/ -> project_root
BACKEND_ROOT: Path = Path(__file__).resolve().parents[2]
LOGS_DIR: Path = BACKEND_ROOT / "logs"
APP_LOG_FILE: Path = LOGS_DIR / "app.log"
