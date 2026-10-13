#!/usr/bin/env python3
"""Release guard regressions without requiring a TeX installation."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_ctan as ctan


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="azhyphen-ctan-unit.")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.stage = self.work / "azhyphen"
        self.stage.mkdir()
        for name in ctan.SOURCES:
            (self.stage / name).write_bytes(ctan.source_bytes(name))
        # Minimal unit-test PDF sentinel; never used by the production build.
        (self.stage / "azhyphen-doc.pdf").write_bytes(b"%PDF-1.5\n%%EOF\n")

    def test_archive_is_deterministic_and_allowlisted(self):
        ctan.validate_stage(self.stage)
        first, second = self.work / "first.zip", self.work / "second.zip"
        ctan.write_archive(self.stage, first, ctan.DEFAULT_EPOCH)
        for path in self.stage.iterdir():
            os.utime(path, (1234567890, 1234567890))
        ctan.write_archive(self.stage, second, ctan.DEFAULT_EPOCH)
        self.assertEqual(hashlib.sha256(first.read_bytes()).digest(),
                         hashlib.sha256(second.read_bytes()).digest())
        ctan.validate_archive(first, self.stage)
        with zipfile.ZipFile(first) as archive:
            self.assertEqual(archive.namelist(), sorted(f"azhyphen/{n}" for n in ctan.EXPECTED))
            for entry in archive.infolist():
                self.assertEqual(entry.date_time, (2000, 1, 1, 0, 0, 0))
                self.assertEqual(entry.external_attr >> 16, 0o100644)

    def test_unexpected_missing_and_changed_staging(self):
        for name in ("manual.log", ".git", "tests", "secret.env"):
            with self.subTest(name=name):
                extra = self.stage / name
                extra.write_text("junk")
                with self.assertRaises(ctan.ReleaseError):
                    ctan.validate_stage(self.stage)
                extra.unlink()
        missing = self.stage / "LICENSE"
        original = missing.read_bytes()
        missing.unlink()
        with self.assertRaises(ctan.ReleaseError):
            ctan.validate_stage(self.stage)
        missing.write_bytes(original + b"tampered")
        with self.assertRaises(ctan.ReleaseError):
            ctan.validate_stage(self.stage)

    def test_archive_traversal_extra_duplicates_and_tampering(self):
        for member in ("../escape", "other/README.md", "azhyphen/.env", "azhyphen/LICENSE"):
            with self.subTest(member=member):
                archive = self.work / "bad.zip"
                ctan.write_archive(self.stage, archive, ctan.DEFAULT_EPOCH)
                with zipfile.ZipFile(archive, "a") as handle:
                    # Avoid duplicate-member warning; duplication itself is intentional.
                    import warnings
                    with warnings.catch_warnings():
                        warnings.simplefilter("ignore", UserWarning)
                        handle.writestr(member, b"tampered")
                with self.assertRaises(ctan.ReleaseError):
                    ctan.validate_archive(archive, self.stage)

    def test_private_paths_and_secrets(self):
        for contents in (b"C:" + b"\\private\\file", b"/" + b"home/person/file",
                         b"/" + b"tmp/build/source", b"\\\\server\\share",
                         b"/" + b"arbitrary/tree/source",
                         b"BEGIN " + b"PRIVATE KEY", b"ghp_" + b"credential"):
            with self.subTest(contents=contents):
                with self.assertRaises(ctan.ReleaseError):
                    ctan.validate_contents("README.md", contents)
        with self.assertRaises(ctan.ReleaseError):
            ctan.validate_contents("azhyphen-doc.pdf", b"not a PDF")
        ctan.validate_contents("README.md", b"https://github.com/abdanar/azhyphen")

    def test_version_tag_and_epoch(self):
        version = ctan.read_version(ROOT)
        ctan.check_tag(version, f"v{version}")
        with self.assertRaises(ctan.ReleaseError):
            ctan.check_tag(version, "v999.0.0")
        for value in ("invalid", "0", "4354819200"):
            with patch.dict(os.environ, SOURCE_DATE_EPOCH=value):
                with self.assertRaises(ctan.ReleaseError):
                    ctan.epoch()

    def test_manual_statistics_are_generated_and_readme_is_archive_aware(self):
        manual = ctan.manual_bytes().decode()
        stats = ctan.load_stats(ROOT / "docs/model-stats.json")
        self.assertIn(f"Patterns & {stats['pattern_count']:,}", manual)
        self.assertIn(r"\input{azhyphen-version.tex}", manual)
        self.assertNotIn("Run make doc to insert", manual)
        readme = ctan.source_bytes("README.md").decode()
        self.assertIn("azhyphen-doc.pdf", readme)
        self.assertNotIn("(docs/PROVENANCE.md)", readme)
        original = (ROOT / "README.md").read_text(encoding="utf-8")
        for marker in ("STATS", "BADGES"):
            start, end = f"<!-- AZHYPHEN-{marker}:START -->", f"<!-- AZHYPHEN-{marker}:END -->"
            self.assertEqual(readme.split(start)[1].split(end)[0],
                             original.split(start)[1].split(end)[0])

    def test_missing_compiler_fails_without_archive_or_source_changes(self):
        with patch.object(ctan, "ROOT", self.work):
            for relative in ctan.SOURCES.values():
                target = self.work / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(ROOT / relative, target)
            (self.work / "docs/model-stats.json").write_bytes((ROOT / "docs/model-stats.json").read_bytes())
            before = {p: p.read_bytes() for p in self.work.rglob("*") if p.is_file()}
            with self.assertRaisesRegex(ctan.ReleaseError, "required tool"):
                ctan.build("azhyphen-nonexistent-compiler", "xelatex", ctan.DEFAULT_EPOCH,
                           ctan.read_version(ROOT))
            self.assertFalse((self.work / "dist").exists())
            for path, data in before.items():
                self.assertEqual(path.read_bytes(), data)

    def test_build_starts_clean_and_refuses_linked_cleanup(self):
        with patch.object(ctan, "ROOT", self.work):
            work = ctan.reset_build("ctan")
            (work / "stale.log").write_text("stale")
            self.assertEqual(list(ctan.reset_build("ctan").iterdir()), [])
            with patch.object(Path, "is_symlink", return_value=True):
                with self.assertRaises(ctan.ReleaseError):
                    ctan.reset_build("ctan")

    def test_manual_rejects_independent_version(self):
        with patch.object(ctan, "ROOT", self.work):
            doc = self.work / "doc/azhyphen-doc.tex"
            doc.parent.mkdir()
            text = (ROOT / "doc/azhyphen-doc.tex").read_text(encoding="utf-8")
            doc.write_text(text.replace(r"\date{Package version \azhyphenversion}",
                                        r"\date{Package version 999.0.0}"), encoding="utf-8")
            with self.assertRaisesRegex(ctan.ReleaseError, "generated package version"):
                ctan.manual_bytes()

    def test_staged_smoke_cache_is_prepared_and_permitted(self):
        engines = []

        def fake_run(command, cwd, env):
            for key in ("TEXMFHOME", "TEXMFVAR", "TEXMFCONFIG", "TEXMFCACHE"):
                self.assertTrue(Path(env[key]).is_dir(), key)
                self.assertNotIn("\\", env[key])
            self.assertTrue(Path(env["TEXMFCACHE"]).is_relative_to(Path(env["TEXMFVAR"])))
            package = Path(env["TEXMFHOME"]) / "tex/latex/azhyphen"
            for name in ctan.RUNTIME:
                self.assertEqual((package / name).read_bytes(), (self.stage / name).read_bytes())
            if command[0] in {"unit-lualatex", "unit-xelatex"}:
                engines.append(command[0])
                (cwd / "smoke.log").write_text("AZHYPHEN-XETEX-LANGUAGE-SELECTED")

        with patch.object(ctan, "run", side_effect=fake_run):
            ctan.smoke(self.stage, "unit-lualatex", "unit-xelatex")
        self.assertEqual(engines, ["unit-lualatex", "unit-xelatex"])

    def test_crlf_checkout_cannot_change_distribution_bytes(self):
        original = ctan.source_bytes("README.md")
        with patch.object(ctan, "ROOT", self.work):
            for name, relative in ctan.SOURCES.items():
                if name == "azhyphen-doc.tex":
                    continue
                destination = self.work / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                canonical = (ROOT / relative).read_bytes().replace(b"\r\n", b"\n")
                crlf = canonical.replace(b"\n", b"\r\n")
                destination.write_bytes(crlf)
                expected = original if name == "README.md" else canonical
                self.assertEqual(ctan.source_bytes(name), expected, name)
                self.assertEqual(destination.read_bytes(), crlf, name)


if __name__ == "__main__":
    unittest.main()
