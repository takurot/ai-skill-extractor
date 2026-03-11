from datetime import date
from pathlib import Path

from src.cli.config_loader import load_repos


def test_load_repos_accepts_yaml_dates_and_strings(tmp_path: Path) -> None:
    repos_path = tmp_path / "repos.yaml"
    repos_path.write_text(
        """
repos:
  - example/repo
filters:
  since: 2024-01-02
  until: "2024-12-31"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    repos_config = load_repos(str(repos_path))

    assert repos_config.filters.since == date(2024, 1, 2)
    assert repos_config.filters.until == date(2024, 12, 31)
