#!/usr/bin/env python3
"""Regression tests for public statistics and README block generation."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "update_readme_stats.py"
START = "<!-- AZHYPHEN-STATS:START -->"
END = "<!-- AZHYPHEN-STATS:END -->"
VALID_STATS = {
    "training_count": 12,
    "evaluation_count": 3,
    "pattern_count": 2,
    "exact_accuracy": 66.67,
    "precision": 80.0,
    "recall": 75.0,
    "f1": 77.42,
    "correct_breakpoints": 6,
    "wrong_breakpoints": 2,
    "missed_breakpoints": 2,
}


def run(
    stats: Path,
    patterns: Path,
    readme: Path,
    output: Path,
    *,
    success: bool,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--stats",
            str(stats),
            "--patterns",
            str(patterns),
            "--readme",
            str(readme),
            "--output-stats",
            str(output),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert (result.returncode == 0) is success, result.stderr
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="azhyphen-stats-test.") as directory:
        temporary = Path(directory)
        stats = temporary / "source.json"
        patterns = temporary / "patterns.pat"
        readme = temporary / "README.md"
        output = temporary / "model-stats.json"
        stats.write_text(json.dumps(VALID_STATS), encoding="utf-8")
        patterns.write_text("a1b\nc2d\n", encoding="utf-8")
        prefix = b"# Test\n\nHand-maintained before.\n\n"
        suffix = b"\nHand-maintained after.\n"
        readme.write_bytes(prefix + START.encode() + b"\nstale\n" + END.encode() + suffix)

        first = run(stats, patterns, readme, output, success=True)
        assert "README statistics: updated" in first.stdout
        generated = readme.read_bytes()
        assert generated.startswith(prefix)
        assert generated.endswith(suffix)
        assert b"| Training annotations | 12 |" in generated
        assert b"| Exact word accuracy | 66.7% |" in generated
        first_stats = output.read_bytes()
        assert first_stats.endswith(b"\n")

        fixed_time = 1_700_000_000_000_000_000
        os.utime(readme, ns=(fixed_time, fixed_time))
        os.utime(output, ns=(fixed_time, fixed_time))
        second = run(stats, patterns, readme, output, success=True)
        assert "README statistics: already up to date" in second.stdout
        assert readme.stat().st_mtime_ns == fixed_time
        assert output.stat().st_mtime_ns == fixed_time
        assert readme.read_bytes() == generated
        assert output.read_bytes() == first_stats

        malformed = temporary / "malformed.json"
        malformed.write_text("{", encoding="utf-8")
        run(malformed, patterns, readme, output, success=False)

        missing = temporary / "missing.json"
        incomplete = dict(VALID_STATS)
        incomplete.pop("f1")
        missing.write_text(json.dumps(incomplete), encoding="utf-8")
        run(missing, patterns, readme, output, success=False)

        mismatch = temporary / "mismatch.json"
        wrong_count = dict(VALID_STATS)
        wrong_count["pattern_count"] = 99
        mismatch.write_text(json.dumps(wrong_count), encoding="utf-8")
        result = run(mismatch, patterns, readme, output, success=False)
        assert "does not match pattern data" in result.stderr

        missing_markers = temporary / "missing-markers.md"
        missing_markers.write_text("# No markers\n", encoding="utf-8")
        run(stats, patterns, missing_markers, output, success=False)

        duplicate = temporary / "duplicate.md"
        duplicate.write_text(
            f"{START}\n{END}\n{START}\n{END}\n", encoding="utf-8"
        )
        run(stats, patterns, duplicate, output, success=False)

    print("README statistics tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
