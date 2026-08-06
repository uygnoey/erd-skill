#!/usr/bin/env python3
"""설치 스크립트·의존성·문서 계약 회귀 시험.

    python3 selftest_install.py          여기 있는 것 전부
    python3 selftest_install.py cwd      이름에 'cwd' 가 든 것만

`selftest_kit.CASES` 에 등록된다 — `selftest.py` 를 돌리면 `load_extras()` 가 옆에
놓인 `selftest_*.py` 를 글로브로 찾아 오므로 네 파일이 한 벌로 돈다.

이번 라운드의 것은 모양이 하나로 모인다. **`--check` 가 안 한 검사를 통과로 적었다.**
잴 것이 없으면 그 사실 자체가 실패여야 하는데, 여기서는 절이 통째로 사라지고
`✓ installation complete` 만 남았다.

  · `scripts/` 가 없으면 6번 절이 출력에서 지워지고 초록불     (I1)
  · clone 을 재고 설치본을 합격시킨다                          (I2)
  · 0바이트 SKILL.md 가 "SKILL.md found"                       (I4)
  · 안 돌린 6개를 `tail -1` 이 버려 사람에게 말하지 않는다     (I-doc)

여기 담은 케이스는 전부 **가짜 HOME** 안에서만 돈다. 진짜 `~/.claude/skills/` 를
건드리면 시험이 사용자의 설치를 망가뜨리므로 그 자체가 치명 버그다. 그리고
**네트워크를 쓰지 않는다** — 폰트 설치 경로(45MB 다운로드)는 가짜 HOME 에 빈
`Pretendard-Regular.otf` 를 미리 놓아 `find_pretendard()` 가 찾게 해서 아예 안
들어간다. 그것만 믿지 않고 `curl`·`unzip` 을 가로채는 껍데기를 PATH 앞에 두고,
**부를 때마다** 한 번도 안 불렸는지 확인한다(`run_install` 의 마지막 줄) —
'안 썼다' 도 재야 하는 말이다.

맨 끝의 둘은 라운드의 것이 아니라 **문서**의 것이다. 네 언어의 `INSTALL*.md` 가
`--check` 의 예시 출력으로 보여 주는 두 숫자, 그리고 `SKILL.md`·`SKILL.ko.md` 의
실행법 블록이 적는 두 숫자를 실제 등록 수와 맞춘다. 그 자리를 재던 것이 다른 문서를
함께 읽다가 그 문서와 함께 사라져, 여섯 곳의 손으로 적은 수를 읽는 것이 하나도 없게
되었다. 여기가 `--check` 를 재는 파일이라 그 옆에 둔다.
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

from selftest_kit import Fail, HERE, case, eq, has, main


EXPECT_CASES = 12       # 등록 개수를 파일이 스스로 못박는다 (selftest_kit.load_extras)

REPO = HERE.parent
INSTALL_SH = REPO / 'install.sh'
REQ_TXT = REPO / 'requirements.txt'

# install.sh 가 말(카탈로그)의 끝에 박아 둔 표시. 여기까지는 부수효과가 없어서
# source 해도 안전하다 — 'every message key renders…' 가 그 성질을 쓴다.
CATALOG_MARK = '#### END OF MESSAGE CATALOG ####'

ANSI = re.compile(r'\x1b\[[0-9;]*m')

# 가짜 selftest.py. 진짜 것은 40초가 걸리고, 무엇보다 **다른 파일의 상태**에 따라
# 빨강이 된다 — install.sh 의 논리를 재려는 시험이 남의 회귀에 딸려 흔들리면 안 된다.
# 출력 모양만 진짜와 똑같이 흉내 낸다: 케이스 줄 → 빈 줄 → 안 돌린 것 → 집계.
#
# 콘솔 처리기도 진짜와 같이 맞춘다(selftest_kit 바닥의 `_keep_console_alive`). 이 줄이
# 없으면 ascii 로케일(LC_ALL=C)에서 이 stub 이 `✓` 를 찍다 UnicodeEncodeError 로 죽어,
# `install.sh --check` 를 재는 다섯 케이스가 **install.sh 와 무관한 이유로** 빨개졌다.
# 흉내 내는 쪽이 흉내 대상보다 약하면 그 차이가 그대로 남의 실패로 보인다.
STUB = """\
import pathlib
import sys
try:
    if sys.stdout.errors in ('strict', 'surrogateescape', 'surrogatepass'):
        sys.stdout.reconfigure(errors='backslashreplace')
except Exception:
    pass
MARK = {mark!r}
if {writes_cwd!r}:
    # 이 판이 어디서 도는지 보이게 제 cwd 에 흔적을 남긴다.
    # (`--check` 가 임시 자리로 안 옮겨 가면 이것이 부르는 사람의 cwd 에 떨어진다)
    p = pathlib.Path('erd-build/out')
    p.mkdir(parents=True, exist_ok=True)
    (p / 'marker.txt').write_text(MARK, encoding='utf-8')
print('  \\033[32m\u2713\\033[0m stub case (' + MARK + ')')
print()
print('  6 cases need a real server and were NOT run (stub ' + MARK + ').')
print('\\033[32mall 1 passed\\033[0m')
sys.exit(0)
"""

GOOD_SKILL_MD = '---\nname: erd\ndescription: stub\n---\n\n# stub\n'


# ── 가짜 홈·가짜 트리 ───────────────────────────────────────────────────────
def fake_home(root):
    """진짜 HOME 을 대신할 자리. 폰트를 미리 놓아 다운로드 경로를 아예 막는다.

    `find_pretendard()` 는 macOS 면 `~/Library/Fonts`, 그 밖이면
    `~/.local/share/fonts` 를 본다 — 어느 쪽에서 돌든 걸리게 둘 다 놓는다.
    """
    home = root / 'home'
    for d in ('Library/Fonts', '.local/share/fonts'):
        p = home / d
        p.mkdir(parents=True, exist_ok=True)
        (p / 'Pretendard-Regular.otf').write_bytes(b'')
        (p / 'Pretendard-Bold.otf').write_bytes(b'')
    return home


def shim_dir(root):
    """curl·unzip 을 가로채는 껍데기. 불리면 기록만 남기고 실패한다.

    폰트 경로를 타는 순간 여기에 줄이 하나 늘고, `run_install` 이 그것을 실패로
    친다. 네트워크를 안 쓴다는 말도 재야 하는 말이다.
    """
    d = root / 'shim'
    d.mkdir(parents=True, exist_ok=True)
    log = d / 'calls.log'
    log.write_text('', encoding='utf-8')
    for name in ('curl', 'unzip'):
        f = d / name
        f.write_text('#!/bin/sh\necho "%s $*" >> "%s"\nexit 1\n' % (name, log), encoding='utf-8')
        f.chmod(0o755)
    return d, log


def make_tree(path, skill_md=GOOD_SKILL_MD, req=None, scripts=True,
              mark='TREE', writes_cwd=False):
    """설치본 한 벌을 흉내 낸 트리. install.sh 는 **진짜 것**을 쓴다."""
    path.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INSTALL_SH, path / 'install.sh')
    if skill_md is not None:
        (path / 'SKILL.md').write_text(skill_md, encoding='utf-8')
    if req is None:
        req = REQ_TXT.read_text(encoding='utf-8')
    if req is not False:
        (path / 'requirements.txt').write_text(req, encoding='utf-8')
    if scripts:
        s = path / 'scripts'
        s.mkdir(parents=True, exist_ok=True)
        (s / 'selftest.py').write_text(
            STUB.format(mark=mark, writes_cwd=writes_cwd), encoding='utf-8')
    return path


def run_install(root, tree, *args, cwd=None, home=None, lang='en'):
    """install.sh 를 돌린다 — 늘 가짜 HOME 에서, 늘 네트워크 없이.

    부르는 사람의 `ERD_*` 는 하나도 물려받지 않는다. `ERD_LABEL` 을 켜 둔 셸에서
    `--check` 가 멀쩡한 설치를 고장 났다고 알린 적이 있다(11라운드).
    """
    home = home or fake_home(root)
    shim, log = shim_dir(root)
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e['HOME'] = str(home)
    e['ERD_LANG'] = lang
    e['PATH'] = f'{shim}:{e.get("PATH", "")}'
    e.pop('VIRTUAL_ENV', None)          # 있으면 줄이 하나 더 늘 뿐이지만 판정을 흔든다
    cwd = cwd or (root / 'elsewhere')
    cwd.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(['bash', str(tree / 'install.sh'), *args],
                       capture_output=True, text=True, encoding='utf-8', env=e, cwd=str(cwd),
                       stdin=subprocess.DEVNULL)
    r.out = ANSI.sub('', r.stdout + r.stderr)
    called = log.read_text(encoding='utf-8').strip()
    if called:
        raise Fail('install.sh reached the network in a test\n      ' + called)
    return r


def snapshot(path):
    """디렉터리 한 그루를 경로+내용 해시로 찍는다 (바이트까지 같은지 보려고)."""
    out = {}
    for p in sorted(path.rglob('*')):
        rel = str(p.relative_to(path))
        if p.is_dir():
            out[rel + '/'] = 'dir'
        else:
            out[rel] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def must_fail(r, what):
    if r.returncode == 0:
        raise Fail(f'{what}\n      exit 0 and this output:\n{r.out}')
    if 'installation complete' in r.out:
        raise Fail(f'{what}\n      it printed "installation complete":\n{r.out}')


def must_pass(r, what):
    if r.returncode != 0:
        raise Fail(f'{what}\n      exit {r.returncode} and this output:\n{r.out}')


# ── I1 · 잴 것이 없으면 통과가 아니라 실패다 ────────────────────────────────
@case('install: --check on a tree with no scripts/ exits non-zero')
def _(work):
    """`[ -n "$ST" ]` 가 6번 절을 통째로 지웠다 — `scripts/` 를 지워도, 읽기 권한만
    뺏어도 "안 돌렸다" 는 한 줄 없이 `✓ installation complete` / exit 0 이었다.
    스킬은 완전히 죽어 있는데 진단 도구는 초록불이었다."""
    root = work.parent
    tree = make_tree(root / 'tree', scripts=False)
    r = run_install(root, tree, '--check')
    must_fail(r, '--check passed a tree with no scripts/ at all')
    has(r.out, 'Regression test', 'the section must appear even when there is nothing '
                                 'to run — a vanished section reads as a pass')
    has(r.out, 'nothing to measure', 'it must say why it could not measure')

    # 같은 부류의 나머지 절반: 있는데 **못 읽는** 것. 지우는 것만 막으면 반만 고친 것이다.
    if os.geteuid() == 0:
        # root 로 돌면 권한이 무의미해 이 반쪽은 잴 수 없다. 안 잰 것을 통과로 적지
        # 않으려고 여기 적어 둔다 — 위의 '삭제' 쪽은 그대로 쟀다.
        return
    t2 = make_tree(root / 'tree2')
    (t2 / 'scripts').chmod(0o000)
    try:
        r2 = run_install(root, t2, '--check')
        must_fail(r2, '--check passed a tree whose scripts/ cannot be read')
    finally:
        (t2 / 'scripts').chmod(0o755)


# ── I2 · 하나의 트리를 골라 그 트리를 끝까지 잰다 ───────────────────────────
@case('install: --check run from the clone reports the installed tree, not the clone')
def _(work):
    """README 가 안내하는 흐름은 `git clone` 뒤 `bash erd-skill/install.sh` 다. 즉
    사용자는 clone 을 쥔 채 `--check` 를 부른다. 그런데 회귀 시험 후보가
    `$SRC → $DEST` 순이라 **늘 clone 이 이겼다** — SKILL.md 는 설치본을 지목해 놓고
    시험은 clone 것을 돌려, 설치본이 ModuleNotFoundError 로 죽는 그 순간에
    `all 101 passed` 를 찍었다."""
    root = work.parent
    home = fake_home(root)
    installed = make_tree(home / '.claude/skills/erd', mark='INSTALLED')
    clone = make_tree(root / 'clone', mark='CLONE')

    r = run_install(root, clone, '--check', home=home)
    must_pass(r, 'a healthy installed tree should check out clean')
    has(r.out, 'INSTALLED', 'the regression test must run in the installed tree')
    if 'CLONE' in r.out:
        raise Fail('--check ran the clone\'s regression test, not the installed one\n'
                   + r.out)
    has(r.out, str(installed), 'the SKILL.md line must name the tree it measured')

    # 시험을 도는 자리와 SKILL.md 를 찾은 자리가 같아야 한다. 설치본의 시험만
    # 없애면, 손에 든 clone 에 멀쩡한 시험이 있어도 실패여야 한다.
    (installed / 'scripts' / 'selftest.py').unlink()
    r2 = run_install(root, clone, '--check', home=home)
    must_fail(r2, 'the installed tree lost its regression test but --check was green')
    if 'CLONE' in r2.out:
        raise Fail('--check fell back to the clone instead of failing\n' + r2.out)

    # 반대쪽도 막는다: 설치본에 SKILL.md 가 아예 없으면 clone 으로 미끄러지지 않는다.
    # 이 검사가 있는 이유가 바로 '/erd 가 목록에 안 뜬다' 인데, 폴백 때문에 그 증상만은
    # 구조적으로 못 잡고 있었다.
    home2 = fake_home(root / 'b')
    inst2 = make_tree(home2 / '.claude/skills/erd', mark='INSTALLED2')
    (inst2 / 'SKILL.md').unlink()
    r3 = run_install(root, clone, '--check', home=home2)
    must_fail(r3, 'the installed tree has no SKILL.md but --check was green')
    has(r3.out, str(inst2), 'it must name the installed tree, not the clone')


# ── I4 · 있기만 하면 통과였다 ───────────────────────────────────────────────
@case('install: --check rejects a SKILL.md without frontmatter')
def _(work):
    """`[ -f "$DEST/SKILL.md" ]` — 존재만 봤다. 2라운드가 "`--check` 가 SKILL.md 를
    안 본다" 를 잡았고 그 수정이 넣은 것이 이 `-f` 한 줄인데, **같은 부류의 나머지
    절반**이 남아 있었다. 셋 다 /erd 는 안 뜨는데 셋 다 초록/exit 0 이었다.

    검사 규칙은 INSTALL.md 가 진단 순서 ③ 으로 이미 적어 둔 그것이다 — 문서가 이름
    붙인 검사를 도구가 하게 한다."""
    root = work.parent
    broken = {
        'empty': '',
        'no frontmatter': '# ERD generation\n\nname: erd is only in the body here.\n',
        'wrong name': '---\nname: totally-different\ndescription: x\n---\n\n# x\n',
        'no closing fence': '---\nname: erd\n',
    }
    for label, text in broken.items():
        tree = make_tree(root / ('bad_' + label.replace(' ', '_')), skill_md=text)
        r = run_install(root, tree, '--check')
        must_fail(r, f'--check accepted a SKILL.md that is {label}')
        has(r.out, 'not a skill file', f'({label}) it must say what is wrong')

    # **이빨이 남아 있는지**도 같이 본다. 늘 실패하는 검사는 검사가 아니다 —
    # 12라운드가 '조건이 늘 거짓이라 아무것도 못 잡는 단정' 을 찾아냈다.
    good = make_tree(root / 'good')
    must_pass(run_install(root, good, '--check'),
              'a real SKILL.md must still pass — an always-red check is not a check')
    # 진짜 SKILL.md 도 통과해야 한다 (규칙이 이 저장소 것과 어긋나지 않는지).
    real = make_tree(root / 'real',
                     skill_md=(REPO / 'SKILL.md').read_text(encoding='utf-8'))
    must_pass(run_install(root, real, '--check'),
              "the repository's own SKILL.md must satisfy the rule")


# ── I3 · 말에 딸린 버그는 한 언어만 보면 안 보인다 ──────────────────────────
@case('install: every message key renders in all four languages')
def _(work):
    """bash 내장 `printf` 는 형식 문자열이 `-` 로 시작하면 **제 옵션으로** 읽는다.
    `pkg_check` 가 en·ko·ja 에서 `--check…` 로 시작해, 패키지가 없는 환경에서
    무엇을 어떻게 깔라고 알려 주는 바로 그 한 줄이 사라지고 사용법 오류가 대신
    찍혔다. es 만 문장이 `con` 으로 시작해 무사했다.

    그래서 한 키만 보지 않고 **네 말 × 모든 키**를 실제로 렌더링해 본다. 자리표시자
    개수가 말끼리 어긋나는 것도 같이 본다 — `next` 는 인자를 다섯 받는다."""
    root = work.parent
    src = INSTALL_SH.read_text(encoding='utf-8')
    if CATALOG_MARK not in src:
        raise Fail(f'install.sh no longer has {CATALOG_MARK!r} — this case could not '
                   f'isolate the catalog, so it measured nothing')
    sh = root / 'catalog.sh'
    sh.write_text(src.split(CATALOG_MARK)[0], encoding='utf-8')

    def keys(lang):
        m = re.search(r'^_t_%s\(\) \{ case "\$1" in$(.*?)^esac; \}$' % lang,
                      src, re.S | re.M)
        if not m:
            raise Fail(f'_t_{lang}() not found in install.sh')
        return [k for k in re.findall(r'^\s{2}([a-z_]+)\)', m.group(1), re.M)]

    def sh_call(lang, script, *args):
        e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
        e['ERD_LANG'] = lang
        return subprocess.run(['bash', '-c', script, '_', str(sh), *args],
                              capture_output=True, text=True, encoding='utf-8', env=e)

    en = keys('en')
    if len(en) < 40:
        raise Fail(f'only {len(en)} keys parsed out of _t_en — the parse is broken, '
                   f'so this case would silently check almost nothing')
    for lang in ('ko', 'ja', 'es'):
        eq(sorted(keys(lang)), sorted(en), f'_t_{lang}() key set')

    for key in en:
        want = None
        for lang in ('en', 'ko', 'ja', 'es'):
            raw = sh_call(lang, '. "$1"; _t_%s "$2"' % lang, key).stdout
            n = len(re.findall(r'%[sd]', raw))
            if want is None:
                want = n
            elif n != want:
                raise Fail(f'{key}: en takes {want} argument(s) but {lang} takes {n}'
                           f'\n      {lang}: {raw.strip()!r}')
            args = [f'ARG{i}' for i in range(1, n + 1)]
            r = sh_call(lang, '. "$1"; shift; k="$1"; shift; t "$k" "$@"', key, *args)
            trouble = r.stdout + r.stderr
            for bad in ('invalid option', 'usage: printf', 'not found'):
                if bad in trouble:
                    raise Fail(f'{lang}/{key} did not render — {bad!r}\n'
                               f'      out: {r.stdout!r}\n      err: {r.stderr!r}')
            if r.returncode != 0 or r.stderr.strip():
                raise Fail(f'{lang}/{key} exited {r.returncode}: {r.stderr!r}')
            if not r.stdout.strip():
                raise Fail(f'{lang}/{key} rendered to nothing')
            for a in args:
                if a not in r.stdout:
                    raise Fail(f'{lang}/{key} swallowed {a}: {r.stdout!r}')


# ── I5 · "아무것도 바꾸지 않는다" 는 약속 ───────────────────────────────────
@case("install: --check leaves the caller's cwd byte-identical")
def _(work):
    """`install.sh:7`·`INSTALL.md:32`·`INSTALL.ko.md:101`·`README.md:86` 이 전부
    "change nothing / 아무것도 바꾸지 않고" 라고 적어 두었는데, 회귀 시험이 기본
    `ERD_WORK`(=PROJ/erd-build)로 떨어져 **부르는 사람의 cwd** 에 `erd-build/out` 을
    만들었고 바이트코드 캐시가 스킬 트리에 `__pycache__` 를 남겼다.

    가짜 시험이 일부러 제 cwd 에 흔적을 남긴다 — `--check` 가 임시 자리로 안 옮겨
    가면 그 흔적이 여기 아래에 떨어진다. 이 케이스에 이빨을 주는 것이 그 한 줄이다."""
    root = work.parent
    tree = make_tree(root / 'tree', writes_cwd=True)
    caller = root / 'caller'
    caller.mkdir(parents=True, exist_ok=True)
    (caller / 'mine.txt').write_text('do not touch', encoding='utf-8')

    before_cwd, before_tree = snapshot(caller), snapshot(tree)
    r = run_install(root, tree, '--check', cwd=caller)
    must_pass(r, '--check should be green on a healthy tree')
    after_cwd, after_tree = snapshot(caller), snapshot(tree)

    if before_cwd != after_cwd:
        new = sorted(set(after_cwd) - set(before_cwd))
        gone = sorted(set(before_cwd) - set(after_cwd))
        raise Fail(f"--check wrote into the caller's cwd\n"
                   f'      new: {new}\n      gone: {gone}')
    if before_tree != after_tree:
        new = sorted(set(after_tree) - set(before_tree))
        raise Fail(f'--check wrote into the skill tree it was checking\n'
                   f'      new: {new}')


# ── I6 · 약속이 플래그 순서에 딸려 있으면 안 된다 ───────────────────────────
@case('install: --check never writes, whatever else is on the command line')
def _(work):
    """`--check --project` 는 충돌 검사가 없어 마지막 것이 이겼다 — MODE=project 로
    끝나 "아무것도 바꾸지 않는다" 고 적힌 플래그를 주고도 38개 파일을 썼다."""
    root = work.parent
    for order in (('--check', '--project'), ('--project', '--check'),
                  ('--check', '--here'), ('--here', '--check')):
        tree = make_tree(root / ('t_' + '_'.join(o.strip('-') for o in order)))
        home = fake_home(root / ('h_' + '_'.join(o.strip('-') for o in order)))
        caller = root / ('c_' + '_'.join(o.strip('-') for o in order))
        caller.mkdir(parents=True, exist_ok=True)
        r = run_install(root, tree, *order, cwd=caller, home=home)
        if r.returncode == 0:
            raise Fail(f'{" ".join(order)} was accepted instead of rejected\n{r.out}')
        for wrote in (caller / '.claude', home / '.claude'):
            if wrote.exists():
                raise Fail(f'{" ".join(order)} installed into {wrote} — '
                           f'"--check changes nothing" must not depend on flag order')


# ── I8 · 실패한 복사 뒤에 "copied" 가 찍혔다 ────────────────────────────────
@case('install: a failed copy never prints "copied"')
def _(work):
    """`cp -R` 의 결과를 안 봐서 "Permission denied" 바로 다음 줄에 "✓ copied" 가
    찍혔다. 이번 판은 다음 줄의 SKILL.md 검사가 받아 내지만 그 그물이 SKILL.md
    하나뿐이라, 복사가 중간에 끊겨 SKILL.md 는 넘어가고 `scripts/` 가 안 넘어가면
    I1 과 합쳐져 전부 초록이 된다."""
    root = work.parent
    if os.geteuid() == 0:
        # root 는 권한을 무시하므로 복사가 실패하지 않는다 — 이 케이스는 root 로는
        # 잴 수 없다. 안 잰 것을 통과로 적지 않으려고 그 사실을 여기 적는다.
        raise Fail('running as root: cp cannot be made to fail, so this case cannot '
                   'measure anything — run the suite as a normal user')
    tree = make_tree(root / 'tree')
    home = fake_home(root)
    base = home / '.claude' / 'skills'
    base.mkdir(parents=True, exist_ok=True)
    base.chmod(0o500)                    # 있는데 못 쓴다 → mkdir -p 는 통과, cp 가 실패
    try:
        r = run_install(root, tree, home=home)          # 기본 모드 = user
    finally:
        base.chmod(0o755)
    must_fail(r, 'a copy that failed was reported as a finished install')
    if 'copied:' in r.out:
        raise Fail('it printed "copied:" after the copy failed\n' + r.out)
    has(r.out, 'copy failed', 'it must say the copy failed')


# ── I11 · --here 가 스킬 아닌 자리에서 초록불 ───────────────────────────────
@case('install: --here in a non-skill directory exits non-zero')
def _(work):
    """SKILL.md 확인이 `MODE=check` 안에만 있어서, `install.sh` 한 개만 든
    디렉터리에서 `--here` 가 `✓ installation complete` / exit 0 이었다. 의존성을
    다 깔아도 그 자리는 스킬이 아니므로 /erd 는 안 뜬다."""
    root = work.parent
    bare = root / 'bare'
    bare.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INSTALL_SH, bare / 'install.sh')
    r = run_install(root, bare, '--here')
    must_fail(r, '--here was green in a directory that holds only install.sh')
    has(r.out, 'SKILL.md', 'it must name what is missing')

    # 이빨: 제대로 놓인 자리에서는 여전히 통과해야 한다.
    tree = make_tree(root / 'tree')
    must_pass(run_install(root, tree, '--here'),
              '--here must still pass on a real skill directory')


# ── I-doc · 안 돌린 것을 사람에게 말한다 ────────────────────────────────────
@case('install: --check reports the cases the regression test did not run')
def _(work):
    """`tail -1` 만 읽어, `selftest.py` 가 집계 **윗줄**에 찍는
    `N cases … were NOT run` 을 버렸다. SKILL.md 는 "안 돌린 개수는 집계 윗줄에
    매번 찍힌다" 고 적는데, 문서가 유일한 입구라고 못박은 `--check` 에서는 그 줄만
    안 보였다 — 안 한 검사를 통과로 적는 그 부류다."""
    root = work.parent
    tree = make_tree(root / 'tree', mark='NOTE')
    r = run_install(root, tree, '--check')
    must_pass(r, '--check should be green on a healthy tree')
    has(r.out, 'all 1 passed', 'the tally must still be shown')
    has(r.out, 'were NOT run', 'the "not run" line above the tally must reach the user')
    has(r.out, 'stub NOTE', 'the whole note must come through, not a truncated one')


# ── I9 · 아무도 안 재는 숫자 ────────────────────────────────────────────────
@case('install: --check measures the version floor in requirements.txt')
def _(work):
    """`import docx` 만 봤다. `python-docx==0.8.11`(선언 하한 1.1.0 미만)에서도
    `✓ python-docx` 가 찍히고 시험이 전부 통과했다 — 그 하한은 **아무도 안 재는
    숫자**였다. 하한이 옳은지는 여기서 판정할 수 없으므로(옛 판을 실제로 깔아 봐야
    한다) 선언한 값을 그대로 잰다. 숫자의 집은 requirements.txt 하나다.

    실제로 옛 python-docx 를 설치해 보지는 **않는다** — 시험이 사용자의 파이썬
    환경을 바꾸면 안 되고 네트워크도 못 쓴다. 대신 하한만 올려 같은 자리를 지난다."""
    root = work.parent
    # (a) 절대 만족할 수 없는 하한 → 반드시 빨강
    high = make_tree(root / 'high', req='python-docx>=99.0.0\npillow>=99.0.0\n')
    r = run_install(root, high, '--check')
    must_fail(r, 'a version floor nobody can satisfy was reported as fine')
    has(r.out, '99.0.0', 'it must name the floor it measured')
    has(r.out, 'too old', 'it must say the installed version is too old')

    # (b) 만족하는 하한 → 초록이어야 한다 (늘 빨간 검사는 검사가 아니다)
    low = make_tree(root / 'low', req='python-docx>=0.0.1\npillow>=0.0.1\n')
    must_pass(run_install(root, low, '--check'),
              'a floor the machine satisfies must still pass')

    # (c) requirements.txt 자체가 없으면 — 예전엔 초록이었고, 패키지가 없는 기계에서는
    #     **존재하지 않는 경로**를 `pip3 install -r` 로 안내했다.
    gone = make_tree(root / 'gone', req=False)
    r3 = run_install(root, gone, '--check')
    must_fail(r3, 'a tree with no requirements.txt was reported as a finished install')
    has(r3.out, 'requirements.txt', 'it must name the file that is missing')


# ── 문서가 적은 케이스 수 ───────────────────────────────────────────────────
# 파일 이름은 install 이지만 담긴 것은 문서다 — 네 언어의 설치 문서가 보여 주는 예시
# 출력이 바로 `install.sh --check` 의 마지막 두 줄이고, 그 두 줄을 만드는 것이 이
# 파일이 재고 있는 그 명령이기 때문이다. `SKILL*.md` 의 실행법 블록도 같은 부류라
# 바로 옆에 둔다(아래 두 번째 케이스).
#
# 같은 숫자가 여섯 군데에 손으로 적혀 있고, 그중 하나만 고쳐도 아무 데서도 빨강이
# 뜨지 않았다. 그래서 숫자를 여기 하드코딩하지 않고 **규칙**으로 잰다: 문서가 적은
# 수는 이 벌이 실제로 등록한 수와 같아야 한다. 라운드가 케이스를 늘리면 이 케이스가
# 빨개지고, 그때 문서를 함께 고치면 된다.
INSTALL_DOCS = ('INSTALL.md', 'INSTALL.ko.md', 'INSTALL.ja.md', 'INSTALL.es.md')
SKILL_DOCS = ('SKILL.md', 'SKILL.ko.md')


def case_defs(path):
    """파일 하나에 `@case(...)` 가 붙은 함수가 몇 개인지 — 소스를 AST 로 센다.

    등록된 목록을 세는 것과 **다른 근거**다. 세는 쪽과 세어지는 쪽이 같은 값을 보면
    어긋나도 자기일관이라 조용하다(`selftest_schema` 의 도커 개수가 그 자리였다).
    """
    import ast
    tree = ast.parse(path.read_text(encoding='utf-8'))
    return sum(1 for n in ast.walk(tree)
               if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
               and any(isinstance(d, ast.Call) and getattr(d.func, 'id', '') == 'case'
                       for d in n.decorator_list))


def _history_module():
    """`selftest_schema` 의 모듈 객체 — 어느 입구로 들어왔든 같은 것을 집는다.

    여기가 `import selftest_schema as hist` 였고, 그 한 줄이 `python3
    selftest_schema.py` 를 통째로 빨갛게 만들었다. 그 입구로 들어오면 그 파일은
    이미 `__main__` 으로 40개를 등록한 상태인데, 제 이름으로 다시 import 하면 **같은
    파일이 두 번째 모듈**이 되어 40개를 또 올리고 이름 중복 검사가 죽인다.
    `selftest_kit.load_extras()` 가 `p.resolve() != _self` 로 일부러 피하는 자리를
    이 import 가 뒤로 돌아 들어가 우회한 것이다.

    그래서 새로 부르지 않는다 — **`_DB_CASES` 를 들고 있는 쪽**을 고른다. 리터럴
    `6` 으로 적지 않는 이유는 그 수가 `_register_db_cases()` 를 세어 나오는 값이라,
    도커 케이스가 늘면 여기만 조용히 틀리기 때문이다.
    """
    for mod in (sys.modules.get('selftest_schema'), sys.modules.get('__main__')):
        if hasattr(mod, '_DB_CASES'):
            return mod
    raise Fail('neither selftest_schema nor __main__ holds _DB_CASES — the number of '
               'cases that need a real server could not be read, so this case measured '
               'nothing')


def suite_counts():
    """문서가 인용하는 세 수 — (집계에 찍히는 수, 안 돌린 수, 입구 파일 몫을 뺀 수).

    도커 케이스는 서버가 있어야만 등록되고, 등록되면 이름이 `db: ` 로 시작한다.
    문서의 `all N passed` 는 **서버 없이** 돈 판의 수이므로 그 여섯을 뺀다 —
    `selftest.py` 의 `TOTAL_FLOOR` 가 쓰는 규칙과 같다. 여섯은 집계 **윗줄**에 따로
    찍히고 문서도 그 줄을 따로 적으므로, 두 수를 따로 돌려준다.

    셋째는 `python3 selftest_schema.py` 로 들어왔을 때 도는 수다. 그 입구는 제 파일
    것만 도는 것이 아니라 글로브에 걸리는 옆 파일을 전부 함께 올린다 — 걸리지 않는
    것은 입구 파일 `selftest.py` 하나뿐이라, 총계에서 그 몫을 뺀 값이다.
    """
    import selftest_kit as kit

    kit.load_extras()      # 이 파일만 직접 돌려도 옆의 것이 함께 올라온다
    ran = sum(1 for n, _f in kit.CASES if not n.startswith('db: '))
    # 입구 파일(`selftest.py`)은 글로브 `selftest_*.py` 에 걸리지 않는다. 그 파일을
    # 돌리는 중이면 그 몫이 이미 CASES 에 있고, 이 파일만 직접 돌리면 통째로 빠져
    # 있다 — 빠진 채로 재면 이 케이스가 보는 수가 사용자가 보는 수와 달라져, 문서를
    # 지켜 주는 척만 하게 된다. 빠졌으면 소스에서 세어 채운다.
    entry = HERE / 'selftest.py'
    if not entry.exists():
        raise Fail(f'{entry.name} is missing — the file that prints the tally the '
                   f'documents quote is not there, so this case measured nothing')
    own = case_defs(entry)
    main_file = getattr(sys.modules.get('__main__'), '__file__', '') or ''
    if 'selftest' not in sys.modules and os.path.basename(main_file) != entry.name:
        ran += own
    return ran, _history_module()._DB_CASES, ran - own


def fenced_spans(body):
    """``` / ~~~ 로 열고 닫은 블록의 (시작, 끝) 오프셋 목록.

    구멍 4 에 대한 판단이 여기 있다. 이전 판은 `re.findall` 로 **파일 전체**를 훑어,
    예시 출력 블록에서 그 줄이 사라져도 같은 문구가 파일 어딘가에 남아 있으면 초록
    이었다(줄을 통째로 지우는 것은 잡았다). 잰다고 말한 것은 '문서가 보여 주는 예시
    출력' 인데 실제로 재던 것은 '파일 어딘가의 문자열' 이라, 그만큼은 재는 척이다.

    그래서 **자리까지 잰다.** 여기가 대는 것은 울타리의 위치뿐이다 — 터미널 출력
    예시는 어느 언어판에서도 코드 블록으로 적히므로, '코드 블록 안일 것' 만으로도
    숫자가 산문으로 새어 나가는 우회는 막히고 문서를 재구성해도 거짓 빨강이 없다.

    다만 그것만으로는 **어느 블록인지**가 안 잡힌다. 얼마나 더 못박을지는 자리마다
    다르므로 여기서 정하지 않고 부르는 쪽에 둔다 — 줄머리의 `✓`·`!` 표를 정규식에
    함께 넣는 것과 `same_block()` 이 그 판단이다.
    """
    spans, open_at, mark = [], None, None
    for m in re.finditer(r'(?m)^[ \t]*(```|~~~)', body):
        if open_at is None:
            open_at, mark = m.end(), m.group(1)
        elif m.group(1) == mark:
            spans.append((open_at, m.start()))
            open_at, mark = None, None
    return spans


def doc_numbers(name, pattern, what):
    """`name` 안에서 `pattern` 의 첫 그룹을 정수로 — **코드 블록 안의 것만** 센다.

    돌려주는 것은 `(수, 몇 번째 블록에서 나왔는가)` 의 목록이다. 부르는 쪽이 두 수가
    **같은 블록** 안에 있기를 요구할 수 있어야 하기 때문이다 — 왜 그 요구가 필요한
    자리와 필요 없는 자리가 갈리는지는 `same_block()` 에 적었다.

    하나도 못 찾으면 실패다. 문서가 그 줄을 잃은 것도 결함이고, 못 찾은 채 통과하면
    이 케이스는 아무것도 안 잰 것이 된다.
    """
    p = REPO / name
    if not p.exists():
        raise Fail(f'{name} is missing — it is part of the skill, and a case that '
                   f'measures nothing must not pass')
    body = p.read_text(encoding='utf-8')
    spans = fenced_spans(body)
    got = [(int(m.group(1)), i) for m in re.finditer(pattern, body)
           for i, (a, b) in enumerate(spans) if a <= m.start() < b]
    if not got:
        loose = re.search(pattern, body)
        raise Fail(f'{name} no longer shows {what} inside a code block' +
                   (' (the text is still in the file, but outside every fence — a '
                    'number in prose is not the example output this measures)'
                    if loose else ''))
    return got


def same_block(name, first, second, what):
    """`doc_numbers()` 가 돌려준 두 무리가 **한 블록** 안에서 만나는지.

    `fenced_spans()` 는 '코드 블록 안' 까지만 봤고 **어느 블록인지**는 안 봤다. 그
    틈으로 이런 우회가 통과했다(실측): `INSTALL.md` 의 `✓ all 201 passed` 와
    `! 6 cases …` 두 줄을 통째로 지우고, 문서 맨 위 설치 명령 bash 블록에 같은 수를
    한 줄로 적어 넣으면 초록이었다. `--check` 예시 출력이 사라졌는데 초록이다.

    두 수가 **한 판의 출력에서 위아래로 붙어 나오는 것**일 때만 이 요구가 옳다.
    서로 다른 블록에 흩어져 있다면 그것은 재겠다고 말한 그 출력이 아니기 때문이다.
    반대로 각 줄이 **명령 자체**를 달고 있어 어디에 있든 뜻이 서는 자리(`SKILL*.md`
    의 실행법)에는 걸지 않는다 — 거기서는 블록이 갈려도 문서가 거짓이 되지 않아,
    문서 구조에 케이스를 묶는 값만 남는다.
    """
    if not ({b for _n, b in first} & {b for _n, b in second}):
        raise Fail(f'{name} shows {what} in different code blocks — they are two lines '
                   f'of one example output, so a number that drifted out of that block '
                   f'is no longer the output this measures')


@case('install: the case counts the INSTALL documents state are the counts a run produces')
def _(work):
    """네 언어의 설치 문서가 `install.sh --check` 의 예시 출력으로 보여 주는 두
    숫자를 잰다 — 집계 줄의 `all N passed` 와 그 아랫줄의 `N cases need a real
    server`. `selftest.py` 자신은 안 돌린 수를 집계 **위**에 찍지만, `install.sh` 는
    집계(`tail -1`)를 먼저 넘기고 남은 줄을 뒤에 붙이므로 문서에는 아래에 온다.

    네 곳에 같은 수가 손으로 적혀 있고 그것을 읽는 것이 하나도 없었다. 문서만 보는
    사람에게 그 줄은 '이 설치가 성공하면 무엇이 나오는가' 의 유일한 근거이므로,
    조용히 틀린 수는 그대로 조용한 거짓말이 된다.

    **넷을 다 본다.** 하나만 보면 나머지 셋이 어긋나도 초록이다.

    자리도 함께 못박는다 — 아래 두 정규식은 `install.sh` 의 `ok`/`warn` 이 붙이는
    `✓`·`!` 표까지 요구하고, 두 매치가 **같은 코드 블록** 안에서 나와야 한다. 표도
    두 줄도 프로그램이 찍는 영문 출력이라 네 언어판이 글자까지 같다(실측 확인).
    이것이 없으면 예시 출력을 통째로 지우고 다른 블록에 수만 적어 넣는 우회가 그대로
    통과한다 — `same_block()` 에 그 실측을 적어 두었다."""
    ran, db, _outside = suite_counts()
    # 이빨: 등록을 못 읽었으면 아래 대조가 전부 통과가 된다. 잴 것이 잡혔는지 먼저
    # 못박는다 — 이 벌은 백 개가 넘고, 안 돌린 것은 최소 하나다.
    if ran < 100 or db < 1:
        raise Fail(f'the counts came out as {ran}/{db} — this case could not read the '
                   f'registry, so it measured nothing')

    seen = set()
    for name in INSTALL_DOCS:
        tally = doc_numbers(name, r'(?m)^[ \t]*✓[ \t]+all (\d+) passed',
                            'a "✓ all N passed" example line')
        skipped = doc_numbers(name,
                              r'(?m)^[ \t]*![ \t]+(\d+) cases need a real server',
                              'the "! N cases need a real server" line that install.sh '
                              '--check prints below the tally')
        for n, _b in tally:
            eq(n, ran, f'{name} 의 예시 출력 (all N passed)')
        for n, _b in skipped:
            eq(n, db, f'{name} 의 안 돌린 개수')
        same_block(name, tally, skipped,
                   'the "all N passed" tally and the "N cases need a real server" line')
        seen.add(name)
    # 이빨: 여기가 `eq(seen, 4)` 였고 `seen` 은 **루프를 돈 횟수**였다 — 목록이
    # `('INSTALL.md',) * 4` 여도 4 라서, 개명 중 오타 하나로 스페인어판이 영영 안
    # 읽히는 채 초록일 수 있었다. 읽은 **이름의 집합**을 저장소에 실제로 있는
    # `INSTALL*.md` 전부와 맞춘다. 언어판이 하나 늘어도 여기서 빨개진다.
    on_disk = {p.name for p in REPO.glob('INSTALL*.md')}
    if len(on_disk) < 4:
        raise Fail(f'the repository holds only {sorted(on_disk)} — the skill ships four '
                   f'install documents, so something was lost')
    if seen != on_disk:
        raise Fail(f'this case read {sorted(seen)} but the repository holds '
                   f'{sorted(on_disk)} — every install document must be measured, or '
                   f'the unread one drifts quietly')


@case('install: the case counts SKILL.md and SKILL.ko.md state are the counts a run produces')
def _(work):
    """`SKILL*.md` 의 실행법이 주석으로 적는 세 수를 잰다 — `python3 selftest.py`
    옆의 전체 개수, `python3 selftest_schema.py` 옆의 개수, 그리고
    `ERD_SELFTEST_DOCKER=1 python3 selftest.py` 옆의 도커 개수.

    바로 위 케이스가 설치 문서 넷을 지키게 된 뒤에도 이 자리는 아무도 안 보고
    있었다. 실제로 `101` 과 `39` 가 남아 있었다 — `199` 시절보다도 오래된 수라, 앞
    라운드가 `grep "199\\|200"` 으로 훑었을 때도 걸리지 않았다. 손으로 적은 수를
    손으로 찾는 것은 이렇게 실패하므로, 같은 부류의 자리는 같은 규칙으로 잰다.

    `39` 쪽은 수만 낡은 것이 아니었다. `그 파일 것 39개만` 이라는 문장은 적힐 당시
    (`c391783`) 에는 **참이었다** — 그때 `scripts/` 에 있던 시험 파일은
    `selftest.py`·`selftest_schema.py`·`selftest_kit.py` 셋뿐이라 글로브에 걸려
    함께 올라올 옆 파일이 없었다(`git ls-tree` 로 확인). `64b643d` 가
    `selftest_r14_*` 넷을 더하면서 그 입구가 옆 파일까지 돌게 되어 문장이 거짓이 됐고
    아무도 안 고쳤다. 그래서 고칠 때 수만 바꾸지 않고 문장을 함께 바꿨다.

    주석에서 **첫 번째 숫자**를 집는다. 언어판마다 어순이 달라 낱말에 못을 박을 수
    없기 때문이다(`# everything (201 cases)` · `# 전부 (201개)`). 뒤따르는 `(10초쯤)`
    같은 수는 그래서 안 걸린다.

    도커 줄도 같은 규칙으로 잰다. 이전 판은 '한 줄에 `postgres:16-alpine` 이 함께
    있어 첫 숫자 규칙이 16 을 집는다' 고 적고 이 자리를 뺐는데, **그 서술이 틀렸다**
    — 두 언어판 모두 `6` 이 `16` 보다 앞에 있어 비탐욕 매치가 `6` 을 문다(정규식을
    실제로 돌려 확인했다: `# + the 6, on postgres:16-alpine …` · `# 6개까지
    (postgres:16-alpine …)`). 잴 수 있는 자리를 못 잰다고 적고 비워 둔 것이라
    되살린다.

    산문 쪽 둘(`Six more cases …` · `6개가 더 …`)은 안 잰다. 영어판이 그 수를
    **낱말로** 적어(`Six`) 숫자를 찾는 규칙에 아예 안 걸리기 때문이다 — 언어마다
    수사 표를 두면 잴 수는 있지만, 그것은 번역문의 표기법에 케이스를 묶는 것이다.
    그래서 이 케이스가 지키는 것은 **코드 블록 안의 세 자리**뿐이고, 산문의 그 수가
    어긋나는 것은 여기서 안 잡힌다.

    세 줄에 `same_block()` 은 걸지 않는다. 각 줄이 명령 자체를 달고 있어 어느 블록에
    있든 뜻이 서고, 실제로 도커 줄은 앞의 둘과 다른 블록에 있다(실측 확인)."""
    ran, db, outside = suite_counts()
    from selftest_schema import BASE_CASES as schema_cases
    if ran < 100 or db < 1 or outside < 50:
        raise Fail(f'the counts came out as {ran}/{db}/{outside} — this case could not '
                   f'read the registry, so it measured nothing')

    seen = set()
    for name in SKILL_DOCS:
        for n, _b in doc_numbers(name, r'(?m)^python3 selftest\.py[ \t]+#[^\n]*?(\d+)',
                                 'the `python3 selftest.py` line with the case count in '
                                 'its comment'):
            eq(n, ran, f'{name} 의 실행법 (python3 selftest.py)')
        for n, _b in doc_numbers(name,
                                 r'(?m)^python3 selftest_schema\.py[ \t]+#[^\n]*?(\d+)',
                                 'the `python3 selftest_schema.py` line with the case '
                                 'count in its comment'):
            eq(n, schema_cases, f'{name} 의 실행법 (python3 selftest_schema.py)')
        for n, _b in doc_numbers(
                name,
                r'(?m)^ERD_SELFTEST_DOCKER=1 python3 selftest\.py[ \t]+#[^\n]*?(\d+)',
                'the `ERD_SELFTEST_DOCKER=1` line with the docker case count in its '
                'comment'):
            eq(n, db, f'{name} 의 실행법 (ERD_SELFTEST_DOCKER=1)')
        seen.add(name)
    on_disk = {p.name for p in REPO.glob('SKILL*.md')}
    if seen != on_disk:
        raise Fail(f'this case read {sorted(seen)} but the repository holds '
                   f'{sorted(on_disk)} — every SKILL document must be measured, or the '
                   f'unread one drifts quietly')


if __name__ == '__main__':
    sys.exit(main(load_all=False))
