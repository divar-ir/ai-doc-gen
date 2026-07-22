import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from utils.cache import is_up_to_date, load_manifest, manifest_path, write_manifest  # noqa: E402


class TestCache(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.docs = self.tmp / ".ai" / "docs"
        self.docs.mkdir(parents=True)
        self.f1 = self.docs / "structure_analysis.md"
        self.f1.write_text("structure")
        self.f2 = self.docs / "dependency_analysis.md"
        self.f2.write_text("dependency")
        self.files = [self.f1, self.f2]

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _write(self, version="1.0", fingerprint="fp"):
        write_manifest(self.docs, analyzer_version=version, repo_fingerprint=fingerprint, analysis_files=self.files)
        return load_manifest(self.docs)

    def test_roundtrip_and_valid(self):
        manifest = self._write()
        self.assertIsNotNone(manifest)
        self.assertEqual(manifest.repo_fingerprint, "fp")
        self.assertEqual(sorted(manifest.included_analyses), ["dependency_analysis.md", "structure_analysis.md"])
        self.assertTrue(
            is_up_to_date(manifest, repo_fingerprint="fp", analyzer_version="1.0", expected_files=self.files)
        )

    def test_fingerprint_mismatch_invalidates(self):
        manifest = self._write()
        self.assertFalse(
            is_up_to_date(manifest, repo_fingerprint="other", analyzer_version="1.0", expected_files=self.files)
        )

    def test_version_mismatch_invalidates(self):
        manifest = self._write()
        self.assertFalse(
            is_up_to_date(manifest, repo_fingerprint="fp", analyzer_version="2.0", expected_files=self.files)
        )

    def test_missing_file_invalidates(self):
        manifest = self._write()
        self.f2.unlink()
        self.assertFalse(
            is_up_to_date(manifest, repo_fingerprint="fp", analyzer_version="1.0", expected_files=self.files)
        )

    def test_edited_file_invalidates(self):
        manifest = self._write()
        self.f2.write_text("edited after manifest write")
        self.assertFalse(
            is_up_to_date(manifest, repo_fingerprint="fp", analyzer_version="1.0", expected_files=self.files)
        )

    def test_included_set_mismatch_invalidates(self):
        manifest = self._write()
        self.assertFalse(
            is_up_to_date(manifest, repo_fingerprint="fp", analyzer_version="1.0", expected_files=[self.f1])
        )

    def test_none_manifest_invalidates(self):
        self.assertFalse(is_up_to_date(None, repo_fingerprint="fp", analyzer_version="1.0", expected_files=self.files))

    def test_corrupt_manifest_loads_as_none(self):
        manifest_path(self.docs).write_text("{ not valid json ")
        self.assertIsNone(load_manifest(self.docs))


if __name__ == "__main__":
    unittest.main()
