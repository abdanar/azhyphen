#!/usr/bin/env python3
"""Test registration ownership and rollback without modifying a TeX installation."""

from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import xetex_language as registration


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="azhyphen-registration-test.") as directory:
        home = Path(directory)
        package = home / "tex/latex/azhyphen"
        config = home / "tex/generic/config"
        package.mkdir(parents=True)
        config.mkdir(parents=True)
        (package / registration.LOADER_NAME).write_text("% test loader\n")
        language_dat = config / "language.dat"
        original = b"% custom user registration\nenglish hyphen.tex\ncustom zerohyph.tex\n"
        language_dat.write_bytes(original)
        language_dat.chmod(0o640)

        def snapshot():
            return {p.relative_to(home): (p.read_bytes(), p.stat().st_mode)
                    for p in home.rglob("*") if p.is_file()}

        before = snapshot()
        with patch.object(registration, "rebuild_xelatex", side_effect=registration.RegistrationError("injected")):
            try:
                registration.install(home)
            except registration.RegistrationError:
                pass
            else:
                raise AssertionError("format failure did not propagate")
        assert snapshot() == before, "failed install changed configuration"

        with patch.object(registration, "rebuild_xelatex"):
            registration.install(home)
            registration.install(home)
            assert language_dat.read_bytes().startswith(original)
            assert language_dat.read_text().count("azhyphen azhyphen-xetex.tex") == 1
            # An edit followed by reinstall must also survive uninstall.
            language_dat.write_bytes(language_dat.read_bytes() + b"later zerohyph.tex\n")
            registration.install(home)
        installed = snapshot()
        with patch.object(registration, "rebuild_xelatex", side_effect=registration.RegistrationError("injected")):
            try:
                registration.uninstall(home)
            except registration.RegistrationError:
                pass
            else:
                raise AssertionError("uninstall format failure did not propagate")
        assert snapshot() == installed, "failed uninstall changed configuration"
        with patch.object(registration, "rebuild_xelatex"):
            registration.uninstall(home)
            registration.uninstall(home)
        assert language_dat.read_bytes() == original + b"later zerohyph.tex\n"
        assert language_dat.stat().st_mode & 0o777 == 0o640
        assert not list(home.rglob("*.tmp"))

        # A registration owned by someone else must never be deleted.
        language_dat.write_text("azhyphen other-loader.tex\n")
        before = snapshot()
        with patch.object(registration, "rebuild_xelatex"):
            try:
                registration.install(home)
            except registration.RegistrationError:
                pass
            else:
                raise AssertionError("conflicting language name was accepted")
            registration.uninstall(home)
        assert snapshot() == before

    print("XeTeX registration ownership and rollback tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
