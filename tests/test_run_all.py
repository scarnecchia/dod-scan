"""Tests for run-all orchestration."""

import logging
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from dod_scan.cli import app


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a CLI runner."""
    return CliRunner()


class TestRunAllOrchestration:
    """Test run-all command orchestration."""

    def test_run_all_executes_stages_in_sequence(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        """Test dod-scan.AC7.1: All stages execute in correct order."""
        db_path = tmp_path / "test.db"
        log_dir = tmp_path / "logs"

        with patch("dod_scan.cli.get_settings") as mock_settings:
            with patch("dod_scan.cli._run_scrape") as mock_scrape:
                with patch("dod_scan.cli._run_parse") as mock_parse:
                    with patch("dod_scan.cli._run_classify") as mock_classify:
                        with patch("dod_scan.cli._run_geocode") as mock_geocode:
                            with patch("dod_scan.cli._run_export") as mock_export:
                                settings = MagicMock()
                                settings.database_path = db_path
                                settings.log_dir = log_dir
                                settings.output_dir = tmp_path / "output"
                                mock_settings.return_value = settings

                                from dod_scan.db import init_db

                                init_db(db_path)

                                result = cli_runner.invoke(app, ["run-all"])

                                assert result.exit_code == 0
                                mock_scrape.assert_called_once()
                                mock_parse.assert_called_once()
                                mock_classify.assert_called_once()
                                mock_geocode.assert_called_once()
                                mock_export.assert_called_once()

    def test_run_all_calls_stages_in_order(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        """Test stages are called in exact sequence: scrape, parse, classify, geocode, export."""
        db_path = tmp_path / "test.db"
        log_dir = tmp_path / "logs"
        call_order = []

        def mock_scrape_fn(*args, **kwargs):
            call_order.append("scrape")

        def mock_parse_fn(*args, **kwargs):
            call_order.append("parse")

        def mock_classify_fn(*args, **kwargs):
            call_order.append("classify")

        def mock_geocode_fn(*args, **kwargs):
            call_order.append("geocode")

        def mock_export_fn(*args, **kwargs):
            call_order.append("export")

        with patch("dod_scan.cli.get_settings") as mock_settings:
            with patch("dod_scan.cli._run_scrape", side_effect=mock_scrape_fn):
                with patch("dod_scan.cli._run_parse", side_effect=mock_parse_fn):
                    with patch("dod_scan.cli._run_classify", side_effect=mock_classify_fn):
                        with patch("dod_scan.cli._run_geocode", side_effect=mock_geocode_fn):
                            with patch("dod_scan.cli._run_export", side_effect=mock_export_fn):
                                settings = MagicMock()
                                settings.database_path = db_path
                                settings.log_dir = log_dir
                                settings.output_dir = tmp_path / "output"
                                mock_settings.return_value = settings

                                from dod_scan.db import init_db

                                init_db(db_path)

                                result = cli_runner.invoke(app, ["run-all"])

                                assert result.exit_code == 0
                                assert call_order == ["scrape", "parse", "classify", "geocode", "export"]

    def test_run_all_stops_on_first_failure(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        """Test dod-scan.AC7.2: Pipeline stops on first stage failure with non-zero exit."""
        db_path = tmp_path / "test.db"
        log_dir = tmp_path / "logs"

        with patch("dod_scan.cli.get_settings") as mock_settings:
            with patch("dod_scan.cli._run_scrape") as mock_scrape:
                with patch("dod_scan.cli._run_parse") as mock_parse:
                    with patch("dod_scan.cli._run_classify") as mock_classify:
                        with patch("dod_scan.cli._run_geocode") as mock_geocode:
                            with patch("dod_scan.cli._run_export") as mock_export:
                                settings = MagicMock()
                                settings.database_path = db_path
                                settings.log_dir = log_dir
                                settings.output_dir = tmp_path / "output"
                                mock_settings.return_value = settings

                                mock_parse.side_effect = RuntimeError("Parse failed")

                                from dod_scan.db import init_db

                                init_db(db_path)

                                result = cli_runner.invoke(app, ["run-all"])

                                assert result.exit_code == 1
                                mock_scrape.assert_called_once()
                                mock_parse.assert_called_once()
                                mock_classify.assert_not_called()
                                mock_geocode.assert_not_called()
                                mock_export.assert_not_called()

    def test_run_all_logs_stage_start_and_completion(
        self, tmp_path: Path, cli_runner: CliRunner, caplog
    ) -> None:
        """Test dod-scan.AC7.3: All stages log start/complete messages to file."""
        db_path = tmp_path / "test.db"
        log_dir = tmp_path / "logs"

        with patch("dod_scan.cli.get_settings") as mock_settings:
            with patch("dod_scan.cli._run_scrape"):
                with patch("dod_scan.cli._run_parse"):
                    with patch("dod_scan.cli._run_classify"):
                        with patch("dod_scan.cli._run_geocode"):
                            with patch("dod_scan.cli._run_export"):
                                settings = MagicMock()
                                settings.database_path = db_path
                                settings.log_dir = log_dir
                                settings.output_dir = tmp_path / "output"
                                mock_settings.return_value = settings

                                from dod_scan.db import init_db

                                init_db(db_path)

                                with caplog.at_level(logging.INFO):
                                    result = cli_runner.invoke(app, ["run-all"])

                                assert result.exit_code == 0

                                log_content = caplog.text

                                assert "Starting stage: scrape" in log_content
                                assert "Completed stage: scrape" in log_content
                                assert "Starting stage: parse" in log_content
                                assert "Completed stage: parse" in log_content
                                assert "Starting stage: classify" in log_content
                                assert "Completed stage: classify" in log_content
                                assert "Starting stage: geocode" in log_content
                                assert "Completed stage: geocode" in log_content
                                assert "Starting stage: export" in log_content
                                assert "Completed stage: export" in log_content

    def test_run_all_with_backfill_option(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        """Test run-all passes backfill option to scrape stage."""
        db_path = tmp_path / "test.db"
        log_dir = tmp_path / "logs"
        captured_args = {}

        def mock_scrape_fn(conn, backfill):
            captured_args["backfill"] = backfill

        with patch("dod_scan.cli.get_settings") as mock_settings:
            with patch("dod_scan.cli._run_scrape", side_effect=mock_scrape_fn):
                with patch("dod_scan.cli._run_parse"):
                    with patch("dod_scan.cli._run_classify"):
                        with patch("dod_scan.cli._run_geocode"):
                            with patch("dod_scan.cli._run_export"):
                                settings = MagicMock()
                                settings.database_path = db_path
                                settings.log_dir = log_dir
                                settings.output_dir = tmp_path / "output"
                                mock_settings.return_value = settings

                                from dod_scan.db import init_db

                                init_db(db_path)

                                result = cli_runner.invoke(app, ["run-all", "--backfill", "5"])

                                assert result.exit_code == 0
                                assert captured_args.get("backfill") == 5

    def test_run_all_with_format_option(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        """Test run-all passes format option to export stage."""
        db_path = tmp_path / "test.db"
        log_dir = tmp_path / "logs"
        captured_args = {}

        def mock_export_fn(conn, settings, format, since, branch):
            captured_args["format"] = format

        with patch("dod_scan.cli.get_settings") as mock_settings:
            with patch("dod_scan.cli._run_scrape"):
                with patch("dod_scan.cli._run_parse"):
                    with patch("dod_scan.cli._run_classify"):
                        with patch("dod_scan.cli._run_geocode"):
                            with patch("dod_scan.cli._run_export", side_effect=mock_export_fn):
                                settings = MagicMock()
                                settings.database_path = db_path
                                settings.log_dir = log_dir
                                settings.output_dir = tmp_path / "output"
                                mock_settings.return_value = settings

                                from dod_scan.db import init_db

                                init_db(db_path)

                                result = cli_runner.invoke(app, ["run-all", "--format", "all"])

                                assert result.exit_code == 0
                                assert captured_args.get("format") == "all"

    def test_run_all_with_filter_options(
        self, tmp_path: Path, cli_runner: CliRunner
    ) -> None:
        """Test run-all passes filter options to export stage."""
        db_path = tmp_path / "test.db"
        log_dir = tmp_path / "logs"
        captured_args = {}

        def mock_export_fn(conn, settings, format, since, branch):
            captured_args["since"] = since
            captured_args["branch"] = branch

        with patch("dod_scan.cli.get_settings") as mock_settings:
            with patch("dod_scan.cli._run_scrape"):
                with patch("dod_scan.cli._run_parse"):
                    with patch("dod_scan.cli._run_classify"):
                        with patch("dod_scan.cli._run_geocode"):
                            with patch("dod_scan.cli._run_export", side_effect=mock_export_fn):
                                settings = MagicMock()
                                settings.database_path = db_path
                                settings.log_dir = log_dir
                                settings.output_dir = tmp_path / "output"
                                mock_settings.return_value = settings

                                from dod_scan.db import init_db

                                init_db(db_path)

                                result = cli_runner.invoke(
                                    app,
                                    [
                                        "run-all",
                                        "--since",
                                        "2026-01-01",
                                        "--branch",
                                        "NAVY",
                                    ],
                                )

                                assert result.exit_code == 0
                                assert captured_args.get("since") == "2026-01-01"
                                assert captured_args.get("branch") == "NAVY"
