#!/usr/bin/env python3
"""Regression tests for atomic pattern synchronization and metadata."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def run(
    script: Path, source: Path, *, expect_success: bool
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(script), str(source)],
        check=False,
        capture_output=True,
        text=True,
    )
    if (result.returncode == 0) != expect_success:
        raise AssertionError(
            f"unexpected synchronizer result ({result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="azhyphen-sync-test.") as directory:
        temporary = Path(directory)
        repository = temporary / "repository"
        scripts = repository / "scripts"
        scripts.mkdir(parents=True)
        script = scripts / "import_patterns.py"
        shutil.copy2(ROOT / "scripts" / "import_patterns.py", script)

        source = temporary / "patterns.txt"
        original = (ROOT / "tests" / "fixtures" / "sample-patterns.txt").read_bytes()
        source.write_bytes(original)

        first = run(script, source, expect_success=True)
        assert "Status:         updated" in first.stdout
        package = repository / "tex" / "latex" / "azhyphen"
        target = package / "azhyphen.pat.txt"
        metadata_path = package / "azhyphen-data.json"
        loader_path = package / "azhyphen-xetex.tex"
        assert target.read_bytes() == original
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["pattern_count"] == 5
        assert metadata["sha256"] == hashlib.sha256(original).hexdigest()
        assert metadata["xetex_loader_sha256"] == hashlib.sha256(
            loader_path.read_bytes()
        ).hexdigest()
        loader_text = loader_path.read_text(encoding="utf-8")
        for pattern in ("fo1to", "el1lər", "ad1dım", "vi1deo", "ət1ür"):
            assert pattern in loader_text
        assert "TEST ONLY" not in loader_text
        target_mtime = target.stat().st_mtime_ns
        metadata_mtime = metadata_path.stat().st_mtime_ns
        loader_mtime = loader_path.stat().st_mtime_ns

        second = run(script, source, expect_success=True)
        assert "Status:         already up to date" in second.stdout
        assert target.stat().st_mtime_ns == target_mtime
        assert metadata_path.stat().st_mtime_ns == metadata_mtime
        assert loader_path.stat().st_mtime_ns == loader_mtime

        metadata_path.write_text("{}\n", encoding="utf-8")
        metadata_repair = run(script, source, expect_success=True)
        assert "Status:         already up to date" in metadata_repair.stdout
        assert "Metadata:       updated" in metadata_repair.stdout
        assert target.stat().st_mtime_ns == target_mtime
        repaired_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert repaired_metadata["sha256"] == hashlib.sha256(original).hexdigest()

        changed = original + b"az1hy\n"
        source.write_bytes(changed)
        third = run(script, source, expect_success=True)
        assert "Old patterns:   5" in third.stdout
        assert "New patterns:   6" in third.stdout
        assert target.read_bytes() == changed
        stable_target = target.read_bytes()
        stable_metadata = metadata_path.read_bytes()
        stable_loader = loader_path.read_bytes()

        for invalid in (b"", b"\\patterns{a1b}\n", b"not-a-pattern\n", b"\xff"):
            source.write_bytes(invalid)
            run(script, source, expect_success=False)
            assert target.read_bytes() == stable_target
            assert metadata_path.read_bytes() == stable_metadata
            assert loader_path.read_bytes() == stable_loader

        assert not list(package.glob("*.tmp"))
        assert not list(package.glob(".*.tmp"))

    print("pattern synchronization tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
