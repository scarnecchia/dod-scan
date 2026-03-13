# pattern: Imperative Shell
"""CLI entry point with subcommand stubs for each pipeline stage."""

import typer

from dod_scan.config import get_settings
from dod_scan.db import get_connection, init_db

app = typer.Typer(
    name="dod-scan",
    help="DOD contract scanner — scrapes, parses, classifies, geocodes, and exports contract awards.",
)


@app.command()
def scrape(
    backfill: int = typer.Option(0, "--backfill", "-b", help="Number of historical pages to fetch"),
) -> None:
    """Fetch daily contract pages from war.gov."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.scraper import scrape as do_scrape
        stored = do_scrape(conn, backfill=backfill)
        typer.echo(f"Scrape complete: {stored} new pages stored")
    except Exception as exc:
        typer.echo(f"Scrape failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()


@app.command()
def parse() -> None:
    """Extract structured contract data from raw HTML."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.parser import parse_all
        count = parse_all(conn)
        typer.echo(f"Parse complete: {count} contracts extracted")
    except Exception as exc:
        typer.echo(f"Parse failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()


@app.command()
def classify() -> None:
    """Classify contracts as procurement vs service using LLM."""
    settings = get_settings()
    if not settings.llm_api_key:
        typer.echo("Error: LLM_API_KEY not set. Configure in .env file.", err=True)
        raise typer.Exit(code=1)

    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.classifier import classify_all
        from dod_scan.classifier_providers import create_provider

        provider = create_provider(
            settings.llm_provider, settings.llm_api_key, settings.llm_model
        )
        count = classify_all(conn, provider)
        typer.echo(f"Classification complete: {count} contracts classified")
    except Exception as exc:
        typer.echo(f"Classification failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()


@app.command()
def geocode() -> None:
    """Resolve contract locations to lat/lon coordinates."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    try:
        from dod_scan.geocoder import geocode_all
        count = geocode_all(conn)
        typer.echo(f"Geocoding complete: {count} contracts geocoded")
    except Exception as exc:
        typer.echo(f"Geocoding failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()


@app.command()
def export(
    format: str = typer.Option("kml", "--format", "-f", help="Export format: kml, map, or all"),
    since: str = typer.Option(
        None, "--since", help="Filter to contracts from this date onward (YYYY-MM-DD)"
    ),
    branch: str = typer.Option(None, "--branch", help="Filter to specific branch (e.g. ARMY)"),
) -> None:
    """Export geocoded procurement contracts as KML and/or Mapbox dashboard."""
    settings = get_settings()
    init_db(settings.database_path)
    conn = get_connection(settings.database_path)
    settings.output_dir.mkdir(parents=True, exist_ok=True)

    try:
        if format in ("kml", "all"):
            from dod_scan.export_kml import export_kml
            kml_path = settings.output_dir / "dod_contracts.kml"
            export_kml(conn, kml_path, since=since, branch=branch)
            typer.echo(f"KML exported to {kml_path}")

        if format in ("map", "all"):
            if not settings.mapbox_token:
                if format == "all":
                    typer.echo("MAPBOX_TOKEN not set — skipping map export, KML only")
                else:
                    typer.echo(
                        "Error: MAPBOX_TOKEN not set. Configure in .env file to generate Mapbox dashboard.",
                        err=True,
                    )
                    raise typer.Exit(code=1)
            else:
                from dod_scan.export_kml import query_contract_pins
                from dod_scan.export_map import export_map
                pins = query_contract_pins(conn, since, branch)
                map_path = settings.output_dir / "dod_contracts.html"
                export_map(pins, map_path, settings.mapbox_token)
                typer.echo(f"Mapbox dashboard exported to {map_path}")
    except typer.Exit:
        raise
    except Exception as exc:
        typer.echo(f"Export failed: {exc}", err=True)
        raise typer.Exit(code=1)
    finally:
        conn.close()


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
