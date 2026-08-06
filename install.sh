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
  # `--` 가 있어야 한다. bash 내장 printf 는 형식 문자열이 `-` 로 시작하면 그것을
  # **제 옵션으로** 읽는다 — `pkg_check` 는 en·ko·ja 에서 `--check…` 로 시작하는데,
  # 패키지가 없는 환경에서 무엇을 어떻게 깔라는 바로 그 한 줄이 사라지고
  # `printf: --: invalid option` 이 대신 찍혔다. es 만 문장이 `con` 으로 시작해
  # 무사했다 — 말에 딸린 버그라 한 언어만 보면 안 보인다.
  # shellcheck disable=SC2059
  printf -- "$s" "$@"
}

_t_en() { case "$1" in
  usage)      echo 'erd skill installer — dependencies + placement + preflight check\n\n  bash install.sh              install for your account (~/.claude/skills/erd)\n  bash install.sh --project    install into the current project (./.claude/skills/erd)\n  bash install.sh --here       install dependencies only, leave files in place\n  bash install.sh --check      check only, change nothing\n\n  ERD_LANG=en|ko|ja|es         message language (default: your locale)' ;;
  opt_bad)    echo 'unknown option: %s  (--help)' ;;
  opt_conflict) echo '%s and %s cannot be combined — pick one' ;;
  s_py)       echo '1. Python' ;;
  py_need)    echo 'Python 3.9 or newer is required. Install it and run this again.' ;;
  py_venv)    echo 'virtualenv: %s' ;;
  s_place)    echo '2. Skill placement' ;;
  s_place_skip) echo '2. Skill placement (skipped — %s)' ;;
  place_same) echo 'already in place: %s' ;;
  place_over) echo '  already exists: %s\n  overwrite? [y/N] ' ;;
  place_keep) echo 'leaving it as is. installing dependencies only.' ;;
  place_noask) echo 'it already exists and there is no terminal to ask on — nothing was installed.\n      run it again from a terminal, or remove it first:  rm -rf %s' ;;
  place_done) echo 'copied: %s' ;;
  place_fail) echo 'the copy failed: %s  (check permissions and free space)' ;;
  place_here) echo 'current location: %s' ;;
  skill_ok)   echo 'SKILL.md found' ;;
  skill_no)   echo 'SKILL.md is missing — this will not be recognized as a skill  (%s)' ;;
  skill_bad)  echo 'SKILL.md is not a skill file — line 1 must be --- and the frontmatter must say name: erd  (%s)' ;;
  s_pkg)      echo '3. Python packages' ;;
  pkg_no)     echo '%s missing' ;;
  pkg_old)    echo '%s %s is too old — requirements.txt asks for %s or newer' ;;
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
  font_noask) echo 'no terminal to ask on, so the ~45MB download was NOT started — run it again from a terminal, or install it yourself (see INSTALL.md)' ;;
  font_none)  echo 'continuing without Pretendard — the OS default font will be used' ;;
  font_fb)    echo 'body (fallback): %s' ;;
  font_miss)  echo 'no body font found — text will render as □ in the PNG' ;;
  font_hint)  echo '      or:  export ERD_FONT=/path/to/font.otf' ;;
  mono_ok)    echo 'mono:   %s' ;;
  mono_miss)  echo 'no monospace font — column names will look misaligned' ;;
  mono_hint)  echo '      or:  export ERD_MONO=/path/to/font.ttf' ;;
  s_selftest) echo '6. Regression test' ;;
  st_none)    echo 'no regression test in the tree being checked (%s) — there is nothing to measure, and an install nobody measured is not an install that works' ;;
  st_skip)    echo 'NOT run — fix the ✗ above first' ;;
  s_result)   echo 'Result' ;;
  done_ok)    echo 'installation complete' ;;
  next)       echo '\n  Next\n    1) start a new Claude Code session (skills are read at startup)\n    2) say "draw the ERD", or call /erd\n\n  Running it yourself\n    cd %s/scripts\n    export ERD_PROJ=/where/documents/go\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'Our Service ERD'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo 'fix the ✗ items above and run it again:  bash install.sh --check' ;;
esac; }

_t_ko() { case "$1" in
  usage)      echo 'erd 스킬 설치 — 의존성 설치 + 스킬 배치 + 준비물 점검\n\n  bash install.sh              내 계정에 설치 (~/.claude/skills/erd)\n  bash install.sh --project    현재 프로젝트에 설치 (./.claude/skills/erd)\n  bash install.sh --here       이미 놓인 자리에서 의존성만 설치\n  bash install.sh --check      아무것도 바꾸지 않고 점검만\n\n  ERD_LANG=en|ko|ja|es         메시지 언어 (기본: 로케일)' ;;
  opt_bad)    echo '모르는 옵션: %s  (--help)' ;;
  opt_conflict) echo '%s 와 %s 는 같이 못 쓴다 — 하나만 준다' ;;
  s_py)       echo '1. Python 확인' ;;
  py_need)    echo 'Python 3.9 이상이 필요하다. 설치 후 다시 실행한다.' ;;
  py_venv)    echo '가상환경: %s' ;;
  s_place)    echo '2. 스킬 배치' ;;
  s_place_skip) echo '2. 스킬 배치 (건너뜀 — %s)' ;;
  place_same) echo '이미 제자리다: %s' ;;
  place_over) echo '  이미 있다: %s\n  덮어쓸까? [y/N] ' ;;
  place_keep) echo '배치를 건너뛴다. 의존성만 설치한다.' ;;
  place_noask) echo '이미 있는데 물어볼 터미널이 없다 — 아무것도 설치하지 않았다.\n      터미널에서 다시 돌리거나, 먼저 지운다:  rm -rf %s' ;;
  place_done) echo '복사 완료: %s' ;;
  place_fail) echo '복사 실패: %s  (권한·디스크 여유를 확인한다)' ;;
  place_here) echo '현재 위치: %s' ;;
  skill_ok)   echo 'SKILL.md 확인' ;;
  skill_no)   echo 'SKILL.md 가 없다 — 스킬로 인식되지 않는다  (%s)' ;;
  skill_bad)  echo 'SKILL.md 가 스킬 파일이 아니다 — 첫 줄이 --- 이고 frontmatter 에 name: erd 가 있어야 한다  (%s)' ;;
  s_pkg)      echo '3. 파이썬 패키지' ;;
  pkg_no)     echo '%s 없음' ;;
  pkg_old)    echo '%s %s 는 너무 낡았다 — requirements.txt 는 %s 이상을 요구한다' ;;
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
  font_noask) echo '물어볼 터미널이 없어 약 45MB 다운로드를 시작하지 않았다 — 터미널에서 다시 돌리거나 직접 설치한다 (INSTALL.ko.md 참고)' ;;
  font_none)  echo 'Pretendard 없이 진행한다 — OS 기본 폰트로 그린다' ;;
  font_fb)    echo '본문(폴백): %s' ;;
  font_miss)  echo '본문 폰트가 하나도 없다 — PNG의 글자가 □ 로 나온다' ;;
  font_hint)  echo '      또는:  export ERD_FONT=/폰트/경로.otf' ;;
  mono_ok)    echo '고정폭: %s' ;;
  mono_miss)  echo '고정폭 폰트 없음 — 컬럼명이 어긋나 보인다' ;;
  mono_hint)  echo '      또는:  export ERD_MONO=/폰트/경로.ttf' ;;
  s_selftest) echo '6. 회귀 시험' ;;
  st_none)    echo '점검 대상 트리에 회귀 시험이 없다 (%s) — 잴 것이 없다. 아무도 재지 않은 설치는 도는 설치가 아니다' ;;
  st_skip)    echo '돌리지 않았다 — 위의 ✗ 를 먼저 고친다' ;;
  s_result)   echo '결과' ;;
  done_ok)    echo '설치 완료' ;;
  next)       echo '\n  다음 단계\n    1) Claude Code 를 새로 띄운다 (스킬은 시작할 때 읽는다)\n    2) "ERD 그려줘" 라고 하거나 /erd 를 부른다\n\n  직접 돌릴 때\n    cd %s/scripts\n    export ERD_PROJ=/문서/저장/위치\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'우리서비스 ERD'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo '위의 ✗ 항목을 해결하고 다시 실행한다:  bash install.sh --check' ;;
esac; }

_t_ja() { case "$1" in
  usage)      echo 'erd スキルのインストール — 依存関係の導入 + スキルの配置 + 前提の点検\n\n  bash install.sh              自分のアカウントに入れる (~/.claude/skills/erd)\n  bash install.sh --project    今のプロジェクトに入れる (./.claude/skills/erd)\n  bash install.sh --here       置かれた場所のまま依存関係だけ入れる\n  bash install.sh --check      何も変えずに点検だけ\n\n  ERD_LANG=en|ko|ja|es         メッセージの言語 (既定: ロケール)' ;;
  opt_bad)    echo '不明なオプション: %s  (--help)' ;;
  opt_conflict) echo '%s と %s は同時に指定できない — どちらか一つにする' ;;
  s_py)       echo '1. Python の確認' ;;
  py_need)    echo 'Python 3.9 以上が必要だ。入れてから実行し直す。' ;;
  py_venv)    echo '仮想環境: %s' ;;
  s_place)    echo '2. スキルの配置' ;;
  s_place_skip) echo '2. スキルの配置 (スキップ — %s)' ;;
  place_same) echo 'すでに所定の位置にある: %s' ;;
  place_over) echo '  すでにある: %s\n  上書きするか? [y/N] ' ;;
  place_keep) echo '配置は飛ばす。依存関係だけ入れる。' ;;
  place_noask) echo 'すでにあるが、尋ねる端末がない — 何もインストールしていない。\n      端末から実行し直すか、先に消す:  rm -rf %s' ;;
  place_done) echo 'コピー完了: %s' ;;
  place_fail) echo 'コピー失敗: %s  (権限とディスクの空きを確認する)' ;;
  place_here) echo '現在の場所: %s' ;;
  skill_ok)   echo 'SKILL.md あり' ;;
  skill_no)   echo 'SKILL.md がない — スキルとして認識されない  (%s)' ;;
  skill_bad)  echo 'SKILL.md がスキルファイルになっていない — 1行目が --- で、frontmatter に name: erd が要る  (%s)' ;;
  s_pkg)      echo '3. Python パッケージ' ;;
  pkg_no)     echo '%s がない' ;;
  pkg_old)    echo '%s %s は古すぎる — requirements.txt は %s 以上を要求している' ;;
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
  font_noask) echo '尋ねる端末がないので、約45MB のダウンロードは開始していない — 端末から実行し直すか、自分で入れる (INSTALL.ja.md 参照)' ;;
  font_none)  echo 'Pretendard なしで進める — OS 標準のフォントで描く' ;;
  font_fb)    echo '本文(代替): %s' ;;
  font_miss)  echo '本文フォントが一つもない — PNG の文字が □ になる' ;;
  font_hint)  echo '      または:  export ERD_FONT=/フォント/パス.otf' ;;
  mono_ok)    echo '等幅:   %s' ;;
  mono_miss)  echo '等幅フォントがない — カラム名がずれて見える' ;;
  mono_hint)  echo '      または:  export ERD_MONO=/フォント/パス.ttf' ;;
  s_selftest) echo '6. 回帰テスト' ;;
  st_none)    echo '点検する木に回帰テストがない (%s) — 測るものがない。誰も測っていないインストールは動くインストールではない' ;;
  st_skip)    echo '実行しなかった — 上の ✗ を先に直す' ;;
  s_result)   echo '結果' ;;
  done_ok)    echo 'インストール完了' ;;
  next)       echo '\n  次にすること\n    1) Claude Code を起動し直す (スキルは起動時に読まれる)\n    2)「ERD を描いて」と言うか、/erd を呼ぶ\n\n  自分で動かすとき\n    cd %s/scripts\n    export ERD_PROJ=/ドキュメントの/保存先\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'自社サービス ERD'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo '上の ✗ を解消してから実行し直す:  bash install.sh --check' ;;
esac; }

_t_es() { case "$1" in
  usage)      echo 'Instalador de la skill erd — dependencias + colocación + comprobación previa\n\n  bash install.sh              instalar en la cuenta (~/.claude/skills/erd)\n  bash install.sh --project    instalar en el proyecto actual (./.claude/skills/erd)\n  bash install.sh --here       instalar solo las dependencias, sin mover los archivos\n  bash install.sh --check      solo comprobar, sin cambiar nada\n\n  ERD_LANG=en|ko|ja|es         idioma de los mensajes (por defecto: la configuración regional)' ;;
  opt_bad)    echo 'opción desconocida: %s  (--help)' ;;
  opt_conflict) echo '%s y %s no se pueden combinar — elija una' ;;
  s_py)       echo '1. Python' ;;
  py_need)    echo 'Se requiere Python 3.9 o superior. Instálelo y vuelva a ejecutarlo.' ;;
  py_venv)    echo 'entorno virtual: %s' ;;
  s_place)    echo '2. Colocación de la skill' ;;
  s_place_skip) echo '2. Colocación de la skill (omitida — %s)' ;;
  place_same) echo 'ya está en su sitio: %s' ;;
  place_over) echo '  ya existe: %s\n  ¿sobrescribir? [s/N] ' ;;
  place_keep) echo 'se deja como está. solo se instalan las dependencias.' ;;
  place_noask) echo 'ya existe y no hay terminal para preguntar — no se ha instalado nada.\n      vuelva a ejecutarlo desde un terminal, o bórrelo antes:  rm -rf %s' ;;
  place_done) echo 'copiado: %s' ;;
  place_fail) echo 'falló la copia: %s  (compruebe permisos y espacio libre)' ;;
  place_here) echo 'ubicación actual: %s' ;;
  skill_ok)   echo 'SKILL.md encontrado' ;;
  skill_no)   echo 'falta SKILL.md — no se reconocerá como skill  (%s)' ;;
  skill_bad)  echo 'SKILL.md no es un archivo de skill — la línea 1 debe ser --- y el frontmatter debe decir name: erd  (%s)' ;;
  s_pkg)      echo '3. Paquetes de Python' ;;
  pkg_no)     echo 'falta %s' ;;
  pkg_old)    echo '%s %s es demasiado antiguo — requirements.txt pide %s o superior' ;;
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
  font_noask) echo 'no hay terminal para preguntar, así que NO se ha iniciado la descarga de unos 45MB — vuelva a ejecutarlo desde un terminal, o instálela a mano (véase INSTALL.es.md)' ;;
  font_none)  echo 'se continúa sin Pretendard — se dibujará con la fuente por defecto del sistema' ;;
  font_fb)    echo 'texto (alternativa): %s' ;;
  font_miss)  echo 'no hay ninguna fuente de texto — el PNG mostrará □ en lugar de letras' ;;
  font_hint)  echo '      o bien:  export ERD_FONT=/ruta/a/la/fuente.otf' ;;
  mono_ok)    echo 'mono:   %s' ;;
  mono_miss)  echo 'no hay fuente monoespaciada — los nombres de columna se verán desalineados' ;;
  mono_hint)  echo '      o bien:  export ERD_MONO=/ruta/a/la/fuente.ttf' ;;
  s_selftest) echo '6. Prueba de regresión' ;;
  st_none)    echo 'no hay prueba de regresión en el árbol comprobado (%s) — no hay nada que medir, y una instalación que nadie ha medido no es una instalación que funcione' ;;
  st_skip)    echo 'NO se ejecutó — corrija antes los ✗ de arriba' ;;
  s_result)   echo 'Resultado' ;;
  done_ok)    echo 'instalación completada' ;;
  next)       echo '\n  Siguiente paso\n    1) abra una sesión nueva de Claude Code (las skills se leen al arrancar)\n    2) diga «dibuja el ERD», o invoque /erd\n\n  Para ejecutarlo a mano\n    cd %s/scripts\n    export ERD_PROJ=/donde/van/los/documentos\n    export ERD_PSQL='"'"'psql postgresql://user:pass@localhost:5432/mydb'"'"'\n    export ERD_DOCNAME='"'"'ERD de nuestro servicio'"'"'\n    %s introspect.py && %s merge_desc.py && %s build_erd.py && %s build_docx.py\n' ;;
  done_bad)   echo 'resuelva los ✗ de arriba y vuelva a ejecutar:  bash install.sh --check' ;;
esac; }

# ── 여기까지가 말이다 ───────────────────────────────────────────────────────
# 이 표시 위쪽은 부수효과가 없다 — 회귀 시험(scripts/selftest_install.py 의
# 'install: every message key renders in all four languages')이 여기까지를 떼어 내
# source 하고 `t` 를 네 말로 직접 부른다. 표시가 없어지면 그 시험은 조용히 통과하는
# 대신 그 자리에서 죽는다.
#### END OF MESSAGE CATALOG ####

# 모드는 하나다. 예전엔 충돌 검사 없이 마지막 것이 이겼다 — `--check --project` 가
# MODE=project 로 끝나 "아무것도 바꾸지 않는다" 고 적힌 플래그를 주고도 38개 파일을
# 썼다. 약속이 플래그 **순서**에 딸려 있으면 안 된다.
MODE=user
MODE_ARG=""
set_mode() {  # set_mode <모드> <사용자가 적은 낱말>
  if [ -n "$MODE_ARG" ] && [ "$MODE" != "$1" ]; then
    t opt_conflict "$MODE_ARG" "$2"; echo; exit 2
  fi
  MODE="$1"; MODE_ARG="$2"
}
for a in "$@"; do
  case "$a" in
    --project) set_mode project "$a" ;;
    --here)    set_mode here    "$a" ;;
    --check)   set_mode check   "$a" ;;
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
# SKILL.md 가 **있기만 하면** 통과였다. 그래서 0바이트 SKILL.md, frontmatter 를 지운
# SKILL.md, `name: totally-different` 세 판이 전부 초록이었다 — 셋 다 /erd 는 안 뜬다.
# 검사 규칙은 INSTALL.md 의 진단 순서(③)가 이미 적어 둔 그것이다: 첫 줄이 `---` 이고
# frontmatter 안에 `name: erd`. 문서가 이름 붙인 검사를 도구가 하게 한다.
skill_md_state() {  # skill_md_state <트리> → none | bad | ok
  local f="$1/SKILL.md"
  [ -f "$f" ] && [ -r "$f" ] || { echo none; return; }
  [ -s "$f" ] || { echo bad; return; }
  head -1 "$f" | tr -d '\r' | grep -qx -- '---' || { echo bad; return; }
  # 여는 --- 다음부터 **닫는 ---** 전까지가 frontmatter 다. 본문에 적힌 `name: erd`
  # (예시·설명문)는 세지 않고, 닫는 줄이 없으면 frontmatter 로 치지 않는다 — 안
  # 닫힌 블록을 본문째 읽어 주면 `---\nname: erd` 두 줄짜리 조각이 통과한다.
  # (회귀 시험 'install: --check rejects a SKILL.md without frontmatter' 의 네 번째
  #  방향이 이 자리다 — 처음 판이 여기서 초록이었다.)
  if awk 'NR==1{next}
          /^---[[:space:]]*\r?$/{closed=1; exit}
          {buf = buf $0 "\n"}
          END{if (closed) printf "%s", buf}' "$f" \
       | tr -d '\r' | grep -qE '^name:[[:space:]]*erd[[:space:]]*$'; then
    echo ok
  else
    echo bad
  fi
}

check_skill_md() {  # check_skill_md <트리> — 실패하면 FAIL 을 세운다
  case "$(skill_md_state "$1")" in
    ok)   ok "$(t skill_ok)  ($1)" ;;
    bad)  bad "$(t skill_bad "$1/SKILL.md")"; FAIL=1 ;;
    *)    bad "$(t skill_no  "$1/SKILL.md")"; FAIL=1 ;;
  esac
}

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
      # tty 가 없으면(CI·파이프) 사용자 파일을 지우지 않는다 — 거기까지는 옛 동작과
      # 같다. 달라진 것은 **그것을 성공이라 부르지 않는다**는 것이다. 예전엔 업그레이드가
      # 통째로 no-op 인데 `✓ installation complete` 가 찍혔고, `Next` 의 cd 가 설치
      # 자리가 아니라 손에 든 clone 을 가리켜 옛 판이 그대로 남은 줄을 아무도 몰랐다.
      # 사람이 "아니오" 라고 **말한** 것과 물어볼 데가 없던 것은 다른 일이다.
      if { read -r ans </dev/tty; } 2>/dev/null; then
        case "$ans" in
          [yYsS]*) rm -rf "$DEST" ;;
          *) warn "$(t place_keep)"; DEST="$SRC" ;;
        esac
      else
        echo
        bad "$(t place_noask "$DEST")"; FAIL=1; DEST="$SRC"
      fi
    fi
    if [ ! -e "$DEST" ]; then
      # 복사 실패를 안 보던 탓에 "Permission denied" 바로 다음 줄에 "✓ copied" 가
      # 찍혔다. 중간에 끊겨 SKILL.md 만 넘어가면 아래 검사도 통과해 버린다.
      if cp -R "$SRC" "$DEST"; then
        # 저장소를 clone 해서 설치하는 경우가 많다 — 스킬 폴더에 .git 을 들고 갈 이유가 없다
        rm -rf "$DEST/.git" "$DEST/__pycache__" "$DEST/scripts/__pycache__" \
               "$DEST/scripts/lang/__pycache__"
        ok "$(t place_done "$DEST")"
      else
        bad "$(t place_fail "$DEST")"; FAIL=1
      fi
    fi
  fi
  check_skill_md "$DEST"
else
  step "$(t s_place_skip "$MODE")"
  ok "$(t place_here "$SRC")"
  # --check 는 문제가 생겼을 때 돌리는 진단이다. /erd 가 목록에 안 뜨는 원인 1순위가
  # SKILL.md 이므로, 배치는 건너뛰더라도 설치돼 있어야 할 자리를 들여다본다.
  # 읽기만 하므로 "아무것도 바꾸지 않는다" 는 원칙은 그대로다.
  #
  # **트리를 하나 고르고, 고른 그 트리를 끝까지 잰다.** 예전엔 후보를 SKILL.md 가
  # 있는 첫 자리로 골랐다. 그러면 설치본의 SKILL.md 가 없어졌을 때 손에 든 clone 으로
  # 조용히 미끄러져, 이 검사가 잡으라고 만들어진 바로 그 증상만 구조적으로 못 잡았다.
  # 그래서 **디렉터리가 있는가**로 고른다 — 설치 자리가 있으면 그 자리가 검사 대상이고,
  # 그 안이 비었으면 그것이 답이다. 회귀 시험도 같은 트리에서 돈다(6번 절).
  if [ "$MODE" = check ]; then
    for d in "$HOME/.claude/skills/erd" "$PWD/.claude/skills/erd" "$SRC"; do
      [ -d "$d" ] && { DEST="$d"; break; }
    done
    check_skill_md "$DEST"
  else
    # --here 는 "놓인 자리에서" 설치한다. 그 자리가 스킬이 아니면 의존성을 다 깔아도
    # /erd 는 안 뜬다 — install.sh 한 개만 든 디렉터리에서 초록불이 뜨던 자리다.
    check_skill_md "$SRC"
  fi
fi

# ── 3. 파이썬 패키지 ────────────────────────────────────────────────────────
step "$(t s_pkg)"

# `requirements.txt` 는 이 스크립트가 pip 에 넘기는 **유일한** 목록이다. 없어도 아무도
# 안 봤다 — 패키지가 다 깔린 기계에서는 아예 안 열었고(그래서 지워도 초록불이었다),
# 안 깔린 기계에서는 **존재하지 않는 경로**를 `pip3 install -r` 로 안내했다.
# 트리는 2번 절이 고른 그 하나다. `$SRC` 로 미끄러지는 폴백은 두지 않는다 — 그 폴백이
# 바로 "clone 을 재고 설치본을 합격시키는" 자리였다.
REQ="$DEST/requirements.txt"
if [ -f "$REQ" ] && [ -r "$REQ" ]; then
  ok "requirements.txt  ($REQ)"
else
  bad "$(t pkg_no "$REQ")"; FAIL=1
fi

# 선언한 하한을 아무도 재지 않았다. `python-docx==0.8.11` (하한 1.1.0 미만) 로도
# `✓ python-docx` 가 찍히고 시험 101개가 전부 통과했다 — 그 숫자는 아무도 안 재는
# 숫자였다. 하한이 맞는지는 여기서 판정할 수 없으므로(그 판정은 실제로 옛 판을 깔아
# 봐야 한다) **선언한 값을 그대로 잰다.** 숫자의 집은 requirements.txt 하나다.
# 설치 여부도 metadata 와 import 를 둘 다 본다 — pip3 와 python3 가 다른 설치본일 때
# metadata 는 있는데 import 가 안 되는 일이 INSTALL.md 가 적어 둔 흔한 사고다.
pkg_probe() {  # pkg_probe <requirements.txt> → "상태<TAB>이름<TAB>가진것<TAB>요구"
  "$PY" - "$1" <<'PY_PROBE'
import re, sys
try:
    from importlib.metadata import PackageNotFoundError, version
except ImportError:                                    # 3.7 이하 — 여기 오지 않는다
    sys.exit(3)

IMPORT_NAME = {'python-docx': 'docx', 'pillow': 'PIL'}


def parts(v):
    out = []
    for p in re.split(r'[.+\-_]', v or ''):
        m = re.match(r'\d+', p)
        out.append(int(m.group(0)) if m else 0)
    return out


def older(have, want):
    a, b = parts(have), parts(want)
    n = max(len(a), len(b))
    return a + [0] * (n - len(a)) < b + [0] * (n - len(b))


for line in open(sys.argv[1], encoding='utf-8'):
    line = line.split('#')[0].strip()
    if not line:
        continue
    m = re.match(r'^([A-Za-z0-9._-]+)\s*(?:>=\s*([0-9][0-9A-Za-z.+_-]*))?\s*$', line)
    if not m:
        print('skip\t%s\t\t' % line)
        continue
    name, want = m.group(1), m.group(2) or ''
    mod = IMPORT_NAME.get(name.lower(), name.replace('-', '_'))
    try:
        have = version(name)
    except PackageNotFoundError:
        print('none\t%s\t\t%s' % (name, want)); continue
    except Exception:                                  # noqa: BLE001
        print('none\t%s\t\t%s' % (name, want)); continue
    try:
        __import__(mod)
    except Exception:                                  # noqa: BLE001
        print('noimp\t%s\t%s\t%s' % (name, have, want)); continue
    if want and older(have, want):
        print('old\t%s\t%s\t%s' % (name, have, want))
    else:
        print('ok\t%s\t%s\t%s' % (name, have, want))
PY_PROBE
}

need_install=0
if [ -f "$REQ" ] && [ -r "$REQ" ]; then
  probe_seen=0
  while IFS=$'\t' read -r st nm have want; do
    [ -n "$st" ] || continue
    probe_seen=1
    case "$st" in
      ok)    [ -n "$want" ] && ok "$nm $have  (>= $want)" || ok "$nm $have" ;;
      old)   bad "$(t pkg_old "$nm" "$have" "$want")"; FAIL=1 ;;
      noimp) bad "$(t imp_no)"; warn "$nm $have"; FAIL=1 ;;
      none)  warn "$(t pkg_no "$nm")"; need_install=1 ;;
      *)     warn "$(t pkg_no "$nm")"; need_install=1 ;;
    esac
  done <<EOF
$(pkg_probe "$REQ")
EOF
  # 목록을 읽었는데 줄이 하나도 안 나오면 잰 것이 없다. '요구가 없어서 통과' 와
  # '재기를 못 해서 통과' 는 다르다 — 뒤엣것은 실패다.
  if [ "$probe_seen" = 0 ]; then
    bad "$(t pkg_no "$REQ")"; FAIL=1
  fi
else
  # 목록이 없으면 무엇이 필요한지도 모른다 — 예전처럼 둘을 손으로 짚어 두긴 한다.
  $PY -c 'import docx' 2>/dev/null && ok "python-docx" || { warn "$(t pkg_no python-docx)"; need_install=1; }
  $PY -c 'import PIL'  2>/dev/null && ok "pillow"      || { warn "$(t pkg_no pillow)";      need_install=1; }
fi

if [ "$need_install" = 1 ] && { [ ! -f "$REQ" ] || [ ! -r "$REQ" ]; }; then
  # 없는 파일을 `pip3 install -r` 로 안내하지 않는다. 위에서 이미 ✗ 를 세웠다.
  :
elif [ "$need_install" = 1 ]; then
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
  # tty 가 없으면(CI·파이프) **받지 않는다.** 예전 기본값은 Y 였다 — 같은 실행에서
  # 사용자 파일은 "물어볼 수 없으니 안 건드린다" 고 보수적으로 굴면서 45MB 네트워크
  # 다운로드는 묻지도 않고 했다. 두 기본값이 반대 방향인 데는 근거가 없었고,
  # INSTALL.md 는 "**물어본 뒤** 받는다" 라고 적어 두었다. 못 물었으면 안 받는다.
  if { read -r ans </dev/tty; } 2>/dev/null; then
    case "${ans:-y}" in
      [nN]*) warn "$(t font_skip)" ;;
      *)     install_pretendard || warn "$(t font_none)" ;;
    esac
  else
    echo
    warn "$(t font_noask)"
  fi
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
# ── 6. 회귀 시험 (점검 모드에서만) ───────────────────────────────────────────
# --check 는 진단이다. 준비물이 갖춰졌다고 스킬이 도는 것은 아니므로, 실제로 한 번
# 돌려 본다. DB 없이 20초쯤 걸린다 — selftest.py 가 옆의 selftest_*.py 까지 끌어온다.
#
# 시험은 **2번 절이 고른 그 트리**에서 돈다. 예전엔 `$SRC → $DEST` 순으로 첫 번째를
# 골라, clone 을 쥔 채 `--check` 를 부르는 README 의 흐름(가장 흔한 흐름)에서 늘
# clone 이 이겼다 — SKILL.md 는 설치본을 지목해 놓고 시험은 clone 것을 돌려,
# 설치본이 `ModuleNotFoundError` 로 죽는 그 순간에 `all 101 passed` 를 찍었다.
#
# 그리고 **시험이 없으면 통과가 아니라 실패다.** 예전엔 `[ -n "$ST" ]` 가 6번 절을
# 통째로 지워, `scripts/` 를 지워도 읽기 권한만 뺏어도 "안 돌렸다" 는 한 줄 없이
# `✓ installation complete` 였다. --check 는 진단 도구다 — 잴 것이 없다는 것 자체가
# 진단 결과다.
if [ "$MODE" = check ]; then
  step "$(t s_selftest)"
  ST="$DEST/scripts/selftest.py"
  if [ ! -f "$ST" ] || [ ! -r "$ST" ]; then
    bad "$(t st_none "$ST")"
    FAIL=1
  elif [ "$FAIL" != 0 ]; then
    # 안 돌렸으면 안 돌렸다고 말한다. 침묵은 통과처럼 읽힌다.
    warn "$(t st_skip)"
  else
    # --check 는 "아무것도 바꾸지 않는다" 고 네 문서가 약속한다. 그런데 시험이 기본
    # ERD_WORK(=PROJ/erd-build)로 떨어져 **부르는 사람의 cwd** 에 erd-build/out 을
    # 만들었고, 바이트코드 캐시가 스킬 트리에 __pycache__ 를 남겼다. 임시 자리에서
    # 돌리고, 캐시는 아예 안 쓴다. 뒤는 치운다.
    st_tmp=$(mktemp -d 2>/dev/null) || st_tmp=""
    if [ -n "$st_tmp" ]; then
      out=$(cd "$st_tmp" && ERD_PROJ="$st_tmp" ERD_WORK="$st_tmp/erd-build" \
              PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX="$st_tmp/pyc" \
              "$PY" "$ST" 2>&1) && st_rc=0 || st_rc=$?
      rm -rf "$st_tmp"
    else
      out=$(PYTHONDONTWRITEBYTECODE=1 "$PY" "$ST" 2>&1) && st_rc=0 || st_rc=$?
    fi
    clean=$(printf '%s\n' "$out" | sed 's/\x1b\[[0-9;]*m//g')
    if [ "$st_rc" = 0 ]; then
      ok "$(printf '%s\n' "$clean" | tail -1)"
      # 집계 **윗줄**에 찍히는 '안 돌린 것' 을 그대로 넘긴다. `tail -1` 만 읽던 탓에
      # "6개는 진짜 서버가 있어야 해서 안 돌렸다" 가, 문서가 유일한 입구라고 못박은
      # 바로 이 자리에서만 안 보였다.
      printf '%s\n' "$clean" | awk '
        /^  [✓✗]/ { last = NR }
        { line[NR] = $0; n = NR }
        END { for (i = last + 1; i < n; i++) if (line[i] ~ /[^ ]/) print line[i] }' \
      | while IFS= read -r nt; do
          warn "$(printf '%s' "$nt" | sed 's/^[[:space:]]*//')"
        done
    else
      bad "$(printf '%s\n' "$clean" | tail -1)"
      printf '%s\n' "$clean" | grep '✗' | head -5
      FAIL=1
    fi
  fi
fi

step "$(t s_result)"
if [ "$FAIL" = 0 ]; then
  ok "$(t done_ok)"
  t next "$DEST" "$PY" "$PY" "$PY" "$PY"
else
  bad "$(t done_bad)"
  exit 1
fi
