import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.repo_context import build_repo_context  # noqa: E402


def write(base: str, rel: str, content: str = "") -> Path:
    path = Path(base) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return path


class TestBuildRepoContextWalk(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_excludes_binary_extensions_and_ai_dir(self):
        write(self.tmp, "src/main.py", "print('x')")
        write(self.tmp, "src/app.pyc", "junk")
        write(self.tmp, ".ai/docs/structure_analysis.md", "cached")
        write(self.tmp, "README.md", "# hi")

        ctx = build_repo_context(Path(self.tmp), respect_gitignore=False)

        self.assertIn("src/main.py", ctx.files)
        self.assertIn("README.md", ctx.files)
        self.assertNotIn("src/app.pyc", ctx.files)
        self.assertFalse(any(f.startswith(".ai/") for f in ctx.files))

    def test_language_detection_orders_by_frequency(self):
        for i in range(3):
            write(self.tmp, f"m{i}.py")
        write(self.tmp, "a.yaml")
        write(self.tmp, "b.md")

        ctx = build_repo_context(Path(self.tmp), respect_gitignore=False)

        self.assertEqual(ctx.languages[0], "Python")
        self.assertIn("YAML", ctx.languages)
        self.assertIn("Primary languages: Python", ctx.structure)

    def test_truncation_caps_listing_but_keeps_total(self):
        for i in range(10):
            write(self.tmp, f"f{i}.py")

        ctx = build_repo_context(Path(self.tmp), respect_gitignore=False, max_files=3)

        self.assertTrue(ctx.truncated)
        self.assertEqual(ctx.shown_file_count, 3)
        self.assertEqual(ctx.file_count, 10)
        self.assertIn("truncated", ctx.structure)

    def test_fingerprint_is_stable_and_content_sensitive(self):
        write(self.tmp, "a.py", "one")

        fp1 = build_repo_context(Path(self.tmp), respect_gitignore=False).fingerprint
        fp2 = build_repo_context(Path(self.tmp), respect_gitignore=False).fingerprint
        self.assertEqual(fp1, fp2)

        write(self.tmp, "a.py", "two")
        fp3 = build_repo_context(Path(self.tmp), respect_gitignore=False).fingerprint
        self.assertNotEqual(fp1, fp3)

    def test_repo_under_ignore_named_parent_is_not_skipped(self):
        repo_root = Path(self.tmp) / "build" / "myrepo"
        write(str(repo_root), "src/main.py", "code")
        write(str(repo_root), "build/artifact.py", "generated")

        ctx = build_repo_context(repo_root, respect_gitignore=False)

        self.assertIn("src/main.py", ctx.files)
        self.assertFalse(any(f.startswith("build/") for f in ctx.files))

    def test_generated_ai_docs_do_not_invalidate_fingerprint(self):
        write(self.tmp, "a.py", "code")
        fp_before = build_repo_context(Path(self.tmp), respect_gitignore=False).fingerprint

        write(self.tmp, ".ai/docs/structure_analysis.md", "freshly generated output")
        fp_after = build_repo_context(Path(self.tmp), respect_gitignore=False).fingerprint

        self.assertEqual(fp_before, fp_after)


class TestBuildRepoContextGit(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _git(self, *args):
        subprocess.run(["git", *args], cwd=self.tmp, check=True, capture_output=True)

    def test_respects_gitignore_beyond_hardcoded_list(self):
        write(self.tmp, "keep.py", "k")
        write(self.tmp, ".gitignore", "custom_ignored/\n")
        write(self.tmp, "custom_ignored/gen.py", "g")
        self._git("init")

        ctx = build_repo_context(Path(self.tmp), respect_gitignore=True)

        self.assertIn("keep.py", ctx.files)
        self.assertFalse(any("custom_ignored" in f for f in ctx.files))


if __name__ == "__main__":
    unittest.main()
