"""
Logger utility module for AI documentation generator.

This module provides a centralized logging system with structured data support,
multiple handlers, and consistent formatting across all agents.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional, Union

import ujson as json


class Logger:
    """
    Centralized logger for AI documentation generator.

    Provides a singleton logging interface with support for:
    - Structured data logging (JSON)
    - Multiple output handlers (file and console)
    - Configurable log levels
    - Automatic log file naming with timestamps
    - Consistent formatting across all agents

    Example:
        ```python
        from pathlib import Path

        # Initialize the logger
        Logger.init(
            log_dir=Path("./logs"),
            file_level=logging.INFO,
            console_level=logging.WARNING
        )

        # Use the logger
        Logger.info("Agent started")
        Logger.info("Processing request", {"user_id": 123, "action": "code_review"})
        Logger.error("Failed to process", {"error": "timeout", "duration": 30})
        ```
    """

    _logger: logging.Logger = None

    @classmethod
    def init(
        cls,
        log_dir: Path,
        file_level=logging.INFO,
        console_level=logging.WARNING,
        file_name: Optional[str] = None,
    ):
        """
        Initialize the logger with the specified configuration.

        This method sets up both file and console handlers with the specified
        log levels and creates the log directory if it doesn't exist.

        Args:
            log_dir (Path): Directory to store log files. Will be created if it doesn't exist.
            file_level (int, optional): Logging level for file output. Defaults to logging.INFO.
            console_level (int, optional): Logging level for console output. Defaults to logging.WARNING.
            file_name (str, optional): Custom log file name. If not provided, uses timestamp-based naming.

        Raises:
            ValueError: If the logger is already initialized (logs a warning instead).

        Note:
            The logger uses a singleton pattern. Calling init() multiple times will
            log a warning and return without re-initializing.
        """
        if cls._logger is not None:
            cls._logger.warning("Logger already initialized")
            return

        # Create log directory if it doesn't exist
        log_dir.mkdir(parents=True, exist_ok=True)

        # Set up logging
        cls._logger = logging.getLogger("ai-doc-gen")
        cls._logger.setLevel(logging.DEBUG)  # Set to lowest level to let handlers control
        cls._logger.propagate = True  # Allow propagation to root logger for logfire integration

        if file_name is None:
            file_name = f"{datetime.now().strftime('%Y-%m-%d__%H-%M-%S')}.log"
        log_file = log_dir / file_name

        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        file_handler.setLevel(file_level)
        cls._logger.addHandler(file_handler)

        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
        console_handler.setLevel(console_level)
        cls._logger.addHandler(console_handler)

        # Log initial message to verify setup
        cls._logger.debug(f"Logger initialized with log file: {log_file}")

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """
        Get the underlying logging.Logger instance for advanced usage.

        Returns:
            logging.Logger: The underlying logger instance.

        Raises:
            ValueError: If the logger has not been initialized yet.

        Example:
            ```python
            logger = Logger.get_logger()
            logger.info("Direct access", extra={"custom_field": "value"})
            ```
        """
        if cls._logger is None:
            raise ValueError("Logger not initialized")

        return cls._logger

    @classmethod
    def info(
        cls,
        message: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        *args,
        **kwargs,
    ):
        """
        Log an info level message with optional structured data.

        Args:
            message (str): The log message.
            data (dict or str, optional): Additional structured data to include.
                If dict, will be JSON-encoded. If str, will be included as-is.
            *args: Additional positional arguments passed to the underlying logger.
            **kwargs: Additional keyword arguments passed to the underlying logger.

        Example:
            ```python
            Logger.info("User action", {"user_id": 123, "action": "login"})
            Logger.info("Simple message")
            ```
        """
        if cls._logger is None:
            raise ValueError("Logger not initialized")

        message = cls._format_data(message, data)
        cls._logger.info(message, *args, **kwargs)

    @classmethod
    def debug(
        cls,
        message: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        *args,
        **kwargs,
    ):
        """
        Log a debug level message with optional structured data.

        Args:
            message (str): The log message.
            data (dict or str, optional): Additional structured data to include.
            *args: Additional positional arguments passed to the underlying logger.
            **kwargs: Additional keyword arguments passed to the underlying logger.

        Example:
            ```python
            Logger.debug("Processing step", {"step": 1, "total": 5})
            ```
        """
        if cls._logger is None:
            raise ValueError("Logger not initialized")

        message = cls._format_data(message, data)
        cls._logger.debug(message, *args, **kwargs)

    @classmethod
    def warning(
        cls,
        message: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        *args,
        **kwargs,
    ):
        """
        Log a warning level message with optional structured data.

        Args:
            message (str): The log message.
            data (dict or str, optional): Additional structured data to include.
            *args: Additional positional arguments passed to the underlying logger.
            **kwargs: Additional keyword arguments passed to the underlying logger.

        Example:
            ```python
            Logger.warning("Rate limit approaching", {"usage": 95, "limit": 100})
            ```
        """
        if cls._logger is None:
            raise ValueError("Logger not initialized")

        message = cls._format_data(message, data)
        cls._logger.warning(message, *args, **kwargs)

    @classmethod
    def error(
        cls,
        message: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        *args,
        **kwargs,
    ):
        """
        Log an error level message with optional structured data.

        Args:
            message (str): The log message.
            data (dict or str, optional): Additional structured data to include.
            *args: Additional positional arguments passed to the underlying logger.
            **kwargs: Additional keyword arguments passed to the underlying logger.

        Example:
            ```python
            Logger.error("API call failed", {"endpoint": "/api/v1/users", "status": 500})
            ```
        """
        if cls._logger is None:
            raise ValueError("Logger not initialized")

        message = cls._format_data(message, data)
        cls._logger.error(message, *args, **kwargs)

    @classmethod
    def critical(
        cls,
        message: str,
        data: Optional[Union[Dict[str, Any], str]] = None,
        *args,
        **kwargs,
    ):
        """
        Log a critical level message with optional structured data.

        Args:
            message (str): The log message.
            data (dict or str, optional): Additional structured data to include.
            *args: Additional positional arguments passed to the underlying logger.
            **kwargs: Additional keyword arguments passed to the underlying logger.

        Example:
            ```python
            Logger.critical("System failure", {"component": "database", "error": "connection_lost"})
            ```
        """
        if cls._logger is None:
            raise ValueError("Logger not initialized")

        message = cls._format_data(message, data)
        cls._logger.critical(message, *args, **kwargs)

    @staticmethod
    def _format_data(message: str, data: Optional[Union[Dict[str, Any], str]] = None) -> str:
        """
        Format a log message with optional structured data.

        This internal method handles the formatting of messages with additional
        data, ensuring consistent output format across all log levels.

        Args:
            message (str): The base log message.
            data (dict or str, optional): Additional data to include.

        Returns:
            str: The formatted message with data appended if provided.

        Note:
            - Dict data is JSON-encoded with ensure_ascii=False for Unicode support
            - Padding is added between message and data for better readability
            - If JSON encoding fails, data is converted to string
        """
        if data is not None:
            if isinstance(data, dict):
                message = f"{message} {' ' * (20 - len(message))} | Data: {json.dumps(data, ensure_ascii=False)}"
            else:
                message = f"{message} {' ' * (20 - len(message))} | Data: {data}"

        return message
