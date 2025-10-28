from opentelemetry import trace

from agents.ai_rules_generator import AIRulesGeneratorAgent, AIRulesGeneratorConfig
from utils import Logger
from utils.repo import get_repo_version

from .base_handler import BaseHandler, BaseHandlerConfig


class AIRulesHandlerConfig(BaseHandlerConfig, AIRulesGeneratorConfig):
    pass


class AIRulesHandler(BaseHandler):
    """Handler for generating AI assistant configuration files."""

    def __init__(self, config: AIRulesHandlerConfig):
        super().__init__(config)
        self.agent = AIRulesGeneratorAgent(config)

    async def handle(self):
        """Generate AI rules files and write them to repository root."""
        Logger.info(f"Generating AI rules for repository {self.config.repo_path}")

        with trace.get_tracer("ai_rules").start_as_current_span("AI Rules Handler") as span:
            span.set_attributes(
                {
                    "repo_path": str(self.config.repo_path),
                    "repo_version": get_repo_version(self.config.repo_path),
                    "skip_existing_claude_md": self.config.skip_existing_claude_md,
                    "skip_existing_agents_md": self.config.skip_existing_agents_md,
                    "skip_existing_cursor_rules": self.config.skip_existing_cursor_rules,
                    "detail_level": self.config.detail_level,
                    "input": str(self.config.repo_path),
                }
            )

            result = await self.agent.run()

            return result
