import threading
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import httpx
import yaml
from typer.testing import CliRunner

from src.cli.main import app
from src.extract.embedder import EmbeddingGenerationError
from src.ingest.collector import CollectionStats
from src.ingest.github_client import GithubClient
from src.models.db import RawPullRequest
from src.models.repos import RepoFilter, RepoLimits
from src.storage.database import get_engine, get_session_factory

runner = CliRunner()


def test_collect_persists_raw_data(tmp_path: Path, monkeypatch: Any) -> None:
    db_path = tmp_path / "rke.db"
    artifact_dir = tmp_path / "output"
    config_path = tmp_path / "config.yaml"
    repos_path = tmp_path / "repos.yaml"
    config_path.write_text(
        yaml.safe_dump(
            {
                "storage": {
                    "db_url": f"sqlite:///{db_path}",
                    "artifact_dir": str(artifact_dir),
                },
                "models": {
                    "embedding_model": "text-embedding-3-large",
                    "classification_model": "gpt-4o",
                    "summarization_model": "gpt-4o-mini",
                },
                "pipeline": {
                    "enable_human_review": True,
                    "min_skill_confidence": 0.72,
                    "min_cross_repo_support": 2,
                    "require_evidence": True,
                    "enable_fix_correlation": True,
                    "dedup_threshold": 0.88,
                    "redact_identity": True,
                },
                "generation": {
                    "skills_output": "skills/SKILLS.yaml",
                    "docs_output_dir": "docs",
                    "language_split": True,
                    "framework_split": True,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    repos_path.write_text(
        yaml.safe_dump(
            {
                "repos": ["example/project"],
                "filters": {
                    "merged_only": True,
                    "since": "2026-03-01",
                    "min_review_comments": 2,
                    "include_issue_comments": True,
                    "include_review_summaries": True,
                    "include_followup_commits": True,
                    "labels_include": ["bug"],
                    "labels_exclude": [],
                    "file_extensions": [".py"],
                },
                "limits": {
                    "max_prs_per_repo": 10,
                    "max_comments_per_pr": 10,
                    "max_files_per_pr": 10,
                },
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path

        if path == "/repos/example/project/pulls":
            return httpx.Response(
                200,
                json=[{"number": 10, "updated_at": "2026-03-11T10:00:00Z"}],
                headers={"ETag": '"prs-v1"'},
                request=request,
            )
        if path == "/repos/example/project/pulls/10":
            return httpx.Response(
                200,
                json={
                    "id": 1010,
                    "number": 10,
                    "state": "closed",
                    "merged_at": "2026-03-11T09:30:00Z",
                    "updated_at": "2026-03-11T10:00:00Z",
                    "labels": [{"name": "bug"}],
                    "changed_files": 1,
                },
                headers={"ETag": '"pr-10"'},
                request=request,
            )
        if path == "/repos/example/project/pulls/10/files":
            return httpx.Response(
                200,
                json=[{"filename": "src/main.py"}],
                headers={"ETag": '"pr-10-files"'},
                request=request,
            )
        if path == "/repos/example/project/pulls/10/comments":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 201,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -1 +1 @@\n-old\n+new",
                        "body": "Please add a test.",
                        "created_at": "2026-03-11T10:05:00Z",
                        "user": {"login": "reviewer1"},
                    },
                    {
                        "id": 202,
                        "path": "src/main.py",
                        "diff_hunk": "@@ -5 +5 @@\n-old\n+new",
                        "body": "Handle the error path too.",
                        "created_at": "2026-03-11T10:06:00Z",
                        "user": {"login": "reviewer2"},
                    },
                ],
                headers={"ETag": '"pr-10-comments"'},
                request=request,
            )
        if path == "/repos/example/project/pulls/10/reviews":
            return httpx.Response(
                200,
                json=[
                    {
                        "id": 301,
                        "state": "COMMENTED",
                        "body": "Looks mostly good.",
                        "submitted_at": "2026-03-11T10:07:00Z",
                        "user": {"login": "reviewer1"},
                    }
                ],
                headers={"ETag": '"pr-10-reviews"'},
                request=request,
            )
        if path == "/repos/example/project/issues/10/comments":
            return httpx.Response(
                200,
                json=[],
                headers={"ETag": '"pr-10-issue-comments"'},
                request=request,
            )
        raise AssertionError(f"Unexpected request path: {path}")

    class TestGithubClient(GithubClient):
        def __init__(self, token: str, base_url: str = "https://api.github.com"):
            super().__init__(
                token=token,
                base_url=base_url,
                transport=httpx.MockTransport(handler),
                sleep_fn=lambda _: None,
            )

    monkeypatch.setattr("src.cli.main.GithubClient", TestGithubClient)

    init_result = runner.invoke(app, ["init-db", "--config-file", str(config_path)])
    assert init_result.exit_code == 0

    result = runner.invoke(
        app,
        [
            "collect",
            "--repos-file",
            str(repos_path),
            "--config-file",
            str(config_path),
        ],
    )

    assert result.exit_code == 0
    assert "Processing repository: example/project" in result.stdout
    assert "Collection completed successfully." in result.stdout

    engine = get_engine(f"sqlite:///{db_path}")
    session_factory = get_session_factory(engine)
    with session_factory() as session:
        saved_pr = session.query(RawPullRequest).one()
        assert saved_pr.repo == "example/project"
        assert saved_pr.pr_number == 10


@patch("src.cli.main.load_repos")
@patch("src.cli.main.load_config")
@patch("src.cli.main.run_preflight")
@patch("src.cli.main.get_engine")
@patch("src.cli.main.get_session_factory")
def test_collect_uses_configured_repo_parallelism(
    mock_get_session_factory: Any,
    mock_get_engine: Any,
    mock_run_preflight: Any,
    mock_load_config: Any,
    mock_load_repos: Any,
    monkeypatch: Any,
) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "fake_token")
    mock_load_config.return_value = MagicMock(
        storage=MagicMock(db_url="sqlite://", artifact_dir="output"),
    )
    mock_load_repos.return_value = MagicMock(
        filters=RepoFilter(),
        limits=RepoLimits(max_parallel_repos=2),
        repos=["example/one", "example/two"],
    )

    active_workers = 0
    peak_workers = 0
    worker_lock = threading.Lock()
    barrier = threading.Barrier(2)

    def fake_collect_single_repository(
        repo: str,
        *,
        token: str,
        session_factory: Any,
        filters: RepoFilter,
        limits: RepoLimits,
    ) -> tuple[str, CollectionStats]:
        nonlocal active_workers, peak_workers
        assert token == "fake_token"
        assert limits.max_parallel_repos == 2

        with worker_lock:
            active_workers += 1
            peak_workers = max(peak_workers, active_workers)

        try:
            barrier.wait(timeout=1)
            return repo, CollectionStats()
        finally:
            with worker_lock:
                active_workers -= 1

    monkeypatch.setattr("src.cli.main._collect_single_repository", fake_collect_single_repository)

    result = runner.invoke(app, ["collect"])

    assert result.exit_code == 0
    assert "Using repo parallelism: 2" in result.stdout
    assert "Completed repository: example/one" in result.stdout
    assert "Completed repository: example/two" in result.stdout
    assert peak_workers == 2
    mock_run_preflight.assert_called_once()


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
