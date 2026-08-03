#!/usr/bin/env bash
# erd 스킬 설치 — 의존성 설치 + 스킬 배치 + 준비물 점검
#
#   bash install.sh              내 계정에 설치 (~/.claude/skills/erd)
#   bash install.sh --project    현재 프로젝트에 설치 (./.claude/skills/erd)
#   bash install.sh --here       이미 놓인 자리에서 의존성만 설치
#   bash install.sh --check      아무것도 바꾸지 않고 점검만
#
# 메시지 언어는 ERD_LANG(en·ko·ja·es), 없으면 로케일, 그것도 없으면 en.
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── 말 ──────────────────────────────────────────────────────────────────────
# ERD_LANG > LC_ALL > LC_MESSAGES > LANG. 아는 말이 아니면 영어로 떨어진다.
pick_lang() {
  local l="${ERD_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}"
  case "$(printf '%s' "$l" | tr '[:upper:]' '[:lower:]')" in
    ko*) echo ko ;;
    ja*) echo ja ;;
    es*) echo es ;;
    *)   echo en ;;
  esac
}
LANGX=$(pick_lang)

t() {  # t <키> [printf 인자…]
  local k="$1"; shift
  local s; s=$("_t_$LANGX" "$k")
  [ -z "$s" ] && s=$(_t_en "$k")
  # shellcheck disable=SC2059
  printf "$s" "$@"
}

_t_en() { case "$1" in
  usage)      echo 'erd skill installer — dependencies + placement + preflight check\n\n  bash install.sh              install for your account (~/.claude/skills/erd)\n  bash install.sh --project    install into the current project (./.claude/skills/erd)\n  bash install.sh --here       install dependencies only, leave files in place\n  bash install.sh --check      check only, change nothing\n\n  ERD_LANG=en|ko|ja|es         message language (default: your locale)' ;;
  opt_bad)    echo 'unknown option: %s  (--help)' ;;
  s_py)       echo '1. Python' ;;
  py_need)    echo 'Python 3.9 or newer is required. Install it and run this again.' ;;
  py_venv)    echo 'virtualenv: %s' ;;
  s_place)    echo '2. Skill placement' ;;
  s_place_skip) echo '2. Skill placement (skipped — %s)' ;;
  place_same) echo 'already in place: %s' ;;
  place_over) echo '  already exists: %s\n  overwrite? [y/N] ' ;;
  place_keep) echo 'leaving it as is. installing dependencies only.' ;;
  place_done) echo 'copied: %s' ;;
  place_here) echo 'current location: %s' ;;
  skill_ok)   echo 'SKILL.md found' ;;
  skill_no)   echo 'SKILL.md is missing — this will not be recognized as a skill' ;;
  s_pkg)      echo '3. Python packages' ;;
  pkg_no)     echo '%s missing' ;;
  pkg_check)  echo '--check, so nothing is installed:  pip3 install -r %s' ;;
  pkg_doing)  echo '  installing:  %s -m pip install -r %s\n' ;;
  pkg_ok)     echo 'installed' ;;
  pkg_ok_u)   echo 'installed (--user)' ;;
  pkg_fail)   echo 'install failed. activate a virtualenv or run it yourself:  %s -m pip install -r %s' ;;
  imp_ok)     echo 'import verified' ;;
  imp_no)     echo 'installed, but the import fails — check whether a different Python is in use' ;;
  s_db)       echo '4. Database client (one of the two)' ;;
  db_no)      echo 'neither psql nor docker. the database cannot be read.' ;;
  s_font)     echo '5. Rendering fonts' ;;
  need_cmd)   echo 'no %s, so it cannot be installed automatically' ;;
  dl_doing)   echo '  downloading (~45MB): Pretendard v%s\n' ;;
  dl_fail)    echo 'download failed (check the network)' ;;
  unzip_fail) echo 'unzip failed — the release layout may have changed' ;;
  font_done)  echo 'Pretendard installed: %s (Regular · Bold)' ;;
  font_body)  echo 'body:   %s' ;;
  font_check) echo 'no Pretendard — --check, so nothing is installed' ;;
  font_ask)   echo '  Pretendard is not installed. download it now? (%s) [Y/n] ' ;;
  font_skip)  echo 'skipped — the OS default font will be used' ;;
  font_none)  echo 'continuing without Pretendard — the OS default font will be used' ;;
  font_fb)    echo 'body (fallback): %s' ;;
  font_miss)  echo 'no body font found — text will render as □ in the PNG' ;;
  font_hint)  echo '      or:  export ERD_FONT=/path/to/font.otf' ;;
  mono_ok)    echo 'mono:   %s' ;;
  mono_miss)  echo 'no monospace font — column names will look misaligned' ;;
  mono_hint)  echo '      or:  export ERD_MONO=/path/to/font.ttf' ;;
  s_result)   echo 'Result' ;;
  done_ok)    echo 'installation complete' ;;
  next)       echo '\n  Next\n    1) start a new Claude Code session (skills are read at startup)\n    2) say "draw the ERD", or call /erd\n\n  Running it yourself\n    cd %s/scripts\n    export ERD_PROJ=/where/documents/go\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'Our Service ERD'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo 'fix the ✗ items above and run it again:  bash install.sh --check' ;;
esac; }

_t_ko() { case "$1" in
  usage)      echo 'erd 스킬 설치 — 의존성 설치 + 스킬 배치 + 준비물 점검\n\n  bash install.sh              내 계정에 설치 (~/.claude/skills/erd)\n  bash install.sh --project    현재 프로젝트에 설치 (./.claude/skills/erd)\n  bash install.sh --here       이미 놓인 자리에서 의존성만 설치\n  bash install.sh --check      아무것도 바꾸지 않고 점검만\n\n  ERD_LANG=en|ko|ja|es         메시지 언어 (기본: 로케일)' ;;
  opt_bad)    echo '모르는 옵션: %s  (--help)' ;;
  s_py)       echo '1. Python 확인' ;;
  py_need)    echo 'Python 3.9 이상이 필요하다. 설치 후 다시 실행한다.' ;;
  py_venv)    echo '가상환경: %s' ;;
  s_place)    echo '2. 스킬 배치' ;;
  s_place_skip) echo '2. 스킬 배치 (건너뜀 — %s)' ;;
  place_same) echo '이미 제자리다: %s' ;;
  place_over) echo '  이미 있다: %s\n  덮어쓸까? [y/N] ' ;;
  place_keep) echo '배치를 건너뛴다. 의존성만 설치한다.' ;;
  place_done) echo '복사 완료: %s' ;;
  place_here) echo '현재 위치: %s' ;;
  skill_ok)   echo 'SKILL.md 확인' ;;
  skill_no)   echo 'SKILL.md 가 없다 — 스킬로 인식되지 않는다' ;;
  s_pkg)      echo '3. 파이썬 패키지' ;;
  pkg_no)     echo '%s 없음' ;;
  pkg_check)  echo '--check 라 설치하지 않는다:  pip3 install -r %s' ;;
  pkg_doing)  echo '  설치 중:  %s -m pip install -r %s\n' ;;
  pkg_ok)     echo '설치 완료' ;;
  pkg_ok_u)   echo '설치 완료 (--user)' ;;
  pkg_fail)   echo '설치 실패. 가상환경을 켜거나 직접 실행한다:  %s -m pip install -r %s' ;;
  imp_ok)     echo 'import 확인' ;;
  imp_no)     echo '설치했는데 import 가 안 된다 — 다른 파이썬을 쓰고 있는지 확인한다' ;;
  s_db)       echo '4. DB 접속 수단 (둘 중 하나)' ;;
  db_no)      echo 'psql 도 docker 도 없다. DB를 읽을 수 없다.' ;;
  s_font)     echo '5. 렌더링 폰트' ;;
  need_cmd)   echo '%s 이 없어 자동 설치를 못 한다' ;;
  dl_doing)   echo '  내려받는 중 (약 45MB): Pretendard v%s\n' ;;
  dl_fail)    echo '다운로드 실패 (네트워크 확인)' ;;
  unzip_fail) echo '압축 해제 실패 — 배포 구조가 바뀌었을 수 있다' ;;
  font_done)  echo 'Pretendard 설치: %s (Regular · Bold)' ;;
  font_body)  echo '본문:   %s' ;;
  font_check) echo 'Pretendard 없음 — --check 라 설치하지 않는다' ;;
  font_ask)   echo '  Pretendard 가 없다. 지금 받아서 설치할까? (%s) [Y/n] ' ;;
  font_skip)  echo '건너뛴다 — OS 기본 폰트로 그린다' ;;
  font_none)  echo 'Pretendard 없이 진행한다 — OS 기본 폰트로 그린다' ;;
  font_fb)    echo '본문(폴백): %s' ;;
  font_miss)  echo '본문 폰트가 하나도 없다 — PNG의 글자가 □ 로 나온다' ;;
  font_hint)  echo '      또는:  export ERD_FONT=/폰트/경로.otf' ;;
  mono_ok)    echo '고정폭: %s' ;;
  mono_miss)  echo '고정폭 폰트 없음 — 컬럼명이 어긋나 보인다' ;;
  mono_hint)  echo '      또는:  export ERD_MONO=/폰트/경로.ttf' ;;
  s_result)   echo '결과' ;;
  done_ok)    echo '설치 완료' ;;
  next)       echo '\n  다음 단계\n    1) Claude Code 를 새로 띄운다 (스킬은 시작할 때 읽는다)\n    2) "ERD 그려줘" 라고 하거나 /erd 를 부른다\n\n  직접 돌릴 때\n    cd %s/scripts\n    export ERD_PROJ=/문서/저장/위치\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'우리서비스 ERD'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo '위의 ✗ 항목을 해결하고 다시 실행한다:  bash install.sh --check' ;;
esac; }

_t_ja() { case "$1" in
  usage)      echo 'erd スキルのインストール — 依存関係の導入 + スキルの配置 + 前提の点検\n\n  bash install.sh              自分のアカウントに入れる (~/.claude/skills/erd)\n  bash install.sh --project    今のプロジェクトに入れる (./.claude/skills/erd)\n  bash install.sh --here       置かれた場所のまま依存関係だけ入れる\n  bash install.sh --check      何も変えずに点検だけ\n\n  ERD_LANG=en|ko|ja|es         メッセージの言語 (既定: ロケール)' ;;
  opt_bad)    echo '不明なオプション: %s  (--help)' ;;
  s_py)       echo '1. Python の確認' ;;
  py_need)    echo 'Python 3.9 以上が必要だ。入れてから実行し直す。' ;;
  py_venv)    echo '仮想環境: %s' ;;
  s_place)    echo '2. スキルの配置' ;;
  s_place_skip) echo '2. スキルの配置 (スキップ — %s)' ;;
  place_same) echo 'すでに所定の位置にある: %s' ;;
  place_over) echo '  すでにある: %s\n  上書きするか? [y/N] ' ;;
  place_keep) echo '配置は飛ばす。依存関係だけ入れる。' ;;
  place_done) echo 'コピー完了: %s' ;;
  place_here) echo '現在の場所: %s' ;;
  skill_ok)   echo 'SKILL.md あり' ;;
  skill_no)   echo 'SKILL.md がない — スキルとして認識されない' ;;
  s_pkg)      echo '3. Python パッケージ' ;;
  pkg_no)     echo '%s がない' ;;
  pkg_check)  echo '--check なので入れない:  pip3 install -r %s' ;;
  pkg_doing)  echo '  インストール中:  %s -m pip install -r %s\n' ;;
  pkg_ok)     echo 'インストール完了' ;;
  pkg_ok_u)   echo 'インストール完了 (--user)' ;;
  pkg_fail)   echo 'インストール失敗。仮想環境を有効にするか、自分で実行する:  %s -m pip install -r %s' ;;
  imp_ok)     echo 'import を確認' ;;
  imp_no)     echo '入れたのに import できない — 別の Python を見ていないか確認する' ;;
  s_db)       echo '4. DB への接続手段 (どちらか一つ)' ;;
  db_no)      echo 'psql も docker もない。DB が読めない。' ;;
  s_font)     echo '5. 描画フォント' ;;
  need_cmd)   echo '%s がないので自動インストールできない' ;;
  dl_doing)   echo '  ダウンロード中 (約45MB): Pretendard v%s\n' ;;
  dl_fail)    echo 'ダウンロード失敗 (ネットワークを確認)' ;;
  unzip_fail) echo '展開に失敗 — 配布構成が変わった可能性がある' ;;
  font_done)  echo 'Pretendard を導入: %s (Regular · Bold)' ;;
  font_body)  echo '本文:   %s' ;;
  font_check) echo 'Pretendard がない — --check なので入れない' ;;
  font_ask)   echo '  Pretendard がない。今すぐ取得して入れるか? (%s) [Y/n] ' ;;
  font_skip)  echo '飛ばす — OS 標準のフォントで描く' ;;
  font_none)  echo 'Pretendard なしで進める — OS 標準のフォントで描く' ;;
  font_fb)    echo '本文(代替): %s' ;;
  font_miss)  echo '本文フォントが一つもない — PNG の文字が □ になる' ;;
  font_hint)  echo '      または:  export ERD_FONT=/フォント/パス.otf' ;;
  mono_ok)    echo '等幅:   %s' ;;
  mono_miss)  echo '等幅フォントがない — カラム名がずれて見える' ;;
  mono_hint)  echo '      または:  export ERD_MONO=/フォント/パス.ttf' ;;
  s_result)   echo '結果' ;;
  done_ok)    echo 'インストール完了' ;;
  next)       echo '\n  次にすること\n    1) Claude Code を起動し直す (スキルは起動時に読まれる)\n    2)「ERD を描いて」と言うか、/erd を呼ぶ\n\n  自分で動かすとき\n    cd %s/scripts\n    export ERD_PROJ=/ドキュメントの/保存先\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'自社サービス ERD'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo '上の ✗ を解消してから実行し直す:  bash install.sh --check' ;;
esac; }

_t_es() { case "$1" in
  usage)      echo 'Instalador de la skill erd — dependencias + colocación + comprobación previa\n\n  bash install.sh              instalar en la cuenta (~/.claude/skills/erd)\n  bash install.sh --project    instalar en el proyecto actual (./.claude/skills/erd)\n  bash install.sh --here       instalar solo las dependencias, sin mover los archivos\n  bash install.sh --check      solo comprobar, sin cambiar nada\n\n  ERD_LANG=en|ko|ja|es         idioma de los mensajes (por defecto: la configuración regional)' ;;
  opt_bad)    echo 'opción desconocida: %s  (--help)' ;;
  s_py)       echo '1. Python' ;;
  py_need)    echo 'Se requiere Python 3.9 o superior. Instálelo y vuelva a ejecutarlo.' ;;
  py_venv)    echo 'entorno virtual: %s' ;;
  s_place)    echo '2. Colocación de la skill' ;;
  s_place_skip) echo '2. Colocación de la skill (omitida — %s)' ;;
  place_same) echo 'ya está en su sitio: %s' ;;
  place_over) echo '  ya existe: %s\n  ¿sobrescribir? [s/N] ' ;;
  place_keep) echo 'se deja como está. solo se instalan las dependencias.' ;;
  place_done) echo 'copiado: %s' ;;
  place_here) echo 'ubicación actual: %s' ;;
  skill_ok)   echo 'SKILL.md encontrado' ;;
  skill_no)   echo 'falta SKILL.md — no se reconocerá como skill' ;;
  s_pkg)      echo '3. Paquetes de Python' ;;
  pkg_no)     echo 'falta %s' ;;
  pkg_check)  echo 'con --check no se instala nada:  pip3 install -r %s' ;;
  pkg_doing)  echo '  instalando:  %s -m pip install -r %s\n' ;;
  pkg_ok)     echo 'instalado' ;;
  pkg_ok_u)   echo 'instalado (--user)' ;;
  pkg_fail)   echo 'falló la instalación. active un entorno virtual o ejecútelo a mano:  %s -m pip install -r %s' ;;
  imp_ok)     echo 'import verificado' ;;
  imp_no)     echo 'se instaló, pero el import falla — compruebe si se está usando otro Python' ;;
  s_db)       echo '4. Cliente de base de datos (uno de los dos)' ;;
  db_no)      echo 'no hay psql ni docker. no se puede leer la base de datos.' ;;
  s_font)     echo '5. Fuentes de renderizado' ;;
  need_cmd)   echo 'no hay %s, así que no se puede instalar automáticamente' ;;
  dl_doing)   echo '  descargando (unos 45MB): Pretendard v%s\n' ;;
  dl_fail)    echo 'falló la descarga (revise la red)' ;;
  unzip_fail) echo 'falló al descomprimir — puede que haya cambiado la estructura del paquete' ;;
  font_done)  echo 'Pretendard instalado: %s (Regular · Bold)' ;;
  font_body)  echo 'texto:  %s' ;;
  font_check) echo 'no hay Pretendard — con --check no se instala' ;;
  font_ask)   echo '  No está Pretendard. ¿Descargarlo e instalarlo ahora? (%s) [S/n] ' ;;
  font_skip)  echo 'omitido — se dibujará con la fuente por defecto del sistema' ;;
  font_none)  echo 'se continúa sin Pretendard — se dibujará con la fuente por defecto del sistema' ;;
  font_fb)    echo 'texto (alternativa): %s' ;;
  font_miss)  echo 'no hay ninguna fuente de texto — el PNG mostrará □ en lugar de letras' ;;
  font_hint)  echo '      o bien:  export ERD_FONT=/ruta/a/la/fuente.otf' ;;
  mono_ok)    echo 'mono:   %s' ;;
  mono_miss)  echo 'no hay fuente monoespaciada — los nombres de columna se verán desalineados' ;;
  mono_hint)  echo '      o bien:  export ERD_MONO=/ruta/a/la/fuente.ttf' ;;
  s_result)   echo 'Resultado' ;;
  done_ok)    echo 'instalación completada' ;;
  next)       echo '\n  Siguiente paso\n    1) abra una sesión nueva de Claude Code (las skills se leen al arrancar)\n    2) diga «dibuja el ERD», o invoque /erd\n\n  Para ejecutarlo a mano\n    cd %s/scripts\n    export ERD_PROJ=/donde/van/los/documentos\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'ERD de nuestro servicio'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo 'resuelva los ✗ de arriba y vuelva a ejecutar:  bash install.sh --check' ;;
esac; }

MODE=user
for a in "$@"; do
  case "$a" in
    --project) MODE=project ;;
    --here)    MODE=here ;;
    --check)   MODE=check ;;
    -h|--help) t usage; echo; exit 0 ;;
    *) t opt_bad "$a"; echo; exit 2 ;;
  esac
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }

FAIL=0

# ── 1. python ───────────────────────────────────────────────────────────────
step "$(t s_py)"
PY=""
for c in python3 python; do
  command -v "$c" >/dev/null 2>&1 || continue
  if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  bad "$(t py_need)"
  exit 1
fi
ok "$($PY -V 2>&1)  ($(command -v "$PY"))"
[ -n "${VIRTUAL_ENV:-}" ] && ok "$(t py_venv "$VIRTUAL_ENV")"

# ── 2. 스킬 배치 ────────────────────────────────────────────────────────────
DEST="$SRC"
if [ "$MODE" = user ] || [ "$MODE" = project ]; then
  step "$(t s_place)"
  if [ "$MODE" = user ]; then
    BASE="$HOME/.claude/skills"
  else
    BASE="$PWD/.claude/skills"
  fi
  DEST="$BASE/erd"

  if [ "$SRC" = "$DEST" ]; then
    ok "$(t place_same "$DEST")"
  else
    mkdir -p "$BASE"
    if [ -e "$DEST" ]; then
      t place_over "$DEST"
      # tty 가 없으면(CI·파이프) 묻지 않고 보수적으로 건너뛴다
      { read -r ans </dev/tty; } 2>/dev/null || { ans=n; echo; }
      case "$ans" in
        [yYsS]*) rm -rf "$DEST" ;;
        *) warn "$(t place_keep)"; DEST="$SRC" ;;
      esac
    fi
    if [ ! -e "$DEST" ]; then
      cp -R "$SRC" "$DEST"
      # 저장소를 clone 해서 설치하는 경우가 많다 — 스킬 폴더에 .git 을 들고 갈 이유가 없다
      rm -rf "$DEST/.git" "$DEST/__pycache__" "$DEST/scripts/__pycache__" \
             "$DEST/scripts/lang/__pycache__"
      ok "$(t place_done "$DEST")"
    fi
  fi
  [ -f "$DEST/SKILL.md" ] && ok "$(t skill_ok)" || { bad "$(t skill_no)"; FAIL=1; }
else
  step "$(t s_place_skip "$MODE")"
  ok "$(t place_here "$SRC")"
  # --check 는 문제가 생겼을 때 돌리는 진단이다. /erd 가 목록에 안 뜨는 원인 1순위가
  # SKILL.md 이므로, 배치는 건너뛰더라도 설치돼 있어야 할 자리는 들여다본다.
  # 읽기만 하므로 "아무것도 바꾸지 않는다" 는 원칙은 그대로다.
  if [ "$MODE" = check ]; then
    for d in "$HOME/.claude/skills/erd" "$PWD/.claude/skills/erd" "$SRC"; do
      [ -f "$d/SKILL.md" ] && { ok "$(t skill_ok)  ($d)"; DEST="$d"; break; }
    done
    [ -f "$DEST/SKILL.md" ] || { bad "$(t skill_no)"; FAIL=1; }
  fi
fi

# ── 3. 파이썬 패키지 ────────────────────────────────────────────────────────
step "$(t s_pkg)"
need_install=0
$PY -c 'import docx' 2>/dev/null && ok "python-docx" || { warn "$(t pkg_no python-docx)"; need_install=1; }
$PY -c 'import PIL'  2>/dev/null && ok "pillow"      || { warn "$(t pkg_no pillow)";      need_install=1; }

REQ="$DEST/requirements.txt"; [ -f "$REQ" ] || REQ="$SRC/requirements.txt"

if [ "$need_install" = 1 ]; then
  if [ "$MODE" = check ]; then
    warn "$(t pkg_check "$REQ")"
    FAIL=1
  else
    t pkg_doing "$PY" "$REQ"
    if $PY -m pip install -q -r "$REQ"; then
      ok "$(t pkg_ok)"
    elif $PY -m pip install -q --user -r "$REQ"; then
      ok "$(t pkg_ok_u)"
    else
      bad "$(t pkg_fail "$PY" "$REQ")"
      FAIL=1
    fi
    $PY -c 'import docx, PIL' 2>/dev/null && ok "$(t imp_ok)" || { bad "$(t imp_no)"; FAIL=1; }
  fi
fi

# ── 4. DB 클라이언트 ────────────────────────────────────────────────────────
step "$(t s_db)"
have_db=0
command -v psql   >/dev/null 2>&1 && { ok "psql   $(psql --version 2>/dev/null | head -1)"; have_db=1; }
command -v docker >/dev/null 2>&1 && { ok "docker $(docker --version 2>/dev/null | head -1)"; have_db=1; }
if [ "$have_db" = 0 ]; then
  warn "$(t db_no)"
  case "$(uname -s)" in
    Darwin) echo "      brew install libpq && brew link --force libpq" ;;
    Linux)  echo "      apt install postgresql-client   /   dnf install postgresql" ;;
  esac
fi

# ── 5. 폰트 ─────────────────────────────────────────────────────────────────
# 본문은 Pretendard 를 쓴다. 없으면 받아서 깔고, 그것도 안 되면 OS 기본으로 내려간다.
step "$(t s_font)"

case "$(uname -s)" in
  Darwin) FONT_DIR="$HOME/Library/Fonts" ;;
  *)      FONT_DIR="$HOME/.local/share/fonts" ;;
esac
PRETENDARD_VER=1.3.9
PRETENDARD_URL="https://github.com/orioncactus/pretendard/releases/download/v${PRETENDARD_VER}/Pretendard-${PRETENDARD_VER}.zip"

find_font() {
  for f in "$@"; do [ -f "$f" ] && { echo "$f"; return 0; }; done
  return 1
}
find_pretendard() {
  find_font \
    "$HOME/Library/Fonts/Pretendard-Regular.otf" \
    /Library/Fonts/Pretendard-Regular.otf \
    "$HOME/.local/share/fonts/Pretendard-Regular.otf" \
    /usr/share/fonts/opentype/pretendard/Pretendard-Regular.otf
}

install_pretendard() {
  command -v curl >/dev/null 2>&1 || { warn "$(t need_cmd curl)"; return 1; }
  command -v unzip >/dev/null 2>&1 || { warn "$(t need_cmd unzip)"; return 1; }
  local tmp; tmp=$(mktemp -d) || return 1
  t dl_doing "$PRETENDARD_VER"
  if ! curl -fsSL -m 300 -o "$tmp/p.zip" "$PRETENDARD_URL"; then
    warn "$(t dl_fail)"; rm -rf "$tmp"; return 1
  fi
  # 필요한 두 굵기만 꺼낸다 — 전체를 깔면 폰트 목록이 지저분해진다
  if ! unzip -qo -j "$tmp/p.zip" \
        'public/static/Pretendard-Regular.otf' \
        'public/static/Pretendard-Bold.otf' -d "$tmp" 2>/dev/null; then
    warn "$(t unzip_fail)"; rm -rf "$tmp"; return 1
  fi
  mkdir -p "$FONT_DIR"
  mv -f "$tmp/Pretendard-Regular.otf" "$tmp/Pretendard-Bold.otf" "$FONT_DIR/" || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  command -v fc-cache >/dev/null 2>&1 && fc-cache -f "$FONT_DIR" >/dev/null 2>&1
  ok "$(t font_done "$FONT_DIR")"
  return 0
}

KR=$(find_pretendard) || true
if [ -n "$KR" ]; then
  ok "$(t font_body "$KR")"
elif [ "$MODE" = check ]; then
  warn "$(t font_check)"
else
  t font_ask "$FONT_DIR"
  # tty 가 없으면(CI·파이프) 기본값 Y — 폰트는 깔아두는 편이 낫다
  { read -r ans </dev/tty; } 2>/dev/null || { ans=y; echo; }
  case "${ans:-y}" in
    [nN]*) warn "$(t font_skip)" ;;
    *)     install_pretendard || warn "$(t font_none)" ;;
  esac
  KR=$(find_pretendard) || true
fi

if [ -z "$KR" ]; then   # Pretendard 가 없으면 OS 기본 폰트라도 있어야 한다
  # 라틴만 덮는 폰트(Helvetica·DejaVu)는 한글·한자를 쓰는 말에서는 후보로 치지 않는다.
  # 그걸로 그리면 글자가 전부 □ 로 나오는데 점검은 ✓ 로 끝나 버린다.
  case "$LANGX" in
    ko|ja) LATIN_OK='' ;;
    *)     LATIN_OK='/System/Library/Fonts/Helvetica.ttc
/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf' ;;
  esac
  # shellcheck disable=SC2086
  KR=$(find_font \
    /System/Library/Fonts/AppleSDGothicNeo.ttc \
    "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc" \
    /usr/share/fonts/truetype/nanum/NanumGothic.ttf \
    /usr/share/fonts/nanum/NanumGothic.ttf \
    /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
    /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc \
    $LATIN_OK) || true
  if [ -n "$KR" ]; then
    ok "$(t font_fb "$KR")"
  else
    warn "$(t font_miss)"
    echo "      apt install fonts-nanum   /   dnf install nanum-gothic-fonts"
    t font_hint; echo
  fi
fi

MONO_F=$(find_font \
  /System/Library/Fonts/Menlo.ttc \
  /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf \
  /usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf \
  /usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf) || true
[ -n "$MONO_F" ] && ok "$(t mono_ok "$MONO_F")" || {
  warn "$(t mono_miss)"
  echo "      apt install fonts-dejavu-core"
  t mono_hint; echo
}

# ── 마무리 ──────────────────────────────────────────────────────────────────
step "$(t s_result)"
if [ "$FAIL" = 0 ]; then
  ok "$(t done_ok)"
  t next "$DEST" "$PY" "$PY" "$PY" "$PY"
else
  bad "$(t done_bad)"
  exit 1
fi
