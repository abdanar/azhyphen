#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/azhyphen-test.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

mkdir -p "$tmp/repository/scripts" "$tmp/repository/tests/fixtures"
mkdir -p "$tmp/texmf/tex/latex/azhyphen" "$tmp/tex-cache"
mkdir -p "$tmp/out-fixture"

# Test the importer in a throwaway repository-shaped directory. Its canonical
# destination is deliberately derived from the copied script's location.
cp "$root/scripts/import_patterns.py" "$tmp/repository/scripts/"
cp "$root/tests/fixtures/sample-patterns.txt" "$tmp/repository/tests/fixtures/"
python3 "$tmp/repository/scripts/import_patterns.py" \
  "$tmp/repository/tests/fixtures/sample-patterns.txt" --quiet
test -s "$tmp/repository/tex/latex/azhyphen/azhyphen.pat.txt"
fixture_checksum=$(cksum \
  "$tmp/repository/tex/latex/azhyphen/azhyphen.pat.txt")
: >"$tmp/empty-patterns.txt"
if python3 "$tmp/repository/scripts/import_patterns.py" \
    "$tmp/empty-patterns.txt" >"$tmp/empty-import.txt" 2>&1; then
  echo "error: importer accepted an empty pattern file" >&2
  exit 1
fi
test "$fixture_checksum" = "$(cksum \
  "$tmp/repository/tex/latex/azhyphen/azhyphen.pat.txt")"

if command -v luac >/dev/null 2>&1; then
  luac -p "$root/tex/latex/azhyphen/azhyphen.lua"
fi

cp "$root/tex/latex/azhyphen/azhyphen.sty" \
   "$root/tex/latex/azhyphen/azhyphen.lua" \
   "$root/tex/latex/azhyphen/azhyphen.hyp.txt" \
   "$tmp/texmf/tex/latex/azhyphen/"
cp "$root/tests/fixtures/sample-patterns.txt" \
   "$tmp/texmf/tex/latex/azhyphen/azhyphen.pat.txt"

run_lualatex() {
  output=$1
  input=$2
  if ! env TEXMFCACHE="$tmp/tex-cache" TEXMFVAR="$tmp/tex-cache" \
      TEXINPUTS="$tmp/texmf//:" \
      "${LUALATEX:-lualatex}" -interaction=nonstopmode -halt-on-error \
        -output-directory="$output" "$input" >"$output/console.txt" 2>&1; then
    echo "error: LuaLaTeX failed for $input" >&2
    tail -n 80 "$output/console.txt" >&2
    return 1
  fi
}

run_lualatex "$tmp/out-fixture" "$root/tests/basic.tex"
run_lualatex "$tmp/out-fixture" "$root/tests/showhyphens.tex"
run_lualatex "$tmp/out-fixture" "$root/tests/runtime.tex"

# The fixture guarantees at least the fo-to break. This checks native LuaTeX
# hyphenation rather than merely checking package discovery or compilation.
if ! grep -q 'fo-toelektrik' "$tmp/out-fixture/showhyphens.log"; then
  echo "error: fixture patterns did not produce the expected native hyphenation" >&2
  grep -n 'foto\|fo-to' "$tmp/out-fixture/showhyphens.log" >&2 || true
  exit 1
fi

mkdir -p "$tmp/out-missing"
mv "$tmp/texmf/tex/latex/azhyphen/azhyphen.pat.txt" \
   "$tmp/azhyphen.pat.txt.saved"
if env TEXMFCACHE="$tmp/tex-cache" TEXMFVAR="$tmp/tex-cache" \
    TEXINPUTS="$tmp/texmf//:" \
    "${LUALATEX:-lualatex}" -interaction=nonstopmode -halt-on-error \
      -output-directory="$tmp/out-missing" "$root/tests/basic.tex" \
      >"$tmp/out-missing/console.txt" 2>&1; then
  echo "error: azhyphen loaded without its required production pattern file" >&2
  exit 1
fi
if ! grep -q 'required pattern file' \
    "$tmp/out-missing/console.txt"; then
  echo "error: missing-pattern failure did not contain the expected diagnostic" >&2
  tail -n 60 "$tmp/out-missing/console.txt" >&2
  exit 1
fi

mkdir -p "$tmp/out-invalid"
printf '\\patterns{not-raw-pattern-data' \
  >"$tmp/texmf/tex/latex/azhyphen/azhyphen.pat.txt"
if env TEXMFCACHE="$tmp/tex-cache" TEXMFVAR="$tmp/tex-cache" \
    TEXINPUTS="$tmp/texmf//:" \
    "${LUALATEX:-lualatex}" -interaction=nonstopmode -halt-on-error \
      -output-directory="$tmp/out-invalid" "$root/tests/basic.tex" \
      >"$tmp/out-invalid/console.txt" 2>&1; then
  echo "error: azhyphen accepted invalid pattern data" >&2
  exit 1
fi
if ! grep -q 'invalid pattern token' "$tmp/out-invalid/console.txt"; then
  echo "error: invalid-pattern failure did not contain the expected diagnostic" >&2
  tail -n 60 "$tmp/out-invalid/console.txt" >&2
  exit 1
fi
mv "$tmp/azhyphen.pat.txt.saved" \
   "$tmp/texmf/tex/latex/azhyphen/azhyphen.pat.txt"

if command -v pdflatex >/dev/null 2>&1; then
  if env TEXINPUTS="$tmp/texmf//:" \
      pdflatex -interaction=nonstopmode -halt-on-error \
        -output-directory="$tmp/out-fixture" "$root/tests/non-luatex.tex" \
        >"$tmp/out-fixture/non-luatex-console.txt" 2>&1; then
    echo "error: azhyphen unexpectedly accepted pdfLaTeX" >&2
    exit 1
  fi
  if ! grep -q 'LuaLaTeX or XeLaTeX is required' \
      "$tmp/out-fixture/non-luatex-console.txt"; then
    echo "error: pdfLaTeX rejection did not contain the expected diagnostic" >&2
    tail -n 40 "$tmp/out-fixture/non-luatex-console.txt" >&2
    exit 1
  fi
fi

echo "azhyphen tests passed"
