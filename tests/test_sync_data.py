#!/usr/bin/env python3
"""Regression tests for coordinated pattern/statistics synchronization."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


ROOT = Path(__file__).resolve().parents[1]
START = "<!-- AZHYPHEN-STATS:START -->"
END = "<!-- AZHYPHEN-STATS:END -->"


def stats_for(pattern_count: int) -> dict[str, int | float]:
    return {
        "training_count": 12,
        "evaluation_count": 3,
        "pattern_count": pattern_count,
        "exact_accuracy": 66.67,
        "precision": 80.0,
        "recall": 75.0,
        "f1": 77.42,
        "correct_breakpoints": 6,
        "wrong_breakpoints": 2,
        "missed_breakpoints": 2,
    }


def run_sync(
    script: Path,
    patterns: Path,
    stats: Path,
    *,
    report: Path | None = None,
    success: bool,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(script),
        "--patterns",
        str(patterns),
        "--stats",
        str(stats),
    ]
    if report is not None:
        command.extend(("--report", str(report)))
    result = subprocess.run(command, check=False, capture_output=True, text=True)
    assert (result.returncode == 0) is success, (
        f"unexpected result {result.returncode}\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    return result


def output_paths(repository: Path) -> tuple[Path, ...]:
    package = repository / "tex" / "latex" / "azhyphen"
    return (
        package / "azhyphen.pat.txt",
        package / "azhyphen-data.json",
        package / "azhyphen-xetex.tex",
        repository / "docs" / "model-stats.json",
        repository / "README.md",
    )


def assert_no_temporaries(repository: Path) -> None:
    leftovers = [path for path in repository.rglob("*") if path.name.endswith(".tmp")]
    assert not leftovers, f"temporary files remain: {leftovers}"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="azhyphen-sync-data-test.") as directory:
        temporary = Path(directory)
        repository = temporary / "repository"
        scripts = repository / "scripts"
        scripts.mkdir(parents=True)
        for name in ("sync_data.py", "import_patterns.py", "update_readme_stats.py"):
            shutil.copy2(ROOT / "scripts" / name, scripts / name)

        package = repository / "tex" / "latex" / "azhyphen"
        package.mkdir(parents=True)
        (package / "azhyphen.hyp.txt").write_text("fo-to\n", encoding="utf-8")
        (repository / "README.md").write_text(
            f"# Test\n\nBefore.\n\n{START}\nstale\n{END}\n\nAfter.\n",
            encoding="utf-8",
        )

        patterns = temporary / "patterns.pat"
        stats = temporary / "stats.json"
        report_path = temporary / "sync-report.json"
        patterns.write_text("a1b\nc2d\n", encoding="utf-8")
        stats.write_text(json.dumps(stats_for(2)), encoding="utf-8")

        first = run_sync(
            scripts / "sync_data.py",
            patterns,
            stats,
            report=report_path,
            success=True,
        )
        assert "Status:         updated" in first.stdout
        first_report = json.loads(report_path.read_text(encoding="utf-8"))
        assert first_report["new_patterns"] == 2
        assert first_report["stats_status"] == "updated"
        assert first_report["readme_status"] == "updated"
        assert first_report["result"] == "success"

        production_patterns = (
            ROOT / "tests" / "fixtures" / "sample-patterns.txt"
        ).read_bytes()
        patterns.write_bytes(production_patterns)
        stats.write_text(json.dumps(stats_for(5)), encoding="utf-8")
        updated = run_sync(
            scripts / "sync_data.py",
            patterns,
            stats,
            report=report_path,
            success=True,
        )
        assert "Old patterns:   2" in updated.stdout
        assert "New patterns:   5" in updated.stdout
        paths = output_paths(repository)
        pattern_path, metadata_path, loader_path, public_stats_path, readme_path = paths
        assert pattern_path.read_bytes() == production_patterns
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert metadata["pattern_count"] == 5
        assert metadata["sha256"] == hashlib.sha256(production_patterns).hexdigest()
        assert metadata["xetex_loader_sha256"] == hashlib.sha256(
            loader_path.read_bytes()
        ).hexdigest()
        assert json.loads(public_stats_path.read_text(encoding="utf-8"))[
            "pattern_count"
        ] == 5
        readme = readme_path.read_text(encoding="utf-8")
        assert "Before." in readme and "After." in readme
        assert "| Patterns | 5 |" in readme

        fixed_time = 1_700_000_000_000_000_000
        for path in paths:
            os.utime(path, ns=(fixed_time, fixed_time))
        unchanged = run_sync(
            scripts / "sync_data.py",
            patterns,
            stats,
            report=report_path,
            success=True,
        )
        assert "Status:         already up to date" in unchanged.stdout
        assert all(path.stat().st_mtime_ns == fixed_time for path in paths)
        unchanged_report = json.loads(report_path.read_text(encoding="utf-8"))
        for key in (
            "status",
            "metadata_status",
            "xetex_loader_status",
            "stats_status",
            "readme_status",
        ):
            assert unchanged_report[key] == "already up to date"

        stable = {path: path.read_bytes() for path in paths}
        invalid_patterns = temporary / "invalid.pat"
        invalid_patterns.write_text("not-a-pattern\n", encoding="utf-8")
        run_sync(
            scripts / "sync_data.py",
            invalid_patterns,
            stats,
            success=False,
        )
        assert all(path.read_bytes() == stable[path] for path in paths)

        invalid_stats = temporary / "invalid.json"
        invalid_stats.write_text("{", encoding="utf-8")
        run_sync(
            scripts / "sync_data.py",
            patterns,
            invalid_stats,
            success=False,
        )
        assert all(path.read_bytes() == stable[path] for path in paths)

        mismatched_stats = temporary / "mismatched.json"
        mismatched_stats.write_text(json.dumps(stats_for(99)), encoding="utf-8")
        mismatch = run_sync(
            scripts / "sync_data.py",
            patterns,
            mismatched_stats,
            success=False,
        )
        assert "does not match pattern data" in mismatch.stderr
        assert all(path.read_bytes() == stable[path] for path in paths)
        assert_no_temporaries(repository)

        sys.path.insert(0, str(scripts))
        import sync_data  # type: ignore[import-not-found]

        rollback_patterns = temporary / "rollback.pat"
        rollback_patterns.write_bytes(production_patterns + b"az1hy\n")
        rollback_stats = temporary / "rollback.json"
        rollback_stats.write_text(json.dumps(stats_for(6)), encoding="utf-8")
        real_replace = sync_data.replace_file
        replacements = 0

        def fail_replace(source: Path, destination: Path) -> None:
            nonlocal replacements
            replacements += 1
            if replacements == failure_at:
                raise OSError("injected replacement failure")
            real_replace(source, destination)

        sync_data.replace_file = fail_replace
        for failure_at in range(1, 6):
            replacements = 0
            try:
                sync_data.synchronize(rollback_patterns, rollback_stats)
            except OSError as exc:
                assert "injected replacement failure" in str(exc)
            else:
                raise AssertionError("injected synchronization failure did not propagate")
            assert all(path.read_bytes() == stable[path] for path in paths)
            assert_no_temporaries(repository)

    print("coordinated synchronization tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
