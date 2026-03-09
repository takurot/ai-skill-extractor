from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ENV_FILE = PROJECT_ROOT / ".env"


def load_project_env(env_file: Optional[Path] = None) -> None:
    """Load repository-local environment variables from .env."""
    load_dotenv(env_file or PROJECT_ENV_FILE, override=True)
