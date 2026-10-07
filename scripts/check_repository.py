#!/usr/bin/env python3
"""Check azhyphen data and repository consistency."""

from __future__ import annotations
import argparse
from pathlib import Path
import sys
from import_patterns import DESTINATION, METADATA_DESTINATION, PatternError, XETEX_LOADER_DESTINATION, metadata_bytes, read_pattern_file, xetex_loader_bytes
from update_readme_stats import check_repository_state
from update_version import check_version_state

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY = REPOSITORY_ROOT / "tex" / "latex" / "azhyphen"
REQUIRED_RUNTIME_FILES = (
    PACKAGE_DIRECTORY / "azhyphen.sty",
    PACKAGE_DIRECTORY / "azhyphen.lua",
    PACKAGE_DIRECTORY / "azhyphen-version.tex",
    PACKAGE_DIRECTORY / "azhyphen.pat.txt",
    PACKAGE_DIRECTORY / "azhyphen.hyp.txt",
    PACKAGE_DIRECTORY / "azhyphen-xetex.tex",
)
ARTIFACT_SUFFIXES = (".aux", ".log", ".out", ".pdf", ".xdv", ".dvi", ".synctex.gz", ".toc", ".pyc", ".fmt", ".fls")
SYNCHRONIZATION_TEMP_PREFIXES = (
    ".azhyphen.pat.txt.",
    ".azhyphen-data.json.",
    ".azhyphen-xetex.tex.",
    ".model-stats.json.",
    ".README.md.",
)

def check_data() -> list[str]:
    """Validate generated data and cross-file consistency.

    The check verifies the canonical PATGEN pattern file, generated metadata,
    deterministic XeTeX loader, public model-statistics state, and package
    version state.

    Returns
    -------
    list[str]
        Validation error messages. An empty list indicates that all generated
        data is internally consistent.
    """
    errors: list[str] = []
    try:
        data = read_pattern_file(DESTINATION, label="bundled pattern file")
    except PatternError as exc:
        return [str(exc)]
    if not METADATA_DESTINATION.is_file():
        return ["generated metadata file is missing"]
    try:
        actual_metadata = METADATA_DESTINATION.read_bytes()
    except OSError as exc:
        return [f"cannot read generated metadata: {exc}"]
    if actual_metadata != metadata_bytes(data):
        errors.append("generated metadata does not match azhyphen.pat.txt")
    if not XETEX_LOADER_DESTINATION.is_file():
        errors.append("generated XeTeX loader is missing")
    elif XETEX_LOADER_DESTINATION.read_bytes() != xetex_loader_bytes(data):
        errors.append("generated XeTeX loader does not match azhyphen.pat.txt")
    errors.extend(check_repository_state())
    errors.extend(check_version_state(REPOSITORY_ROOT))
    return errors

def project_files() -> list[Path]:
    """Collect repository files subject to public consistency checks.

    Git internals, Python cache directories, the private ``local.mk`` file,
    and directories themselves are excluded.

    Returns
    -------
    list[pathlib.Path]
        Files in the repository that should be inspected for build artifacts,
        encoding problems, private paths, and other public-repository issues.
    """
    files: list[Path] = []
    for path in REPOSITORY_ROOT.rglob("*"):
        relative = path.relative_to(REPOSITORY_ROOT)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.name == "local.mk" or not path.is_file():
            continue
        files.append(path)
    return files

def check_repository(source: Path | None, stats_source: Path | None) -> list[str]:
    """Validate the complete azhyphen repository state.

    In addition to generated-data validation, this check verifies required
    runtime files, the single-canonical-pattern invariant, UTF-8 integrity,
    absence of build and synchronization artifacts, public-path privacy,
    runtime independence from external projects, and Azerbaijani-specific
    smoke-test data.

    Parameters
    ----------
    source : pathlib.Path or None
        External PATGEN source path used during synchronization. When
        provided, its resolved machine-local path is forbidden from appearing
        in public repository files.
    stats_source : pathlib.Path or None
        External public-statistics source path used during synchronization.
        When provided, its resolved machine-local path is likewise forbidden
        from appearing in public repository files.

    Returns
    -------
    list[str]
        Repository-consistency error messages. An empty list indicates that
        all checks passed.

    Notes
    -----
    ``local.mk`` is intentionally excluded from public-path inspection because
    it is private, ignored developer configuration and may legitimately contain
    machine-local paths.
    """
    errors = check_data()
    for path in REQUIRED_RUNTIME_FILES:
        if not path.is_file():
            errors.append(f"required runtime file is missing: {path.name}")
    pattern_datasets = set(PACKAGE_DIRECTORY.glob("*.pat.txt"))
    if pattern_datasets != {DESTINATION}:
        errors.append("package must contain exactly one canonical .pat.txt dataset")
    public_files = project_files()
    forbidden_paths = {str(REPOSITORY_ROOT), str(Path.home())}
    if source is not None:
        forbidden_paths.add(str(source.expanduser().resolve()))
    if stats_source is not None:
        forbidden_paths.add(str(stats_source.expanduser().resolve()))
    for path in public_files:
        relative = path.relative_to(REPOSITORY_ROOT)
        if path.name.endswith(".tmp") and path.name.startswith(SYNCHRONIZATION_TEMP_PREFIXES):
            errors.append(f"temporary synchronization file remains: {relative}")
        if path.name.endswith(ARTIFACT_SUFFIXES):
            errors.append(f"build artifact remains in repository: {relative}")
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(f"project file is not valid UTF-8: {relative}")
            continue
        except OSError as exc:
            errors.append(f"cannot inspect {relative}: {exc}")
            continue
        for forbidden in forbidden_paths:
            if forbidden and forbidden in text:
                errors.append(f"machine-local absolute path appears in {relative}")
                break
    for path in (
        PACKAGE_DIRECTORY / "azhyphen.sty",
        PACKAGE_DIRECTORY / "azhyphen.lua",
        PACKAGE_DIRECTORY / "azhyphen-version.tex",
        PACKAGE_DIRECTORY / "azhyphen-xetex.tex",
    ):
        if not path.is_file():
            continue
        runtime = path.read_text(encoding="utf-8")
        runtime_lower = runtime.lower()
        if "localization" in runtime_lower or "PATTERNS" in runtime or "../" in runtime:
            errors.append(f"external-project runtime dependency appears in {path.name}")
        if "usepackage{babel}" in runtime_lower or "usepackage{polyglossia}" in runtime_lower:
            errors.append(f"forbidden language-package dependency appears in {path.name}")
    lua_path = PACKAGE_DIRECTORY / "azhyphen.lua"
    basic_path = REPOSITORY_ROOT / "tests" / "basic.tex"
    lua_text = lua_path.read_text(encoding="utf-8") if lua_path.is_file() else ""
    basic_text = basic_path.read_text(encoding="utf-8") if basic_path.is_file() else ""
    if "Azərbaycan dilində mətn burada yazılır." not in basic_text:
        errors.append("Azerbaijani UTF-8 smoke-test text is missing or damaged")
    # This is an integrity check only; runtime tests verify the mappings themselves.
    for character in "iİıIçÇəƏğĞöÖşŞüÜ":
        if character not in lua_text:
            errors.append(f"Azerbaijani mapping character is missing: {character}")
    if PACKAGE_DIRECTORY.is_dir():
        for path in PACKAGE_DIRECTORY.iterdir():
            if path.name.endswith(".tmp"):
                errors.append(f"temporary synchronization file remains: {path.name}")
    return errors

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-only", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--stats-source", type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()

def main() -> int:
    """Run repository validation from the command line.

    Returns
    -------
    int
        Process exit status. ``0`` indicates success and ``1`` indicates one
        or more validation errors.
    """
    args = parse_args()
    errors = check_data() if args.data_only else check_repository(args.source, args.stats_source)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("data validation passed" if args.data_only else "repository consistency passed")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
