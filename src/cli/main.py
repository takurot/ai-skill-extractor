import os

import typer

from src.cli.config_loader import load_config, load_repos
from src.ingest.collector import Collector
from src.ingest.github_client import GithubClient
from src.models.db import RawIssueComment, RawPullRequest, RawReview, RawReviewComment, ReviewItem
from src.normalize.normalizer import Normalizer
from src.storage.database import get_engine, get_session_factory, upsert

app = typer.Typer(help="Review Knowledge Extractor (RKE) CLI")


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


@app.command()
def dedup() -> None:
    """Deduplicate and integrate skill candidates."""
    typer.echo("Deduplicating skills...")


@app.command()
def generate() -> None:
    """Generate SKILLS.yaml and human-readable documentation."""
    typer.echo("Generating output...")


@app.command()
def run() -> None:
    """Run the entire pipeline."""
    typer.echo("Running pipeline...")


if __name__ == "__main__":
    app()
