#!/usr/bin/env python3
"""Manage azhyphen's reversible user-level XeTeX language registration."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile


LANGUAGE_NAME = "azhyphen"
LOADER_NAME = "azhyphen-xetex.tex"
BEGIN_MARKER = "% BEGIN azhyphen managed registration"
END_MARKER = "% END azhyphen managed registration"
REGISTRATION_BLOCK = (
    f"{BEGIN_MARKER}\n{LANGUAGE_NAME} {LOADER_NAME}\n{END_MARKER}\n"
)


class RegistrationError(RuntimeError):
    """Raised for a failed or unsafe registration operation."""


def atomic_write(path: Path, contents: bytes, mode: int | None = None) -> None:
    if mode is None:
        mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(contents)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def remove_owned_registration(text: str) -> tuple[str, bool]:
    block_pattern = re.compile(
        rf"(?m)^{re.escape(BEGIN_MARKER)}\r?\n.*?"
        rf"^{re.escape(END_MARKER)}(?:\r?\n)?",
        re.DOTALL,
    )
    updated, block_count = block_pattern.subn("", text)
    line_pattern = re.compile(
        rf"(?m)^[ \t]*{re.escape(LANGUAGE_NAME)}[ \t]+"
        rf"{re.escape(LOADER_NAME)}[ \t]*(?:%[^\r\n]*)?(?:\r?\n|$)"
    )
    updated, line_count = line_pattern.subn("", updated)
    return updated, bool(block_count or line_count)


def update_local_config(path: Path, *, install: bool) -> tuple[bool, bool]:
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    without_owned, had_owned = remove_owned_registration(original)
    updated = without_owned
    if install:
        if updated and not updated.endswith(("\n", "\r")):
            updated += "\n"
        updated += REGISTRATION_BLOCK
    changed = updated != original
    if changed:
        # This is a shared user configuration file.  Keep it in place even
        # when removing our block leaves it empty; never delete it wholesale.
        atomic_write(path, updated.encode("utf-8"))
    has_unrelated_entries = any(
        line.strip() and not line.lstrip().startswith("%")
        for line in without_owned.splitlines()
    )
    return changed or had_owned, has_unrelated_entries


def run_checked(command: list[str], environment: dict[str, str]) -> None:
    try:
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
    except OSError as exc:
        raise RegistrationError(f"cannot run {command[0]}: {exc}") from exc
    if result.returncode != 0:
        detail = "\n".join(
            output.strip() for output in (result.stdout, result.stderr) if output.strip()
        )
        raise RegistrationError(
            f"{' '.join(command[:2])} failed"
            + (f": {detail}" if detail else "")
        )


def generate_language_dat(
    local_config: Path, language_dat: Path, environment: dict[str, str]
) -> None:
    tlmgr = shutil.which("tlmgr")
    if not tlmgr:
        raise RegistrationError("tlmgr is required to generate language.dat")
    run_checked(
        [
            tlmgr,
            "generate",
            "language.dat",
            "--localcfg",
            str(local_config),
            "--dest",
            str(language_dat),
        ],
        environment,
    )


def rebuild_xelatex(environment: dict[str, str]) -> None:
    fmtutil = shutil.which("fmtutil-user")
    if not fmtutil:
        raise RegistrationError("fmtutil-user is required to rebuild XeLaTeX")
    run_checked([fmtutil, "--byfmt", "xelatex"], environment)


@contextmanager
def preserve_on_failure(paths: tuple[Path, ...]):
    """Restore configuration and ownership records if registration fails."""
    previous = {
        path: (path.read_bytes(), stat.S_IMODE(path.stat().st_mode))
        if path.exists() else None
        for path in paths
    }
    try:
        yield
    except BaseException:
        for path, saved in previous.items():
            if saved is None:
                path.unlink(missing_ok=True)
            else:
                atomic_write(path, saved[0], saved[1])
        raise


def registered_text(text: str) -> str:
    """Append our registration while retaining all unrelated lines verbatim."""
    text, _ = remove_owned_registration(text)
    if any(line.split("%", 1)[0].split()[:1] == [LANGUAGE_NAME]
           for line in text.splitlines()):
        raise RegistrationError("language name azhyphen is already registered to another loader")
    return text + ("\n" if text and not text.endswith("\n") else "") + REGISTRATION_BLOCK


def install(texmfhome: Path) -> None:
    package_directory = texmfhome / "tex" / "latex" / "azhyphen"
    loader = package_directory / LOADER_NAME
    if not loader.is_file():
        raise RegistrationError(f"installed XeTeX loader is missing: {loader}")

    config_directory = texmfhome / "tex" / "generic" / "config"
    local_config = config_directory / "language-local.dat"
    language_dat = config_directory / "language.dat"
    state = package_directory / ".azhyphen-xetex-state.json"
    backup = package_directory / ".azhyphen-language.dat.backup"

    environment = dict(os.environ)
    environment["TEXMFHOME"] = str(texmfhome)
    with preserve_on_failure((local_config, language_dat, state, backup)):
        if state.exists():
            state_data = json.loads(state.read_text(encoding="utf-8"))
            if language_dat.exists() and hashlib.sha256(
                language_dat.read_bytes()
            ).hexdigest() != state_data.get("installed_sha256"):
                state_data["preserve_language_dat"] = True
        else:
            preexisting = language_dat.is_file()
            state_data = {"language_dat_preexisting": preexisting}
            if preexisting:
                atomic_write(backup, language_dat.read_bytes())
        # Check for a conflicting name before modifying shared configuration.
        if local_config.exists():
            registered_text(local_config.read_text(encoding="utf-8"))
        update_local_config(local_config, install=True)
        if language_dat.exists():
            atomic_write(language_dat, registered_text(
                language_dat.read_text(encoding="utf-8")
            ).encode("utf-8"))
        else:
            generate_language_dat(local_config, language_dat, environment)
        state_data["installed_sha256"] = hashlib.sha256(language_dat.read_bytes()).hexdigest()
        atomic_write(state, (json.dumps(state_data) + "\n").encode("utf-8"), mode=0o600)
        rebuild_xelatex(environment)
    print("XeLaTeX language registration installed")


def uninstall(texmfhome: Path) -> None:
    package_directory = texmfhome / "tex" / "latex" / "azhyphen"
    config_directory = texmfhome / "tex" / "generic" / "config"
    local_config = config_directory / "language-local.dat"
    language_dat = config_directory / "language.dat"
    state = package_directory / ".azhyphen-xetex-state.json"
    backup = package_directory / ".azhyphen-language.dat.backup"

    # No ownership record means we must not remove someone else's registration.
    if not state.exists():
        print("XeLaTeX language registration already absent")
        return

    environment = dict(os.environ)
    environment["TEXMFHOME"] = str(texmfhome)
    with preserve_on_failure((local_config, language_dat, state, backup)):
        state_data = json.loads(state.read_text(encoding="utf-8"))
        _, has_unrelated_entries = update_local_config(local_config, install=False)
        if language_dat.exists():
            raw = language_dat.read_bytes()
            unchanged = hashlib.sha256(raw).hexdigest() == state_data.get("installed_sha256")
            if unchanged and not has_unrelated_entries and not state_data.get("preserve_language_dat"):
                if state_data.get("language_dat_preexisting"):
                    if not backup.is_file():
                        raise RegistrationError("saved pre-install language.dat is missing")
                    atomic_write(language_dat, backup.read_bytes())
                else:
                    language_dat.unlink()
            else:
                # Preserve edits made by other tools since installation, also
                # for older state files without an installed checksum.
                text, _ = remove_owned_registration(raw.decode("utf-8"))
                atomic_write(language_dat, text.encode("utf-8"))
        rebuild_xelatex(environment)
        state.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)
    print("XeLaTeX language registration removed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("install", "uninstall"))
    parser.add_argument("--texmfhome", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    texmfhome = args.texmfhome.expanduser().resolve()
    if texmfhome == Path(texmfhome.anchor):
        print("error: refusing to use a filesystem root as TEXMFHOME", file=sys.stderr)
        return 1
    try:
        if args.action == "install":
            install(texmfhome)
        else:
            uninstall(texmfhome)
    except (OSError, RegistrationError, UnicodeError, ValueError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
