# pattern: Imperative Shell
"""CLI entry point with subcommand stubs for each pipeline stage."""

import typer

from dod_scan.config import get_settings
from dod_scan.db import init_db

app = typer.Typer(
    name="dod-scan",
    help="DOD contract scanner — scrapes, parses, classifies, geocodes, and exports contract awards.",
)


@app.command()
def scrape(
    backfill: int = typer.Option(0, "--backfill", "-b", help="Number of historical pages to fetch"),
) -> None:
    """Fetch daily contract pages from war.gov."""
    typer.echo("scrape: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def parse() -> None:
    """Extract structured contract data from raw HTML."""
    typer.echo("parse: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def classify() -> None:
    """Classify contracts as procurement vs service using LLM."""
    typer.echo("classify: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def geocode() -> None:
    """Resolve contract locations to lat/lon coordinates."""
    typer.echo("geocode: not yet implemented")
    raise typer.Exit(code=1)


@app.command()
def export(
    format: str = typer.Option("kml", "--format", "-f", help="Export format: kml, map, or all"),
    since: str = typer.Option(
        None, "--since", help="Filter to contracts from this date onward (YYYY-MM-DD)"
    ),
    branch: str = typer.Option(None, "--branch", help="Filter to specific branch (e.g. ARMY)"),
) -> None:
    """Export geocoded procurement contracts as KML and/or Mapbox dashboard."""
    typer.echo("export: not yet implemented")
    raise typer.Exit(code=1)


@app.command(name="run-all")
def run_all() -> None:
    """Execute all pipeline stages in sequence: scrape -> parse -> classify -> geocode -> export."""
    typer.echo("run-all: not yet implemented")
    raise typer.Exit(code=1)


@app.command(name="init-db")
def init_database() -> None:
    """Initialize the database schema."""
    settings = get_settings()
    init_db(settings.database_path)
    typer.echo(f"Database initialized at {settings.database_path}")
