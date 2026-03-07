import os
from unittest.mock import patch

from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


@patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"})
@patch("src.cli.main.load_repos")
@patch("src.cli.main.GithubClient")
@patch("src.cli.main.Collector")
def test_collect_stub(mock_collector, mock_client, mock_load_repos) -> None:
    # Setup mock repos config
    mock_repos_config = type(
        "obj", (object,), {"filters": None, "limits": None, "repos": ["test/repo"]}
    )
    mock_load_repos.return_value = mock_repos_config

    result = runner.invoke(app, ["collect"])
    assert result.exit_code == 0
    assert "Collecting data using repos.yaml and config.yaml..." in result.stdout
    assert "Collection completed successfully." in result.stdout


def test_normalize_stub() -> None:
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 0
    assert "Normalizing data..." in result.stdout


def test_run_stub() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "Running pipeline..." in result.stdout
