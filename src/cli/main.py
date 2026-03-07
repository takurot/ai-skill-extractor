import os

import typer

from src.cli.config_loader import load_repos
from src.ingest.collector import Collector
from src.ingest.github_client import GithubClient

app = typer.Typer(help="Review Knowledge Extractor (RKE) CLI")

@app.command()
def collect(repos_file: str = "repos.yaml", config_file: str = "config.yaml") -> None:
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
def normalize() -> None:
    """Normalize raw data into ReviewItems."""
    typer.echo("Normalizing data...")

@app.command()
def analyze() -> None:
    """Analyze ReviewItems using LLM."""
    typer.echo("Analyzing data...")

@app.command("extract-skills")
def extract_skills() -> None:
    """Extract skill candidates from analyzed ReviewItems."""
    typer.echo("Extracting skills...")

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
