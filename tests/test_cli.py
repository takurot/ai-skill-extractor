import os
from typing import Any
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from src.cli.main import app
from src.extract.embedder import EmbeddingGenerationError

runner = CliRunner()


@patch.dict(os.environ, {"GITHUB_TOKEN": "fake_token"})
@patch("src.cli.main.load_repos")
@patch("src.cli.main.GithubClient")
@patch("src.cli.main.Collector")
def test_collect_stub(mock_collector: Any, mock_client: Any, mock_load_repos: Any) -> None:
    # Setup mock repos config
    mock_repos_config = type(
        "obj", (object,), {"filters": None, "limits": None, "repos": ["test/repo"]}
    )
    mock_load_repos.return_value = mock_repos_config

    result = runner.invoke(app, ["collect"])
    assert result.exit_code == 0
    assert "Collecting data using configs/repos.yaml and configs/config.yaml..." in result.stdout
    assert "Collection completed successfully." in result.stdout


@patch("src.cli.main.load_config")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.cli.main.Normalizer")
def test_normalize_stub(
    mock_normalizer: Any, mock_get_session: Any, mock_get_engine: Any, mock_load_config: Any
) -> None:
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 0
    assert "Normalizing data using configs/config.yaml..." in result.stdout
    assert "Normalization completed successfully." in result.stdout


def test_run_stub() -> None:
    result = runner.invoke(app, ["run"])
    assert result.exit_code == 0
    assert "Running pipeline..." in result.stdout


@patch("src.cli.main.load_config")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.extract.embedder.SkillEmbedder")
@patch("src.analyze.llm_client.LLMClient")
def test_embed_uses_configured_embedding_model(
    mock_llm_client: Any,
    mock_embedder_cls: Any,
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_load_config: Any,
) -> None:
    mock_load_config.return_value = MagicMock(
        models=MagicMock(embedding_model="text-embedding-3-large")
    )
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    mock_get_session_factory.return_value.return_value.__enter__.return_value = mock_session

    result = runner.invoke(app, ["embed"])

    assert result.exit_code == 0
    mock_llm_client.assert_called_once_with(embedding_model="text-embedding-3-large")
    mock_embedder_cls.return_value.process_candidates.assert_called_once_with([])


@patch("src.cli.main.load_config")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.extract.embedder.SkillEmbedder")
@patch("src.analyze.llm_client.LLMClient")
def test_embed_exits_nonzero_when_embedding_generation_fails(
    mock_llm_client: Any,
    mock_embedder_cls: Any,
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_load_config: Any,
) -> None:
    mock_load_config.return_value = MagicMock(
        models=MagicMock(embedding_model="text-embedding-3-large")
    )
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = [MagicMock(id="sc_1")]
    mock_get_session_factory.return_value.return_value.__enter__.return_value = mock_session
    mock_embedder_cls.return_value.process_candidates.side_effect = EmbeddingGenerationError(
        [("sc_1", "API Error")]
    )

    result = runner.invoke(app, ["embed"])

    assert result.exit_code == 1
    assert "Embedding generation failed:" in result.stdout
    mock_llm_client.assert_called_once_with(embedding_model="text-embedding-3-large")
    mock_session.commit.assert_not_called()
