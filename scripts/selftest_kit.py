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


# ── 러너 자신의 콘솔 ─────────────────────────────────────────────────────────
# `LC_ALL=C python3 selftest.py` 는 **첫 결과 한 줄에서** 죽었다:
#   print(f'  \033[32m✓\033[0m {name}')
#   UnicodeEncodeError: 'ascii' codec can't encode character '✓'
# 그리고 그 예외를 잡아 빨강으로 찍으려던 줄이 '✗' 로 또 죽어, 181개 중 **한 건도**
# 판정이 안 나온 채 트레이스백 둘로 끝났다. 재는 쪽이 재는 대상보다 먼저 죽으면
# 그날은 아무것도 재지 못한다.
#
# 무엇을 바꾸는가 — `errors` 하나뿐이고, 지금 처리기가 '터질 수 있는' 것일 때만이다.
# 규칙도 값도 `i18n._keep_console_alive` 와 **같다**(`backslashreplace`). 이유도 같다:
# `encoding` 을 덮으면 선언한 것과 다른 바이트가 파이프로 나가고, `replace` 의 `?` 는
# 진짜 `?` 와 구별되지 않아 조용히 틀린 것이 된다.
#
# 왜 `import i18n` 으로 그 혜택을 받지 않는가. 근거 셋이다.
#  ① **러너는 제가 재는 모듈에 제 목숨을 걸면 안 된다.** i18n 은 이 시험이 재는
#     대상이다. 그것을 import 해서 콘솔이 사는 구조면, i18n 이 import 에서 터지는
#     날 러너는 '181개 중 N개 빨강' 대신 트레이스백 하나로 끝난다 — 무엇이 깨졌는지
#     말해야 할 자리에서 말을 잃는다.
#  ② i18n 쪽 처방은 **import 부작용**이다(모듈 바닥의 `_keep_console_alive(...)`
#     두 줄). 남의 import 부작용에 기대는 것은 이 문서가 여섯 라운드째 적고 있는
#     '조용히 죽는' 모양 그대로다 — 누가 그 두 줄을 함수 안으로 옮기면 러너는 다시
#     ascii 콘솔에서 죽고, 그날까지 아무 데서도 빨강이 안 뜬다.
#  ③ 러너가 찍는 '✓'·'✗' 와 표 줄은 **카탈로그의 말이 아니다.** i18n 이 사는 이유
#     (사람에게 나가는 줄은 카탈로그를 거친다)가 여기엔 걸리지 않는다.
# 대가는 규칙이 두 벌이 된다는 것이고, 그것은 감수한다 — 재는 쪽의 독립이 더 비싸다.
_RAISING = ('strict', 'surrogateescape', 'surrogatepass')


def _keep_console_alive(stream):
    """터질 수 있는 오류 처리기를 `backslashreplace` 로 무르게 한다. 바꿨으면 True.

    `PYTHONIOENCODING` 이 처리기를 **직접** 골랐으면(`utf-8:strict` 처럼) 그 뜻대로
    둔다. `io.StringIO` 로 갈아 끼운 스트림·`None` 인 스트림은 `errors` 도
    `reconfigure` 도 없어 저절로 빠진다.
    """
    if (os.environ.get('PYTHONIOENCODING') or '').partition(':')[2].strip():
        return False
    if getattr(stream, 'errors', None) not in _RAISING:
        return False
    reconfigure = getattr(stream, 'reconfigure', None)
    if reconfigure is None:
        return False
    try:
        reconfigure(errors='backslashreplace')
    except Exception:                                            # noqa: BLE001
        return False
    return True


_keep_console_alive(sys.stdout)
_keep_console_alive(sys.stderr)

# ── 입구 파일의 바닥 ─────────────────────────────────────────────────────────
# `selftest.py` 의 `CASE_FLOOR` 는 **글로브로 올라오는 파일들**에만 걸린다. 입구
# 파일(직접 돌린 그 파일) 자신은 `want` 에서 명시적으로 빠지고, 제가 올린 수가 0 보다
# 큰지만 확인했다. 16라운드 검증자가 그 자리를 뚫었다:
#
#   selftest.py 안의 @case 4개를 no-op 데코레이터로 →  all 157 passed, rc=0, ✗ 0건
#   selftest.py 안의 15R 검증 케이스 3개를 삭제      →  all 158 passed
#
# 시험 벌의 43%(70/161)에 대해 '조용히 줄기' 가 그대로 열려 있었다 — 15라운드가
# 막았다고 적은 바로 그 결함이다.
#
# 그래서 바닥을 여기 둔다. `CASE_FLOOR` 를 `selftest.py` 에 둔 이유와 같다: 지키려는
# 파일 **바깥**에 있어야 그 파일만 손보는 변경으로 못 내린다. 입구 파일은 정의상
# `selftest.py` 안의 표로는 지킬 수 없으므로 한 칸 더 바깥, 곧 여기다.
# 값은 16라운드가 끝나는 자리의 실측이다. 케이스를 더하는 것은 자유다(바닥은 하한이다).
#
# 표는 '어느 파일이 입구인가' 로 찾는다. 오늘 이 검사를 하는 케이스는 `selftest.py`
# 안에 있고, `selftest_history.py` 를 직접 돌리면 `selftest.py` 는 글로브에 안 걸려
# 아예 안 올라온다 — 그러니 `'selftest_history'` 행은 **오늘은 안 걸린다.** 지워도
# 오늘의 동작은 같지만, 입구가 바뀌었을 때 바닥이 조용히 1 로 떨어지는 쪽보다
# 적혀 있는 쪽이 낫다고 보고 남겨 둔다.
ENTRY_FLOOR = {'selftest': 110, 'selftest_history': 40}

# ── 한 케이스가 그린 것과 남긴 것 ────────────────────────────────────────────
# erd.py 는 `ERD_VERIFY_LOG` 를 **프로세스마다** 처음부터 다시 쓴다(_LOG_STARTED 가
# 프로세스 전역이다). 그래서 케이스 하나가 build_erd.py 를 두 번 이상 부르면, 뒤의
# 프로세스가 앞의 기록을 지워 버렸다 — 174장을 그리고 114장만 훑었다. 지워진 60장은
# 중복 렌더가 아니라 **서로 다른 스키마**였다(ERD_MAX_AREAS·오른쪽 끝 검사 등).
#
# 고치는 자리는 두 군데가 있었다. erd.py 가 늘 이어 쓰게 하고 케이스가 시작할 때
# 시험이 지우는 것, 또는 **부를 때마다 다른 파일을 주는 것**. 뒤쪽을 골랐다 —
# erd.py 를 건드리지 않고, 프로세스가 제 파일을 비우는 것이 그대로 옳은 동작이 된다.
# 파일이 나뉘어도 '이번 판의 것만 본다'(verify_recs) 와 '이 케이스가 그린 것을 전부
# 본다'(sweep_verify) 를 둘 다 말할 수 있다 — 예전 한 파일 구조는 둘을 구분할 수가
# 없어서 뒤엣것을 잃었다.
_LOGS = []                  # 이번 케이스가 만든 검증 기록 파일 (run() 부른 순서)
_DREW = [0]                 # 이번 케이스가 그린 도판 수 — 기록이 아니라 찍힌 줄에서 센다
_SWEPT = [0]                # 훑기가 실제로 끝까지 돈 케이스 수 (main 이 대조한다)


def new_case():
    """케이스 하나가 시작한다 — 그린 것·남긴 것 셈을 0 으로."""
    _LOGS.clear()
    _DREW[0] = 0


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


_VERIFY_RE = {}


def drawn_names(stdout, lang='en'):
    """이 판이 그린 도판의 이름 — **사람이 읽는 줄**에서 센다.

    기록(JSONL)을 세면 '기록에 남은 것이 기록에 남았다' 는 동어반복이 된다. 훑기가
    놓친 60장이 바로 그렇게 안 보였다. 그래서 세는 자리를 기록 바깥에 둔다 — 도판
    하나에 검증 줄 하나가 찍히고, 그 줄의 서식은
    `verify: the printed line and the machine record say the same thing` 이 글자까지
    못박고 있다. 재는 값은 하나도 긁지 않는다 — 값을 긁던 정규식이 꼬리 하나에 눈을
    감은 적이 있다. 여기서 가져오는 것은 줄 수와 파일 이름뿐이다.

    말이 바뀌면 줄도 바뀌므로 서식은 그 말의 목록에서 가져온다 — 네 말로 도는
    케이스가 있다.
    """
    rx = _VERIFY_RE.get(lang)
    if rx is None:
        if str(HERE) not in sys.path:
            sys.path.insert(0, str(HERE))

        def catalog(code):
            try:
                return dict(importlib.import_module(f'lang.{code}').M)
            except Exception:                                     # noqa: BLE001
                return {}                   # i18n._load 와 같다 — 영어로 떨어진다

        own = catalog(lang).get('log.verify')
        tmpl = own or catalog('en').get('log.verify')
        if not tmpl:
            raise Fail('lang/en.py has no log.verify — the drawn-vs-checked count '
                       'would silently read 0')
        pat = (re.escape(tmpl).replace(re.escape('{name}'), r'(\S+?)')
               .replace(re.escape('{report}'), '.*'))
        rx = re.compile('^' + pat + '$', re.M)
        # 깨진 카탈로그는 캐시하지 않는다 — 일부러 하나 깨뜨렸다 되돌리는 케이스가
        # 있고, 그때 캐시가 남으면 그다음 판을 엉뚱한 서식으로 센다.
        if own:
            _VERIFY_RE[lang] = rx
    return rx.findall(stdout)


def run(script, work, proj=None, env=None, sql_dir=None, expect_ok=True):
    """스크립트 하나를 별도 프로세스로 돌린다 (import 시점 상태가 섞이지 않게).

    ERD_* 는 **하나도 물려받지 않는다**. 예전엔 ERD_DB·ERD_PSQL 둘만 지웠고, 나머지는
    부르는 사람의 껍데기에서 그대로 새어 들어왔다 — 문서가 권하는 다중 DB 흐름대로
    `ERD_LABEL=shop` 을 켜 둔 사람이 시험을 돌리면 2개가, `ERD_EXCLUDE='.*'` 면
    19개가 깨졌다. `install.sh --check` 는 그걸 그대로 물려받아 멀쩡한 설치를
    고장 났다고 알렸다. 시험은 부르는 사람의 설정이 아니라 코드를 재야 한다.
    """
    # 부를 때마다 **다른** 기록 파일을 준다. erd.py 는 제 파일을 처음부터 쓰는데,
    # 그 파일을 모두가 나눠 쓰면 뒤 프로세스가 앞 프로세스의 기록을 지운다.
    log = Path(work).parent / f'verify.{len(_LOGS):03d}.jsonl'
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e.update({'ERD_WORK': str(work), 'ERD_PROJ': str(proj or work),
              'ERD_LANG': 'en', 'ERD_DOCNAME': 'T',
              # 그림 검증 결과를 기계가 읽을 자리에 남기게 한다 (verify_recs 참고)
              'ERD_VERIFY_LOG': str(log)})
    if sql_dir:
        e['ERD_SQL_DIR'] = str(sql_dir)
    if env:
        e.update({k: str(v) for k, v in env.items()})
    r = subprocess.run([sys.executable, str(HERE / script)], capture_output=True,
                       text=True, encoding='utf-8', env=e, cwd=str(HERE))
    if expect_ok and r.returncode != 0:
        raise Fail(f'{script} exited {r.returncode}\n{r.stdout}\n{r.stderr}')
    if e['ERD_VERIFY_LOG'] == str(log):
        # 이 판이 남긴 자리와, 이 판이 그렸다고 **말한** 장수를 함께 적어 둔다.
        # 케이스가 제 손으로 ERD_VERIFY_LOG 를 딴 데로 돌렸으면(그런 케이스가 하나
        # 있다) 그 판의 기록은 훑기의 몫이 아니므로 장수도 세지 않는다.
        _LOGS.append(log)
        _DREW[0] += len(drawn_names(r.stdout, e['ERD_LANG']))
    return r


def ddl(work, text, sql_dir=None):
    d = sql_dir or (work / 'sql')
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text(text, encoding='utf-8')
    run('parse_ddl.py', work, sql_dir=d)
    return json.loads((work / 'schema.json').read_text(encoding='utf-8'))


def write_schema(work, tables):
    work.mkdir(parents=True, exist_ok=True)
    (work / 'schema.json').write_text(json.dumps(tables, ensure_ascii=False), encoding='utf-8')


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


def _read_log(p):
    return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]


def verify_recs(work, name='', scope='last'):
    """그림 자체검증 결과를 erd.py 가 남긴 JSONL 에서 읽는다.

    예전엔 사람이 읽는 검증 줄에서 `(\\d+)(?=\\s*(?:·|$))` 로 숫자를 긁었다. 그 줄에
    (허용)·[경고] 꼬리가 붙자 정규식이 **마지막 항목을 통째로 놓쳤다** — 하필 그
    항목이 0 이 아닐 때만 놓치니, 가로선 중첩이 44 여도 시험은 전부 통과라고 했다.
    사람 좋으라고 바뀌는 서식 대신 값을 직접 읽는다.

    기록이 아예 없으면 통과가 아니라 실패다. '못 찾았으니 깨끗하다' 가 바로 위
    버그의 모양이었다.

    scope='last' 는 **방금 돈 판**의 기록만 준다 — 부르는 쪽 대부분이 한 판을 돌리고
    그 판을 묻는다. scope='all' 은 이 케이스가 돌린 모든 판의 것을 부른 순서대로
    준다 (훑기가 쓴다). 예전엔 판마다 같은 파일을 덮어써서 둘이 구분되지 않았고,
    그래서 앞 판의 기록은 아무 데도 남지 않았다.
    """
    got = [p for p in _LOGS if p.exists()]
    if not got:
        raise Fail('erd.py left no verify log — the check would measure nothing')
    if scope == 'last':
        got = got[-1:]
    recs = [r for p in got for r in _read_log(p)]
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
#
# **이 숫자는 상한이 아니라 정확값이다.** 상한으로 두었을 때, 5 를 50 으로 벌리는
# 한 줄이면 그 케이스의 그림 품질 보증이 통째로 조용해졌다 (실제로 그 뮤턴트에
# 11라운드의 '같은 선 두 번' 회귀를 함께 넣어도 101개가 전부 통과했다). 봐주는 수를
# 늘리는 것과 그 자리에 회귀가 들어오는 것이 구분되지 않는 셈이다. 그래서 훑기는
# 이 케이스가 남긴 기록 전체의 **최댓값이 정확히 이 수인지**를 본다 — 넓히면
# 넓힌 만큼 빨강이고, 그림이 좋아져 수가 줄어도 빨강이다(그때는 줄여 적으면 된다).
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

    **훑었다는 말도 반증을 받아야 한다.** 이 함수는 케이스마다 돌긴 했지만 판마다
    덮어써지는 파일 하나만 읽어서, 두 번 이상 그리는 열 케이스에서 앞 판의 기록을
    통째로 잃고 있었다 — 174장을 그리고 114장(66%)만 봤다. 그래서 이제 그린 장수와
    본 장수를 맞춰 본다. 어긋나면 그 자체가 실패다: **재지 않은 것은 깨끗한 것이
    아니다** 를 훑기 자신에게도 댄다.
    """
    logs = [p for p in _LOGS if p.exists()]
    drew, kept = _DREW[0], sum(len(_read_log(p)) for p in logs)
    if drew != kept:
        raise Fail(f'this case drew {drew} diagram(s) but only {kept} left a record — '
                   f'{drew - kept} went unchecked\n'
                   f'      (logs: {[p.name for p in logs]})')
    if not logs:
        _SWEPT[0] += 1
        return                      # 그림을 안 그리는 케이스 — 여기서 잴 것이 없다
    allow = RENDER_ALLOW.get(name)
    recs = [r for p in logs for r in _read_log(p)]
    for r in recs:
        bad = verify_faults(r, allow)
        if bad:
            raise Fail(f'the diagrams this case drew are not clean\n'
                       f'      {r["file"]}: ' + '; '.join(bad)
                       + f'\n      counts: {r["counts"]}')
    # 봐주기는 상한이 아니라 **정확값**이다 (RENDER_ALLOW 주석 참고). 케이스가 5 를
    # 적었으면 이 케이스의 기록 중 어딘가에 정확히 5 가 있어야 한다 — 넓혀 놓고
    # 그 아래에 회귀를 숨길 수 없게.
    for k, want in (allow or {}).items():
        peak = max((r.get('counts', {}).get(k) or 0) for r in recs)
        if peak != want:
            raise Fail(f'this case is allowed {k}={want} but its diagrams peak at {peak}'
                       f' — the allowance is an exact number, not a ceiling\n'
                       f'      (widen it only with a reason; lower it when the drawing '
                       f'improves)\n'
                       f'      records: {[r["counts"].get(k) for r in recs]}')
    _SWEPT[0] += 1


# ── 등록 ────────────────────────────────────────────────────────────────────
LOADED = []                 # [(모듈 이름, 그 파일이 등록한 케이스 수)] — 신고서


def load_extras():
    """옆에 놓인 `selftest_*.py` 를 전부 불러 CASES 에 등록한다.

    `selftest.py` 가 import 한 줄을 직접 들고 있으면, 파일이 하나 더 늘 때 그 줄을
    잊는 것으로 끝난다 — 잊어도 아무 말이 없고 '전부 통과' 만 찍힌다. 실제로 한 번
    그랬다. 그래서 사람이 적는 대신 옆에 있는 것을 센다.

    **등록이 조용히 0 이 되는 자리를 막는다.** 13라운드가 만든 이 장치는 제가 실패한
    것을 스스로 말하지 못했다 — 글로브 패턴이 어긋나면 39개가 사라지는데 종료코드 0
    에 마지막 줄은 초록 `all 62 passed` 였고, `install.sh --check` 는 그 줄만 보여
    준다. 이름 중복은 `case()` 가 죽여 '조용히 두 배' 를 막았지만 '조용히 0' 은
    아무도 안 막고 있었다. 그래서 여기서 셋을 못박는다:
      · 옆에 `selftest_*.py` 가 **하나도 없으면** 그 자체가 실패다 (패턴이 어긋난 것)
      · 파일 하나가 케이스를 **하나도 안 올리면** 실패다
      · 파일이 `EXPECT_CASES` 를 신고했으면 그 수와 **정확히** 맞아야 한다
    총계 상수를 여기 적지 않는 이유는, 케이스는 라운드마다 늘어서 곧 어긋나기
    때문이다 — 세는 자리를 파일 옆에 둔다.
    """
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))   # 어디서 불러도 옆 파일을 찾게
    # 돌고 있는 파일 자신은 뺀다. `python3 selftest_history.py` 처럼 곁가지 파일을
    # 직접 부르면 그 파일은 이미 `__main__` 으로 올라와 있고, 여기서 제 이름으로 한 번
    # 더 import 하면 **같은 파일이 두 번째 모듈**이 되어 케이스 이름이 통째로 겹친다.
    _self = getattr(sys.modules.get('__main__'), '__file__', None)
    _self = Path(_self).resolve() if _self else None
    files = [p for p in sorted(HERE.glob('selftest_*.py'))
             if p.stem != Path(__file__).stem and p.resolve() != _self]
    if not files:
        raise RuntimeError(
            f'no selftest_*.py next to {Path(__file__).name} — the glob found nothing, '
            f'so every extra case would vanish and the tally would still print green')
    done = {n for n, _ in LOADED}
    for p in files:
        if p.stem in done:
            continue
        before = len(CASES)
        mod = importlib.import_module(p.stem)
        n = len(CASES) - before
        want = getattr(mod, 'EXPECT_CASES', None)
        if want is None:
            if n == 0:
                raise RuntimeError(
                    f'{p.name} registered no case at all — a selftest_*.py that adds '
                    f'nothing is either broken or should not be named that')
        elif n != want:
            raise RuntimeError(f'{p.name} says EXPECT_CASES = {want} but registered {n}')
        LOADED.append((p.stem, n))
    return LOADED


def main():
    # 등록은 여기서 한 번 더 확인한다. 예전엔 `selftest.py` 의 `__main__` 한 줄만이
    # 39개를 불러왔고, 그 줄이 사라져도 초록 `all 62 passed` 였다. import 는 두 번
    # 불러도 sys.modules 에서 그대로 돌아오므로 이 줄은 안전하고, 부르는 자리가
    # 하나 없어져도 개수가 조용히 줄지 않는다.
    load_extras()
    only = sys.argv[1] if len(sys.argv) > 1 else ''
    cases = [(n, f) for n, f in CASES if only in n]
    if not cases:
        print(f'no case matches {only!r}')
        return 2
    width = max(len(n) for n, _ in cases)
    passed = 0
    before_sweep = _SWEPT[0]
    for name, fn in cases:
        tmp = Path(tempfile.mkdtemp(prefix='erd-selftest-'))
        new_case()
        try:
            fn(tmp / 'work')
            sweep_verify(name, tmp)
            passed += 1
            print(f'  \033[32m✓\033[0m {name}')
        except Exception as e:                                    # noqa: BLE001
            FAILED.append((name, e))
            print(f'  \033[31m✗\033[0m {name.ljust(width)}  {e}')
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    # 훑기가 실제로 돌았는가. 13라운드의 간판인 sweep_verify() 는 호출을 통째로
    # 지워도 아무 데서도 빨강이 뜨지 않았다 — **재는 장치가 빠진 것과 잴 것이 없는
    # 것을 구분하지 못했다.** 통과한 케이스 수와 훑은 케이스 수를 맞춰 둔다.
    swept = _SWEPT[0] - before_sweep
    if swept != passed:
        FAILED.append(('selftest: every passing case has its diagrams swept',
                       Fail(f'{passed} cases passed but the sweep ran on {swept}')))
        print(f'  \033[31m✗\033[0m the diagram sweep ran on {swept} of {passed} '
              f'passing cases')
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
