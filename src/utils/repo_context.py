import hashlib
import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from utils.ignore_patterns import DEFAULT_IGNORED_DIRS, DEFAULT_IGNORED_EXTENSIONS

DEFAULT_MAX_CONTEXT_FILES = 1000
DEFAULT_MAX_STRUCTURE_CHARS = 100_000
_MAX_HASH_FILE_BYTES = 1_000_000
DEFAULT_EXCLUDED_COMPONENTS = {".ai"}
LANGUAGE_BY_EXTENSION: Dict[str, str] = {
    ".py": "Python",
    ".pyi": "Python",
    ".go": "Go",
    ".java": "Java",
    ".kt": "Kotlin",
    ".kts": "Kotlin",
    ".scala": "Scala",
    ".rb": "Ruby",
    ".php": "PHP",
    ".js": "JavaScript",
    ".jsx": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".tsx": "TypeScript",
    ".rs": "Rust",
    ".c": "C",
    ".h": "C/C++ Header",
    ".cc": "C++",
    ".cpp": "C++",
    ".cxx": "C++",
    ".hpp": "C++ Header",
    ".cs": "C#",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".mm": "Objective-C++",
    ".dart": "Dart",
    ".ex": "Elixir",
    ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".clj": "Clojure",
    ".elm": "Elm",
    ".lua": "Lua",
    ".r": "R",
    ".jl": "Julia",
    ".sh": "Shell",
    ".bash": "Shell",
    ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".proto": "Protocol Buffers",
    ".graphql": "GraphQL",
    ".gql": "GraphQL",
    ".vue": "Vue",
    ".svelte": "Svelte",
    ".html": "HTML",
    ".css": "CSS",
    ".scss": "SCSS",
    ".sass": "Sass",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".toml": "TOML",
    ".json": "JSON",
    ".tf": "Terraform",
    ".md": "Markdown",
    ".rst": "reStructuredText",
}


@dataclass
class RepoContext:
    structure: str
    languages: List[str]
    file_count: int
    shown_file_count: int
    truncated: bool
    files: List[str] = field(default_factory=list)
    fingerprint: str = ""


def build_repo_context(
    repo_path: Path,
    *,
    max_files: int = DEFAULT_MAX_CONTEXT_FILES,
    max_chars: int = DEFAULT_MAX_STRUCTURE_CHARS,
    respect_gitignore: bool = True,
    ignored_dirs: Optional[List[str]] = None,
    ignored_extensions: Optional[List[str]] = None,
    excluded_components: Optional[set] = None,
) -> RepoContext:
    repo_path = Path(repo_path)
    ignored_dirs = DEFAULT_IGNORED_DIRS if ignored_dirs is None else ignored_dirs
    ignored_extensions = DEFAULT_IGNORED_EXTENSIONS if ignored_extensions is None else ignored_extensions
    excluded_components = DEFAULT_EXCLUDED_COMPONENTS if excluded_components is None else excluded_components

    files: Optional[List[str]] = None
    if respect_gitignore:
        files = _git_tracked_files(repo_path)

    if files is None:
        files = _walk_files(repo_path, ignored_dirs, ignored_extensions)

    files = [f for f in files if not _has_ignored_extension(f, ignored_extensions)]
    if excluded_components:
        files = [f for f in files if not (set(Path(f).parts) & excluded_components)]
    files = sorted(set(files))

    languages = _detect_languages(files)
    fingerprint = compute_fingerprint(repo_path, files)

    structure, shown_count, truncated = _render_structure(
        repo_path=repo_path,
        files=files,
        languages=languages,
        max_files=max_files,
        max_chars=max_chars,
    )

    return RepoContext(
        structure=structure,
        languages=languages,
        file_count=len(files),
        shown_file_count=shown_count,
        truncated=truncated,
        files=files,
        fingerprint=fingerprint,
    )


def compute_fingerprint(repo_path: Path, files: List[str]) -> str:
    repo_path = Path(repo_path)
    digest = hashlib.sha256()

    for rel_path in sorted(files):
        digest.update(rel_path.encode("utf-8", errors="replace"))
        digest.update(b"\0")
        digest.update(_hash_file(repo_path / rel_path).encode("ascii"))
        digest.update(b"\n")

    return digest.hexdigest()


def _hash_file(path: Path) -> str:
    try:
        size = path.stat().st_size
        if size > _MAX_HASH_FILE_BYTES:
            return hashlib.sha256(f"__large__:{size}".encode("ascii")).hexdigest()
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except (OSError, PermissionError):
        return hashlib.sha256(b"__unreadable__").hexdigest()


def _git_tracked_files(repo_path: Path) -> Optional[List[str]]:
    try:
        inside = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=repo_path,
            capture_output=True,
            text=True,
        )
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return None

        result = subprocess.run(
            ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
            cwd=repo_path,
            capture_output=True,
        )
        if result.returncode != 0:
            return None

        raw = result.stdout.decode("utf-8", errors="replace")
        return [part for part in raw.split("\0") if part]
    except (OSError, FileNotFoundError):
        return None


def _walk_files(repo_path: Path, ignored_dirs: List[str], ignored_extensions: List[str]) -> List[str]:
    ignored_dir_set = set(ignored_dirs)
    gitignore_names, gitignore_suffixes = _read_gitignore_simple(repo_path)
    ignored_dir_set |= gitignore_names

    collected: List[str] = []
    for root, dirs, files in os.walk(repo_path):
        rel_root = Path(root).relative_to(repo_path)
        rel_parts = rel_root.parts
        if ignored_dir_set and any(part in ignored_dir_set for part in rel_parts):
            dirs[:] = []
            continue

        dirs[:] = [d for d in dirs if d not in ignored_dir_set]

        for filename in files:
            if _has_ignored_extension(filename, ignored_extensions):
                continue
            if gitignore_suffixes and any(filename.endswith(suffix) for suffix in gitignore_suffixes):
                continue
            abs_path = Path(root) / filename
            collected.append(str(abs_path.relative_to(repo_path)))

    return collected


def _read_gitignore_simple(repo_path: Path) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    suffixes: set[str] = set()

    gitignore = repo_path / ".gitignore"
    if not gitignore.exists():
        return names, suffixes

    try:
        lines = gitignore.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return names, suffixes

    for line in lines:
        entry = line.strip()
        if not entry or entry.startswith("#") or entry.startswith("!"):
            continue
        entry = entry.rstrip("/")
        if entry.startswith("*.") and "/" not in entry:
            suffixes.add(entry[1:])
        elif "/" not in entry and "*" not in entry:
            names.add(entry)

    return names, suffixes


def _has_ignored_extension(filename: str, ignored_extensions: List[str]) -> bool:
    return any(filename.endswith(ext) for ext in ignored_extensions)


def _detect_languages(files: List[str], top_n: int = 5) -> List[str]:
    counts: Dict[str, int] = defaultdict(int)
    for rel_path in files:
        ext = os.path.splitext(rel_path)[1].lower()
        language = LANGUAGE_BY_EXTENSION.get(ext)
        if language:
            counts[language] += 1

    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [language for language, _ in ranked[:top_n]]


def _render_structure(
    repo_path: Path,
    files: List[str],
    languages: List[str],
    max_files: int,
    max_chars: int,
) -> tuple[str, int, bool]:
    total = len(files)
    truncated = max_files > 0 and total > max_files
    shown_files = files[:max_files] if truncated else files
    shown_count = len(shown_files)

    dir_files: Dict[str, List[str]] = defaultdict(list)
    for rel_path in shown_files:
        parent = os.path.dirname(rel_path)
        key = "/" if parent == "" else "/" + parent
        dir_files[key].append(os.path.basename(rel_path))

    header_lines = []
    if languages:
        header_lines.append(f"Primary languages: {', '.join(languages)}")
    if truncated:
        header_lines.append(f"Total source files: {total} (showing first {shown_count}; listing truncated)")
    else:
        header_lines.append(f"Total source files: {total}")

    body = f"Files grouped by directory (relative to {repo_path}):\n"
    for dir_path in sorted(dir_files.keys()):
        body += f"\n{dir_path}: {sorted(dir_files[dir_path])}\n"

    if total == 0:
        body = f"No source files found in {repo_path}."

    structure = "\n".join(header_lines) + "\n\n" + body

    if max_chars > 0 and len(structure) > max_chars:
        structure = structure[:max_chars] + "\n... [structure truncated to fit context window] ...\n"
        truncated = True

    return structure, shown_count, truncated
