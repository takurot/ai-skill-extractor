import typer

app = typer.Typer(help="Review Knowledge Extractor (RKE) CLI")


@app.command()
def collect() -> None:
    """Collect raw data from GitHub."""
    typer.echo("Collecting data...")


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
