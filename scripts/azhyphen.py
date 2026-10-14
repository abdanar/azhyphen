#!/usr/bin/env python3
"""Generate, check, test, install and package azhyphen. Python 3.10+, stdlib only."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unicodedata
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOWER = "abcçdeəfgğhxıijkqlmnoöprsştuüvyz"
UPPER = "ABCÇDEƏFGĞHXIİJKQLMNOÖPRSŞTUÜVYZ"
CASE = dict(zip(UPPER, LOWER))
MINIMUM = 2
# Same parameters as the migrated model; always start with empty patterns.
PATGEN_INPUT = "1 1\n2 4\n1 3 3\nn\n"
RUNTIME = ("azhyphen.sty", "azhyphen.lua", "azhyphen.pat.txt",
           "azhyphen-xetex.tex", "azhyphen-version.tex")
SOURCES = (*RUNTIME, "VERSION", "README.md", "LICENSE", "LPPL-1.3c.txt",
           "CC0-1.0.txt", "CHANGELOG.md", "Makefile", "data/hyphenated.txt",
           "data/evaluation.txt", "scripts/azhyphen.py", "doc/azhyphen-doc.tex")
TEST_WORDS = ("fotoelektrik", "ellərarası", "addımölçən", "videobloger", "ətürpərdici")
START = "<!-- AZHYPHEN-GENERATED:START -->"
END = "<!-- AZHYPHEN-GENERATED:END -->"
BEGIN_REG = "% BEGIN azhyphen managed registration"
END_REG = "% END azhyphen managed registration"
REGISTRATION = f"{BEGIN_REG}\nazhyphen azhyphen-xetex.tex\n{END_REG}\n"


def run(command: list[str], cwd: Path | None = None,
        env: dict[str, str] | None = None, input: str | None = None) -> str:
    result = subprocess.run(command, cwd=cwd or ROOT, env=env, input=input,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=300)
    output = result.stdout + result.stderr
    if result.returncode:
        raise ValueError(f"{' '.join(command[:2])} failed ({result.returncode}):\n{output[-10000:]}")
    return output


def text_bytes(path: Path) -> bytes:
    return path.read_bytes().replace(b"\r\n", b"\n")


def write(path: Path, content: bytes) -> None:
    """Atomic per-file replacement, preserving permissions and unchanged files."""
    if path.exists() and path.read_bytes() == content:
        return
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as handle:
        temporary = Path(handle.name)
        handle.write(content)
    try:
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def lower(word: str) -> str:
    return "".join(CASE.get(ch, ch) for ch in word)


def read_words(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    words = text.splitlines()
    if not words or not text.endswith("\n"):
        raise ValueError(f"{path.name}: expected words with a final newline")
    seen = set()
    for number, word in enumerate(words, 1):
        if (unicodedata.normalize("NFC", word) != word or
            not re.fullmatch(f"[{LOWER}{UPPER}]+(?:-[{LOWER}{UPPER}]+)*", word)):
            raise ValueError(f"{path.name}:{number}: expected one NFC Azerbaijani word with ASCII hyphens")
        plain = lower(word.replace("-", ""))
        if plain in seen:
            raise ValueError(f"{path.name}:{number}: duplicate word {plain}")
        seen.add(plain)
    return words


def datasets(root: Path = ROOT) -> tuple[list[str], list[str]]:
    train = read_words(root / "data/hyphenated.txt")
    evaluation = read_words(root / "data/evaluation.txt")
    overlap = {lower(s.replace("-", "")) for s in train} & {
        lower(s.replace("-", "")) for s in evaluation}
    if overlap:
        raise ValueError("training/evaluation overlap: " + ", ".join(sorted(overlap)))
    return train, evaluation


def patterns(raw: bytes) -> dict[str, list[int]]:
    result = {}
    for token in raw.decode("utf-8").split():
        if not re.fullmatch(f"[.{LOWER}0-9]+", token) or not re.search("[0-9]", token):
            raise ValueError("invalid PATGEN pattern: " + token)
        letters, values = [], [0]
        for ch in token:
            if ch in "0123456789":
                values[-1] = int(ch)
            else:
                letters.append(ch)
                values.append(0)
        key = "".join(letters)
        if not key or key in result:
            raise ValueError("empty or duplicate pattern key: " + key)
        result[key] = values
    if not result:
        raise ValueError("PATGEN produced no patterns")
    return result


def generate(train: list[str]) -> bytes:
    # PATGEN 2.4's translation table accepts multibyte UTF-8 letter strings.
    # Annotations pass through unchanged; minima restrict predictions only.
    with tempfile.TemporaryDirectory(prefix="azhyphen-patgen.") as temporary:
        work = Path(temporary)
        (work / "words").write_bytes("".join(f".{s}.\n" for s in train).encode("utf-8"))
        (work / "empty").write_bytes(b"")
        translation = f"{MINIMUM:02}{MINIMUM:02}\n" + "".join(
            f" {lo} {up}\n" for lo, up in zip(LOWER, UPPER))
        (work / "translate").write_bytes(translation.encode("utf-8"))
        run(["patgen", "words", "empty", "patterns", "translate"], work, input=PATGEN_INPUT)
        raw = text_bytes(work / "patterns")
        patterns(raw)
    print(f"PATGEN: {len(train)} training words -> {len(raw.split())} patterns")
    return raw


def predict(word: str, model: dict[str, list[int]]) -> set[int]:
    """Reference Liang scoring for offline evaluation; runtime uses native TeX."""
    word = lower(word)
    padded = "." + word + "."
    weights = [0] * (len(padded) + 1)
    for start in range(len(padded)):
        for end in range(start + 1, len(padded) + 1):
            for offset, value in enumerate(model.get(padded[start:end], ())):
                weights[start + offset] = max(weights[start + offset], value)
    return {i for i in range(MINIMUM, len(word) - MINIMUM + 1) if weights[i + 1] % 2}


def breaks(annotation: str) -> set[int]:
    position, result = 0, set()
    for ch in annotation:
        if ch == "-":
            result.add(position)
        else:
            position += 1
    return result


def statistics(train: list[str], evaluation: list[str], raw: bytes) -> dict[str, float | int]:
    model = patterns(raw)
    correct = wrong = missed = exact = 0
    for annotated in evaluation:
        expected = breaks(annotated)
        actual = predict(annotated.replace("-", ""), model)
        correct += len(actual & expected)
        wrong += len(actual - expected)
        missed += len(expected - actual)
        exact += actual == expected
    ratio = lambda a, b: 100 * a / b if b else 0.0
    return dict(training=len(train), evaluation=len(evaluation), patterns=len(model),
                exact=ratio(exact, len(evaluation)), precision=ratio(correct, correct + wrong),
                recall=ratio(correct, correct + missed),
                f1=ratio(2 * correct, 2 * correct + wrong + missed),
                correct=correct, wrong=wrong, missed=missed)


def loader(raw: bytes) -> bytes:
    patterns(raw)
    return ("% Generated by scripts/azhyphen.py; do not edit.\n"
            "% Pattern SHA-256: " + hashlib.sha256(raw).hexdigest() + "\n"
            "\\begingroup\n\\patterns{\n" + raw.decode("utf-8") +
            "}\n\\endgroup\n\\endinput\n").encode("utf-8")


def version(root: Path = ROOT) -> str:
    value = (root / "VERSION").read_text(encoding="utf-8")
    if not re.fullmatch(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\n", value):
        raise ValueError("VERSION must contain one semantic version and a newline")
    return value.strip()


def generated(root: Path, raw: bytes, train: list[str], evaluation: list[str]) -> dict[str, bytes]:
    metrics = statistics(train, evaluation, raw)
    number = version(root)
    status = "development release" if number.startswith("0.") else "release"
    block = (f"Azhyphen **{number}** is currently a **{status}**. Its hyphenation\n"
             "patterns are generated reproducibly from the public annotated Azerbaijani\n"
             "dataset included in this repository.\n\n"
             f"**Dataset** · {metrics['training']:,} training words · {metrics['evaluation']:,} evaluation words · "
             f"{metrics['patterns']:,} patterns\\\n"
             f"**Quality** · {metrics['exact']:.2f}% exact-word accuracy · {metrics['precision']:.2f}% precision · "
             f"{metrics['recall']:.2f}% recall · **{metrics['f1']:.2f}% F1**\\\n"
             f"**Breakpoints** · {metrics['correct']} correct · {metrics['wrong']} wrong · {metrics['missed']} missed\n")
    readme = (root / "README.md").read_bytes()
    readme.decode("utf-8")
    start, end = START.encode(), END.encode()
    if readme.count(start) != 1 or readme.count(end) != 1 or readme.index(start) >= readme.index(end):
        raise ValueError("README must have one ordered generated block")
    readme = readme[:readme.index(start) + len(start)] + b"\n" + block.encode("utf-8") + readme[readme.index(end):]
    return {"azhyphen.pat.txt": raw, "azhyphen-xetex.tex": loader(raw),
            "azhyphen-version.tex": ("% Generated from VERSION; do not edit.\n"
                                     f"\\def\\azhyphenversion{{{number}}}\n\\endinput\n").encode(),
            "README.md": readme}


def update(root: Path = ROOT, check: bool = False) -> None:
    train, evaluation = datasets(root)
    outputs = generated(root, generate(train), train, evaluation)
    stale = [name for name, content in outputs.items()
             if not (root / name).is_file() or text_bytes(root / name) != content.replace(b"\r\n", b"\n")]
    if check and stale:
        raise ValueError("stale generated files: " + ", ".join(stale) + "; run make update")
    if not check:
        for name in stale:
            write(root / name, outputs[name])
    print("Generated files current" if not stale else "Updated: " + ", ".join(stale))


def privacy(name: str, raw: bytes) -> None:
    # Build paths and credentials never belong in public sources or archives.
    if re.search(rb"(?<![A-Za-z])[A-Za-z]:[\\/]|/(?:Users|home|private|mnt)/|(?<!\\)\\\\[\w.-]+\\(?!\\)[\w.-]+\\(?!\\)", raw):
        raise ValueError(f"private absolute path in {name}")
    if any(token in raw for token in (b"gh" + b"p_", b"github" + b"_pat_", b"BEGIN " + b"PRIVATE KEY",
                                      b"BEGIN RSA " + b"PRIVATE KEY")):
        raise ValueError(f"possible credential in {name}")
    for path in (ROOT, Path.home()):
        if str(path).encode() in raw or path.as_posix().encode() in raw:
            raise ValueError(f"local path in {name}")


def check() -> None:
    update(ROOT, check=True)
    # Scan all public project files while excluding only disposable/local trees.
    names = []
    for directory, children, files in os.walk(ROOT):
        children[:] = [name for name in children if name not in
                       {".git", "build", "dist", "__pycache__", ".venv"}]
        names.extend((Path(directory) / name).relative_to(ROOT).as_posix()
                     for name in files if name != ".env")
    missing = set(SOURCES) - set(names)
    if missing:
        raise ValueError("missing source files: " + ", ".join(sorted(missing)))
    for name in names:
        path = ROOT / name
        if path.is_symlink() or not path.is_file():
            raise ValueError(f"expected regular source file: {name}")
        if name == "doc/azhyphen-doc.pdf":
            raw = path.read_bytes()
            if not raw.startswith(b"%PDF-") or b"%%EOF" not in raw[-1024:]:
                raise ValueError("invalid distributed manual PDF")
            privacy(name, raw)
            continue
        raw = text_bytes(path)
        raw.decode("utf-8")
        privacy(name, raw)
        if path.suffix in {".json", ".pdf", ".zip", ".log", ".fmt", ".pyc"}:
            raise ValueError("unexpected generated artifact outside build/dist: " + name)
    workflow = ROOT / ".github/workflows/ci.yml"
    if workflow.exists():
        text = workflow.read_text(encoding="utf-8")
        if "contents: read" not in text or "persist-credentials: false" not in text or "secrets." in text:
            raise ValueError("CI must use read-only permissions and no secrets")
        if any(not re.fullmatch(r"[^@]+@[a-f0-9]{40}", action)
               for action in re.findall(r"uses:\s+(\S+)", text)):
            raise ValueError("CI actions must use pinned commit identifiers")
    print("Dataset separation, generated state, version and privacy checks passed")


def tex_environment(work: Path) -> dict[str, str]:
    for name in ("home", "var", "config"):
        (work / name).mkdir(parents=True, exist_ok=True)
    # Native Windows TeX uses semicolon; MSYS TeX uses colon.
    native_windows = os.name == "nt" and not sys.platform.startswith("cygwin")
    separator = ";" if native_windows else ":"
    return dict(os.environ, TEXMFHOME=(work / "home").as_posix(),
                TEXMFVAR=(work / "var").as_posix(), TEXMFCONFIG=(work / "config").as_posix(),
                TEXMFCACHE=(work / "var").as_posix(), TEXINPUTS="." + separator,
                LUAINPUTS="." + separator, LC_ALL="C", LANG="C")


def strip_registration(text: str) -> str:
    return re.sub(rf"(?m)^{re.escape(BEGIN_REG)}\r?\n.*?^{re.escape(END_REG)}(?:\r?\n|$)",
                  "", text, flags=re.DOTALL)


def registered(text: str) -> str:
    text = strip_registration(text)
    if any(line.split("%", 1)[0].split()[:1] == ["azhyphen"] for line in text.splitlines()):
        raise ValueError("language name azhyphen already belongs to an unmanaged registration")
    return text + ("\n" if text and not text.endswith("\n") else "") + REGISTRATION


def registration(home: Path, env: dict[str, str], install: bool) -> None:
    """Edit only marked user registrations; rollback bytes and formats on failure."""
    config = home / "tex/generic/config"
    local = config / "language-local.dat"
    language = config / "language.dat"
    saved = {p: p.read_bytes() if p.exists() else None for p in (local, language)}
    if any(not p.resolve().is_relative_to(home.resolve()) for p in (local, language)):
        raise ValueError("language configuration resolves outside TEXMFHOME")
    local_text = saved[local].decode("utf-8") if saved[local] is not None else ""
    language_text = saved[language].decode("utf-8") if saved[language] is not None else ""
    if not install and BEGIN_REG not in local_text and BEGIN_REG not in language_text:
        return
    if install:
        # Validate both shared files before changing either.
        next_local = registered(local_text)
        next_language = registered(language_text) if saved[language] is not None else None
    else:
        next_local, next_language = strip_registration(local_text), strip_registration(language_text)
    try:
        write(local, next_local.encode("utf-8"))
        if next_language is None:
            run([shutil.which("tlmgr") or "tlmgr", "generate", "language.dat",
                 "--localcfg", local.as_posix(), "--dest", language.as_posix()], cwd=home, env=env)
            # tlmgr does not preserve markers from language-local.dat.
            text = language.read_text(encoding="utf-8")
            text = re.sub(r"(?m)^azhyphen azhyphen-xetex\.tex\s*$\n?", "", text)
            write(language, registered(text).encode("utf-8"))
        else:
            write(language, next_language.encode("utf-8"))
        run(["fmtutil-user", "--byfmt", "xelatex"], cwd=home, env=env)
    except BaseException:
        for path, content in saved.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                write(path, content)
        # Restore the previous format too if a rebuild replaced it partially.
        try:
            run(["fmtutil-user", "--byfmt", "xelatex"], cwd=home, env=env)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        raise


def installation(install: bool, home: Path | None = None) -> None:
    home = (home or Path(run(["kpsewhich", "-var-value=TEXMFHOME"]).strip())).expanduser().resolve()
    if home == Path(home.anchor):
        raise ValueError("refusing to install into a filesystem root")
    env = dict(os.environ, TEXMFHOME=home.as_posix(), LC_ALL="C", LANG="C")
    # fmtutil-user writes to TeX Live's user format storage; never use fmtutil-sys.
    package = home / "tex/latex/azhyphen"
    if any(not (package / name).resolve().is_relative_to(home) for name in RUNTIME):
        raise ValueError("runtime destination resolves outside TEXMFHOME")
    saved = {package / name: (package / name).read_bytes() if (package / name).exists() else None
             for name in RUNTIME}
    try:
        if install:
            for name in RUNTIME:
                write(package / name, text_bytes(ROOT / name))
        registration(home, env, install)
        if not install:
            for name in RUNTIME:
                path = package / name
                if path.is_file() and text_bytes(path) == text_bytes(ROOT / name):
                    path.unlink()
            if package.exists() and not any(package.iterdir()):
                package.rmdir()
    except BaseException:
        for path, content in saved.items():
            if content is None:
                path.unlink(missing_ok=True)
            else:
                write(path, content)
        try:
            run(["fmtutil-user", "--byfmt", "xelatex"], cwd=home, env=env)
        except (OSError, ValueError, subprocess.TimeoutExpired):
            pass
        raise
    print("User installation complete" if install else "User registration removed; unrelated files preserved")


def prepare_test_languages(home: Path, env: dict[str, str]) -> None:
    config = home / "tex/generic/config"
    config.mkdir(parents=True, exist_ok=True)
    local = config / "language-local.dat"
    language = config / "language.dat"
    write(local, b"% Unrelated test registration\nazhyphen-unrelated zerohyph.tex\n")
    run([shutil.which("tlmgr") or "tlmgr", "generate", "language.dat",
         "--localcfg", local.as_posix(), "--dest", language.as_posix()], cwd=home, env=env)
    # Minimal CI TeX installs may have enabled but absent unrelated language files.
    # Stubs exist ONLY in this disposable test tree, never runtime/distribution.
    for line in language.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0].startswith(("%", "=")):
            continue
        result = subprocess.run(["kpsewhich", fields[1]], env=env, capture_output=True)
        if result.returncode:
            name = Path(fields[1])
            if name.name != fields[1]:
                raise ValueError("unexpected language loader filename")
            write(home / "tex/generic/azhyphen-test-stubs" / name, b"% Test-only unrelated loader stub\n")


def compile_tex(source: bytes, work: Path, engine: str, env: dict[str, str],
                passes: int = 1, success: bool = True) -> str:
    work.mkdir(parents=True, exist_ok=True)
    write(work / "document.tex", source)
    output = ""
    for _ in range(passes):
        try:
            output = run([engine, "-no-shell-escape", "-interaction=nonstopmode",
                          "-halt-on-error", "-file-line-error", "document.tex"], work, env)
        except ValueError as exc:
            if success:
                raise
            return str(exc)
    if not success:
        raise ValueError("expected compilation failure: " + engine)
    # Native Windows TeX diagnostics mix UTF-8, legacy single-byte glyphs and
    # escaped Unicode notation. Preserve them all when checking native breaks.
    log = (work / "document.log").read_bytes().decode("utf-8", errors="surrogateescape")
    log = "".join(chr(ord(ch) - 0xDC00) if 0xDC80 <= ord(ch) <= 0xDCFF else ch for ch in log)
    return re.sub(r"\\u([0-9a-fA-F]{4})", lambda m: chr(int(m[1], 16)), log)


def runtime_test(runtime: Path = ROOT, fixture: bool = False, source: bytes | None = None) -> None:
    with tempfile.TemporaryDirectory(prefix="azhyphen-runtime.") as temporary:
        work = Path(temporary)
        env = tex_environment(work)
        home = work / "home"
        package = home / "tex/latex/azhyphen"
        package.mkdir(parents=True)
        for name in RUNTIME:
            write(package / name, text_bytes(runtime / name))
        if fixture:
            raw = text_bytes(ROOT / "tests/fixtures/patterns.txt")
            write(package / "azhyphen.pat.txt", raw)
            write(package / "azhyphen-xetex.tex", loader(raw))
        prepare_test_languages(home, env)
        registration(home, env, True)
        registration(home, env, True)
        source = source if source is not None else text_bytes(ROOT / "tests/runtime.tex")
        model = patterns(text_bytes(package / "azhyphen.pat.txt"))
        expected = ["".join(("-" if i in predict(word, model) else "") + ch
                            for i, ch in enumerate(word)) for word in TEST_WORDS]
        for engine in ("lualatex", "xelatex"):
            log = compile_tex(source, work / engine, engine, env)
            for hyphenated in expected:
                if hyphenated not in log:
                    detail = "\n".join(line for line in log.splitlines() if any(word[:2] in line for word in TEST_WORDS))
                    raise ValueError(f"{engine}: native hyphenation did not match {hyphenated}\n{detail}")
            if fixture and "fo-toelektrik" not in log:
                raise ValueError(engine + ": fixture not active")
        registration(home, env, False)
        registration(home, env, False)
        unrelated = (r"\documentclass{article}\begin{document}\makeatletter"
                     r"\@ifundefined{l@azhyphen-unrelated}{\errmessage{Unrelated language lost}}{}"
                     r"\end{document}").encode()
        compile_tex(unrelated, work / "unrelated", "xelatex", env)
        missing = compile_tex(source, work / "unregistered", "xelatex", env, success=False)
        if "not registered" not in re.sub(r"\s+", " ", missing):
            raise ValueError("XeLaTeX registration failure diagnostic missing:\n" + missing)
        path = package / "azhyphen.pat.txt"
        path.unlink()
        missing = compile_tex(source, work / "missing", "lualatex", env, success=False)
        if "required pattern file" not in missing:
            raise ValueError("LuaLaTeX missing-pattern diagnostic missing")
        write(path, b"\\patterns{invalid}")
        invalid = compile_tex(source, work / "invalid", "lualatex", env, success=False)
        if "invalid pattern token" not in invalid:
            raise ValueError("LuaLaTeX invalid-pattern diagnostic missing")
        if shutil.which("pdflatex"):
            unsupported = compile_tex(b"\\documentclass{article}\\usepackage{azhyphen}"
                                      b"\\begin{document}Test\\end{document}",
                                      work / "unsupported", "pdflatex", env, success=False)
            if "LuaLaTeX or XeLaTeX is required" not in unsupported:
                raise ValueError("unsupported-engine diagnostic missing")
    print("Both engines: " + ("isolated fixtures" if fixture else "real patterns") +
          ", Azerbaijani mappings, native breaks and reversible registration passed")


def epoch() -> int:
    timestamp = int(os.environ.get("SOURCE_DATE_EPOCH", "946684800"))
    if not 315532800 <= timestamp <= 4354819199:
        raise ValueError("SOURCE_DATE_EPOCH must fit ZIP dates (1980–2107)")
    return timestamp


def archive_bytes() -> dict[str, bytes]:
    return {name: text_bytes(ROOT / name) for name in SOURCES}


def archive_write(target: Path, files: dict[str, bytes], timestamp: int) -> None:
    date = datetime.fromtimestamp(timestamp, timezone.utc).timetuple()[:6]
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            privacy(name, raw)
            entry = zipfile.ZipInfo("azhyphen/" + name, date_time=date)
            entry.create_system = 3
            entry.external_attr = 0o100644 << 16
            archive.writestr(entry, raw)
    with zipfile.ZipFile(target) as archive:
        if (archive.testzip() or len(archive.namelist()) != len(files) or
            set(archive.namelist()) != {"azhyphen/" + name for name in files} or
            any(archive.read("azhyphen/" + name) != raw for name, raw in files.items())):
            raise ValueError("archive inspection failed")


def ctan() -> Path:
    check()
    timestamp = epoch()
    build = ROOT / "build/ctan"
    if build.resolve() != build or build.is_symlink():
        raise ValueError("refusing redirected CTAN build directory")
    build.mkdir(parents=True, exist_ok=True)
    files = archive_bytes()
    with tempfile.TemporaryDirectory(prefix="stage.", dir=build) as temporary:
        work = Path(temporary)
        env = dict(os.environ, SOURCE_DATE_EPOCH=str(timestamp), FORCE_SOURCE_DATE="1", TZ="UTC",
                   TEXINPUTS="." + os.pathsep, LUAINPUTS="." + os.pathsep)
        write(work / "azhyphen-version.tex", files["azhyphen-version.tex"])
        log = compile_tex(files["doc/azhyphen-doc.tex"], work, "lualatex", env, passes=2)
        if any(token in log for token in ("Missing character:", "undefined references", "Overfull \\hbox")):
            raise ValueError("manual contains missing glyphs, unresolved references or overfull lines")
        files["doc/azhyphen-doc.pdf"] = (work / "document.pdf").read_bytes()
        if not files["doc/azhyphen-doc.pdf"].startswith(b"%PDF-"):
            raise ValueError("manual PDF missing")
        stage = work / "azhyphen"
        for name, raw in files.items():
            write(stage / name, raw)
        # Keep repository tests out of CTAN; its generator can verify staged
        # native breakpoints with this minimal document in an extracted archive.
        smoke = (r"\documentclass{article}\usepackage{fontspec}\setmainfont{cmunrm.otf}"
                 r"\usepackage{azhyphen}\begin{document}" + "\n" +
                 "\n".join(r"\showhyphens{" + word + "}" for word in TEST_WORDS) +
                 r"\end{document}")
        runtime_test(stage, source=smoke.encode("utf-8"))
        candidate = work / "archive.zip"
        archive_write(candidate, files, timestamp)
        destination = ROOT / "dist"
        if destination.resolve() != destination or destination.is_symlink():
            raise ValueError("refusing redirected distribution directory")
        destination.mkdir(exist_ok=True)
        target = destination / f"azhyphen-{version()}.zip"
        os.replace(candidate, target)
        write(ROOT / "build/azhyphen-doc.pdf", files["doc/azhyphen-doc.pdf"])
    print(f"{target.relative_to(ROOT)}\nSHA-256: {hashlib.sha256(target.read_bytes()).hexdigest()}")
    return target


def clean() -> None:
    for name in ("build", "dist"):
        path = ROOT / name
        if path.resolve() != path or path.is_symlink():
            raise ValueError("refusing redirected cleanup directory: " + name)
        if path.exists():
            shutil.rmtree(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("update", "test", "check", "stats", "ctan", "clean", "install", "uninstall"))
    parser.add_argument("--texmfhome", type=Path, help="user TeX tree for install/uninstall")
    args = parser.parse_args()
    try:
        if args.action == "update":
            update()
        elif args.action == "check":
            check()
        elif args.action == "test":
            if not (ROOT / "tests/test_azhyphen.py").is_file():
                raise ValueError("tests are repository-only; run make test in a GitHub source checkout")
            check()
            print(run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]))
            runtime_test(fixture=True)
            runtime_test()
        elif args.action == "stats":
            train, evaluation = datasets()
            for name, value in statistics(train, evaluation, text_bytes(ROOT / "azhyphen.pat.txt")).items():
                print(f"{name}: {value:.2f}" if isinstance(value, float) else f"{name}: {value}")
        elif args.action == "ctan":
            ctan()
        elif args.action == "clean":
            clean()
        else:
            installation(args.action == "install", args.texmfhome)
    except (OSError, UnicodeError, ValueError, subprocess.TimeoutExpired, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
