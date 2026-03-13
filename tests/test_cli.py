"""CLI integration tests."""

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
