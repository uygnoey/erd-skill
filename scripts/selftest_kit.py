#!/usr/bin/env python3
"""회귀 시험이 함께 쓰는 것 — 항목 목록, 도우미, 실행기.

시험 항목은 `selftest.py` 와 `selftest_*.py` 들에 나뉘어 있고, 목록(CASES)은 여기
하나뿐이다. 예전엔 목록이 `selftest.py` 안에 있어서 `selftest_history.py` 가
`from selftest import CASES` 로 가져다 썼는데, 그러면 **`selftest.py` 를 직접 돌릴 때
등록이 조용히 실패한다** — 그때 그 파일은 `__main__` 이라는 이름으로 이미 올라와 있고
`import selftest` 는 같은 파일을 **두 번째 모듈**로 다시 올린다. 항목은 그 사본의
CASES 에 붙고, 돌고 있는 `__main__.main()` 은 제 것만 세다가 '전부 통과' 를 찍는다.
36개가 어디서도 안 돌던 것이 그 모양이었다.

목록을 제3의 모듈로 빼면 그 함정이 없어진다 — 누가 어떤 이름으로 올라오든 CASES 는
`selftest_kit` 것 하나다.
"""
import importlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = []
FAILED = []
NOTES = []                  # 결과 앞에 덧붙일 한 줄들 (안 돌린 것이 있으면 그것)


def case(name):
    def deco(fn):
        # 이름이 겹치면 세워 둔다. 같은 파일이 두 번 올라오는 사고(모듈 이름이 둘이
        # 되는 그 사고)가 나면 개수만 조용히 두 배가 되지 이름은 반드시 겹친다 —
        # '전부 통과' 뒤에 숨지 않게 여기서 죽는다.
        if any(n == name for n, _ in CASES):
            raise RuntimeError(f'two cases are named {name!r} — registered twice?')
        CASES.append((name, fn))
        return fn
    return deco


class Fail(AssertionError):
    pass


def eq(got, want, what):
    if got != want:
        raise Fail(f'{what}\n      want: {want!r}\n      got : {got!r}')


def has(hay, needle, what):
    # 건초더미가 HTML 한 장이면 실패 한 줄에 수십 KB 가 쏟아져 정작 무엇이 없는지가
    # 안 보인다. 못 찾은 것을 앞에 두고 더미는 끝을 자른다.
    if needle not in hay:
        shown = hay if len(hay) <= 600 else hay[:300] + ' … ' + hay[-300:]
        raise Fail(f'{what}\n      {needle!r} not in ({len(hay)} chars) {shown!r}')


def run(script, work, proj=None, env=None, sql_dir=None, expect_ok=True):
    """스크립트 하나를 별도 프로세스로 돌린다 (import 시점 상태가 섞이지 않게).

    ERD_* 는 **하나도 물려받지 않는다**. 예전엔 ERD_DB·ERD_PSQL 둘만 지웠고, 나머지는
    부르는 사람의 껍데기에서 그대로 새어 들어왔다 — 문서가 권하는 다중 DB 흐름대로
    `ERD_LABEL=shop` 을 켜 둔 사람이 시험을 돌리면 2개가, `ERD_EXCLUDE='.*'` 면
    19개가 깨졌다. `install.sh --check` 는 그걸 그대로 물려받아 멀쩡한 설치를
    고장 났다고 알렸다. 시험은 부르는 사람의 설정이 아니라 코드를 재야 한다.
    """
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e.update({'ERD_WORK': str(work), 'ERD_PROJ': str(proj or work),
              'ERD_LANG': 'en', 'ERD_DOCNAME': 'T',
              # 그림 검증 결과를 기계가 읽을 자리에 남기게 한다 (verify_recs 참고)
              'ERD_VERIFY_LOG': str(Path(work).parent / 'verify.jsonl')})
    if sql_dir:
        e['ERD_SQL_DIR'] = str(sql_dir)
    if env:
        e.update({k: str(v) for k, v in env.items()})
    r = subprocess.run([sys.executable, str(HERE / script)], capture_output=True,
                       text=True, env=e, cwd=str(HERE))
    if expect_ok and r.returncode != 0:
        raise Fail(f'{script} exited {r.returncode}\n{r.stdout}\n{r.stderr}')
    return r


def ddl(work, text, sql_dir=None):
    d = sql_dir or (work / 'sql')
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text(text, encoding='utf-8')
    run('parse_ddl.py', work, sql_dir=d)
    return json.loads((work / 'schema.json').read_text())


def write_schema(work, tables):
    work.mkdir(parents=True, exist_ok=True)
    (work / 'schema.json').write_text(json.dumps(tables, ensure_ascii=False))


def col(name, typ='bigint', **kw):
    c = {'name': name, 'type': typ, 'not_null': False, 'default': None,
         'comment': '', 'added': False, 'identity': False}
    c.update(kw)
    return c


def table(name, cols, **kw):
    t = {'name': name, 'schema': 'public', 'db': '', 'origin': 'existing',
         'columns': cols, 'pk': [], 'fks': [], 'uniques': [], 'checks': [],
         'indexes': [], 'note': '', 'rows': 1, 'size': ''}
    t.update(kw)
    return t


def hub_schema(n=24):
    """허브 하나에 자식 n개 — 관계가 한 점으로 모이는, 실제 DB 에 흔한 모양.

    전체도는 노드 진출 y 가 고정이라 이 모양에서 가로선이 몇 번 스친다. 그 '아는
    겹침' 이 있어야 (허용)·[경고] 서식을 실제로 지나갈 수 있어 두 케이스가 함께 쓴다.
    """
    t = {'hub': table('hub', [col('id'), col('name', 'text')], pk=['id'])}
    for i in range(n):
        nm = f'c{i:02d}'
        t[nm] = table(nm, [col('id'), col('hub_id')], pk=['id'],
                      fks=[{'column': 'hub_id', 'ref_table': 'hub', 'ref_column': 'id',
                            'on_delete': 'CASCADE'}])
    return t


def verify_recs(work, name=''):
    """그림 자체검증 결과를 erd.py 가 남긴 JSONL 에서 읽는다.

    예전엔 사람이 읽는 검증 줄에서 `(\\d+)(?=\\s*(?:·|$))` 로 숫자를 긁었다. 그 줄에
    (허용)·[경고] 꼬리가 붙자 정규식이 **마지막 항목을 통째로 놓쳤다** — 하필 그
    항목이 0 이 아닐 때만 놓치니, 가로선 중첩이 44 여도 시험은 전부 통과라고 했다.
    사람 좋으라고 바뀌는 서식 대신 값을 직접 읽는다.

    기록이 아예 없으면 통과가 아니라 실패다. '못 찾았으니 깨끗하다' 가 바로 위
    버그의 모양이었다.
    """
    p = Path(work).parent / 'verify.jsonl'
    if not p.exists():
        raise Fail('erd.py left no verify log — the check would measure nothing')
    recs = [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
    if name:
        recs = [r for r in recs if name in r['file']]
    if not recs:
        raise Fail(f'no verify record for {name or "any diagram"}')
    return recs


# ── '깨끗하다' 의 뜻은 시험이 가진다 ────────────────────────────────────────
# 예전엔 `if r['warn']` 한 줄이 전부였다. 그런데 그 목록은 **재는 쪽이 직접 내린
# 판정**이다 — erd.py 가 tolerate 에 든 항목을 빼고 적는다. 즉 코드가 '이건 봐줘도
# 된다' 고 적으면 시험은 그대로 믿었다. 세 번 재 봤다:
#
#   · 모든 항목을 n/a(None) 로 만든다          → 57개 중 3개만 붉어졌다
#   · counts 는 정직하게 두고 warn 만 비운다    → 57개 전부 통과
#   · tolerate 를 전 항목으로 넓히고 가로선 중첩 2 를 되살린다 → 57개 전부 통과
#
# 경고를 잠재우려 tolerate 를 한 항목 넓히는 것은 다음 판이 충분히 할 법한 한 줄이고,
# 그 한 줄이면 그림 품질 보증이 통째로 조용해진다. 그래서 아래 규칙은 counts 만 읽고
# warn·tolerated 는 판정에 쓰지 않는다 — 두 값은 실패 메시지에 참고로만 싣는다.
MEASURES = ('label_table', 'label_x', 'thru', 'v_overlap', 'h_overlap')

# 라벨을 아예 그리지 않는 그림(개요도 — edge_labels=False)에서만 라벨 항목이 '해당
# 없음' 일 수 있다. 그 밖의 n/a 는 재기를 그만둔 것이고, **안 잰 것은 깨끗한 것이
# 아니다**. 그래서 기본은 '숫자여야 한다' 이고, 케이스가 따로 말할 필요가 없다.
NA_OK = {('overview', 'label_table'), ('overview', 'label_x')}


def diagram_kind(fname):
    """그림의 갈래 — 규칙이 갈래마다 다르다. 모르는 이름은 가장 엄한 쪽(area)으로 친다."""
    s = str(fname)
    return 'overview' if 'overview' in s else 'full' if 'full' in s else 'area'


def verify_faults(rec, allow=None):
    """기록 하나가 어긴 규칙을 말로 돌려준다. 빈 목록이면 깨끗하다.

    allow 는 **케이스가 적는** 예외다: {'h_overlap': 5} 처럼 항목마다 숫자를 못박아야
    하고, 재는 쪽이 넘긴 tolerate 와는 아무 상관이 없다. 코드를 고쳐서는 늘릴 수 없는
    자리에 두는 것이 요점이다 — 봐주는 것은 시험을 고쳐야만 늘어난다.
    """
    allow = allow or {}
    kind = diagram_kind(rec.get('file', ''))
    counts = rec.get('counts') or {}
    bad = []
    gone = [k for k in MEASURES if k not in counts]
    if gone:
        # 항목이 이름째 사라지면 '전부 0' 이 되어 조용히 통과한다 — 그 자리를 막는다
        bad.append(f'{", ".join(gone)}: not in the record at all')
    new = [k for k in counts if k not in MEASURES]
    if new:
        # 반대쪽도 막는다: erd.py 가 검사를 하나 늘렸는데 여기가 모르면, 그 검사는
        # 재기만 하고 아무도 안 보는 숫자가 된다. 붉어지면 MEASURES 에 한 줄 늘린다.
        bad.append(f'{", ".join(new)}: measured by the code but not known to this test')
    for k in MEASURES:
        if k not in counts:
            continue
        v = counts[k]
        if v is None:
            if (kind, k) not in NA_OK:
                bad.append(f'{k}: n/a — a check that stopped measuring is not a clean check')
        elif not isinstance(v, int) or isinstance(v, bool):
            bad.append(f'{k}: {v!r} is not a count')
        elif v > allow.get(k, 0):
            cap = allow.get(k, 0)
            bad.append(f'{k}={v} (this case allows at most {cap})')
    return bad


def verify_clean(work, name='', what='the diagram must be clean', allow=None):
    """그림 검증 기록이 **시험의 규칙대로** 깨끗한지 본다."""
    recs = verify_recs(work, name)
    for r in recs:
        bad = verify_faults(r, allow)
        if bad:
            raise Fail(f'{what}\n      {r["file"]}: ' + '; '.join(bad)
                       + f'\n      counts: {r["counts"]}'
                       + f'\n      (the record itself said warn={r.get("warn")!r}'
                         f' tolerated={r.get("tolerated")!r} — not consulted)')
    return recs


# 일부러 어지러운 그림을 그리는 케이스는 여기에 숫자로 적는다. 어느 파일의 케이스든
# 이름으로 여기 적는다 — 지금은 같은 허브 fixture(자식 24개)를 쓰는 둘뿐이다. 전체도는
# 노드 진출 y 가 고정이라 그 모양에서 가로선이 다섯 번 스친다.
# (허용치가 실제보다 헐거워지면 그만큼 회귀가 숨는다. 늘릴 때는 왜인지 같이 적는다.)
RENDER_ALLOW = {
    'render: a hub with many children keeps lines out of the tables':
        {'h_overlap': 5},
    # 같은 허브 fixture 를 (허용)·[경고] 서식을 지나가게 하는 데 쓴다 — 그 케이스는
    # 일부러 '봐주기 없이' 한 번 더 그려서 경고 줄을 만든다.
    'verify: the printed line and the machine record say the same thing':
        {'h_overlap': 5},
}


def sweep_verify(name, tmp):
    """케이스가 그린 **모든** 그림을 같은 규칙에 걸어 본다.

    verify_clean 을 직접 부르는 케이스는 셋뿐인데 그림을 그리는 케이스는 스무 개가
    넘는다. 나머지는 '자기가 보려던 것' 만 보고 그림이 어떻게 나왔는지는 묻지 않았다 —
    렌더 회귀가 스물 몇 개의 그림을 지나가면서 한 번도 붙잡히지 않을 수 있었다.
    케이스가 통과한 뒤 그 케이스가 남긴 기록을 전부 훑는다.
    """
    p = tmp / 'verify.jsonl'
    if not p.exists():
        return                      # 그림을 안 그리는 케이스 — 여기서 잴 것이 없다
    allow = RENDER_ALLOW.get(name)
    for line in p.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        bad = verify_faults(r, allow)
        if bad:
            raise Fail(f'the diagrams this case drew are not clean\n'
                       f'      {r["file"]}: ' + '; '.join(bad)
                       + f'\n      counts: {r["counts"]}')


# ── 등록 ────────────────────────────────────────────────────────────────────
def load_extras():
    """옆에 놓인 `selftest_*.py` 를 전부 불러 CASES 에 등록한다.

    `selftest.py` 가 import 한 줄을 직접 들고 있으면, 파일이 하나 더 늘 때 그 줄을
    잊는 것으로 끝난다 — 잊어도 아무 말이 없고 '전부 통과' 만 찍힌다. 실제로 한 번
    그랬다. 그래서 사람이 적는 대신 옆에 있는 것을 센다.
    """
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))   # 어디서 불러도 옆 파일을 찾게
    for p in sorted(HERE.glob('selftest_*.py')):
        if p.stem == Path(__file__).stem:
            continue                 # 이 파일 자신
        importlib.import_module(p.stem)


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else ''
    cases = [(n, f) for n, f in CASES if only in n]
    if not cases:
        print(f'no case matches {only!r}')
        return 2
    width = max(len(n) for n, _ in cases)
    for name, fn in cases:
        tmp = Path(tempfile.mkdtemp(prefix='erd-selftest-'))
        try:
            fn(tmp / 'work')
            sweep_verify(name, tmp)
            print(f'  \033[32m✓\033[0m {name}')
        except Exception as e:                                    # noqa: BLE001
            FAILED.append((name, e))
            print(f'  \033[31m✗\033[0m {name.ljust(width)}  {e}')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    print()
    # 안 돈 것이 있으면 여기서 말한다. 마지막 줄은 집계여야 한다 — `install.sh --check`
    # 가 tail -1 만 떼어 보여 주므로, 뒤에 한 줄이라도 붙으면 개수가 안 보인다.
    for note in NOTES:
        print(f'  {note}')
    if FAILED:
        print(f'\033[31m{len(FAILED)} of {len(cases)} failed\033[0m')
        return 1
    print(f'\033[32mall {len(cases)} passed\033[0m')
    return 0
