import json
import os
from collections import Counter
from collections.abc import Callable
from time import perf_counter

import typer

from src.cli.config_loader import load_config, load_repos
from src.ingest.collector import Collector
from src.ingest.github_client import GithubClient
from src.models.db import RawIssueComment, RawPullRequest, RawReview, RawReviewComment, ReviewItem
from src.normalize.normalizer import Normalizer
from src.runtime_env import load_project_env
from src.storage.database import get_engine, get_session_factory, upsert

load_project_env()

app = typer.Typer(help="Review Knowledge Extractor (RKE) CLI")


def _emit_pipeline_event(stage: str, status: str, **payload: object) -> None:
    typer.echo(json.dumps({"stage": stage, "status": status, **payload}, sort_keys=True))


@app.command()
def collect(
    repos_file: str = "configs/repos.yaml", config_file: str = "configs/config.yaml"
) -> None:
    """Collect raw data from GitHub."""
    typer.echo(f"Collecting data using {repos_file} and {config_file}...")

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        typer.secho("Error: GITHUB_TOKEN environment variable not set.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    try:
        repos_config = load_repos(repos_file)
        # config = load_config(config_file) # Will be used for DB connection later

        client = GithubClient(token=token)
        collector = Collector(
            client=client, filters=repos_config.filters, limits=repos_config.limits
        )

        for repo in repos_config.repos:
            typer.echo(f"Processing repository: {repo}")
            # Placeholder for actual collection loop using `collector`
            # prs = collector.fetch_prs(repo)
            # for pr in prs:
            #     collector.fetch_comments(repo, pr.number)
            _ = collector  # temporarily suppress unused variable warning
        client.close()
        typer.secho("Collection completed successfully.", fg=typer.colors.GREEN)

    except Exception as e:
        typer.secho(f"Collection failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def normalize(config_file: str = "configs/config.yaml") -> None:
    """Normalize raw data into ReviewItems."""
    typer.echo(f"Normalizing data using {config_file}...")

    try:
        config = load_config(config_file)
        engine = get_engine(config.storage.db_url)
        session_factory = get_session_factory(engine)
        normalizer = Normalizer(redact_identity=config.pipeline.redact_identity)

        with session_factory() as session:
            prs = session.query(RawPullRequest).all()
            typer.echo(f"Found {len(prs)} Pull Requests to process.")

            for pr in prs:
                typer.echo(f"  Normalizing PR #{pr.pr_number} from {pr.repo}...")

                # Process review comments
                comments = (
                    session.query(RawReviewComment)
                    .filter(
                        RawReviewComment.repo == pr.repo, RawReviewComment.pr_number == pr.pr_number
                    )
                    .all()
                )
                for comment in comments:
                    item = normalizer.normalize_review_comment(pr.repo, pr, comment)
                    if item:
                        # Convert SQLAlchemy object to dict for upsert, but handle id properly
                        data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
                        upsert(session, ReviewItem, data)

                # Process issue comments
                issue_comments = (
                    session.query(RawIssueComment)
                    .filter(
                        RawIssueComment.repo == pr.repo, RawIssueComment.pr_number == pr.pr_number
                    )
                    .all()
                )
                for ic in issue_comments:
                    item = normalizer.normalize_issue_comment(pr.repo, pr, ic)
                    if item:
                        data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
                        upsert(session, ReviewItem, data)

                # Process review summaries
                reviews = (
                    session.query(RawReview)
                    .filter(RawReview.repo == pr.repo, RawReview.pr_number == pr.pr_number)
                    .all()
                )
                for review in reviews:
                    item = normalizer.normalize_review_summary(pr.repo, pr, review)
                    if item:
                        data = {c.name: getattr(item, c.name) for c in item.__table__.columns}
                        upsert(session, ReviewItem, data)

            session.commit()
        typer.secho("Normalization completed successfully.", fg=typer.colors.GREEN)

    except Exception as e:
        typer.secho(f"Normalization failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def analyze(config_file: str = "configs/config.yaml") -> None:
    """Analyze ReviewItems using LLM."""
    typer.echo(f"Analyzing data using {config_file}...")
    try:
        from src.analyze.analyzer import SemanticAnalyzer
        from src.analyze.llm_client import LLMClient

        config = load_config(config_file)
        engine = get_engine(config.storage.db_url)
        session_factory = get_session_factory(engine)

        # Initialize LLM Client and Analyzer
        llm_client = LLMClient(model=config.models.classification_model)
        analyzer = SemanticAnalyzer(llm_client)

        with session_factory() as session:
            # Fetch unanalyzed items (where category is None)
            items = session.query(ReviewItem).filter(ReviewItem.category.is_(None)).all()
            typer.echo(f"Found {len(items)} unanalyzed ReviewItems.")

            analyzer.process_items(items)
            session.commit()

        typer.secho("Analysis completed successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Analysis failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("extract-skills")
def extract_skills(config_file: str = "configs/config.yaml") -> None:
    """Extract skill candidates from analyzed ReviewItems."""
    typer.echo(f"Extracting skills using {config_file}...")
    try:
        from src.analyze.llm_client import LLMClient
        from src.extract.extractor import SkillExtractor
        from src.models.db import SkillCandidate

        config = load_config(config_file)
        engine = get_engine(config.storage.db_url)
        session_factory = get_session_factory(engine)

        llm_client = LLMClient(model=config.models.classification_model)
        extractor = SkillExtractor(llm_client, min_confidence=config.pipeline.min_skill_confidence)

        with session_factory() as session:
            # Fetch analyzed items
            items = session.query(ReviewItem).filter(ReviewItem.category.is_not(None)).all()
            typer.echo(f"Found {len(items)} analyzed ReviewItems to extract skills from.")

            candidates = extractor.process_items(items)
            for candidate in candidates:
                data = {c.name: getattr(candidate, c.name) for c in candidate.__table__.columns}
                upsert(session, SkillCandidate, data)

            session.commit()
            typer.echo(f"Extracted {len(candidates)} new skill candidates.")

        typer.secho("Skill extraction completed successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Skill extraction failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command("embed")
def embed(config_file: str = "configs/config.yaml") -> None:
    """Generate and save embeddings for SkillCandidates."""
    typer.echo(f"Generating embeddings using {config_file}...")
    try:
        from src.analyze.llm_client import LLMClient
        from src.extract.embedder import SkillEmbedder
        from src.models.db import SkillCandidate

        config = load_config(config_file)
        engine = get_engine(config.storage.db_url)
        session_factory = get_session_factory(engine)

        llm_client = LLMClient(embedding_model=config.models.embedding_model)
        embedder = SkillEmbedder(llm_client)

        with session_factory() as session:
            # Fetch candidates without embeddings
            candidates = (
                session.query(SkillCandidate).filter(SkillCandidate.embedding.is_(None)).all()
            )
            typer.echo(f"Found {len(candidates)} candidates requiring embeddings.")

            embedder.process_candidates(candidates)
            session.commit()

        typer.secho("Embedding generation completed successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Embedding generation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def dedup(config_file: str = "configs/config.yaml") -> None:
    """Deduplicate and integrate skill candidates."""
    typer.echo(f"Deduplicating skills using {config_file}...")
    try:
        from src.models.db import SkillCandidate

        config = load_config(config_file)
        engine = get_engine(config.storage.db_url)
        session_factory = get_session_factory(engine)

        with session_factory() as session:
            candidates = (
                session.query(SkillCandidate)
                .filter(
                    SkillCandidate.status == "proposed",
                    SkillCandidate.embedding.is_not(None),
                )
                .all()
            )
            if not candidates:
                typer.echo("No proposed embedded candidates found. Skipping deduplication.")
                typer.secho("Deduplication completed successfully.", fg=typer.colors.GREEN)
                return

            from src.analyze.llm_client import LLMClient
            from src.curate.deduplicator import SkillDeduplicator, write_deduplication_artifacts

            llm_client = LLMClient(model=config.models.classification_model)
            deduplicator = SkillDeduplicator(
                llm_client,
                dedup_threshold=config.pipeline.dedup_threshold,
                min_skill_confidence=config.pipeline.min_skill_confidence,
                min_cross_repo_support=config.pipeline.min_cross_repo_support,
            )
            review_items = session.query(ReviewItem).all()
            review_item_ids = {
                review_item_id
                for candidate in candidates
                for review_item_id in (candidate.source_review_item_ids or [])
            }
            review_item_map = {
                item.id: item for item in review_items if item.id and item.id in review_item_ids
            }
            typer.echo(f"Found {len(candidates)} proposed candidates to curate.")
            outcome = deduplicator.process_candidates(candidates, review_item_map)
            write_deduplication_artifacts(config.storage.artifact_dir, outcome)
            session.commit()
            typer.echo(
                "Accepted "
                f"{len(outcome.accepted_candidates)} skills and rejected "
                f"{len(outcome.rejected_candidates)} candidates."
            )

        typer.secho("Deduplication completed successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Deduplication failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def generate(config_file: str = "configs/config.yaml") -> None:
    """Generate SKILLS.yaml and human-readable documentation."""
    typer.echo(f"Generating output using {config_file}...")
    try:
        from src.generate.generator import ArtifactGenerator
        from src.models.db import SkillCandidate

        config = load_config(config_file)
        engine = get_engine(config.storage.db_url)
        session_factory = get_session_factory(engine)

        generator = ArtifactGenerator(
            config.storage.artifact_dir,
            language_split=config.generation.language_split,
            framework_split=config.generation.framework_split,
        )

        with session_factory() as session:
            accepted_candidates = (
                session.query(SkillCandidate).filter(SkillCandidate.status == "accepted").all()
            )
            all_candidates = session.query(SkillCandidate).all()
            review_items = session.query(ReviewItem).all()
        rejection_reasons = Counter(
            candidate.rejection_reason
            for candidate in all_candidates
            if candidate.rejection_reason and candidate.rejection_reason != "duplicate_cluster"
        )
        written_files = generator.generate(
            accepted_candidates,
            review_items,
            skills_output_path=config.generation.skills_output,
            docs_output_dir=config.generation.docs_output_dir,
            all_candidates=all_candidates,
            rejection_reasons=dict(rejection_reasons),
        )

        typer.echo(f"Generated {len(written_files)} artifact files.")
        typer.secho("Generation completed successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        typer.secho(f"Generation failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@app.command()
def run(
    repos_file: str = "configs/repos.yaml",
    config_file: str = "configs/config.yaml",
) -> None:
    """Run the entire pipeline."""
    typer.echo("Running pipeline...")
    steps: list[tuple[str, Callable[[], None]]] = [
        ("collect", lambda: collect(repos_file=repos_file, config_file=config_file)),
        ("normalize", lambda: normalize(config_file=config_file)),
        ("analyze", lambda: analyze(config_file=config_file)),
        ("extract_skills", lambda: extract_skills(config_file=config_file)),
        ("embed", lambda: embed(config_file=config_file)),
        ("dedup", lambda: dedup(config_file=config_file)),
        ("generate", lambda: generate(config_file=config_file)),
    ]

    try:
        total_steps = len(steps)
        for index, (step_name, step) in enumerate(steps, start=1):
            started_at = perf_counter()
            _emit_pipeline_event(step_name, "started", step=index, total=total_steps)
            step()
            duration_ms = int((perf_counter() - started_at) * 1000)
            _emit_pipeline_event(
                step_name,
                "completed",
                step=index,
                total=total_steps,
                duration_ms=duration_ms,
            )
        typer.secho("Pipeline completed successfully.", fg=typer.colors.GREEN)
    except Exception as e:
        duration_ms = int((perf_counter() - started_at) * 1000)
        _emit_pipeline_event(
            step_name,
            "failed",
            step=index,
            total=total_steps,
            duration_ms=duration_ms,
            error=str(e),
        )
        typer.secho(f"Pipeline failed: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
