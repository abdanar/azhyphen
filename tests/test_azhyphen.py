"""Maintenance regression tests; engine integration is run by make test."""

from pathlib import Path
import hashlib
import os
import tempfile
import unittest
from unittest.mock import patch
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import azhyphen as az


class MaintenanceTests(unittest.TestCase):
    def test_dataset_validation(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "words.txt"
            for invalid in ("", "a--bad\n", "a-bad", "a-bad\nabad\n", "secret@example.com\n",
                            "../../private\n", "əl\təl\n", "s\u0327ə-hər\n", "-abad\n", "a-bad\n\n",
                            "# comment\n", "% comment\n", "a-bad \n", "a1bad\n", "\ufeffa-bad\n"):
                path.write_text(invalid, encoding="utf-8")
                with self.assertRaises(ValueError, msg=invalid):
                    az.read_words(path)
            path.write_bytes(b"a\xff-bad\n")
            with self.assertRaises(UnicodeError):
                az.read_words(path)
            path.write_text("Azər-bay-can\nİn-ki-şaf\nI-şıq\nşpat\n", encoding="utf-8")
            self.assertEqual(len(az.read_words(path)), 4)
            self.assertEqual(az.lower("İI"), "iı")

    def test_split_overlap_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            (root / "data/hyphenated.txt").write_text("İn-ki-şaf\n", encoding="utf-8")
            (root / "data/evaluation.txt").write_text("in-ki-şaf\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "overlap"):
                az.datasets(root)

    def test_metrics_and_minima(self):
        raw = "fo1to\nfo2to\n".encode()
        with self.assertRaisesRegex(ValueError, "duplicate"):
            az.patterns(raw)
        raw = "fo1to\na1ba\n".encode()
        model = az.patterns(raw)
        self.assertEqual(az.predict("foto", model), {2})
        self.assertEqual(az.predict("aba", model), set())
        self.assertEqual(az.breaks("a-ba"), {1})  # No minima filtering of annotations.
        metrics = az.statistics(["fo-to"], ["fo-to", "a-ba", "foto"], raw)
        self.assertEqual((metrics['correct'], metrics['wrong'], metrics['missed']), (1, 1, 1))
        self.assertAlmostEqual(metrics['precision'], 50)
        self.assertAlmostEqual(metrics['recall'], 50)
        self.assertAlmostEqual(metrics['f1'], 50)
        self.assertAlmostEqual(metrics['exact'], 100 / 3)

    def test_pattern_validation(self):
        for invalid in (b"", b"\\patterns{a1b}", b"abc", b"a1b a2b", b"a\x001b", b"a\xff1b"):
            with self.assertRaises((ValueError, UnicodeError)):
                az.patterns(invalid)

    def test_patgen_reproducible_and_annotations_unchanged(self):
        train, _ = az.datasets()
        before = tuple(train)
        first, second = az.generate(train), az.generate(train)
        self.assertEqual(first, second)
        self.assertEqual(before, tuple(train))
        self.assertEqual(first, az.text_bytes(az.ROOT / "azhyphen.pat.txt"))

    def test_stale_detection_and_failed_generation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "data").mkdir()
            for name in ("hyphenated.txt", "evaluation.txt"):
                (root / "data" / name).write_bytes((az.ROOT / "data" / name).read_bytes())
            for name in ("README.md", "VERSION", "azhyphen.pat.txt", "azhyphen-xetex.tex", "azhyphen-version.tex"):
                (root / name).write_bytes(az.text_bytes(az.ROOT / name))
            (root / "azhyphen.pat.txt").write_bytes(b"stale")
            before = {p: p.read_bytes() for p in root.iterdir() if p.is_file()}
            with self.assertRaisesRegex(ValueError, "run make update"):
                az.update(root, check=True)
            self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir() if p.is_file()})
            with patch.object(az, "run", side_effect=OSError("missing PATGEN")):
                with self.assertRaises(OSError):
                    az.update(root)
            self.assertEqual(before, {p: p.read_bytes() for p in root.iterdir() if p.is_file()})
            az.update(root)
            az.update(root, check=True)

    def test_loader_and_version(self):
        raw = b"fo1to\n"
        loader = az.loader(raw)
        self.assertIn(hashlib.sha256(raw).hexdigest().encode(), loader)
        self.assertIn(b"\\patterns{\nfo1to\n}", loader)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for invalid in ("1.0\n", "01.0.0\n", "1.0.0", "1.0.0\n\n", "1٢.0.0\n"):
                (root / "VERSION").write_text(invalid, encoding="utf-8")
                with self.assertRaises(ValueError):
                    az.version(root)

    def test_generated_status_values_and_readme_preservation(self):
        train, evaluation = az.datasets()
        raw = az.text_bytes(az.ROOT / "azhyphen.pat.txt")
        model = az.patterns(raw)
        # Compute the scores independently of statistics formatting/aggregation.
        predicted = [az.predict(s.replace("-", ""), model) for s in evaluation]
        expected = [az.breaks(s) for s in evaluation]
        correct = sum(len(actual & gold) for actual, gold in zip(predicted, expected))
        wrong = sum(len(actual - gold) for actual, gold in zip(predicted, expected))
        missed = sum(len(gold - actual) for actual, gold in zip(predicted, expected))
        exact = 100 * sum(actual == gold for actual, gold in zip(predicted, expected)) / len(evaluation)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "VERSION").write_bytes(az.text_bytes(az.ROOT / "VERSION"))
            prefix = b"Unrelated prefix\r\n" + az.START.encode()
            suffix = az.END.encode() + "\r\nUnrelated suffix ·\r\n".encode()
            (root / "README.md").write_bytes(prefix + b"\nstale\n" + suffix)
            first = az.generated(root, raw, train, evaluation)
            (root / "README.md").write_bytes(first['README.md'])
            self.assertEqual(first, az.generated(root, raw, train, evaluation))
            self.assertTrue(first['README.md'].startswith(prefix))
            self.assertTrue(first['README.md'].endswith(suffix))
            block = first['README.md'][len(prefix):-len(suffix)].decode().strip()
            self.assertIn(f"Azhyphen **{az.version()}** is currently a **development release**.", block)
            lines = [line for line in block.splitlines() if line.startswith("**")]
            self.assertEqual(len(lines), 3)
            self.assertEqual(lines[0], f"**Dataset** · {len(train):,} training words · {len(evaluation):,} evaluation words · {len(model):,} patterns" + "\\")
            self.assertEqual(lines[1], f"**Quality** · {exact:.2f}% exact-word accuracy · {100*correct/(correct+wrong):.2f}% precision · {100*correct/(correct+missed):.2f}% recall · **{200*correct/(2*correct+wrong+missed):.2f}% F1**" + "\\")
            self.assertEqual(lines[2], f"**Breakpoints** · {correct} correct · {wrong} wrong · {missed} missed")
            self.assertNotIn('|', block)
            # Evaluation count must be derived independently of training count.
            smaller = az.generated(root, raw, train, evaluation[:-1])['README.md'].decode()
            self.assertIn(f"{len(train):,} training words · {len(evaluation)-1:,} evaluation words", smaller)
            (root / "VERSION").write_text("0.9.0\n")
            self.assertIn(b"Azhyphen **0.9.0**", az.generated(root, raw, train, evaluation)['README.md'])
            (root / "README.md").write_text(az.END + "\n" + az.START)
            with self.assertRaisesRegex(ValueError, "ordered"):
                az.generated(root, raw, train, evaluation)

    def test_stale_status_values_are_detected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("VERSION", "README.md", "azhyphen.pat.txt", "azhyphen-xetex.tex", "azhyphen-version.tex", "data/hyphenated.txt", "data/evaluation.txt"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(az.text_bytes(az.ROOT / name))
            original = (root / "README.md").read_bytes()
            train, evaluation = az.datasets(root)
            scores = az.statistics(train, evaluation, az.text_bytes(root / "azhyphen.pat.txt"))
            tokens = [az.version(root), f"{scores['training']:,} training words",
                      f"{scores['evaluation']:,} evaluation words", f"{scores['patterns']:,} patterns",
                      *(f"{scores[key]:.2f}% {label}" for key, label in
                        [('exact', 'exact-word accuracy'), ('precision', 'precision'), ('recall', 'recall'), ('f1', 'F1')]),
                      *(f"{scores[key]} {key}" for key in ('correct', 'wrong', 'missed'))]
            for token in tokens:
                self.assertIn(token.encode(), original)
                (root / "README.md").write_bytes(original.replace(token.encode(), b"stale value", 1))
                with self.assertRaisesRegex(ValueError, "README.md.*make update"):
                    az.update(root, check=True)
                az.update(root)
                self.assertEqual((root / "README.md").read_bytes(), original)

    def test_ctan_construction_excludes_repository_material(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in az.SOURCES:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(az.text_bytes(az.ROOT / name))
            for name in ('tests/fixture.txt', '.github/workflows/ci.yml', 'build/probe.py'):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text('repository only')
            def compile_manual(source, work, *args, **kwargs):
                (work / 'document.pdf').write_bytes(b'%PDF-1.7\n%%EOF\n')
                return ''
            with patch.object(az, 'ROOT', root), patch.object(az, 'check'), \
                 patch.object(az, 'compile_tex', side_effect=compile_manual), \
                 patch.object(az, 'runtime_test') as smoke:
                target = az.ctan()
            with zipfile.ZipFile(target) as archive:
                self.assertEqual(set(archive.namelist()), {'azhyphen/' + name for name in az.SOURCES} | {'azhyphen/doc/azhyphen-doc.pdf'})
                self.assertEqual(len(archive.namelist()), 17)
                self.assertFalse(any('/tests/' in name or '/.git' in name or '/build/' in name for name in archive.namelist()))
            self.assertIn(b'\\usepackage{azhyphen}', smoke.call_args.kwargs['source'])

    def test_extracted_ctan_source_check_accepts_only_the_manual_pdf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in az.SOURCES:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(az.text_bytes(az.ROOT / name))
            manual = root / 'doc/azhyphen-doc.pdf'
            manual.write_bytes(b'%PDF-1.7\n\xff\n%%EOF\n')
            with patch.object(az, 'ROOT', root):
                az.check()
                manual.write_bytes(b'not a PDF')
                with self.assertRaisesRegex(ValueError, 'manual PDF'):
                    az.check()
                manual.write_bytes(b'%PDF-1.7\n%%EOF\n')
                (root / 'doc/unexpected.pdf').write_bytes(b'other generated file')
                with self.assertRaisesRegex(ValueError, 'unexpected generated artifact'):
                    az.check()

    def test_registration_ownership_idempotence_and_rollback(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            config = home / "tex/generic/config"
            config.mkdir(parents=True)
            local, language = config / "language-local.dat", config / "language.dat"
            original = b"% User registration\ncustom zerohyph.tex\n"
            for path in (local, language):
                path.write_bytes(original)
                path.chmod(0o640)
            env = dict(os.environ, TEXMFHOME=home.as_posix())
            with patch.object(az, "run", side_effect=ValueError("format failure")):
                with self.assertRaises(ValueError):
                    az.registration(home, env, True)
            self.assertEqual(local.read_bytes(), original)
            self.assertEqual(language.read_bytes(), original)
            with patch.object(az, "run"):
                az.registration(home, env, True)
                az.registration(home, env, True)
                self.assertEqual(language.read_text().count("azhyphen azhyphen-xetex.tex"), 1)
                language.write_bytes(language.read_bytes() + b"later zerohyph.tex\n")
                installed = language.read_bytes()
                with patch.object(az, "run", side_effect=ValueError("format failure")):
                    with self.assertRaises(ValueError):
                        az.registration(home, env, False)
                self.assertEqual(language.read_bytes(), installed)
                az.registration(home, env, False)
                az.registration(home, env, False)
            self.assertEqual(language.read_bytes(), original + b"later zerohyph.tex\n")
            self.assertEqual(local.read_bytes(), original)
            language.write_text("azhyphen other-loader.tex\n")
            with self.assertRaisesRegex(ValueError, "unmanaged"):
                az.registration(home, env, True)
            az.registration(home, env, False)
            self.assertEqual(language.read_text(), "azhyphen other-loader.tex\n")

    @unittest.skipIf(os.name == "nt", "Windows chmod has no POSIX permission semantics")
    def test_posix_mode_preserved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config"
            path.write_bytes(b"before")
            path.chmod(0o640)
            az.write(path, b"after")
            self.assertEqual(path.stat().st_mode & 0o777, 0o640)

    def test_runtime_installation_preserves_changes_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as temporary:
            home = Path(temporary)
            package = home / "tex/latex/azhyphen"
            package.mkdir(parents=True)
            unrelated = package / "unrelated.txt"
            unrelated.write_bytes(b"unrelated")
            before = {p.name: p.read_bytes() for p in package.iterdir()}
            with patch.object(az, "registration", side_effect=ValueError("failed format")), patch.object(az, "run"):
                with self.assertRaises(ValueError):
                    az.installation(True, home)
            self.assertEqual(before, {p.name: p.read_bytes() for p in package.iterdir()})
            with patch.object(az, "registration"):
                az.installation(True, home)
                az.installation(True, home)
                self.assertEqual(set(p.name for p in package.iterdir()), set(az.RUNTIME) | {'unrelated.txt'})
                (package / "azhyphen.lua").write_bytes(b"user modified")
                az.installation(False, home)
                self.assertEqual(set(p.name for p in package.iterdir()), {'unrelated.txt', 'azhyphen.lua'})
                self.assertEqual((package / "azhyphen.lua").read_bytes(), b"user modified")

    def test_archive_exact_members_bytes_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            files = {"data/hyphenated.txt": "Azər-bay-can\n".encode(), "azhyphen.sty": b"runtime\n"}
            first, second = root / "one.zip", root / "two.zip"
            az.archive_write(first, files, 946684800)
            az.archive_write(second, files, 946684800)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(archive.namelist(), sorted("azhyphen/" + s for s in files))
                for entry in archive.infolist():
                    self.assertEqual(entry.external_attr >> 16, 0o100644)
                    self.assertEqual(entry.date_time, (2000, 1, 1, 0, 0, 0))

    def test_privacy_scan(self):
        for private in (b"C:" + b"\\Users\\someone",
                        b"/".join((b"", b"home", b"private", b"data")),
                        b"\\".join((b"", b"", b"server", b"share", b"data")), b"gh" + b"p_secret"):
            with self.assertRaises(ValueError):
                az.privacy("test", private)
        az.privacy("public", b"https://github.com/abdanar/azhyphen")

    def test_isolated_tex_environment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            env = az.tex_environment(root)
            self.assertEqual(env['TEXMFCACHE'], env['TEXMFVAR'])
            for name in ("TEXMFHOME", "TEXMFVAR", "TEXMFCONFIG"):
                self.assertTrue(Path(env[name]).is_dir())


if __name__ == "__main__":
    unittest.main()
