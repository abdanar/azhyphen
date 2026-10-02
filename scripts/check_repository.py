#!/usr/bin/env python3
"""Check azhyphen data and repository consistency."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from import_patterns import (
    DESTINATION,
    METADATA_DESTINATION,
    PatternError,
    XETEX_LOADER_DESTINATION,
    metadata_bytes,
    read_pattern_file,
    xetex_loader_bytes,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRECTORY = REPOSITORY_ROOT / "tex" / "latex" / "azhyphen"
REQUIRED_RUNTIME_FILES = (
    PACKAGE_DIRECTORY / "azhyphen.sty",
    PACKAGE_DIRECTORY / "azhyphen.lua",
    PACKAGE_DIRECTORY / "azhyphen.pat.txt",
    PACKAGE_DIRECTORY / "azhyphen.hyp.txt",
    PACKAGE_DIRECTORY / "azhyphen-xetex.tex",
)
ARTIFACT_SUFFIXES = (
    ".aux",
    ".log",
    ".out",
    ".pdf",
    ".xdv",
    ".dvi",
    ".synctex.gz",
    ".toc",
    ".pyc",
    ".fmt",
    ".fls",
)


def check_data() -> list[str]:
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
    return errors


def project_files() -> list[Path]:
    files: list[Path] = []
    for path in REPOSITORY_ROOT.rglob("*"):
        relative = path.relative_to(REPOSITORY_ROOT)
        if ".git" in relative.parts or "__pycache__" in relative.parts:
            continue
        if path.name == "local.mk" or not path.is_file():
            continue
        files.append(path)
    return files


def check_repository(source: Path | None) -> list[str]:
    errors = check_data()
    for path in REQUIRED_RUNTIME_FILES:
        if not path.is_file():
            errors.append(f"required runtime file is missing: {path.name}")

    pattern_datasets = list(PACKAGE_DIRECTORY.glob("*.pat.txt"))
    if pattern_datasets != [DESTINATION]:
        errors.append("package must contain exactly one canonical .pat.txt dataset")

    public_files = project_files()
    forbidden_paths = {str(REPOSITORY_ROOT), str(Path.home())}
    if source is not None:
        forbidden_paths.add(str(source.expanduser().resolve()))

    for path in public_files:
        relative = path.relative_to(REPOSITORY_ROOT)
        if path.name.startswith(".azhyphen") and path.name.endswith(".tmp"):
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
        PACKAGE_DIRECTORY / "azhyphen-xetex.tex",
    ):
        if not path.is_file():
            continue
        runtime = path.read_text(encoding="utf-8")
        if "localization" in runtime.lower() or "PATTERNS" in runtime or "../" in runtime:
            errors.append(f"external-project runtime dependency appears in {path.name}")
        if "usepackage{babel}" in runtime.lower() or "usepackage{polyglossia}" in runtime.lower():
            errors.append(f"forbidden language-package dependency appears in {path.name}")

    lua_path = PACKAGE_DIRECTORY / "azhyphen.lua"
    basic_path = REPOSITORY_ROOT / "tests" / "basic.tex"
    lua_text = lua_path.read_text(encoding="utf-8") if lua_path.is_file() else ""
    basic_text = basic_path.read_text(encoding="utf-8") if basic_path.is_file() else ""
    if "Azərbaycan dilində mətn burada yazılır." not in basic_text:
        errors.append("Azerbaijani UTF-8 smoke-test text is missing or damaged")
    for character in "iİıIçÇəƏğĞöÖşŞüÜ":
        if character not in lua_text:
            errors.append(f"Azerbaijani mapping character is missing: {character}")

    if PACKAGE_DIRECTORY.is_dir():
        for path in PACKAGE_DIRECTORY.iterdir():
            if path.name.endswith(".tmp"):
                errors.append(f"temporary synchronization file remains: {path.name}")
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-only", action="store_true")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    errors = check_data() if args.data_only else check_repository(args.source)
    if errors:
        for error in errors:
            print(f"error: {error}", file=sys.stderr)
        return 1
    if not args.quiet:
        print(
            "data validation passed"
            if args.data_only
            else "repository consistency passed"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
