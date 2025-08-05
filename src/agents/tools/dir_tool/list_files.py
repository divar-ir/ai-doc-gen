import os
from collections import defaultdict
from typing import Any, List, Optional

from opentelemetry import trace
from pydantic_ai import Tool

DEFAULT_IGNORED_DIRS = [
    ".git",
    ".venv",
    "assets",
    ".idea",
    "k8s",
    "logs",
    ".logs",
    "__pycache__",
    ".venv",
    ".old-venv",
]

DEFAULT_IGNORED_EXTENSIONS = [
    ".pyc",
    ".class",
    ".o",
    ".so",
    ".dll",
    ".exe",
    ".jar",
    ".war",
    ".ear",
    ".zip",
    ".tar.gz",
    ".tgz",
    ".rar",
    ".log",
    ".tmp",
    ".temp",
    ".swp",
    ".iml",
    ".cache",
    ".dat",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".env",
]


class ListFilesTool:
    def __init__(
        self,
        ignored_dirs: Optional[List[str]] = DEFAULT_IGNORED_DIRS,
        ignored_extensions: Optional[List[str]] = DEFAULT_IGNORED_EXTENSIONS,
    ):
        self.ignored_dirs = ignored_dirs or []
        self.ignored_extensions = ignored_extensions or []

    def get_tool(self):
        return Tool(self._run, name="List-Files-Tool", takes_ctx=False, max_retries=2)

    def _run(self, directory: str) -> Any:
        """List files in a directory recursively, grouping them by directory.

        This function walks through the directory tree starting from the given path,
        collecting all files and organizing them by their parent directories.
        It skips any directories specified in the ignored_dirs list.

        Args:
            directory (str): The path to the directory to list files from.

        Returns:
            str: A formatted string containing the directory structure and files,
                with files grouped by their parent directories. Each directory's
                files are listed on a new line, sorted alphabetically.

        Example:
            Files grouped by directory (relative to /path/to/dir):
            /: ['file1.txt', 'file2.txt']
            /subdir: ['file3.txt', 'file4.txt']
        """
        trace.get_current_span().set_attribute("input", directory)
        directory = directory
        if directory[-1] == "/":
            directory = directory[:-1]

        # Group files by directory
        dir_files = defaultdict(list)

        for root, dirs, files in os.walk(directory):
            # Skip ignored directories
            if self.ignored_dirs and any(ignored_dir in root for ignored_dir in self.ignored_dirs):
                continue

            # Get relative directory path
            rel_dir = os.path.relpath(root, directory)
            if rel_dir == ".":
                rel_dir = "/"
            else:
                rel_dir = "/" + rel_dir

            # Add files to this directory
            for filename in files:
                # Skip files with ignored extensions
                if self.ignored_extensions and any(filename.endswith(ext) for ext in self.ignored_extensions):
                    continue
                dir_files[rel_dir].append(filename)

        # Sort directories and files for readability
        result = f"Files grouped by directory (relative to {directory}):\n"

        for dir_path in sorted(dir_files.keys()):
            files = sorted(dir_files[dir_path])
            result += f"\n{dir_path}: {files}\n"

        if not dir_files:
            result = f"No files found in {directory}."

        trace.get_current_span().set_attribute("output", result)
        return result
