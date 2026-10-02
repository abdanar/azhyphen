#!/bin/sh
set -eu

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
tmp=$(mktemp -d "${TMPDIR:-/tmp}/azhyphen-install-test.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
mkdir -p "$tmp/texmfhome" "$tmp/cache" "$tmp/config" "$tmp/var" "$tmp/out"
sh "$root/tests/prepare-isolated-xetex.sh" "$tmp/texmfhome"

run_make() {
  env TEXMFHOME="$tmp/texmfhome" TEXMFVAR="$tmp/var" \
    TEXMFCONFIG="$tmp/config" TEXMFCACHE="$tmp/cache" \
    LUALATEX="${LUALATEX:-lualatex}" XELATEX="${XELATEX:-xelatex}" \
    make --no-print-directory -C "$root" "$@"
}

run_make install >/dev/null
run_make install >/dev/null

installed=$tmp/texmfhome/tex/latex/azhyphen
for file in azhyphen.sty azhyphen.lua azhyphen.pat.txt azhyphen.hyp.txt \
    azhyphen-xetex.tex; do
  test -f "$installed/$file" || {
    echo "error: installation smoke test did not install $file" >&2
    exit 1
  }
done

if ! env TEXMFHOME="$tmp/texmfhome" TEXMFCACHE="$tmp/cache" \
    TEXMFVAR="$tmp/var" TEXMFCONFIG="$tmp/config" \
    "${XELATEX:-xelatex}" -interaction=nonstopmode -halt-on-error \
      -output-directory="$tmp/out" "$root/tests/xetex-runtime.tex" \
      >"$tmp/out/console.txt" 2>&1; then
  echo "error: installed-package XeLaTeX smoke test failed" >&2
  tail -n 80 "$tmp/out/console.txt" >&2
  exit 1
fi

run_make uninstall >/dev/null
run_make uninstall >/dev/null
test ! -e "$installed/azhyphen.sty" || {
  echo "error: installation smoke test uninstall left runtime files" >&2
  exit 1
}
echo "installation smoke test passed"
