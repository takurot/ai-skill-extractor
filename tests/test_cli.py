from typer.testing import CliRunner

from src.cli.main import app

runner = CliRunner()


def test_collect_stub() -> None:
    result = runner.invoke(app, ["collect"])
    assert result.exit_code == 0
    assert "Collecting data..." in result.stdout


def test_normalize_stub() -> None:
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 0
    assert "Normalizing data..." in result.stdout


def test_run_stub() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "Running pipeline..." in result.stdout
