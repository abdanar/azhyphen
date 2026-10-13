# Shared environment conventions for POSIX recipes calling native TeX.
tex_path_separator=:
tex_native_path() { printf '%s\n' "$1"; }
tex_tlmgr() { tlmgr "$@"; }

case $(uname -s) in
  MSYS*|MINGW*)
    tex_path_separator=';'
    tex_native_path() { cygpath -m -- "$1"; }
    tex_tlmgr() { tlmgr.bat "$@"; }
    # Native TeX Live's Perl does not recognize the POSIX C.UTF-8 locale.
    export LC_ALL=C
    ;;
esac
