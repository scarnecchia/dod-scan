# pattern: Imperative Shell
"""Mapbox dashboard export — generates self-contained HTML with interactive map."""

from __future__ import annotations

import logging
from pathlib import Path

import jinja2

from dod_scan.export_kml_build import ContractPin
from dod_scan.export_map_data import get_unique_branches, pins_to_geojson

logger = logging.getLogger(__name__)

TEMPLATE_DIR = Path(__file__).parent / "templates"


class MapExportError(Exception):
    pass


def export_map(
    pins: list[ContractPin],
    output_path: Path,
    mapbox_token: str,
) -> Path:
    if not mapbox_token:
        raise MapExportError(
            "MAPBOX_TOKEN not configured. Set it in your .env file to generate the Mapbox dashboard."
        )

    geojson = pins_to_geojson(pins)
    branches = get_unique_branches(pins)

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=True,
    )
    template = env.get_template("map.html")

    html = template.render(
        mapbox_token=mapbox_token,
        geojson_data=geojson,
        branches=branches,
        total_contracts=len(pins),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    logger.info("Mapbox dashboard written to %s", output_path)
    return output_path
