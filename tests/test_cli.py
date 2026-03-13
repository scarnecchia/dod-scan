"""CLI integration tests."""

from pathlib import Path
from unittest.mock import patch, MagicMock

from typer.testing import CliRunner

from dod_scan.cli import app

runner = CliRunner()


class TestCLIIntegration:
    """Test CLI subcommand wiring with --help."""

    def test_scrape_help(self) -> None:
        """Test scrape subcommand --help returns exit code 0."""
        result = runner.invoke(app, ["scrape", "--help"])
        assert result.exit_code == 0
        assert "Fetch daily contract pages" in result.stdout

    def test_parse_help(self) -> None:
        """Test parse subcommand --help returns exit code 0."""
        result = runner.invoke(app, ["parse", "--help"])
        assert result.exit_code == 0
        assert "Extract structured contract data" in result.stdout

    def test_classify_help(self) -> None:
        """Test classify subcommand --help returns exit code 0."""
        result = runner.invoke(app, ["classify", "--help"])
        assert result.exit_code == 0
        assert "Classify contracts" in result.stdout

    def test_geocode_help(self) -> None:
        """Test geocode subcommand --help returns exit code 0."""
        result = runner.invoke(app, ["geocode", "--help"])
        assert result.exit_code == 0
        assert "Resolve contract locations" in result.stdout

    def test_export_help(self) -> None:
        """Test export subcommand --help returns exit code 0."""
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "Export geocoded procurement contracts" in result.stdout

    def test_run_all_help(self) -> None:
        """Test run-all subcommand --help returns exit code 0."""
        result = runner.invoke(app, ["run-all", "--help"])
        assert result.exit_code == 0
        assert "Execute all pipeline stages in sequence" in result.stdout

    def test_init_db_help(self) -> None:
        """Test init-db subcommand --help returns exit code 0."""
        result = runner.invoke(app, ["init-db", "--help"])
        assert result.exit_code == 0
        assert "Initialize the database schema" in result.stdout

    def test_export_format_all_without_mapbox_token(self, tmp_path: Path) -> None:
        """Verify AC6.4: export --format all without MAPBOX_TOKEN skips map, exports KML with message."""
        settings_mock = MagicMock()
        settings_mock.database_path = tmp_path / "test.db"
        settings_mock.output_dir = tmp_path
        settings_mock.mapbox_token = ""

        with patch("dod_scan.cli.get_settings", return_value=settings_mock):
            with patch("dod_scan.cli.init_db"):
                with patch("dod_scan.cli.get_connection") as mock_conn:
                    with patch("dod_scan.export_kml.export_kml") as mock_export_kml:
                        mock_conn.return_value = MagicMock()

                        result = runner.invoke(app, ["export", "--format", "all"])

                        # Should succeed with exit code 0
                        assert result.exit_code == 0
                        # Should export KML
                        assert mock_export_kml.called
                        # Should output message about skipping map export
                        assert "skipping map export" in result.stdout.lower()
                        assert "KML only" in result.stdout
