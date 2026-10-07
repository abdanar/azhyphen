#!/usr/bin/env python3
"""Regression tests for VERSION-derived public and package metadata."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update_version.py"
START = "<!-- AZHYPHEN-BADGES:START -->"
END = "<!-- AZHYPHEN-BADGES:END -->"


def run(root: Path, *arguments: str, success: bool) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is success, result.stderr
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="azhyphen-version-test.") as directory:
        root = Path(directory)
        package = root / "tex" / "latex" / "azhyphen"
        package.mkdir(parents=True)
        (root / "VERSION").write_text("0.1.0\n", encoding="utf-8")
        prefix = b"# Test\n\n"
        suffix = b"\nHand-maintained content.\n"
        readme = root / "README.md"
        readme.write_bytes(prefix + START.encode() + b"\nstale\n" + END.encode() + suffix)

        first = run(root, success=True)
        assert "updated version metadata" in first.stdout
        rendered = readme.read_bytes()
        assert rendered.startswith(prefix)
        assert rendered.endswith(suffix)
        assert b"version-0.1.0--development" in rendered
        assert b'version: "0.1.0"' in (root / "CITATION.cff").read_bytes()
        assert b"azhyphenversion{0.1.0}" in (
            package / "azhyphen-version.tex"
        ).read_bytes()
        run(root, "--check", success=True)

        fixed_time = 1_700_000_000_000_000_000
        generated = (
            readme,
            root / "CITATION.cff",
            package / "azhyphen-version.tex",
        )
        for path in generated:
            os.utime(path, ns=(fixed_time, fixed_time))
        run(root, success=True)
        assert all(path.stat().st_mtime_ns == fixed_time for path in generated)

        (root / "VERSION").write_text("0.2.0\n", encoding="utf-8")
        stale = run(root, "--check", success=False)
        assert "stale" in stale.stderr

        (root / "VERSION").write_text("version 1\n", encoding="utf-8")
        malformed = run(root, "--check", success=False)
        assert "Semantic Versioning" in malformed.stderr

    print("version metadata tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
