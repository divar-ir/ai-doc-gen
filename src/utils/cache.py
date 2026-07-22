import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

MANIFEST_FILENAME = ".manifest.json"


class AnalysisManifest(BaseModel):
    analyzer_version: str = Field(..., description="Analyzer/app version that produced the docs")
    repo_fingerprint: str = Field(..., description="Content-based fingerprint of the analyzed file set")
    included_analyses: List[str] = Field(
        default_factory=list, description="Names of analysis files that were generated"
    )
    file_hashes: Dict[str, str] = Field(default_factory=dict, description="Analysis file name -> sha256 of its content")
    created_at: str = Field(default="", description="ISO timestamp of when the manifest was written")


def manifest_path(docs_dir: Path) -> Path:
    return Path(docs_dir) / MANIFEST_FILENAME


def load_manifest(docs_dir: Path) -> Optional[AnalysisManifest]:
    path = manifest_path(docs_dir)
    if not path.exists():
        return None

    try:
        return AnalysisManifest.model_validate_json(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def write_manifest(
    docs_dir: Path,
    *,
    analyzer_version: str,
    repo_fingerprint: str,
    analysis_files: List[Path],
) -> AnalysisManifest:
    docs_dir = Path(docs_dir)
    docs_dir.mkdir(parents=True, exist_ok=True)

    file_hashes: Dict[str, str] = {}
    for file_path in analysis_files:
        if file_path.exists():
            file_hashes[file_path.name] = _sha256_file(file_path)

    manifest = AnalysisManifest(
        analyzer_version=analyzer_version,
        repo_fingerprint=repo_fingerprint,
        included_analyses=sorted(file_hashes.keys()),
        file_hashes=file_hashes,
        created_at=datetime.now().isoformat(),
    )

    manifest_path(docs_dir).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
    return manifest


def is_up_to_date(
    manifest: Optional[AnalysisManifest],
    *,
    repo_fingerprint: str,
    analyzer_version: str,
    expected_files: List[Path],
) -> bool:
    if manifest is None:
        return False

    if manifest.analyzer_version != analyzer_version:
        return False

    if manifest.repo_fingerprint != repo_fingerprint:
        return False

    expected_names = sorted(file_path.name for file_path in expected_files)
    if sorted(manifest.included_analyses) != expected_names:
        return False

    for file_path in expected_files:
        if not file_path.exists():
            return False
        stored_hash = manifest.file_hashes.get(file_path.name)
        if stored_hash is None or stored_hash != _sha256_file(file_path):
            return False

    return True


def _sha256_file(path: Path) -> str:
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()
