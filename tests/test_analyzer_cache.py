import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

for _var in (
    "ANALYZER_LLM_MODEL",
    "ANALYZER_LLM_BASE_URL",
    "ANALYZER_LLM_API_KEY",
    "DOCUMENTER_LLM_MODEL",
    "DOCUMENTER_LLM_BASE_URL",
    "DOCUMENTER_LLM_API_KEY",
):
    os.environ.setdefault(_var, "test-placeholder")

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from agents.analyzer import AnalyzerAgent, AnalyzerAgentConfig  # noqa: E402
from utils import Logger  # noqa: E402
from utils.cache import load_manifest  # noqa: E402
from utils.repo_context import build_repo_context  # noqa: E402


def setUpModule():
    Logger.init(Path(tempfile.mkdtemp()) / "logs")


class TestAnalyzerCacheWiring(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "a.py").write_text("print(1)")
        self.docs = self.tmp / ".ai" / "docs"
        self.docs.mkdir(parents=True)
        self.expected = [
            self.docs / "structure_analysis.md",
            self.docs / "dependency_analysis.md",
            self.docs / "data_flow_analysis.md",
        ]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _agent(self, **overrides) -> AnalyzerAgent:
        cfg = AnalyzerAgentConfig(
            repo_path=self.tmp,
            exclude_request_flow=True,
            exclude_api_analysis=True,
            respect_gitignore=False,
            **overrides,
        )
        agent = AnalyzerAgent(cfg)
        agent._repo_context = build_repo_context(self.tmp, respect_gitignore=False)
        return agent

    def _produce_outputs(self):
        for file_path in self.expected:
            file_path.write_text("analysis output")

    def test_miss_then_hit_then_invalidate(self):
        agent = self._agent()

        self.assertFalse(agent._is_cache_valid(self.docs, self.expected))

        self._produce_outputs()
        agent._update_cache(self.docs, self.expected)

        self.assertTrue(agent._is_cache_valid(self.docs, self.expected))

        forced = self._agent(force_reanalysis=True)
        self.assertFalse(forced._is_cache_valid(self.docs, self.expected))

        disabled = self._agent(cache_enabled=False)
        self.assertFalse(disabled._is_cache_valid(self.docs, self.expected))

        (self.tmp / "a.py").write_text("print(2)")
        changed = self._agent()
        self.assertFalse(changed._is_cache_valid(self.docs, self.expected))

    def test_partial_run_is_not_cached(self):
        agent = self._agent()
        self.expected[0].write_text("only one output")

        agent._update_cache(self.docs, self.expected)

        self.assertIsNone(load_manifest(self.docs))


if __name__ == "__main__":
    unittest.main()
