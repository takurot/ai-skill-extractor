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
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.cli.main.Normalizer")
def test_normalize_stub(
    mock_normalizer: Any,
    mock_get_session: Any,
    mock_get_engine: Any,
    mock_run_preflight: Any,
    mock_load_config: Any,
) -> None:
    result = runner.invoke(app, ["normalize"])
    assert result.exit_code == 0
    assert "Normalizing data using configs/config.yaml..." in result.stdout
    assert "Normalization completed successfully." in result.stdout
    mock_run_preflight.assert_called_once()


@patch("src.cli.main.load_config")
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.generate.generator.ArtifactGenerator")
def test_generate_uses_accepted_skills_and_writes_output(
    mock_generator_cls: Any,
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_run_preflight: Any,
    mock_load_config: Any,
) -> None:
    mock_load_config.return_value = MagicMock(
        storage=MagicMock(db_url="sqlite://", artifact_dir="output"),
        generation=MagicMock(
            skills_output="skills/SKILLS.yaml",
            docs_output_dir="docs",
            language_split=True,
            framework_split=True,
        ),
    )
    accepted_query = MagicMock()
    all_candidates_query = MagicMock()
    review_query = MagicMock()
    mock_candidates = [MagicMock(id="sc_1")]
    mock_all_candidates = [
        MagicMock(id="sc_1", rejection_reason=None),
        MagicMock(id="sc_2", rejection_reason="low_confidence"),
    ]
    mock_review_items = [MagicMock(id="ri_1")]
    accepted_query.filter.return_value.all.return_value = mock_candidates
    all_candidates_query.all.return_value = mock_all_candidates
    review_query.all.return_value = mock_review_items
    mock_session = MagicMock()
    mock_session.query.side_effect = [accepted_query, all_candidates_query, review_query]
    mock_get_session_factory.return_value.return_value.__enter__.return_value = mock_session
    mock_generator_cls.return_value.generate.return_value = ["output/skills/SKILLS.yaml"]

    result = runner.invoke(app, ["generate"])

    assert result.exit_code == 0
    mock_generator_cls.assert_called_once_with(
        "output",
        language_split=True,
        framework_split=True,
    )
    mock_generator_cls.return_value.generate.assert_called_once_with(
        mock_candidates,
        mock_review_items,
        skills_output_path="skills/SKILLS.yaml",
        docs_output_dir="docs",
        all_candidates=mock_all_candidates,
        rejection_reasons={"low_confidence": 1},
    )
    assert "Generation completed successfully." in result.stdout
    mock_run_preflight.assert_called_once()


@patch("src.cli.main.load_config")
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.curate.deduplicator.write_deduplication_artifacts")
@patch("src.curate.deduplicator.SkillDeduplicator")
@patch("src.analyze.llm_client.LLMClient")
def test_dedup_processes_candidates(
    mock_llm_client: Any,
    mock_deduplicator_cls: Any,
    mock_write_artifacts: Any,
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_run_preflight: Any,
    mock_load_config: Any,
) -> None:
    mock_load_config.return_value = MagicMock(
        storage=MagicMock(db_url="sqlite://", artifact_dir="output"),
        models=MagicMock(classification_model="gpt-4o"),
        pipeline=MagicMock(
            dedup_threshold=0.88,
            min_skill_confidence=0.72,
            min_cross_repo_support=2,
        ),
    )
    candidate_query = MagicMock()
    review_query = MagicMock()
    mock_candidates = [MagicMock(id="sc_1", source_review_item_ids=["ri_1"], embedding=[0.1, 0.2])]
    mock_review_item = MagicMock(id="ri_1")
    candidate_query.filter.return_value.all.return_value = mock_candidates
    review_query.all.return_value = [mock_review_item]
    mock_session = MagicMock()
    mock_session.query.side_effect = [candidate_query, review_query]
    mock_get_session_factory.return_value.return_value.__enter__.return_value = mock_session
    mock_deduplicator_cls.return_value.process_candidates.return_value = MagicMock(
        accepted_candidates=[MagicMock(id="sc_1")],
        clusters=[MagicMock(status="accepted")],
        rejection_reasons={},
    )

    result = runner.invoke(app, ["dedup"])

    assert result.exit_code == 0
    assert "Deduplicating skills using configs/config.yaml..." in result.stdout
    mock_llm_client.assert_called_once_with(model="gpt-4o")
    mock_deduplicator_cls.assert_called_once_with(
        mock_llm_client.return_value,
        dedup_threshold=0.88,
        min_skill_confidence=0.72,
        min_cross_repo_support=2,
    )
    mock_deduplicator_cls.return_value.process_candidates.assert_called_once_with(
        mock_candidates,
        {"ri_1": mock_review_item},
    )
    mock_write_artifacts.assert_called_once()
    mock_deduplicator_cls.return_value.process_candidates.assert_called_once()
    mock_session.commit.assert_called_once()
    mock_run_preflight.assert_called_once()


@patch("src.cli.main.load_config")
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.curate.deduplicator.write_deduplication_artifacts")
@patch("src.curate.deduplicator.SkillDeduplicator")
@patch("src.analyze.llm_client.LLMClient")
def test_dedup_skips_when_no_proposed_candidates(
    mock_llm_client: Any,
    mock_deduplicator_cls: Any,
    mock_write_artifacts: Any,
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_run_preflight: Any,
    mock_load_config: Any,
) -> None:
    mock_load_config.return_value = MagicMock(
        storage=MagicMock(db_url="sqlite://", artifact_dir="output"),
        models=MagicMock(classification_model="gpt-4o"),
        pipeline=MagicMock(
            dedup_threshold=0.88,
            min_skill_confidence=0.72,
            min_cross_repo_support=2,
        ),
    )
    candidate_query = MagicMock()
    candidate_query.filter.return_value.all.return_value = []
    mock_session = MagicMock()
    mock_session.query.return_value = candidate_query
    mock_get_session_factory.return_value.return_value.__enter__.return_value = mock_session

    result = runner.invoke(app, ["dedup"])

    assert result.exit_code == 0
    assert "No proposed embedded candidates found." in result.stdout
    mock_llm_client.assert_not_called()
    mock_deduplicator_cls.assert_not_called()
    mock_deduplicator_cls.return_value.process_candidates.assert_not_called()
    mock_write_artifacts.assert_not_called()
    mock_session.commit.assert_not_called()
    mock_run_preflight.assert_called_once()


@patch("src.cli.main.generate")
@patch("src.cli.main.dedup")
@patch("src.cli.main.embed")
@patch("src.cli.main.extract_skills")
@patch("src.cli.main.analyze")
@patch("src.cli.main.normalize")
@patch("src.cli.main.collect")
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.load_config")
def test_run_executes_pipeline_in_order(
    mock_load_config: Any,
    mock_run_preflight: Any,
    mock_collect: Any,
    mock_normalize: Any,
    mock_analyze: Any,
    mock_extract_skills: Any,
    mock_embed: Any,
    mock_dedup: Any,
    mock_generate: Any,
) -> None:
    mock_load_config.return_value = MagicMock()
    call_order: list[str] = []
    for name, mock_fn in [
        ("collect", mock_collect),
        ("normalize", mock_normalize),
        ("analyze", mock_analyze),
        ("extract_skills", mock_extract_skills),
        ("embed", mock_embed),
        ("dedup", mock_dedup),
        ("generate", mock_generate),
    ]:
        mock_fn.side_effect = lambda *args, _name=name, **kwargs: call_order.append(_name)

    result = runner.invoke(app, ["run"])

    assert result.exit_code == 0
    assert call_order == [
        "collect",
        "normalize",
        "analyze",
        "extract_skills",
        "embed",
        "dedup",
        "generate",
    ]
    mock_run_preflight.assert_called_once_with(
        mock_load_config.return_value,
        required_env_vars=("GITHUB_TOKEN", "OPENAI_API_KEY"),
    )


@patch("src.cli.main.load_config")
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.extract.embedder.SkillEmbedder")
@patch("src.analyze.llm_client.LLMClient")
def test_embed_uses_configured_embedding_model(
    mock_llm_client: Any,
    mock_embedder_cls: Any,
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_run_preflight: Any,
    mock_load_config: Any,
) -> None:
    mock_load_config.return_value = MagicMock(
        models=MagicMock(embedding_model="text-embedding-3-large"),
    )
    mock_session = MagicMock()
    mock_session.query.return_value.filter.return_value.all.return_value = []
    mock_get_session_factory.return_value.return_value.__enter__.return_value = mock_session

    result = runner.invoke(app, ["embed"])

    assert result.exit_code == 0
    mock_llm_client.assert_called_once_with(embedding_model="text-embedding-3-large")
    mock_embedder_cls.return_value.process_candidates.assert_called_once_with([])
    mock_run_preflight.assert_called_once()


@patch("src.cli.main.load_config")
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
@patch("src.extract.embedder.SkillEmbedder")
@patch("src.analyze.llm_client.LLMClient")
def test_embed_exits_nonzero_when_embedding_generation_fails(
    mock_llm_client: Any,
    mock_embedder_cls: Any,
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_run_preflight: Any,
    mock_load_config: Any,
) -> None:
    mock_load_config.return_value = MagicMock(
        models=MagicMock(embedding_model="text-embedding-3-large"),
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
    mock_run_preflight.assert_called_once()
