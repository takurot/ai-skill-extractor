from typing import Any, Dict

import yaml

from src.models.config import Config
from src.models.repos import ReposConfig


def load_config(config_path: str) -> Config:
    """Load and validate config.yaml."""
    with open(config_path, "r") as f:
        data: Dict[str, Any] = yaml.safe_load(f)
    return Config(**data)


def load_repos(repos_path: str) -> ReposConfig:
    """Load and validate repos.yaml."""
    with open(repos_path, "r") as f:
        data: Dict[str, Any] = yaml.safe_load(f)
    return ReposConfig(**data)
