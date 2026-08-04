#!/usr/bin/env python3
"""회귀 시험 (4) — 14라운드가 `install.sh` 쪽에서 고친 것.

    python3 selftest_r14_install.py          여기 있는 것 전부
    python3 selftest_r14_install.py cwd      이름에 'cwd' 가 든 것만

`selftest_kit.CASES` 에 등록된다 — `selftest.py` 를 돌리면 `load_extras()` 가 옆에
놓인 `selftest_*.py` 를 글로브로 찾아 오므로 네 파일이 한 벌로 돈다.

이번 라운드의 것은 모양이 하나로 모인다. **`--check` 가 안 한 검사를 통과로 적었다.**
REVIEW-LOG 가 세 번 이름 붙인 그 부류다 — 잴 것이 없으면 그 사실 자체가 실패여야
하는데, 여기서는 절이 통째로 사라지고 `✓ installation complete` 만 남았다.

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
"""
import hashlib
import os
import re
import shutil
import subprocess
import sys

from selftest_kit import Fail, HERE, case, eq, has, main


EXPECT_CASES = 13       # 등록 개수를 파일이 스스로 못박는다 (selftest_kit.load_extras)

REPO = HERE.parent
INSTALL_SH = REPO / 'install.sh'
REQ_TXT = REPO / 'requirements.txt'
REVIEW_LOG = REPO / 'REVIEW-LOG.md'
INSTALL_DOCS = ('INSTALL.md', 'INSTALL.ko.md', 'INSTALL.ja.md', 'INSTALL.es.md')

# 한 칸의 상한. `REVIEW-LOG.md` 가 제 규칙으로 "칸은 한 문장을 넘기지 않는다" 를
# 적어 두었는데 그것을 재는 것이 없었다. 문장 길이를 기계가 셀 수는 없으므로 글자
# 수로 대신 잰다 — 넘치면 `### 각주` 로 빼라는 뜻이다. 15라운드가 표를 다시 세울 때
# 가장 긴 칸이 110자였으므로, 그 위로 조금만 여유를 준다.
CELL_MAX = 140

# install.sh 가 말(카탈로그)의 끝에 박아 둔 표시. 여기까지는 부수효과가 없어서
# source 해도 안전하다 — 'every message key renders…' 가 그 성질을 쓴다.
CATALOG_MARK = '#### END OF MESSAGE CATALOG ####'

ANSI = re.compile(r'\x1b\[[0-9;]*m')

# 가짜 selftest.py. 진짜 것은 40초가 걸리고, 무엇보다 **다른 파일의 상태**에 따라
# 빨강이 된다 — install.sh 의 논리를 재려는 시험이 남의 회귀에 딸려 흔들리면 안 된다.
# 출력 모양만 진짜와 똑같이 흉내 낸다: 케이스 줄 → 빈 줄 → 안 돌린 것 → 집계.
STUB = """\
import pathlib
import sys
MARK = {mark!r}
if {writes_cwd!r}:
    # 이 판이 어디서 도는지 보이게 제 cwd 에 흔적을 남긴다.
    # (`--check` 가 임시 자리로 안 옮겨 가면 이것이 부르는 사람의 cwd 에 떨어진다)
    p = pathlib.Path('erd-build/out')
    p.mkdir(parents=True, exist_ok=True)
    (p / 'marker.txt').write_text(MARK)
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
    log.write_text('')
    for name in ('curl', 'unzip'):
        f = d / name
        f.write_text('#!/bin/sh\necho "%s $*" >> "%s"\nexit 1\n' % (name, log))
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
                       capture_output=True, text=True, env=e, cwd=str(cwd),
                       stdin=subprocess.DEVNULL)
    r.out = ANSI.sub('', r.stdout + r.stderr)
    called = log.read_text().strip()
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
                              capture_output=True, text=True, env=e)

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
    (caller / 'mine.txt').write_text('do not touch')

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
    `N cases … were NOT run` 을 버렸다. SKILL.md 와 REVIEW-LOG 는 "안 돌린 개수는
    집계 윗줄에 매번 찍힌다" 고 적는데, 문서가 유일한 입구라고 못박은 `--check`
    에서는 그 줄만 안 보였다 — 안 한 검사를 통과로 적는 그 부류다."""
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


# ── 16R · 문서를 재는 것이 하나도 없었다 ───────────────────────────────────
# 15라운드 수정자 D 가 `반증 안 됨` 으로 남긴 네 행(#109~#112)의 원인을 그렇게 짚었다.
# 네 행 전부가 `REVIEW-LOG.md` 자신에 대한 것이고, 그 문서를 여는 시험이 하나도 없어서
# **되돌려도 아무 데서도 빨강이 뜨지 않았다.** 여기 셋이 그 자리를 문다.
#
# 파일 이름은 install 이지만 담긴 것은 문서다 — 이 파일이 `install.sh --check` 가
# 돌리는 회귀 시험의 한 조각이고, `--check` 가 사용자에게 보여 주는 예시 출력이 바로
# 아래 두 번째 케이스가 재는 숫자이기 때문이다. 더 나은 자리가 생기면 옮기면 된다.

_CELL = re.compile(r'(?<!\\)\|')        # `\|` 는 칸을 나누지 않는다 (마크다운 규칙)
_SEP = re.compile(r'^[\s:|-]+$')


def md_tables(text):
    """마크다운 표를 [(첫 줄 번호, [행…])] 로 끊어 낸다. 행은 칸 목록이다."""
    out, cur, start = [], [], 0
    for i, line in enumerate(text.split('\n'), 1):
        s = line.strip()
        if s.startswith('|') and s.endswith('|') and len(s) > 1:
            if not cur:
                start = i
            cur.append((i, [c.strip() for c in _CELL.split(s)[1:-1]]))
        elif cur:
            out.append((start, cur))
            cur = []
    if cur:
        out.append((start, cur))
    return out


@case('docs: every row of the REVIEW-LOG tables has the shape its header declares')
def _(work):
    """`REVIEW-LOG.md` 의 주 표는 여덟 열이다. 그런데 그 모양을 재는 것이 없어서,
    칸 안의 `|` 하나가 열을 늘려도(표가 깨진다) 빈 칸이 남아도(문서 제 규칙 위반)
    한 칸에 문단이 들어가도(15라운드까지 그랬다) 아무 데서도 빨강이 안 떴다.

    세 가지를 잰다 — 모든 행이 제 표 머리와 같은 열 수인가, 빈 칸이 없는가, 어떤
    칸도 `CELL_MAX` 를 넘지 않는가."""
    if not REVIEW_LOG.exists():
        raise Fail(f'{REVIEW_LOG} is missing — the log is part of the skill, and a '
                   f'case that measures nothing must not pass')
    tables = md_tables(REVIEW_LOG.read_text(encoding='utf-8'))
    rows = sum(len(t) for _s, t in tables)
    # 이빨: 파싱이 무너지면 '전부 통과' 가 된다. 표가 실제로 잡혔는지 먼저 못박는다.
    if len(tables) < 2 or rows < 100:
        raise Fail(f'the table parse found {len(tables)} table(s) and {rows} row(s) — '
                   f'that is too little to be this document, so this case measured '
                   f'nothing')
    for _start, table in tables:
        width = len(table[0][1])
        for ln, cells in table:
            if _SEP.fullmatch('|'.join(cells)) and set(''.join(cells)) <= set(' :-'):
                continue                       # 머리 아래 구분선
            if len(cells) != width:
                raise Fail(f'REVIEW-LOG.md:{ln} has {len(cells)} columns but its '
                           f'header has {width} — a raw "|" inside a cell must be '
                           f'written as \\| \n      {"|".join(cells)[:160]}')
            for i, c in enumerate(cells, 1):
                if not c:
                    raise Fail(f'REVIEW-LOG.md:{ln} column {i} is empty — the '
                               f"document's own rule is that no cell is left blank")
                if len(c) > CELL_MAX:
                    raise Fail(f'REVIEW-LOG.md:{ln} column {i} is {len(c)} characters '
                               f'(limit {CELL_MAX}) — move it into ### 각주 as a '
                               f'footnote\n      {c[:120]}…')


@case('docs: the case counts the documents state are the counts a run produces')
def _(work):
    """`지금 있는 것` 의 "131개" 는 **두 라운드째 틀린 값**이었고, 15라운드가 그것을
    161 로 고칠 때 `INSTALL.md`·`.ko`·`.ja`·`.es` 네 곳의 같은 131 은 그대로 남았다.
    같은 숫자가 다섯 군데에 손으로 적혀 있고 그중 하나만 고쳐도 아무 데서도 빨강이
    안 떴다 — 그것이 `반증 안 됨` 네 행의 모양이다.

    그래서 숫자를 하드코딩하지 않고 **규칙**으로 잰다: 문서가 적은 수는 이 판이
    실제로 등록한 수와 같아야 한다. 라운드가 케이스를 늘리면 이 케이스가 빨개지고,
    그때 다섯 자리를 함께 고치면 된다."""
    import selftest_kit as kit
    import selftest_history as hist

    ran = len(kit.CASES)                 # 지금 등록된 것 (도커면 DB 케이스도 포함)
    db = hist._DB_CASES
    no_docker = ran - db if hist._DB_RAN else ran
    if no_docker < 1 or db < 1:
        raise Fail(f'the counts came out as {no_docker}/{db} — this case could not '
                   f'read the registry, so it measured nothing')

    text = REVIEW_LOG.read_text(encoding='utf-8')
    m = re.search(r'\*\*(\d+)개 항목\*\*', text)
    if not m:
        raise Fail('REVIEW-LOG.md no longer states its case count as "**N개 항목**" — '
                   'this case cannot find the number it is meant to keep honest')
    eq(int(m.group(1)), no_docker, 'REVIEW-LOG.md 의 `지금 있는 것` 개수')
    m2 = re.search(r'ERD_SELFTEST_DOCKER=1` 이면 여기에 (\d+)개가 더해진다', text)
    if not m2:
        raise Fail('REVIEW-LOG.md no longer states how many cases docker adds')
    eq(int(m2.group(1)), db, 'REVIEW-LOG.md 의 도커 추가분')

    # 날짜가 없으면 그 숫자가 언제의 것인지 아무 데도 없다 — 이 문서가 네 번 틀린
    # 자리의 공통점이다.
    near = text[m.start():m.start() + 200]
    if not re.search(r'20\d\d-\d\d-\d\d', near):
        raise Fail('the case count in REVIEW-LOG.md carries no measurement date — '
                   '"131" survived two rounds precisely because nobody could tell '
                   'when it had been measured')

    # 네 언어의 INSTALL 예시 출력. 15라운드는 여기 넷을 잊었다.
    for name in INSTALL_DOCS:
        p = REPO / name
        if not p.exists():
            raise Fail(f'{name} is missing')
        body = p.read_text(encoding='utf-8')
        got = re.findall(r'all (\d+) passed', body)
        if not got:
            raise Fail(f'{name} no longer shows an "all N passed" example line — the '
                       f'documented output of install.sh --check is what this measures')
        for n in got:
            eq(int(n), no_docker, f'{name} 의 예시 출력')
        skipped = re.findall(r'(\d+) cases need a real server|! (\d+) ', body)
        nums = [int(a or b) for a, b in skipped]
        if nums and any(n != db for n in nums):
            raise Fail(f'{name} says {nums} cases were not run, but the suite reports '
                       f'{db}')


@case('docs: "확인 필요" never survives as a cell of the REVIEW-LOG table')
def _(work):
    """14라운드가 라운드가 *끝나기 전에* 문서를 써서 세 칸을 `확인 필요` 로 두었고,
    그 셋은 다음 라운드가 실측해서야 채워졌다. 15라운드가 그것을 규칙 문장으로
    넣었지만, **규칙을 지키는지 보는 것은 아무것도 없었다.**

    규칙을 말하는 산문은 그대로 둔다 — 재는 것은 표의 칸이다."""
    tables = md_tables(REVIEW_LOG.read_text(encoding='utf-8'))
    if not tables:
        raise Fail('no table found in REVIEW-LOG.md — this case measured nothing')
    for _start, table in tables:
        for ln, cells in table:
            for i, c in enumerate(cells, 1):
                if c.strip('* `').startswith('확인 필요'):
                    raise Fail(f'REVIEW-LOG.md:{ln} column {i} is still "확인 필요" — '
                               f'a round that has ended may not leave one behind '
                               f'(the document says so itself)')


if __name__ == '__main__':
    sys.exit(main())
