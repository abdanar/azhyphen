#!/usr/bin/env python3
"""Checks for public-repository metadata and accidental local disclosure."""

from __future__ import annotations

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def repository_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [ROOT / name for name in result.stdout.splitlines()]


def main() -> int:
    forbidden = (
        "BEGIN " + "PRIVATE KEY",
    )
    private_path = re.compile(r"(?<![A-Za-z0-9_$])/(?:home|Users)/[A-Za-z0-9_.-]+/")
    files = repository_files()
    assert ROOT / "local.mk" not in files, "developer-local local.mk is tracked"
    for path in files:
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for value in forbidden:
            assert value not in text, f"private value appears in {path.relative_to(ROOT)}"
        assert not private_path.search(text), f"private path appears in {path.relative_to(ROOT)}"

    workflow = (ROOT / ".github" / "workflows" / "ci.yml").read_text(
        encoding="utf-8"
    )
    for required in ("push:", "pull_request:", "make test", "make check"):
        assert required in workflow, f"CI workflow is missing {required}"
    for forbidden_ci in ("localization", "local.mk", "secrets."):
        assert forbidden_ci not in workflow, f"CI workflow contains {forbidden_ci}"
    for action in re.findall(r"uses:\s+(\S+)", workflow):
        assert re.fullmatch(r"[^@]+@[0-9a-f]{40}", action), f"mutable action: {action}"
    assert "persist-credentials: false" in workflow
    assert "contents: read" in workflow

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("AZHYPHEN-BADGES:START") == 1
    assert readme.count("AZHYPHEN-BADGES:END") == 1
    assert readme.count("img.shields.io") == 5

    print("public repository checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
