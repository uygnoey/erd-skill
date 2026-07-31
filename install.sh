#!/usr/bin/env bash
# erd 스킬 설치 — 의존성 설치 + 스킬 배치 + 준비물 점검
#
#   bash install.sh              내 계정에 설치 (~/.claude/skills/erd)
#   bash install.sh --project    현재 프로젝트에 설치 (./.claude/skills/erd)
#   bash install.sh --here       이미 놓인 자리에서 의존성만 설치
#   bash install.sh --check      아무것도 바꾸지 않고 점검만
set -uo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MODE=user
for a in "$@"; do
  case "$a" in
    --project) MODE=project ;;
    --here)    MODE=here ;;
    --check)   MODE=check ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "모르는 옵션: $a  (--help)"; exit 2 ;;
  esac
done

ok()   { printf '  \033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '  \033[33m!\033[0m %s\n' "$*"; }
bad()  { printf '  \033[31m✗\033[0m %s\n' "$*"; }
step() { printf '\n\033[1m%s\033[0m\n' "$*"; }

FAIL=0

# ── 1. python ───────────────────────────────────────────────────────────────
step "1. Python 확인"
PY=""
for c in python3 python; do
  command -v "$c" >/dev/null 2>&1 || continue
  if "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,9) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  bad "Python 3.9 이상이 필요하다. 설치 후 다시 실행한다."
  exit 1
fi
ok "$($PY -V 2>&1)  ($(command -v "$PY"))"
[ -n "${VIRTUAL_ENV:-}" ] && ok "가상환경: $VIRTUAL_ENV"

# ── 2. 스킬 배치 ────────────────────────────────────────────────────────────
DEST="$SRC"
if [ "$MODE" = user ] || [ "$MODE" = project ]; then
  step "2. 스킬 배치"
  if [ "$MODE" = user ]; then
    BASE="$HOME/.claude/skills"
  else
    BASE="$PWD/.claude/skills"
  fi
  DEST="$BASE/erd"

  if [ "$SRC" = "$DEST" ]; then
    ok "이미 제자리다: $DEST"
  else
    mkdir -p "$BASE"
    if [ -e "$DEST" ]; then
      printf '  이미 있다: %s\n  덮어쓸까? [y/N] ' "$DEST"
      # tty 가 없으면(CI·파이프) 묻지 않고 보수적으로 건너뛴다
      { read -r ans </dev/tty; } 2>/dev/null || { ans=n; echo; }
      case "$ans" in
        [yY]*) rm -rf "$DEST" ;;
        *) warn "배치를 건너뛴다. 의존성만 설치한다."; DEST="$SRC" ;;
      esac
    fi
    if [ ! -e "$DEST" ]; then
      cp -R "$SRC" "$DEST"
      rm -rf "$DEST/__pycache__" "$DEST/scripts/__pycache__"
      ok "복사 완료: $DEST"
    fi
  fi
  [ -f "$DEST/SKILL.md" ] && ok "SKILL.md 확인" || { bad "SKILL.md 가 없다 — 스킬로 인식되지 않는다"; FAIL=1; }
else
  step "2. 스킬 배치 (건너뜀 — $MODE)"
  ok "현재 위치: $SRC"
fi

# ── 3. 파이썬 패키지 ────────────────────────────────────────────────────────
step "3. 파이썬 패키지"
need_install=0
$PY -c 'import docx' 2>/dev/null && ok "python-docx" || { warn "python-docx 없음"; need_install=1; }
$PY -c 'import PIL'  2>/dev/null && ok "pillow"      || { warn "pillow 없음";      need_install=1; }

REQ="$DEST/requirements.txt"; [ -f "$REQ" ] || REQ="$SRC/requirements.txt"

if [ "$need_install" = 1 ]; then
  if [ "$MODE" = check ]; then
    warn "--check 라 설치하지 않는다:  pip3 install -r $REQ"
    FAIL=1
  else
    echo "  설치 중:  $PY -m pip install -r $REQ"
    if $PY -m pip install -q -r "$REQ"; then
      ok "설치 완료"
    elif $PY -m pip install -q --user -r "$REQ"; then
      ok "설치 완료 (--user)"
    else
      bad "설치 실패. 가상환경을 켜거나 직접 실행한다:  $PY -m pip install -r $REQ"
      FAIL=1
    fi
    $PY -c 'import docx, PIL' 2>/dev/null && ok "import 확인" || { bad "설치했는데 import 가 안 된다 — 다른 파이썬을 쓰고 있는지 확인한다"; FAIL=1; }
  fi
fi

# ── 4. DB 클라이언트 ────────────────────────────────────────────────────────
step "4. DB 접속 수단 (둘 중 하나)"
have_db=0
command -v psql   >/dev/null 2>&1 && { ok "psql   $(psql --version 2>/dev/null | head -1)"; have_db=1; }
command -v docker >/dev/null 2>&1 && { ok "docker $(docker --version 2>/dev/null | head -1)"; have_db=1; }
if [ "$have_db" = 0 ]; then
  warn "psql 도 docker 도 없다. DB를 읽을 수 없다."
  case "$(uname -s)" in
    Darwin) echo "      brew install libpq && brew link --force libpq" ;;
    Linux)  echo "      apt install postgresql-client   # 또는  dnf install postgresql" ;;
  esac
fi

# ── 5. 폰트 ─────────────────────────────────────────────────────────────────
# 본문은 Pretendard 를 쓴다. 없으면 받아서 깔고, 그것도 안 되면 OS 기본으로 내려간다.
step "5. 렌더링 폰트"

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
  command -v curl >/dev/null 2>&1 || { warn "curl 이 없어 자동 설치를 못 한다"; return 1; }
  command -v unzip >/dev/null 2>&1 || { warn "unzip 이 없어 자동 설치를 못 한다"; return 1; }
  local tmp; tmp=$(mktemp -d) || return 1
  echo "  내려받는 중 (약 45MB): Pretendard v$PRETENDARD_VER"
  if ! curl -fsSL -m 300 -o "$tmp/p.zip" "$PRETENDARD_URL"; then
    warn "다운로드 실패 (네트워크 확인)"; rm -rf "$tmp"; return 1
  fi
  # 필요한 두 굵기만 꺼낸다 — 전체를 깔면 폰트 목록이 지저분해진다
  if ! unzip -qo -j "$tmp/p.zip" \
        'public/static/Pretendard-Regular.otf' \
        'public/static/Pretendard-Bold.otf' -d "$tmp" 2>/dev/null; then
    warn "압축 해제 실패 — 배포 구조가 바뀌었을 수 있다"; rm -rf "$tmp"; return 1
  fi
  mkdir -p "$FONT_DIR"
  mv -f "$tmp/Pretendard-Regular.otf" "$tmp/Pretendard-Bold.otf" "$FONT_DIR/" || { rm -rf "$tmp"; return 1; }
  rm -rf "$tmp"
  command -v fc-cache >/dev/null 2>&1 && fc-cache -f "$FONT_DIR" >/dev/null 2>&1
  ok "Pretendard 설치: $FONT_DIR (Regular · Bold)"
  return 0
}

KR=$(find_pretendard) || true
if [ -n "$KR" ]; then
  ok "본문:   $KR"
elif [ "$MODE" = check ]; then
  warn "Pretendard 없음 — --check 라 설치하지 않는다"
else
  printf '  Pretendard 가 없다. 지금 받아서 설치할까? (%s) [Y/n] ' "$FONT_DIR"
  # tty 가 없으면(CI·파이프) 기본값 Y — 폰트는 깔아두는 편이 낫다
  { read -r ans </dev/tty; } 2>/dev/null || { ans=y; echo; }
  case "${ans:-y}" in
    [nN]*) warn "건너뛴다 — OS 기본 한글 폰트로 그린다" ;;
    *)     install_pretendard || warn "Pretendard 없이 진행한다 — OS 기본 한글 폰트로 그린다" ;;
  esac
  KR=$(find_pretendard) || true
fi

if [ -z "$KR" ]; then   # Pretendard 가 없으면 OS 기본 한글 폰트라도 있어야 한다
  KR=$(find_font \
    /System/Library/Fonts/AppleSDGothicNeo.ttc \
    /usr/share/fonts/truetype/nanum/NanumGothic.ttf \
    /usr/share/fonts/nanum/NanumGothic.ttf \
    /usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc \
    /usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc) || true
  if [ -n "$KR" ]; then
    ok "본문(폴백): $KR"
  else
    warn "한글 폰트가 하나도 없다 — PNG의 한글이 □ 로 나온다"
    echo "      apt install fonts-nanum   /   dnf install nanum-gothic-fonts"
    echo "      또는:  export ERD_FONT=/폰트/경로.otf"
  fi
fi

MONO_F=$(find_font \
  /System/Library/Fonts/Menlo.ttc \
  /usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf \
  /usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf \
  /usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf) || true
[ -n "$MONO_F" ] && ok "고정폭: $MONO_F" || {
  warn "고정폭 폰트 없음 — 컬럼명이 어긋나 보인다"
  echo "      apt install fonts-dejavu-core"
  echo "      또는:  export ERD_MONO=/폰트/경로.ttf"
}

# ── 마무리 ──────────────────────────────────────────────────────────────────
step "결과"
if [ "$FAIL" = 0 ]; then
  ok "설치 완료"
  cat <<EOF

  다음 단계
    1) Claude Code 를 새로 띄운다 (스킬은 시작할 때 읽는다)
    2) "ERD 그려줘" 라고 하거나 /erd 를 부른다

  직접 돌릴 때
    cd $DEST/scripts
    export ERD_PROJ=/문서/저장/위치
    export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
    export ERD_DOCNAME='우리서비스 ERD'
    $PY introspect.py && $PY merge_desc.py && $PY build_erd.py && $PY build_docx.py
EOF
else
  bad "위의 ✗ 항목을 해결하고 다시 실행한다:  bash install.sh --check"
  exit 1
fi
