#!/usr/bin/env python3
"""Build and validate an allowlisted CTAN distribution; never publish it."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from check_repository import check_data
from update_readme_stats import load_stats
from update_version import read_version

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = (
    "azhyphen.sty", "azhyphen.lua", "azhyphen-xetex.tex",
    "azhyphen.pat.txt", "azhyphen.hyp.txt", "azhyphen-data.json",
    "azhyphen-version.tex",
)
SOURCES = {
    **{name: f"tex/latex/azhyphen/{name}" for name in RUNTIME},
    **{name: name for name in ("README.md", "LICENSE", "LPPL-1.3c.txt", "CHANGELOG.md")},
    "PROVENANCE.md": "docs/PROVENANCE.md",
    "azhyphen-doc.tex": "doc/azhyphen-doc.tex",
}
EXPECTED = set(SOURCES) | {"azhyphen-doc.pdf"}
STATS_START = "% AZHYPHEN-DOC-STATS:START"
STATS_END = "% AZHYPHEN-DOC-STATS:END"
# Stable default independent of checkout/commit times. Override explicitly.
DEFAULT_EPOCH = 946684800
PRIVATE_PATH = re.compile(
    rb"(?:(?<![A-Za-z0-9])[A-Za-z]:[\\/]|(?<![A-Za-z0-9:])/(?:home|Users|mnt|tmp|private|var|opt|usr|etc)/|\\\\[A-Za-z0-9_.-]+\\)"
)
ABSOLUTE_TEXT_PATH = re.compile(rb"(?<![A-Za-z0-9_:/])/(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+")


class ReleaseError(RuntimeError):
    pass


def run(command: list[str], cwd: Path, env: dict[str, str] | None = None) -> None:
    try:
        result = subprocess.run(command, cwd=cwd, env=env, capture_output=True,
                                text=True, encoding="utf-8", errors="replace", check=False)
    except OSError as exc:
        raise ReleaseError(f"required tool {command[0]} could not run: {exc}") from exc
    if result.returncode:
        detail = (result.stdout + result.stderr)[-12000:]
        raise ReleaseError(f"{command[0]} failed ({result.returncode}):\n{detail}")


def epoch() -> int:
    try:
        value = int(os.environ.get("SOURCE_DATE_EPOCH", str(DEFAULT_EPOCH)))
    except ValueError as exc:
        raise ReleaseError("SOURCE_DATE_EPOCH must be an integer") from exc
    if not 315532800 <= value <= 4354819199:
        raise ReleaseError("SOURCE_DATE_EPOCH must fit ZIP dates (1980 through 2107)")
    return value


def check_tag(version: str, tag: str | None) -> None:
    if tag is not None and tag != f"v{version}":
        raise ReleaseError(f"release tag {tag!r} does not agree with VERSION={version}")


def validate_inputs() -> str:
    errors = check_data()
    if errors:
        raise ReleaseError("inconsistent generated state:\n" + "\n".join(errors))
    version = read_version(ROOT)
    tag = os.environ.get("RELEASE_TAG")
    if os.environ.get("GITHUB_REF_TYPE") == "tag":
        tag = os.environ.get("GITHUB_REF_NAME", "")
    check_tag(version, tag)
    run(["git", "diff", "--check"], ROOT)
    run(["git", "diff", "--cached", "--check"], ROOT)
    return version


def manual_bytes() -> bytes:
    source = (ROOT / SOURCES["azhyphen-doc.tex"]).read_text(encoding="utf-8")
    if source.count(r"\input{azhyphen-version.tex}") != 1 or source.count(
        r"\date{Package version \azhyphenversion}"
    ) != 1:
        raise ReleaseError("manual must read and display the generated package version")
    if source.count(STATS_START) != 1 or source.count(STATS_END) != 1:
        raise ReleaseError("manual requires exactly one pair of statistics markers")
    start, end = source.index(STATS_START), source.index(STATS_END)
    if start >= end:
        raise ReleaseError("manual statistics markers are out of order")
    stats = load_stats(ROOT / "docs/model-stats.json")
    labels = {
        "training_count": "Training annotations", "evaluation_count": "Evaluation annotations",
        "pattern_count": "Patterns", "exact_accuracy": "Exact word accuracy",
        "precision": "Break precision", "recall": "Break recall", "f1": "Break F1",
        "correct_breakpoints": "Correct breakpoints", "wrong_breakpoints": "Wrong breakpoints",
        "missed_breakpoints": "Missed breakpoints",
    }
    rows = []
    for field, label in labels.items():
        value = stats[field]
        displayed = f"{value:.2f}\\%" if field in {"exact_accuracy", "precision", "recall", "f1"} else f"{value:,}"
        rows.append(f"{label} & {displayed} " + r"\\")
    table = "\\begin{tabular}{lr}\n" + "\n".join(rows) + "\n\\end{tabular}\n"
    return (source[:start + len(STATS_START)] + "\n" + table + source[end:]).encode("utf-8")


def source_bytes(name: str) -> bytes:
    if name == "azhyphen-doc.tex":
        return manual_bytes()
    contents = (ROOT / SOURCES[name]).read_bytes()
    if name == "README.md":
        # CTAN has no Makefile/maintenance tools. Keep generated badges/statistics intact.
        text = contents.decode("utf-8")
        start = text.index("## Installation\n")
        end = text.index("## Development\n", start)
        text = text[:start] + (
            "## Installation\n\n"
            "See `azhyphen-doc.pdf` (source: `azhyphen-doc.tex`) for installation\n"
            "from this archive, including XeLaTeX language registration.\n"
            "The `make install` command is available in the source repository only.\n\n"
        ) + text[end:]
        text = text.replace(
            "[DEVELOPMENT.md](DEVELOPMENT.md)",
            "[DEVELOPMENT.md](https://github.com/abdanar/azhyphen/blob/main/DEVELOPMENT.md)",
        ).replace("[docs/PROVENANCE.md](docs/PROVENANCE.md)", "[PROVENANCE.md](PROVENANCE.md)")
        contents = text.encode("utf-8")
    return contents


def validate_contents(name: str, contents: bytes) -> None:
    if name == "azhyphen-doc.pdf":
        if not contents.startswith(b"%PDF-") or b"%%EOF" not in contents[-1024:]:
            raise ReleaseError("manual PDF is missing or invalid")
    else:
        contents.decode("utf-8")
        if ABSOLUTE_TEXT_PATH.search(contents):
            raise ReleaseError(f"absolute filesystem path in {name}")
    if PRIVATE_PATH.search(contents):
        raise ReleaseError(f"absolute/private machine path in {name}")
    for token in (b"BEGIN " + b"PRIVATE KEY", b"BEGIN RSA " + b"PRIVATE KEY",
                  b"BEGIN OPENSSH " + b"PRIVATE KEY", b"ghp_", b"github_pat_"):
        if token in contents:
            raise ReleaseError(f"possible secret in {name}")
    for path in (ROOT, Path.home()):
        for spelling in (str(path), path.as_posix()):
            if spelling.encode() in contents:
                raise ReleaseError(f"local build path in {name}")


def validate_stage(stage: Path) -> None:
    entries = list(stage.iterdir())
    if {p.name for p in entries} != EXPECTED or any(
        p.is_symlink() or not p.is_file() for p in entries
    ):
        raise ReleaseError("CTAN staging does not contain exactly the allowlisted regular files")
    for path in entries:
        contents = path.read_bytes()
        validate_contents(path.name, contents)
        if path.name in SOURCES and contents != source_bytes(path.name):
            raise ReleaseError(f"staged file differs from its source: {path.name}")


def compile_manual(work: Path, lualatex: str, timestamp: int) -> Path:
    work.mkdir(parents=True, exist_ok=True)
    (work / "azhyphen-doc.tex").write_bytes(manual_bytes())
    (work / "azhyphen-version.tex").write_bytes(source_bytes("azhyphen-version.tex"))
    env = dict(os.environ, SOURCE_DATE_EPOCH=str(timestamp), FORCE_SOURCE_DATE="1",
               TZ="UTC", TEXINPUTS=f".{os.pathsep}", LUAINPUTS=f".{os.pathsep}")
    for _ in range(2):
        run([lualatex, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
             "-file-line-error", "azhyphen-doc.tex"], work, env)
    pdf = work / "azhyphen-doc.pdf"
    if not pdf.is_file():
        raise ReleaseError("documentation compiler did not produce azhyphen-doc.pdf")
    validate_contents(pdf.name, pdf.read_bytes())
    log = (work / "azhyphen-doc.log").read_text(encoding="utf-8", errors="replace")
    if "Missing character:" in log or "undefined references" in log or "Overfull \\hbox" in log:
        raise ReleaseError("manual has missing glyphs, unresolved references, or overfull lines")
    return pdf


def smoke(stage: Path, lualatex: str, xelatex: str) -> None:
    # Use only staged runtime bytes; tests/helpers never enter the distribution.
    with tempfile.TemporaryDirectory(prefix="azhyphen-ctan-smoke.") as temporary:
        work = Path(temporary)
        for directory in ("var", "config"):
            (work / directory).mkdir()
        home = work / "home"
        package = home / "tex/latex/azhyphen"
        package.mkdir(parents=True)
        for name in RUNTIME:
            shutil.copyfile(stage / name, package / name)
        # TeX-style paths, with font cache writes confined to allowed TEXMFVAR.
        env = dict(os.environ, TEXMFHOME=home.as_posix(), TEXMFVAR=(work / "var").as_posix(),
                   TEXMFCONFIG=(work / "config").as_posix(), TEXMFCACHE=(work / "var").as_posix(),
                   TEXINPUTS=f".{os.pathsep}", LUAINPUTS=f".{os.pathsep}")
        run(["sh", str(ROOT / "tests/prepare-isolated-xetex.sh"), str(home)], work, env)
        run([sys.executable, str(ROOT / "scripts/xetex_language.py"), "install",
             "--texmfhome", str(home)], work, env)
        for engine, input_name in ((lualatex, "real-patterns.tex"), (xelatex, "xetex-runtime.tex")):
            destination = work / input_name.removesuffix(".tex")
            destination.mkdir()
            shutil.copyfile(ROOT / "tests" / input_name, destination / "smoke.tex")
            run([engine, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
                 "smoke.tex"], destination, env)
            log = (destination / "smoke.log").read_text(encoding="utf-8", errors="replace")
            if input_name == "xetex-runtime.tex" and "AZHYPHEN-XETEX-LANGUAGE-SELECTED" not in log:
                raise ReleaseError("staged XeLaTeX package did not select its registered language")


def write_archive(stage: Path, target: Path, timestamp: int) -> None:
    date = datetime.fromtimestamp(timestamp, timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(EXPECTED):
            entry = zipfile.ZipInfo(f"azhyphen/{name}", date_time=date)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, (stage / name).read_bytes())


def validate_archive(target: Path, stage: Path) -> None:
    with zipfile.ZipFile(target) as archive:
        expected = {f"azhyphen/{name}" for name in EXPECTED}
        names = archive.namelist()
        if len(names) != len(expected) or set(names) != expected or archive.testzip():
            raise ReleaseError("CTAN archive members/CRC do not match the exact allowlist")
        for entry in archive.infolist():
            name = entry.filename.split("/")[1]
            data = archive.read(entry)
            validate_contents(name, data)
            if data != (stage / name).read_bytes():
                raise ReleaseError(f"archive bytes differ from staging: {name}")


def reset_build(name: str) -> Path:
    build = ROOT / "build"
    target = build / name
    if build.is_symlink() or target.is_symlink() or target.resolve() != target:
        raise ReleaseError("refusing to clean a symlinked build directory")
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True)
    return target


def build(lualatex: str, xelatex: str, timestamp: int, version: str) -> Path:
    work = reset_build("ctan")
    stage = work / "azhyphen"
    stage.mkdir()
    for name in SOURCES:
        (stage / name).write_bytes(source_bytes(name))
    shutil.copyfile(compile_manual(work / "doc", lualatex, timestamp), stage / "azhyphen-doc.pdf")
    validate_stage(stage)
    smoke(stage, lualatex, xelatex)
    dist = ROOT / "dist"
    if dist.is_symlink() or dist.resolve() != dist:
        raise ReleaseError("refusing a symlinked dist directory")
    dist.mkdir(exist_ok=True)
    target = dist / f"azhyphen-{version}.zip"
    # Publish locally only after all checks pass; failures leave no partial ZIP.
    with tempfile.TemporaryDirectory(prefix="archive.", dir=work) as directory:
        candidate = Path(directory) / target.name
        write_archive(stage, candidate, timestamp)
        validate_archive(candidate, stage)
        os.replace(candidate, target)
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("doc", "ctan", "clean", "clean-dist"))
    parser.add_argument("--lualatex", default=os.environ.get("LUALATEX", "lualatex"))
    parser.add_argument("--xelatex", default=os.environ.get("XELATEX", "xelatex"))
    args = parser.parse_args()
    try:
        if args.action in {"clean", "clean-dist"}:
            names = ("build/doc", "build/ctan") if args.action == "clean" else ("dist",)
            for name in names:
                target = ROOT / name
                if target.is_symlink() or target.resolve() != target:
                    raise ReleaseError(f"refusing symlinked cleanup target: {name}")
                if target.exists():
                    shutil.rmtree(target)
            return 0
        version = validate_inputs()
        timestamp = epoch()
        if args.action == "doc":
            result = compile_manual(reset_build("doc"), args.lualatex, timestamp)
        else:
            result = build(args.lualatex, args.xelatex, timestamp, version)
        print(result.relative_to(ROOT))
        print(f"SHA-256: {hashlib.sha256(result.read_bytes()).hexdigest()}")
    except (ReleaseError, OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
