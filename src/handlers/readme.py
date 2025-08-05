from opentelemetry import trace

from agents.documenter import DocumenterAgent, DocumenterAgentConfig
from utils.repo import get_repo_version
from utils import Logger

from .base_handler import BaseHandler, BaseHandlerConfig


class ReadmeHandlerConfig(BaseHandlerConfig, DocumenterAgentConfig):
    pass


class ReadmeHandler(BaseHandler):
    def __init__(self, config: ReadmeHandlerConfig):
        super().__init__(config)

        self.agent = DocumenterAgent(config)

    async def handle(self):
        Logger.info("Starting readme handler")

        with trace.get_tracer("doc_readme").start_as_current_span("Readme Handler") as span:
            span.set_attributes(
                {
                    "repo_path": str(self.config.repo_path),
                    "repo_version": get_repo_version(self.config.repo_path),
                    "input": str(self.config.repo_path),
                }
            )
            result = await self.agent.run()

            return result
