"""Tests for logging configuration."""

import logging
from pathlib import Path

import pytest

from dod_scan.logging_config import configure_logging


class TestLoggingConfiguration:
    """Test logging configuration setup."""

    def test_configure_logging_creates_log_directory(self, tmp_path: Path) -> None:
        """Test configure_logging creates log directory if missing."""
        log_dir = tmp_path / "nonexistent" / "logs"
        assert not log_dir.exists()

        configure_logging(log_dir)

        assert log_dir.exists()
        assert log_dir.is_dir()

    def test_configure_logging_creates_log_file(self, tmp_path: Path) -> None:
        """Test configure_logging creates log file."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        configure_logging(log_dir)

        test_logger = logging.getLogger("test_log_file")
        test_logger.info("Create file")

        log_file = log_dir / "dod_scan.log"
        assert log_file.exists()

    def test_configure_logging_logs_to_file(self, tmp_path: Path) -> None:
        """Test messages are written to log file."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        configure_logging(log_dir)

        test_logger = logging.getLogger("test")
        test_logger.info("Test message to file")

        log_file = log_dir / "dod_scan.log"
        log_content = log_file.read_text()

        assert "Test message to file" in log_content

    def test_configure_logging_includes_timestamp_and_name(self, tmp_path: Path) -> None:
        """Test log file contains expected format."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        configure_logging(log_dir)

        test_logger = logging.getLogger("test_module")
        test_logger.info("Formatted message")

        log_file = log_dir / "dod_scan.log"
        log_content = log_file.read_text()

        assert "test_module" in log_content
        assert "INFO" in log_content
        assert "Formatted message" in log_content

    def test_configure_logging_console_shows_warnings_and_above(
        self, tmp_path: Path
    ) -> None:
        """Test console handler only shows WARNING and above."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        configure_logging(log_dir)

        console_handler = None
        for handler in root.handlers:
            if isinstance(handler, logging.StreamHandler) and not isinstance(
                handler, logging.FileHandler
            ):
                console_handler = handler
                break

        assert console_handler is not None
        assert console_handler.level == logging.WARNING

    def test_configure_logging_idempotent(self, tmp_path: Path) -> None:
        """Test calling configure_logging twice doesn't duplicate handlers."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        initial_handler_count = len(root.handlers)

        configure_logging(log_dir)
        handlers_after_first_call = len(root.handlers)

        configure_logging(log_dir)
        handlers_after_second_call = len(root.handlers)

        assert handlers_after_first_call == handlers_after_second_call

    def test_configure_logging_sets_level(self, tmp_path: Path) -> None:
        """Test configure_logging sets root logger level."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        configure_logging(log_dir, level=logging.WARNING)

        test_logger = logging.getLogger("test_level")
        test_logger.info("Info message")
        test_logger.warning("Warning message")

        log_file = log_dir / "dod_scan.log"
        log_content = log_file.read_text()

        assert "Info message" not in log_content
        assert "Warning message" in log_content

    def test_configure_logging_default_level_is_info(self, tmp_path: Path) -> None:
        """Test default logging level is INFO."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        configure_logging(log_dir)

        test_logger = logging.getLogger("test_default_level")
        test_logger.debug("Debug message")
        test_logger.info("Info message")

        log_file = log_dir / "dod_scan.log"
        log_content = log_file.read_text()

        assert "Debug message" not in log_content
        assert "Info message" in log_content

    def test_configure_logging_different_loggers_write_to_same_file(
        self, tmp_path: Path
    ) -> None:
        """Test different loggers write to the same log file."""
        log_dir = tmp_path / "logs"

        root = logging.getLogger()
        for handler in root.handlers[:]:
            root.removeHandler(handler)

        configure_logging(log_dir)

        logger1 = logging.getLogger("module1")
        logger2 = logging.getLogger("module2")
        logger1.info("Message from module1")
        logger2.info("Message from module2")

        log_file = log_dir / "dod_scan.log"
        log_content = log_file.read_text()

        assert "Message from module1" in log_content
        assert "Message from module2" in log_content
