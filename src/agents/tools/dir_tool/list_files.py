import os
from collections import defaultdict
from typing import Any, List, Optional

from opentelemetry import trace
from pydantic_ai import Tool

from utils import Logger


DEFAULT_IGNORED_DIRS = [
    # Version Control
    ".git",  # Git repository metadata
    ".svn",  # Subversion metadata
    ".hg",  # Mercurial metadata
    # Development Environment
    ".venv",  # Python virtual environment
    ".old-venv",  # Old Python virtual environment backup
    "venv",  # Python virtual environment (common name)
    "env",  # Python virtual environment (common name)
    ".idea",  # JetBrains IDE configuration files
    ".vscode",  # Visual Studio Code settings
    ".eclipse",  # Eclipse IDE files
    # Runtime/Build Artifacts
    "__pycache__",  # Python bytecode cache files
    "node_modules",  # Node.js dependencies
    "target",  # Maven/Gradle build output (Java)
    "build",  # Generic build output
    "dist",  # Distribution files
    "out",  # Output directory
    ".next",  # Next.js build output
    ".nuxt",  # Nuxt.js build output
    ".output",  # Nitro output
    # Language/Framework Specific
    # Python
    ".tox",  # Tox environments
    ".nox",  # Nox environments
    ".pytest_cache",  # Pytest cache
    ".mypy_cache",  # MyPy cache
    ".pyre",  # Pyre type checker
    ".pytype",  # Pytype static analyzer
    "site-packages",  # Python packages
    ".eggs",  # Python eggs
    "wheels",  # Python wheels directory
    # Go
    "vendor",  # Go vendor dependencies
    ".mod",  # Go module cache
    "go.work.sum",  # Go workspace sum
    # Java/JVM
    ".gradle",  # Gradle cache
    ".m2",  # Maven local repository
    ".metadata",  # Eclipse metadata
    ".recommenders",  # Eclipse recommenders
    "bin",  # Java compiled classes
    "gen",  # Generated sources
    # Node.js/JavaScript
    ".npm",  # NPM cache
    ".yarn",  # Yarn cache
    "yarn-error.log",  # Yarn error logs
    ".pnpm-store",  # PNPM store
    ".turbo",  # Turborepo cache
    ".rush",  # Rush.js cache
    "lerna-debug.log*",  # Lerna debug logs
    ".eslintcache",  # ESLint cache
    ".parcel-cache",  # Parcel cache
    ".cache",  # General cache
    "coverage",  # Coverage reports
    # PHP
    ".phpunit.result.cache",  # PHPUnit cache
    "composer.phar",  # Composer executable
    ".phplint-cache",  # PHP Lint cache
    # Framework Specific
    "bower_components",  # Bower components
    ".bundle",  # Ruby bundle
    "Pods",  # iOS CocoaPods
    "DerivedData",  # Xcode derived data
    ".cargo",  # Rust cargo
    ".stack-work",  # Haskell Stack
    "elm-stuff",  # Elm packages
    "_site",  # Jekyll/Static site generators
    # Infrastructure/Deployment
    "k8s",  # Kubernetes configuration files
    ".terraform",  # Terraform state
    ".docker",  # Docker build context
    # Documentation/Generated
    "docs/_build",  # Sphinx documentation build
    "site",  # MkDocs site
    # Logging/Output
    "logs",  # Application log files
    ".logs",  # Hidden log directory
    "log",  # Log directory
    # Static Assets
    "assets",  # Static files (images, fonts, etc.)
    "public",  # Public web assets (when not source)
    "static",  # Static files
    # Testing
    ".coverage",  # Coverage data
    "htmlcov",  # Coverage HTML reports
    ".nyc_output",  # NYC coverage output
    "jest-coverage",  # Jest coverage
    # OS/System
    ".DS_Store",  # macOS metadata
    "Thumbs.db",  # Windows thumbnails
]

DEFAULT_IGNORED_EXTENSIONS = [
    # Compiled/Binary Files
    ".pyc",  # Python bytecode
    ".pyo",  # Python optimized bytecode
    ".pyd",  # Python extension module (Windows)
    ".class",  # Java bytecode
    ".o",  # Object files
    ".so",  # Shared libraries (Linux)
    ".dll",  # Dynamic libraries (Windows)
    ".dylib",  # Dynamic libraries (macOS)
    ".exe",  # Executable files
    ".bin",  # Binary files
    ".a",  # Static libraries
    ".lib",  # Library files (Windows)
    # Other Languages
    ".beam",  # Erlang/Elixir compiled
    ".hi",  # Haskell interface files
    ".cmi",  # OCaml compiled interface
    ".cmo",  # OCaml compiled object
    ".cmx",  # OCaml optimized compiled
    ".rlib",  # Rust library
    ".pdb",  # Program database (debugging)
    # Java/JVM Archives
    ".jar",  # Java archive
    ".war",  # Web application archive
    ".ear",  # Enterprise application archive
    ".aar",  # Android archive
    # .NET
    ".mdb",  # Mono debug database
    # Compressed Archives
    ".zip",  # ZIP archive
    ".tar",  # Tar archive
    ".tar.gz",  # Compressed tar archive
    ".tgz",  # Compressed tar archive (short)
    ".tar.bz2",  # Bzip2 compressed tar
    ".tbz2",  # Bzip2 compressed tar (short)
    ".tar.xz",  # XZ compressed tar
    ".rar",  # RAR archive
    ".7z",  # 7-Zip archive
    ".gz",  # Gzip compressed
    ".bz2",  # Bzip2 compressed
    ".xz",  # XZ compressed
    # Package Manager Files
    ".whl",  # Python wheel
    ".egg",  # Python egg (deprecated)
    ".phar",  # PHP Archive
    ".deb",  # Debian package
    ".rpm",  # RPM package
    ".msi",  # Windows installer
    ".dmg",  # macOS disk image
    ".pkg",  # Package files
    ".gem",  # Ruby gem
    ".nupkg",  # NuGet package
    # Runtime/Cache Files
    ".log",  # Log files
    ".tmp",  # Temporary files
    ".temp",  # Temporary files
    ".swp",  # Vim swap files
    ".swo",  # Vim swap files
    "~",  # Backup files
    ".bak",  # Backup files
    ".orig",  # Original files
    ".cache",  # Cache files
    ".pid",  # Process ID files
    # Database Files
    ".dat",  # Data files
    ".db",  # Database files
    ".sqlite",  # SQLite database
    ".sqlite3",  # SQLite 3 database
    ".accdb",  # Microsoft Access database (newer)
    # Configuration/Environment
    ".env",  # Environment variable files
    ".env.local",  # Local environment variables
    ".env.production",  # Production environment variables
    ".env.development",  # Development environment variables
    # IDE/Editor Files
    ".iml",  # IntelliJ module files
    ".ipr",  # IntelliJ project files
    ".iws",  # IntelliJ workspace files
    ".sublime-project",  # Sublime Text project
    ".sublime-workspace",  # Sublime Text workspace
    ".vscode",  # VS Code settings (file)
    # OS/System Files
    ".DS_Store",  # macOS metadata
    "Thumbs.db",  # Windows thumbnails
    "desktop.ini",  # Windows desktop settings
    ".localized",  # macOS localization
    # Media Files (often not needed for code analysis)
    ".jpg",  # JPEG image
    ".jpeg",  # JPEG image
    ".png",  # PNG image
    ".gif",  # GIF image
    ".bmp",  # Bitmap image
    ".svg",  # SVG image (keeping minimal, might be needed)
    ".ico",  # Icon files
    ".mp3",  # Audio files
    ".mp4",  # Video files
    ".avi",  # Video files
    ".mov",  # Video files
    ".pdf",  # PDF files
    ".doc",  # Word documents
    ".docx",  # Word documents
    ".xls",  # Excel files
    ".xlsx",  # Excel files
    ".ppt",  # PowerPoint files
    ".pptx",  # PowerPoint files
    # Font Files
    ".ttf",  # TrueType fonts
    ".otf",  # OpenType fonts
    ".woff",  # Web fonts
    ".woff2",  # Web fonts
    ".eot",  # Embedded fonts
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
        Logger.debug("Tool Call: List Files", data={"directory": directory})

        trace.get_current_span().set_attribute("input", directory)
        directory = directory
        if directory[-1] == "/":
            directory = directory[:-1]

        # Group files by directory
        dir_files = defaultdict(list)

        for root, _, files in os.walk(directory):
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
