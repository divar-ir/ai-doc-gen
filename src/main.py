import argparse
import asyncio
import base64
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import logfire
import nest_asyncio
from gitlab import Gitlab
from pydantic import BaseModel
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefinedType

import config
from config import load_config
from handlers.analyze import AnalyzeHandler, AnalyzeHandlerConfig
from handlers.cronjob import JobAnalyzeHandler, JobAnalyzeHandlerConfig
from handlers.readme import ReadmeHandler, ReadmeHandlerConfig
from utils import Logger

nest_asyncio.apply()


def configure_logging(
    repo_path: Path,
    file_level: int = logging.INFO,
    console_level: int = logging.WARNING,
):
    repo_name = repo_path.name

    logs_dir = Path(os.path.dirname(__file__)) / ".logs" / repo_name / datetime.now().strftime("%Y_%m_%d")
    os.makedirs(logs_dir, exist_ok=True)
    Logger.init(logs_dir, file_level=file_level, console_level=console_level)


async def analyze(args: argparse.Namespace):
    cfg: AnalyzeHandlerConfig = load_config(args, AnalyzeHandlerConfig, "analyzer")
    configure_logging(
        repo_path=cfg.repo_path,
        file_level=config.FILE_LOG_LEVEL,
        console_level=config.CONSOLE_LOG_LEVEL,
    )

    handler = AnalyzeHandler(cfg)

    await handler.handle()


async def document(args: argparse.Namespace):
    cfg: ReadmeHandlerConfig = load_config(args, ReadmeHandlerConfig, "documenter")
    configure_logging(
        repo_path=cfg.repo_path,
        file_level=config.FILE_LOG_LEVEL,
        console_level=config.CONSOLE_LOG_LEVEL,
    )

    handler = ReadmeHandler(cfg)

    await handler.handle()


async def cronjob_analyze(args: argparse.Namespace):
    cfg: JobAnalyzeHandlerConfig = load_config(
        args=args,
        handler_config=JobAnalyzeHandlerConfig,
        file_key="cronjob.analyze",
    )

    configure_logging(
        repo_path=Path("."),
        file_level=config.FILE_LOG_LEVEL,
        console_level=config.CONSOLE_LOG_LEVEL,
    )

    gitlab_client = Gitlab(
        url=config.GITLAB_API_URL,
        oauth_token=config.GITLAB_OAUTH_TOKEN,
    )

    handler = JobAnalyzeHandler(config=cfg, gitlab_client=gitlab_client)

    await handler.handle()


def _add_field_arg(handler_group: argparse.ArgumentParser, field_name: str, field_info: FieldInfo):
    arg_name = f"--{field_name.replace('_', '-')}"
    help_text = field_info.description

    # check if field is pydantic base model, iterate over those and add args for them
    if issubclass(field_info.annotation, BaseModel):
        for field_name, field_info in field_info.annotation.model_fields.items():
            _add_field_arg(handler_group, field_name, field_info)
        return

    # Boolean flags are special - use store_const with None as default
    # This lets us distinguish between "not specified" (None) and explicitly set (True/False)
    if field_info.annotation in [bool, Optional[bool]]:
        # Model default is stored for help text only
        if not field_info.is_required():
            help_text = "(optional) " + help_text
        if default := field_info.default:
            if not isinstance(default, PydanticUndefinedType):
                help_text += f" (default: {default})"

        handler_group.add_argument(
            arg_name,
            action="store_true",
            default=None,  # None means "not specified" for explicit detection
            help=help_text,
            required=field_info.is_required(),
        )
    else:
        if not field_info.is_required():
            help_text = "(optional) " + help_text
        if default := field_info.default:
            if not isinstance(default, PydanticUndefinedType):
                help_text += f" (default: {default})"

        # For non-boolean fields
        handler_group.add_argument(
            arg_name,
            default=None,  # None means "not specified"
            help=help_text,
            required=field_info.is_required(),
        )


def add_handler_args(
    parser: argparse.ArgumentParser,
    config_fields: dict[str, FieldInfo],
    handler_name: str,
):
    # Create an argument group for local run
    handler_group = parser.add_argument_group(handler_name)

    for field_name, field_info in config_fields.items():
        _add_field_arg(handler_group, field_name, field_info)


def parse_args():
    parser = argparse.ArgumentParser(description="Run code documentation tools")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Analyzer command
    analyze_parser = subparsers.add_parser("analyze", help="Run code analyzer")
    add_handler_args(analyze_parser, AnalyzeHandlerConfig.model_fields, "Analyzer Configuration")

    # Documenter command
    document_parser = subparsers.add_parser("document", help="Run code documenter")
    add_handler_args(document_parser, ReadmeHandlerConfig.model_fields, "Documenter Configuration")

    # Cronjob command
    cronjob_parser = subparsers.add_parser("cronjob", help="Run cronjob")
    cronjob_subparsers = cronjob_parser.add_subparsers(dest="sub_command", required=True)

    cronjob_analyze_parser = cronjob_subparsers.add_parser("analyze", help="Run cronjob analyzer")
    add_handler_args(
        cronjob_analyze_parser,
        JobAnalyzeHandlerConfig.model_fields,
        "Cronjob Analyzer Configuration",
    )

    return parser.parse_args()


def configure_langfuse():
    langfuse_auth = base64.b64encode(f"{config.LANGFUSE_PUBLIC_KEY}:{config.LANGFUSE_SECRET_KEY}".encode()).decode()
    os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {langfuse_auth}"

    logfire.configure(
        service_name="ai-doc-gen",
        send_to_logfire=False,
        environment=config.ENVIRONMENT,
    )

    logfire.instrument_pydantic_ai()
    logfire.instrument_httpx(capture_all=True)


async def main() -> Optional[int]:
    if config.ENABLE_LANGFUSE:
        configure_langfuse()

    try:
        args = parse_args()
    except SystemExit as e:
        return e.code

    # Exit if no command is provided
    if not args.command:
        print("Error: Please specify a command (analyze, document, cronjob)")
        return 1

    match args.command:
        case "analyze":
            await analyze(args)
        case "document":
            await document(args)
        case "cronjob":
            if args.sub_command == "analyze":
                await cronjob_analyze(args)
            else:
                print(f"Error: Unknown cronjob sub-command '{args.sub_command}'")
                return 1
        case _:
            print(f"Error: Unknown command '{args.command}'")
            return 1


def cli_main():
    """Entry point for the CLI script."""
    result = asyncio.run(main())
    if result is not None:
        sys.exit(result)


if __name__ == "__main__":
    cli_main()
