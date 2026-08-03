#!/usr/bin/env python3
"""회귀 시험 — DB 없이 스킬 전체를 한 번 돌려 보고 결과를 검사한다.

    python3 selftest.py            전부
    python3 selftest.py parse      이름에 'parse' 가 든 항목만

그림 품질은 렌더링할 때마다 자체 검증이 찍히지만, 그 밖의 기능은 재는 것이 없었다.
그래서 고칠 때마다 다른 데가 조용히 죽었다 — 인라인 주석은 두 판을 통째로 빈
문자열인 채 지나갔고(pg_dump 는 COMMENT ON 을 쓰므로 그쪽 시험만 통과했다), 자기참조
루프는 두 개가 겹쳐 하나로 보이는 동안 검증이 0 을 찍었다.

여기 담는 것은 **한 번이라도 조용히 깨졌던 것들**이다. 새로 고칠 때마다 그 자리를
지키는 항목을 하나 남긴다.

DB 도 docker 도 필요 없다. 임시 디렉토리에서 돌고 뒤를 치운다.
출력은 영어다 — 사용자가 아니라 이 코드를 고치는 사람이 보는 것이라서.
"""
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


def case(name):
    def deco(fn):
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


# 일부러 어지러운 그림을 그리는 케이스는 여기에 숫자로 적는다. 지금은 하나뿐이다:
# 허브 하나에 자식 24개 — 전체도는 노드 진출 y 가 고정이라 가로선이 다섯 번 스친다.
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


# ── 말 ──────────────────────────────────────────────────────────────────────
@case('i18n: four catalogs agree')
def _(work):
    sys.path.insert(0, str(HERE))
    import lang.en as en
    for code in ('ko', 'ja', 'es'):
        m = __import__(f'lang.{code}', fromlist=['M']).M
        eq(set(m), set(en.M), f'lang/{code}.py key set')
        for k in en.M:
            eq(sorted(re.findall(r'{(\w+)}', m[k])),
               sorted(re.findall(r'{(\w+)}', en.M[k])), f'{code} placeholders in {k}')
            if not str(m[k]).strip():
                raise Fail(f'{code} {k} is empty')


@case('i18n: every key used by the code exists')
def _(work):
    sys.path.insert(0, str(HERE))
    import lang.en as en
    used = set()
    for f in HERE.glob('*.py'):
        if f.name == 'selftest.py':
            continue
        for m in re.finditer(r"""T\(\s*['"]([a-z_]+\.[a-z_0-9]+)['"]""",
                             f.read_text(encoding='utf-8')):
            used.add(m.group(1))
    missing = sorted(used - set(en.M))
    eq(missing, [], 'keys used in code but absent from lang/en.py')


@case('i18n: {key} placeholder does not collide with t()')
def _(work):
    from i18n import t
    # t(key, /, **kw) 라야 {key} 를 자리표시자로 쓸 수 있다 — 위치 전용이 아니면
    # 여기서 TypeError 가 난다
    has(t('err.spec_layer', key='ZZZ', value=[]), 'ZZZ',
        'a message whose placeholder is named {key} must still format')


# ── 값 다듬기 ────────────────────────────────────────────────────────────────
@case('clean: newline and control chars collapse')
def _(work):
    from config import clean
    eq(clean('a\nb\tc\x0bd\x1fe   f'), 'a b c d e f', 'clean() flattens to one line')
    eq(clean(None), '', 'clean(None)')
    eq(clean('키 | 파이프'), '키 | 파이프', 'pipe survives')


@case('clean: a newline in a comment does not kill the diagram')
def _(work):
    write_schema(work, {'t': table('t', [col('id'), col('m', 'text',
                                                        comment='one\ntwo\x0bthree')])})
    run('build_erd.py', work)
    if not (work / 'out' / 'erd_full.png').exists():
        raise Fail('no PNG produced')


@case('config: docname is made safe for a filename')
def _(work):
    # 예전엔 `any('/' in n for n in names)` 를 봤다 — names 는 Path.name 이라 구분자가
    # **들어 있을 수 없다**. 즉 조건이 늘 거짓인, 아무것도 못 잡는 줄이었다. 슬래시가
    # 살아남으면 실제로 나는 일은 '이름에 /가 남는 것' 이 아니라 하위 디렉토리가 생겨
    # 산출물이 엉뚱한 자리로 가는 것이다. 그러니 나온 이름과 자리를 직접 못박는다.
    write_schema(work, {'t': table('t', [col('id')])})
    run('build_erd.py', work, env={'ERD_DOCNAME': 'a/b:c'})
    eq(sorted(p.name for p in work.glob('*.graphml')), ['a_b_c.graphml'],
       'every separator becomes _ and the file lands in the project directory itself')
    if (work / 'a').exists():
        raise Fail('a slash turned into a subdirectory — the artifact left its place')
    if list(work.parent.glob('*.graphml')):
        raise Fail(f'an artifact escaped the project directory: '
                   f'{[p.name for p in work.parent.glob("*.graphml")]}')
    # 위로 거슬러 올라가는 이름도 (.. 은 strip('. ') 로 사라진다)
    run('build_erd.py', work, env={'ERD_DOCNAME': '../../etc/passwd'})
    eq(sorted(p.name for p in work.glob('*.graphml')),
       ['_.._etc_passwd.graphml', 'a_b_c.graphml'], 'a traversal cannot climb out')
    # 빈 이름은 '.html' 같은 숨김 파일이 된다 — 기본 이름으로 떨어져야 한다
    run('build_erd.py', work, env={'ERD_DOCNAME': '  . '})
    if not (work / 'ERD.graphml').exists():
        raise Fail('an empty docname must fall back to a visible default name')


# ── DDL 파서 ─────────────────────────────────────────────────────────────────
@case('parse: inline -- comment attaches to its own column')
def _(work):
    s = ddl(work, """
CREATE TABLE t (
  id bigint PRIMARY KEY,   -- row id
  amount numeric(12,2),    -- amount
  plain text
);
""")
    got = {c['name']: c['comment'] for c in s['t']['columns']}
    eq(got, {'id': 'row id', 'amount': 'amount', 'plain': ''},
       'trailing comments belong to the column they follow, not the next one')


@case('parse: a comment on a shared line does not swallow the next column')
def _(work):
    s = ddl(work, """
CREATE TABLE t (a int, b int,  -- shared line
  c int);
CREATE TABLE leading (
    id int PRIMARY KEY   -- row id
  , name text            -- leading-comma style
  , v int
);
""")
    eq([c['name'] for c in s['t']['columns']], ['a', 'b', 'c'],
       'a trailing comment must not merge two columns')
    eq([c['name'] for c in s['leading']['columns']], ['id', 'name', 'v'],
       'leading-comma style keeps every column')
    eq({c['name']: c['comment'] for c in s['leading']['columns']},
       {'id': 'row id', 'name': 'leading-comma style', 'v': ''},
       'and each comment stays with its own column')


@case('parse: a constraint written after REFERENCES still counts')
def _(work):
    s = ddl(work, """
CREATE TABLE t (
  id int PRIMARY KEY,
  parent_id int REFERENCES users(id) NOT NULL
);
""")
    c = [x for x in s['t']['columns'] if x['name'] == 'parent_id'][0]
    eq(c['not_null'], True, 'NOT NULL after REFERENCES is still NOT NULL')


@case('parse: PRIMARY KEY implies NOT NULL')
def _(work):
    # Postgres puts NOT NULL on every PK column; introspect reports it that way.
    # The diagrams hide a miss (the PK icon wins) but the definition tables do not.
    s = ddl(work, """
CREATE TABLE t (id bigint PRIMARY KEY, v text);
CREATE TABLE pair (a int, b int, note text, PRIMARY KEY (a, b));
CREATE TABLE later (id bigint, v text);
ALTER TABLE later ADD CONSTRAINT later_pk PRIMARY KEY (id);
""")
    eq({c['name']: c['not_null'] for c in s['t']['columns']},
       {'id': True, 'v': False}, 'an inline PK column is NOT NULL')
    eq({c['name']: c['not_null'] for c in s['pair']['columns']},
       {'a': True, 'b': True, 'note': False}, 'a composite table-level PK too')
    eq({c['name']: c['not_null'] for c in s['later']['columns']},
       {'id': True, 'v': False}, 'and a PK added by ALTER TABLE')


@case('parse: columns named after table-level keywords survive')
def _(work):
    s = ddl(work, """
CREATE TABLE t (
  id bigint PRIMARY KEY, checksum text, like_count int, unique_code varchar(20),
  constraint_type text, partition_id int, exclude_flag boolean
);
""")
    eq([c['name'] for c in s['t']['columns']],
       ['id', 'checksum', 'like_count', 'unique_code', 'constraint_type',
        'partition_id', 'exclude_flag'], 'keyword-prefixed column names')


@case('parse: string literals cannot break the split')
def _(work):
    s = ddl(work, """
CREATE TABLE t (
  id bigint PRIMARY KEY,
  a text DEFAULT '(',
  b text DEFAULT '--none--',
  c text DEFAULT 'it''s fine',
  d text DEFAULT 'see REFERENCES users',
  e text
);
""")
    eq([c['name'] for c in s['t']['columns']], ['id', 'a', 'b', 'c', 'd', 'e'],
       'no column lost to a string literal')
    eq(s['t']['fks'], [], 'REFERENCES inside a string is not a foreign key')
    eq(s['t']['pk'], ['id'], 'PRIMARY KEY inside a string is not a key')
    eq([c['default'] for c in s['t']['columns'] if c['name'] == 'd'],
       ["'see REFERENCES users'"], 'default value kept whole')


@case('parse: dollar-quoted function bodies are skipped')
def _(work):
    s = ddl(work, """
CREATE FUNCTION f() RETURNS void AS $_$
BEGIN
  CREATE TABLE ghost (x int);
  RAISE NOTICE 'it''s $$ tricky';
END
$_$ LANGUAGE plpgsql;
CREATE TABLE real_one (id bigint PRIMARY KEY);
""")
    eq(sorted(s), ['real_one'], 'no ghost table from a function body')


@case('parse: nested block comments and E-strings')
def _(work):
    s = ddl(work, r"""
CREATE TABLE t (
  id int PRIMARY KEY,
  /* outer /* inner */ still a comment */
  x int,
  y text DEFAULT E'it\'s',
  z int
);
""")
    eq([c['name'] for c in s['t']['columns']], ['id', 'x', 'y', 'z'],
       'nested comment / E-string do not swallow columns')


@case('parse: one-line definition keeps every column')
def _(work):
    s = ddl(work, "CREATE TABLE t (a int PRIMARY KEY, b text, c varchar(10));\n")
    eq([c['name'] for c in s['t']['columns']], ['a', 'b', 'c'], 'one-line CREATE TABLE')


@case('parse: pg_dump shapes — schema-qualified, ONLY, ADD CONSTRAINT')
def _(work):
    s = ddl(work, """
CREATE TABLE IF NOT EXISTS public.users (id bigint NOT NULL, email character varying(255));
CREATE TABLE public.orders (id bigint NOT NULL, user_id bigint);
ALTER TABLE ONLY public.users ADD CONSTRAINT users_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.orders ADD CONSTRAINT orders_user_fk FOREIGN KEY (user_id)
    REFERENCES public.users(id) ON DELETE CASCADE ON UPDATE CASCADE;
COMMENT ON TABLE public.users IS 'members';
COMMENT ON COLUMN public.users.email IS 'login id';
""")
    eq(s['users']['pk'], ['id'], 'PK from ALTER TABLE ONLY')
    eq([(f['column'], f['ref_table'], f['on_delete']) for f in s['orders']['fks']],
       [('user_id', 'users', 'CASCADE')], 'FK and delete rule (ON UPDATE must not leak in)')
    eq(s['users']['note'], 'members', 'COMMENT ON TABLE')
    eq([c['comment'] for c in s['users']['columns'] if c['name'] == 'email'],
       ['login id'], 'COMMENT ON COLUMN')
    eq([c['type'] for c in s['users']['columns'] if c['name'] == 'email'],
       ['varchar(255)'], 'character varying(N) normalizes like introspect')


@case('parse: two-part COMMENT ON COLUMN (no schema)')
def _(work):
    s = ddl(work, """
CREATE TABLE t (id bigint PRIMARY KEY, email text);
COMMENT ON COLUMN t.email IS 'hand written';
""")
    eq([c['comment'] for c in s['t']['columns'] if c['name'] == 'email'],
       ['hand written'], 'two-part column comment')


@case('parse: same name in two schemas stays two tables')
def _(work):
    s = ddl(work, """
CREATE TABLE shop.orders (id bigint PRIMARY KEY, amount numeric(10,2));
CREATE TABLE mart.orders (id bigint PRIMARY KEY, loaded_at timestamptz);
CREATE UNIQUE INDEX uq ON shop.orders (amount);
""")
    eq(sorted(s), ['mart.orders', 'shop.orders'], 'schema-qualified keys')
    eq(s['shop.orders']['uniques'], [['amount']], 'unique index attaches by schema')
    eq(s['mart.orders']['uniques'], [], 'and not to the other schema')


@case('parse: composite FK pairs columns positionally')
def _(work):
    s = ddl(work, """
CREATE TABLE order_items (order_id bigint, line_no int, PRIMARY KEY (order_id, line_no));
CREATE TABLE notes (
  id bigint PRIMARY KEY, o bigint, l int,
  FOREIGN KEY (o, l) REFERENCES order_items(order_id, line_no) ON DELETE CASCADE
);
""")
    eq([(f['column'], f['ref_column']) for f in s['notes']['fks']],
       [('o', 'order_id'), ('l', 'line_no')], 'child column ↔ parent column by position')


@case('parse: REFERENCES serial_numbers does not make a column identity')
def _(work):
    s = ddl(work, """
CREATE TABLE t (id bigint PRIMARY KEY, ref bigint REFERENCES serial_numbers(id));
""")
    c = [x for x in s['t']['columns'] if x['name'] == 'ref'][0]
    eq((c['identity'], c['not_null']), (False, False), 'substring SERIAL must not match')


@case('parse: DDL only, no database')
def _(work):
    s = ddl(work, """
CREATE TABLE orders (id bigint PRIMARY KEY, m bigint REFERENCES merchants(id));
""")
    has(sorted(s), 'merchants', 'referenced-but-undefined table is kept')
    eq(s['merchants']['columns'], [], 'with no columns')
    run('build_erd.py', work)          # 예전엔 여기서 max() 가 죽었다
    if not (work / 'out' / 'erd_full.png').exists():
        raise Fail('a column-less table must render as a title-only box')


# ── 인트로스펙션 ─────────────────────────────────────────────────────────────
# 진짜 DB 없이 introspect 의 **판단**을 재현하는 가짜 psql. 진짜 서버가 하는 것만 한다:
#   · 조회가 JSON 으로 싸여 오면 JSON 한 줄씩, 아니면 받은 -F·-R 로 이어 붙여 내보낸다
#     (전송이 구분자 방식으로 되돌아가면 값 속 \x1e 가 행을 쪼개는 것까지 재현된다)
#   · FAKE_PG_VER 이 11 미만이면 conparentid 를 묻는 조회를 거절한다 (PG 10 이하)
#   · FAKE_FAIL 에 적힌 조각이 든 조회는 **몇 행 흘린 뒤** 죽는다 (문 타임아웃·재기동)
_FAKE_PSQL = '''\
import json
import os
import re
import sys
a = sys.argv
sep = a[a.index('-F') + 1]
rs = a[a.index('-R') + 1] if '-R' in a else chr(10)
q = a[a.index('-c') + 1]
NL, RS, FS = chr(10), chr(30), chr(31)
ver = int(os.environ.get('FAKE_PG_VER', '160000'))
rows = []
if 'server_version' in q:
    rows = [['%d.%d' % (ver // 10000, ver % 100), str(ver)]]
elif 'information_schema.columns' in q:
    rows = [['s1', 'claims', 'id', 'bigint', 'NO', '', 'NO', ''],
            ['s1', 'claims', 'owner_id', 'bigint', 'YES', '', 'NO', ''],
            ['s2', 'owners', 'id', 'bigint', 'NO', '', 'NO', ''],
            ['s1', 'tricky', 'id', 'bigint', 'NO', '', 'NO', ''],
            ['s1', 'tricky', 'note', 'text', 'YES',
             "'line1" + NL + "line2'::text", 'NO', ''],
            ['s1', 'tricky', 'ctrl', 'text', 'YES',
             "'has" + RS + "record" + RS + "sep'::text", 'NO',
             'comment with ' + RS + ' RS and ' + FS + ' FS inside']]
elif 'PRIMARY KEY' in q:
    rows = [['s1', 'claims', 'id'], ['s2', 'owners', 'id'], ['s1', 'tricky', 'id']]
elif "contype='f'" in q:
    if 'conparentid' in q and ver < 110000:
        sys.stderr.write('ERROR:  column con.conparentid does not exist' + NL)
        sys.exit(1)
    rows = [['s1', 'claims', 'owner_id', 'hidden', 'owners', 'id', 'NO ACTION'],
            ['s1', 'tricky', 'id', 's2', 'owners', 'id', 'CASCADE']]
if rows:
    m = re.search(r'_r\\(([^()]*)\\)\\s*$', q)
    if m:                          # 구조화 출력 — 값이 무엇을 담아도 한 행이 한 줄이다
        names = [c.strip() for c in m.group(1).split(',')]
        out = NL.join(json.dumps(dict(zip(names, r))) for r in rows) + NL
    else:
        out = rs.join(sep.join(r) for r in rows) + NL
    sys.stdout.write(out)
fail = os.environ.get('FAKE_FAIL', '')
if fail and fail in q:
    sys.stdout.flush()             # 흘릴 만큼 흘리고 죽는다 — 부분 출력 + 0 아닌 종료
    sys.stderr.write('ERROR:  canceling statement due to statement timeout' + NL)
    sys.exit(1)
'''


def db_fake(work, **env):
    import shlex
    work.mkdir(parents=True, exist_ok=True)
    fake = work / 'fake_psql.py'
    fake.write_text(_FAKE_PSQL, encoding='utf-8')
    e = {'ERD_PSQL': f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}',
         'ERD_SCHEMAS': 's1,s2'}
    e.update(env)
    return e


@case('introspect: an FK parent you cannot see is dropped, not rewired')
def _(work):
    # hidden.owners 는 목록 밖 — 같은 이름의 s2.owners 로 갈아타면 없는 관계가 그려진다
    r = run('introspect.py', work, env=db_fake(work))
    s = json.loads((work / 'schema.json').read_text())
    eq(s['claims']['fks'], [], 'an FK to hidden.owners must not become s2.owners')
    has(r.stdout, 'outside the target: 1', 'the dropped FK is counted, not silent')


@case('introspect: a newline inside a default does not forge a row')
def _(work):
    run('introspect.py', work, env=db_fake(work))
    s = json.loads((work / 'schema.json').read_text())
    eq(sorted(s), ['claims', 'owners', 'tricky'], 'no ghost table from a split row')
    eq([c['default'] for c in s['tricky']['columns'] if c['name'] == 'note'],
       ["'line1\nline2'::text"], 'the default keeps both of its lines')


@case('introspect: partition copies of an FK are filtered in the query')
def _(work):
    # 파티션마다 복제된 제약은 SQL 에서 걸러진다 — 여기서는 그 술어가 지워지지
    # 않았는지만 지킨다 (충실한 재현은 진짜 DB 가 필요하다)
    sys.path.insert(0, str(HERE))
    import introspect
    has(introspect.Q_FK, 'conparentid=0',
        'inherited (per-partition) constraint copies must be filtered out')


# ── 손으로 쓴 DDL 의 주석 소유권 ─────────────────────────────────────────────
# 규칙은 하나다: **주석은 아래로 붙는다**. 같은 줄 앞에 코드가 있으면 그 코드 것이고,
# 제 줄을 쓰는 주석은 바로 아래 코드 것이며, 아래에 코드가 없으면 임자가 없다.
# 콤마로 재던 두 판이 번갈아 한쪽을 깨뜨렸으므로 두 방식을 같은 자리에서 함께 지킨다.
@case('parse: a comment above a column describes that column')
def _(work):
    s = ddl(work, """
CREATE TABLE accounts (
  -- account identifier
  id bigint PRIMARY KEY,
  -- login email address
  email varchar(255) NOT NULL,
  -- account balance in cents
  balance bigint NOT NULL
);
""")
    eq({c['name']: c['comment'] for c in s['accounts']['columns']},
       {'id': 'account identifier', 'email': 'login email address',
        'balance': 'account balance in cents'},
       'comment-above-column must not shift every description down by one')


@case('parse: both comment styles in one table')
def _(work):
    s = ddl(work, """
CREATE TABLE t (
  id bigint PRIMARY KEY,   -- row id
  -- how much money
  -- in cents
  amount bigint,
  name text  -- display name
  , tenant_id bigint
  -- unique per tenant
  , UNIQUE (tenant_id, name)
  -- nothing below owns this
);
""")
    eq({c['name']: c['comment'] for c in s['t']['columns']},
       {'id': 'row id', 'amount': 'how much money in cents',
        'name': 'display name', 'tenant_id': ''},
       'trailing, stacked-above and leading-comma comments each keep their own column')
    eq(s['t']['uniques'], [['tenant_id', 'name']], 'the constraint itself still parses')


@case('parse: a comment above a constraint is not a column description')
def _(work):
    s = ddl(work, """
CREATE TABLE t (
  tenant_id bigint,   -- owning tenant
  code text,
  -- unique per tenant
  UNIQUE (tenant_id, code)
);
""")
    eq({c['name']: c['comment'] for c in s['t']['columns']},
       {'tenant_id': 'owning tenant', 'code': ''},
       'a note written above a table-level constraint belongs to no column')


@case('parse: a comment after the last column owns nothing')
def _(work):
    s = ddl(work, """
CREATE TABLE t (
  id bigint PRIMARY KEY,
  balance bigint NOT NULL   -- in cents
  -- TODO: add a currency column
);
CREATE TABLE u (
  id bigint PRIMARY KEY,
  -- first and last
  name text,
  -- TODO: add an email column
);
""")
    eq({c['name']: c['comment'] for c in s['t']['columns']},
       {'id': '', 'balance': 'in cents'},
       'a note before the closing paren must not overwrite the last description')
    eq({c['name']: c['comment'] for c in s['u']['columns']},
       {'id': '', 'name': 'first and last'},
       'and the same after a trailing comma')


# 4개 필드로 풀던 자리들 — 값에 개행이 들어오면 그대로 ValueError 였다.
# 컬럼 이름에도 개행이 들어갈 수 있다: create table t ("a<개행>b" int) 는 합법이다.
_FAKE_PSQL_DDL = '''\
import sys
a = sys.argv
sep = a[a.index('-F') + 1]
rs = a[a.index('-R') + 1] if '-R' in a else chr(10)
q = a[a.index('-c') + 1]
NL = chr(10)
if "'src'" in q:
    rows = [['lookup', 'co' + NL + 'de', 'text', 'NO']]
else:
    rows = [['merchants', 'id', 'bigint', 'NO'],
            ['merchants', 'me' + NL + 'mo', 'text', 'YES']]
sys.stdout.write(rs.join(sep.join(r) for r in rows) + NL)
'''


@case('parse: a newline inside a fetched value does not kill the parser')
def _(work):
    import shlex
    work.mkdir(parents=True, exist_ok=True)
    fake = work / 'fake_psql.py'
    fake.write_text(_FAKE_PSQL_DDL, encoding='utf-8')
    env = {'ERD_PSQL': f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}',
           'ERD_REF_SCHEMA': 'src', 'ERD_REF_TABLES': 'lookup'}
    d = work / 'sql'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text(
        'CREATE TABLE orders (id bigint PRIMARY KEY, m bigint REFERENCES merchants(id));\n',
        encoding='utf-8')
    run('parse_ddl.py', work, env=env, sql_dir=d)      # 예전엔 여기서 ValueError 였다
    s = json.loads((work / 'schema.json').read_text())
    eq([c['name'] for c in s['merchants']['columns']], ['id', 'me\nmo'],
       'fetch_existing keeps a column name that contains a newline')
    eq([c['name'] for c in s['lookup']['columns']], ['co\nde'],
       'and so does fetch_ref')


# ── 설명 ─────────────────────────────────────────────────────────────────────
@case('merge_desc: common dictionary follows ERD_LANG')
def _(work):
    write_schema(work, {'t': table('t', [col('id'), col('created_at', 'timestamptz')])})
    run('merge_desc.py', work, env={'ERD_LANG': 'ko'})
    s = json.loads((work / 'schema.json').read_text())
    got = [c['comment'] for c in s['t']['columns'] if c['name'] == 'created_at']
    eq(got, ['생성 일시'], 'COMMON dictionary is localized')


@case('merge_desc: a second run does not relabel where descriptions came from')
def _(work):
    write_schema(work, {'t': table('t', [col('id'), col('x', 'text', comment='given')])})
    a = run('merge_desc.py', work).stdout
    b = run('merge_desc.py', work).stdout
    src = lambda out: re.search(r'\{.*\}', out).group(0)
    eq(src(b), src(a), 'provenance stats are stable across runs')


@case('merge_desc: descriptions come back from a previous edition')
def _(work):
    write_schema(work, {'t': table('t', [col('id'), col('x', 'text')])})
    run('merge_desc.py', work)
    run('build_erd.py', work)
    run('build_html.py', work)
    doc = work / 'T.html'
    doc.write_text(doc.read_text(encoding='utf-8').replace(
        '<td></td></tr>', '<td>polished by hand</td></tr>', 1), encoding='utf-8')
    write_schema(work, {'t': table('t', [col('id'), col('x', 'text')])})
    run('merge_desc.py', work, env={'ERD_DOC_HTML': str(doc)})
    s = json.loads((work / 'schema.json').read_text())
    joined = ' '.join(c['comment'] for c in s['t']['columns'])
    has(joined, 'polished by hand', 'a hand-edited description survives regeneration')


# ── 서버가 다르고, 값이 험하고, 조회가 죽는 날 ────────────────────────────────
@case('introspect: a server without conparentid keeps its foreign keys')
def _(work):
    # conparentid 는 PG 11 부터다. 10 이하에 그대로 물으면 FK 조회가 통째로 실패하는데
    # 요약은 그것을 'FK 0' 이라고 참인 양 찍었다 — 관계가 하나도 없는 문서가 exit 0.
    r = run('introspect.py', work, env=db_fake(work, FAKE_PG_VER='100021'))
    s = json.loads((work / 'schema.json').read_text())
    eq([(f['ref_table'], f['on_delete']) for f in s['tricky']['fks']],
       [('owners', 'CASCADE')], 'an old server must still report its foreign keys')
    if 'query failed' in r.stdout:
        raise Fail(f'the FK query must not be sent as-is to an old server:\n{r.stdout}')
    sys.path.insert(0, str(HERE))
    import introspect
    has(introspect.q_fk(110000), 'conparentid', 'PG 11+ still filters partition copies')
    if 'conparentid' in introspect.q_fk(100021):
        raise Fail('PG 10 must not be asked for a column it does not have')


@case('introspect: a control character in a value cannot forge a row')
def _(work):
    # 값 하나에 든 \x1e 가 행을 쪼개 테이블 1개짜리 DB 를 4개로 읽혔다. 구분자를 무엇으로
    # 골라도 값이 그 바이트를 담을 수 있다 — 전송이 구분자를 쓰지 않아야 끝나는 이야기다.
    run('introspect.py', work, env=db_fake(work))
    s = json.loads((work / 'schema.json').read_text())
    eq(sorted(s), ['claims', 'owners', 'tricky'], 'no ghost table from \x1e in a value')
    got = {c['name']: (c['default'], c['comment']) for c in s['tricky']['columns']}
    eq(got['ctrl'], ("'has\x1erecord\x1esep'::text",
                     'comment with RS and FS inside'),
       'the value arrives whole and does not shift into the next column')
    eq(got['note'][0], "'line1\nline2'::text", 'and a newline still survives too')


@case('introspect: a half-read database is refused, not documented')
def _(work):
    # 일곱 조회 중 하나만 죽어도 예전엔 완성본이 나왔다: Q_PK 가 죽으면 모든 pk 가 [],
    # 요약은 멀쩡, exit 0. 몇 행 흘린 뒤 죽은 조회는 경고조차 없었다.
    r = run('introspect.py', work, expect_ok=False,
            env=db_fake(work, FAKE_FAIL='PRIMARY KEY'))
    if 'Traceback' in r.stderr:
        raise Fail(f'should be a message:\n{r.stderr[-300:]}')
    has(r.stdout, 'database query failed',
        'a query that died after streaming rows must still warn')
    has(r.stdout + r.stderr, 'primary keys', 'the message names what could not be read')
    if (work / 'schema.json').exists():
        raise Fail('a half-read schema must not be written as if it were complete')

    # 없어도 그림이 나오는 부가정보는 멈추지 않는다 — 대신 무엇이 빠졌는지 이름을 댄다
    r = run('introspect.py', work, env=db_fake(work, FAKE_FAIL='pg_indexes'))
    has(r.stdout, 'indexes', 'an optional query names itself in the summary when it fails')
    if not (work / 'schema.json').exists():
        raise Fail('an optional query must not stop the run')


# ── spec ────────────────────────────────────────────────────────────────────
@case('spec: a typo names what is wrong instead of a traceback')
def _(work):
    write_schema(work, {'t': table('t', [col('id')])})
    (work / 'erd.spec.json').write_text(json.dumps(
        {'areas': [['A', 'ok', 'public', ['t', 'ghost']], ['B', 'empty', 'public', []]]}))
    out = run('build_erd.py', work).stdout
    has(out, 'ghost', 'the missing table is named')
    (work / 'erd.spec.json').write_text('{ "areas": [')
    r = run('build_erd.py', work, expect_ok=False)
    if 'Traceback' in r.stderr:
        raise Fail(f'broken spec should not traceback:\n{r.stderr[-400:]}')


@case('spec: a bad layer colour is refused, not pasted into the document')
def _(work):
    write_schema(work, {'t': table('t', [col('id')])})
    (work / 'erd.spec.json').write_text(json.dumps(
        {'areas': [['A', 'ok', 'public', ['t']]],
         'layers': {'A': ['#12345', '#35507D', '#4A80C0', 'x']}}))
    r = run('build_erd.py', work, expect_ok=False)
    if 'Traceback' in r.stderr:
        raise Fail('bad colour should be a message, not a traceback')
    has(r.stdout + r.stderr, '#12345', 'the offending value is shown')


# ── 검증을 검증한다 ──────────────────────────────────────────────────────────
# 그림 품질에 대한 이 스킬의 주장은 전부 자체검증 한 줄에 얹혀 있다. 그래서 **그 줄을
# 읽는 쪽**이 눈을 감으면 나머지 시험이 다 통과해도 아무것도 지켜지지 않는다. 실제로
# 그 줄에 (허용)·[경고] 꼬리가 붙자 숫자를 긁던 정규식이 마지막 항목을 놓쳤고, 가로선
# 중첩이 44 여도 render 항목은 전부 통과라고 했다. 여기 담는 것은 그 자리다.
@case('verify: a clean verdict is computed here, not taken from the record')
def _(work):
    # 이 케이스가 막는 것은 그림 버그가 아니라 **시험이 눈을 감는 것**이다. 검사하는
    # 쪽이 재는 쪽의 판정(warn·tolerated)을 다시 믿기 시작하면, 아래 세 가지가 전부
    # 통과로 돌아선다 — 실제로 셋 다 한 번씩 전부 통과였다.
    honest = {'file': 'erd_area_A.png',
              'counts': {'label_table': 0, 'label_x': 0, 'thru': 0,
                         'v_overlap': 0, 'h_overlap': 2},
              'tolerated': [], 'warn': ['h_overlap']}
    if not verify_faults(honest):
        raise Fail('a real regression must be a fault')
    # ① 재는 쪽이 경고를 지워도 판정은 그대로여야 한다
    if not verify_faults({**honest, 'warn': []}):
        raise Fail('an empty warn list must not make a nonzero count clean')
    # ② tolerate 를 전 항목으로 넓혀도 마찬가지다
    if not verify_faults({**honest, 'warn': [], 'tolerated': list(MEASURES)}):
        raise Fail('the code tolerating a check must not silence the test')
    # ③ 재기를 그만두고 n/a 를 찍는 것은 '깨끗하다' 가 아니다
    blind = {'file': 'erd_area_A.png', 'counts': {k: None for k in MEASURES},
             'tolerated': [], 'warn': []}
    eq(len(verify_faults(blind)), len(MEASURES), 'every unmeasured check is a fault')
    # 라벨을 안 그리는 개요도에서만 라벨 항목이 n/a 여도 된다 — 그 밖은 아니다
    ov = {'file': 'erd_overview.png',
          'counts': {'label_table': None, 'label_x': None, 'thru': 0,
                     'v_overlap': 0, 'h_overlap': 0}, 'tolerated': [], 'warn': []}
    eq(verify_faults(ov), [], 'the overview draws no labels — n/a is honest there')
    eq(verify_faults({**ov, 'file': 'erd_area_A.png'})[:1],
       ['label_table: n/a — a check that stopped measuring is not a clean check'],
       'the same n/a on a diagram that does draw labels is an escape hatch')
    # ④ 항목이 이름째 사라지면 남은 것이 전부 0 이라 조용히 통과한다
    gone = {'file': 'erd_area_A.png',
            'counts': {k: 0 for k in MEASURES if k != 'thru'}, 'tolerated': [], 'warn': []}
    if not verify_faults(gone):
        raise Fail('a check that vanished from the record must be a fault')
    extra = {'file': 'erd_area_A.png',
             'counts': {**{k: 0 for k in MEASURES}, 'brand_new': 0},
             'tolerated': [], 'warn': []}
    if not verify_faults(extra):
        raise Fail('a check the code added but this test ignores must be a fault')
    # ⑤ 봐주기는 케이스가 숫자로 적을 때만, 그 숫자까지만
    eq(verify_faults(honest, {'h_overlap': 2}), [], 'an explicit allowance covers it')
    if not verify_faults(honest, {'h_overlap': 1}):
        raise Fail('an allowance must not cover more than the number it names')


@case('verify: the printed line and the machine record say the same thing')
def _(work):
    # 사람이 읽는 줄과 기계가 읽는 기록이 갈라지면 둘 중 하나는 거짓말이 된다.
    #
    # 예전엔 항목마다 `has(line, ...)` 로 조각을 찾고 `'[warn]' in line == bool(warn)`
    # 을 봤다. 그런데 붙박이 fixture 는 어느 그림도 경고를 내지 않아서, 그 마지막 줄은
    # 모든 그림에서 False == False 를 비교했다 — 경고 꼬리는 한 번도 재지 않았다.
    # (허용) 서식도 마찬가지로 한 번도 지나가지 않았다.
    #
    # 그래서 ① 세 갈래(숫자·n/a·허용·경고)가 다 나오는 입력을 쓰고 ② 조각이 아니라
    # **줄 전체를 기록에서 되만들어** 글자까지 맞춘다. 꼬리·서식·항목 순서가 다 걸린다.
    sys.path.insert(0, str(HERE))
    import lang.en as en
    write_schema(work, hub_schema(24))
    seen = {'a number': 0, 'n/a': 0, 'tolerated': 0, 'the warn tail': 0}

    def check(stdout):
        """방금 돈 판이 찍은 줄과 그 판이 남긴 기록을 짝지어 글자까지 맞춘다.

        기록은 판마다 처음부터 다시 쓰이므로(erd.verify_log), 한 판이 끝난 그 자리에서
        읽어야 그 판의 것만 본다. 줄 순서 = 기록 순서다.
        """
        lines = [x.strip() for x in stdout.split('\n') if 'verify ' in x]
        recs = verify_recs(work)
        eq(len(lines), len(recs), 'one machine record per printed verify line')
        for line, r in zip(lines, recs):
            parts = []
            for k in MEASURES:
                v = r['counts'][k]
                if v is None:
                    shown, kind = en.M['verify.na'], 'n/a'
                elif v and k in r['tolerated']:
                    shown, kind = en.M['verify.tolerated'].format(n=v), 'tolerated'
                else:
                    shown, kind = str(v), 'a number'
                seen[kind] += 1
                parts.append(f"{en.M['verify.' + k]} {shown}")
            want = en.M['log.verify'].format(name=r['file'], report=' · '.join(parts))
            if r['warn']:
                want += en.M['verify.warn'].format(
                    list=', '.join(en.M['verify.' + k] for k in r['warn']))
                seen['the warn tail'] += 1
            eq(line, want.strip(),
               f'{r["file"]}: the printed line is exactly what the record says')

    check(run('build_erd.py', work).stdout)

    # 같은 전체도를 '봐주기 없이' 한 번 더 그린다 — 경고 꼬리가 붙은 줄을 실제로 만든다.
    # tolerate 는 draw_erd 의 인자라, 코드를 고치지 않고 시험 쪽에서 끌 수 있다.
    probe = work / 'probe.py'
    probe.write_text(
        "import erd\n"
        "pos, boxes, groups = erd.layout_global()\n"
        "erd.draw_erd(erd.OUT / 'erd_full.png', list(erd.SCHEMA), pos, boxes, 'again',\n"
        "             with_desc=True, scale=2, legend=True, groups=groups,\n"
        "             derives=True, tolerate=())\n", encoding='utf-8')
    check(run(str(probe), work, env={'PYTHONPATH': str(HERE)}).stdout)

    for kind, n in seen.items():
        if not n:
            raise Fail(f'no diagram exercised {kind} — the fixture proves nothing about it. '
                       f'(the hub fixture is expected to leave a few horizontal overlaps '
                       f'on the full diagram; if the layout got better, pick another one)')


@case('verify: a diagram without labels does not report a label check it never ran')
def _(work):
    # 개요도는 관계 라벨을 아예 그리지 않는다(edge_labels=False). 그러면 라벨 겹침은
    # 잴 것이 없는데도 예전엔 0 이 찍혔다 — 검사하지 않은 것을 '깨끗하다' 로 읽히게
    # 하는 것은 이 저장소가 몇 판째 반복해 온 바로 그 잘못이다.
    write_schema(work, {
        'a': table('a', [col('id'), col('b_id')], pk=['id'],
                   fks=[{'column': 'b_id', 'ref_table': 'b', 'ref_column': 'id',
                         'on_delete': 'CASCADE'}]),
        'b': table('b', [col('id')], pk=['id'])})
    out = run('build_erd.py', work).stdout
    ov = verify_recs(work, 'overview')[0]
    for k in ('label_table', 'label_x'):
        if ov['counts'][k] is not None:
            raise Fail(f'the overview draws no labels — {k} cannot be a number')
    has([x for x in out.split('\n') if 'overview' in x and 'verify' in x][0],
        'n/a', 'the printed line says so too, instead of a reassuring 0')
    # 라벨을 그리는 그림에서는 반대로 반드시 숫자여야 한다 (n/a 로 도망가지 못하게)
    for r in verify_recs(work, 'area'):
        for k in ('label_table', 'label_x'):
            if r['counts'][k] is None:
                raise Fail(f'{r["file"]} draws labels — {k} must actually be measured')


@case('verify: a plain hub-and-spoke schema raises no warning on its first run')
def _(work):
    # 21테이블 두 허브 — 아무 데도 이상한 구석이 없는 입력이다. 그런데도 첫 판부터
    # `erd_area_B: 가로선 중첩 2 [경고]` 가 나왔다. [경고] 는 회귀 신호인데 평범한
    # 입력에서 울리면 사람은 그것을 무시하는 법부터 배운다 — 신호가 죽는다.
    t = {}
    for hub, n in (('shop', 10), ('user', 9)):
        t[f'{hub}_hub'] = table(f'{hub}_hub', [col('id'), col('name', 'text')], pk=['id'])
        for i in range(n):
            nm = f'{hub}_t{i:02d}'
            cols, fks = [col('id'), col('hub_id')], [
                {'column': 'hub_id', 'ref_table': f'{hub}_hub', 'ref_column': 'id',
                 'on_delete': 'CASCADE'}]
            if i >= 2:                      # 형제를 하나 건너 참조 — 통로가 붐빈다
                cols.append(col('prev_id'))
                fks.append({'column': 'prev_id', 'ref_table': f'{hub}_t{i - 2:02d}',
                            'ref_column': 'id', 'on_delete': 'SET NULL'})
            t[nm] = table(nm, cols, pk=['id'], fks=fks)
    write_schema(work, t)
    r = run('build_erd.py', work)
    verify_clean(work, what='an ordinary schema must not warn on its first run')
    if '[warn]' in r.stdout:
        raise Fail(f'a [warn] a user would learn to ignore:\n{r.stdout}')


@case('verify: relationships that cross the corridors do not stack on an exit row')
def _(work):
    # 위 허브-앤-스포크는 진출입 꼬리끼리 스치는 쪽이었다. 이쪽은 다른 갈래다:
    # 열을 건너뛰는 선이 통로에서 고른 lane 이, **나중에** 정해진 다른 관계의 진출입
    # y 위에 그대로 얹혔다. 진출입 y 를 다 잡은 뒤에야 lane 을 고르게 바꿔 고쳤다.
    # 관계가 고르게 퍼진 스키마에서는 재현되지 않아, 어긋난 참조를 그대로 박아 둔다.
    link = {'ord_t00': ['inv_t03'], 'ord_t02': ['inv_t02', 'inv_t00'],
            'ord_t03': ['ord_t04'], 'ord_t04': ['ord_t03', 'usr_t04'],
            'usr_t01': ['inv_t00', 'ord_t02'], 'usr_t02': ['inv_t00'],
            'usr_t03': ['inv_t02'], 'usr_t04': ['inv_t03', 'usr_t03'],
            'inv_t00': ['usr_t03'], 'inv_t01': ['usr_t03'], 'inv_t02': ['inv_t04']}
    t = {}
    for p in ('ord', 'usr', 'inv'):
        for i in range(5):
            nm = f'{p}_t{i:02d}'
            cols, fks = [col('id'), col('v', 'text')], []
            for j, ref in enumerate(link.get(nm, [])):
                cols.append(col(f'r{j}'))
                fks.append({'column': f'r{j}', 'ref_table': ref, 'ref_column': 'id',
                            'on_delete': 'CASCADE'})
            t[nm] = table(nm, cols, pk=['id'], fks=fks)
    write_schema(work, t)
    r = run('build_erd.py', work)
    verify_clean(work, what='a corridor lane must not land on a column exit row')
    if '[warn]' in r.stdout:
        raise Fail(f'a [warn] a user would learn to ignore:\n{r.stdout}')


@case('selftest: the suite does not inherit the caller ERD_* environment')
def _(work):
    # `ERD_LABEL=shop python3 selftest.py` 는 2개, `ERD_EXCLUDE=.* ` 는 19개를
    # 깨뜨렸다. 문서가 권하는 다중 DB 흐름을 그대로 따른 사람이 `install.sh --check`
    # 에서 '설치가 고장 났다' 는 말을 들었다. 시험은 코드를 재야지 껍데기를 재면 안 된다.
    write_schema(work, {'t': table('t', [col('id'), col('v', 'text')])})
    clean = run('build_erd.py', work).stdout
    poison = {'ERD_EXCLUDE': '.*', 'ERD_LABEL': 'shop', 'ERD_LANG': 'ko',
              'ERD_DOCNAME': 'leaked', 'ERD_SVG_TITLE': '1'}
    keep = {k: os.environ.get(k) for k in poison}
    os.environ.update(poison)
    try:
        eq(run('build_erd.py', work).stdout, clean,
           'the caller environment must not reach the scripts under test')
    finally:
        for k, v in keep.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


# ── 그림 ─────────────────────────────────────────────────────────────────────
@case('render: two self-references draw as two loops')
def _(work):
    write_schema(work, {'cat': table(
        'cat', [col('id'), col('parent_id'), col('root_id')], pk=['id'],
        fks=[{'column': 'parent_id', 'ref_table': 'cat', 'ref_column': 'id',
              'on_delete': 'SET NULL'},
             {'column': 'root_id', 'ref_table': 'cat', 'ref_column': 'id',
              'on_delete': 'SET NULL'}])})
    run('build_erd.py', work)
    verify_clean(work, what='self-loops must not overlap')
    # 루프의 팔 높이는 라우터가 고른 값이라 중첩 검사에서 면제되지 않는다. 두 루프가
    # 포개지면 v_overlap·h_overlap 이 잡는다 — 이 항목이 정말로 재고 있는지(0 이
    # 아니라 '재지 않음' 이 아닌지) 못박는다. 이 항목이 장식이던 판이 있었다.
    for r in verify_recs(work):
        for k in ('v_overlap', 'h_overlap'):
            if r['counts'][k] is None:
                raise Fail(f'{r["file"]}: {k} was not measured at all')
    for r in verify_recs(work, 'area'):
        if r['counts']['label_x'] is None:
            raise Fail('the area diagram draws both loop labels — label↔label must be measured')
    svg = (work / 'out' / 'erd_area_A.svg').read_text(encoding='utf-8')
    eq(svg.count('parent_id'), 2, 'each loop keeps its own label')   # 라벨 + 컬럼행


@case('render: a hub with many children keeps lines out of the tables')
def _(work):
    t = {'hub': table('hub', [col('id'), col('name', 'text')], pk=['id'])}
    for i in range(24):
        n = f'c{i:02d}'
        t[n] = table(n, [col('id'), col('hub_id')], pk=['id'],
                     fks=[{'column': 'hub_id', 'ref_table': 'hub', 'ref_column': 'id',
                           'on_delete': 'CASCADE'}])
    write_schema(work, t)
    run('build_erd.py', work)
    for r in verify_recs(work, 'area'):
        if r['counts']['thru'] != 0:
            raise Fail(f'a line runs through a table: {r["file"]} thru={r["counts"]["thru"]}')


@case('render: many unrelated tables do not become a vertical ribbon')
def _(work):
    # 예전엔 60테이블 하나에 1:4 였다. 열 수를 옛 고정값(4)으로 되돌리면 그 자리는
    # 1:2.30 이라 통과한다 — 고칠 때 잡으라고 둔 시험이 정작 그 회귀를 통과시킨다.
    # 리본이 되는지는 **테이블이 늘 때 비율이 어떻게 되는가**로 재야 보인다:
    # 고정 4열이면 60→200 에서 1:2.30 → 1:7.26 으로 자라고(열은 그대로, 세로만 길어짐),
    # 열 수가 따라 늘면 1:1.49 → 1:1.82 로 거의 그대로다.
    from PIL import Image
    ratio = {}
    for n in (60, 200):
        write_schema(work, {f't{i:03d}': table(f't{i:03d}', [col('id'), col('v', 'text')])
                            for i in range(n)})
        run('build_erd.py', work)
        w, h = Image.open(work / 'out' / 'erd_full.png').size
        ratio[n] = h / w
        if ratio[n] > 3:
            raise Fail(f'{n} tables → aspect ratio 1:{ratio[n]:.2f} — '
                       f'unreadable once fitted into a document')
    if ratio[200] > ratio[60] * 1.5:
        raise Fail(f'the sheet only grows downward: 1:{ratio[60]:.2f} at 60 tables → '
                   f'1:{ratio[200]:.2f} at 200 — columns are not keeping up')


@case('render: badge clears the name on a title-only box')
def _(work):
    # 컬럼을 모르는 테이블(참조만 되고 정의가 없는 것)도 배지를 단다. 상자 폭이
    # 제목 폭만 보고 정해지면 배지가 이름 위에 얹힌다 — 픽셀 대신 기하로 잰다:
    # 오른쪽 정렬로 그려질 배지의 왼쪽 끝이 제목의 오른쪽 끝보다 오른쪽이어야 한다.
    write_schema(work, {
        'orders': table('orders', [col('id'), col('m')], origin='new', pk=['id'],
                        fks=[{'column': 'm', 'ref_table': 'merchants',
                              'ref_column': 'id', 'on_delete': 'NO ACTION'}]),
        'merchants': table('merchants', [])})
    probe = work / 'probe.py'
    probe.write_text(
        "import erd\n"
        "f = erd.load_fonts()\n"
        "for name in erd.SCHEMA:\n"
        "    box = erd.measure(name)\n"
        "    bd, _c = erd.badge(name)\n"
        "    name_right = erd.PAD + erd.tw(name, f['title'])\n"
        "    badge_left = box['w'] - erd.PAD - erd.tw(bd, f['badge'])\n"
        "    assert badge_left > name_right, (\n"
        "        f'{name}: badge at x={badge_left} overlaps name ending at x={name_right}')\n",
        encoding='utf-8')
    run(str(probe), work, env={'PYTHONPATH': str(HERE)})


# ── 산출물 ───────────────────────────────────────────────────────────────────
@case('artifacts: html, docx and graphml describe the same schema')
def _(work):
    t = {'a': table('a', [col('id'), col('x', 'text', comment='note a')], pk=['id']),
         'b': table('b', [col('id'), col('a_id')], pk=['id'],
                    fks=[{'column': 'a_id', 'ref_table': 'a', 'ref_column': 'id',
                          'on_delete': 'CASCADE'}])}
    write_schema(work, t)
    run('merge_desc.py', work)
    run('build_erd.py', work)
    run('build_html.py', work)
    run('build_docx.py', work)
    # 세 벌 다 **자리를 못박아** 본다. 예전엔 GraphML·docx 쪽이 맨 `in` 검사였다:
    # graphml_node() 가 빈 문자열을 돌려주게 해도 통과했다 — <node> 가 하나도 없는
    # GraphML 인데, 남은 <edge> 하나가 'a' 와 'b' 를 둘 다 품고 있어서다. GraphML 은
    # 이 스킬이 내건 네 산출물 중 하나인데 텅 빈 채로 나갈 수 있었다.
    html = (work / 'T.html').read_text(encoding='utf-8')
    for name in t:
        has(html, f'<h4 id="tb_{name}">', f'{name} has its own section in the HTML')

    import xml.etree.ElementTree as ET
    NS = {'g': 'http://graphml.graphdrawing.org/xmlns',
          'y': 'http://www.yworks.com/xml/graphml'}
    root = ET.parse(work / 'T.graphml').getroot()
    nodes = root.findall('.//g:node', NS)
    titles = []
    for n in nodes:
        for lab in n.findall('.//y:NodeLabel', NS):
            if 'label.name' in (lab.get('configuration') or ''):
                titles.append((lab.text or '').split('  ·  ')[0])
    eq(sorted(titles), sorted(t), 'one GraphML <node> per table, each carrying its name')
    edges = root.findall('.//g:edge', NS)
    eq([(e.get('source'), e.get('target')) for e in edges],
       [(nodes[1].get('id'), nodes[0].get('id'))], 'the one FK is the one GraphML edge')
    eq([e.findtext('g:data[@key="d3"]', namespaces=NS) for e in edges], ['a_id : id'],
       'and it says which columns it joins')

    # docx 도 4장의 테이블별 절 제목으로 못박는다 — 어디든 이름이 스치기만 하면
    # 통과하던 검사는 컬럼표가 통째로 빠져도 몰랐다.
    from docx import Document
    doc = Document(str(work / 'T.docx'))
    heads = [p.text for p in doc.paragraphs if re.match(r'^4\.\d+\.\d+ ', p.text)]
    eq(sorted(h.split(' ', 1)[1].split(' · ')[0] for h in heads), sorted(t),
       'each table gets its own section in chapter 4 of the docx')
    cells = {c.text for tb in doc.tables for row in tb.rows for c in row.cells}
    for name in t:
        for c in t[name]['columns']:
            if c['name'] not in cells:
                raise Fail(f'the docx column table lost {name}.{c["name"]}')


@case('artifacts: graphml and svg are well-formed xml')
def _(work):
    write_schema(work, {'t': table('t', [
        col('id'), col('x', 'text', comment='an & ampersand <tag> "quote" \x0b')])})
    run('build_erd.py', work)
    import xml.etree.ElementTree as ET
    ET.parse(work / 'T.graphml')
    for svg in (work / 'out').glob('*.svg'):
        ET.parse(svg)


@case('artifacts: html escapes what a comment may contain')
def _(work):
    write_schema(work, {'t': table('t', [
        col('id'), col('x', 'text', comment='<script>alert(1)</script>')])})
    run('build_erd.py', work)
    run('build_html.py', work)
    html = (work / 'T.html').read_text(encoding='utf-8')
    if '<script>alert(1)</script>' in html:
        raise Fail('a comment must not become live markup')


@case('artifacts: no unresolved message keys anywhere')
def _(work):
    # 표식(⟨키⟩)은 i18n.py 것이다. 예전엔 그 모양을 여기에 그대로 적어 두어서, 저쪽이
    # 표식을 바꾸면 이 케이스는 아무것도 못 보면서 계속 통과했다. 표식을 **저쪽에
    # 물어서** 만든다 — 그리고 물어본 답이 키를 담고 있지 않으면 그것부터 실패다.
    write_schema(work, {'t': table('t', [col('id')])})
    sys.path.insert(0, str(HERE))
    from i18n import t
    probe = 'zz_probe.no_such_key'
    mark = t(probe)
    if probe not in mark or mark == probe:
        raise Fail(f'i18n no longer marks an unresolved key ({mark!r}) — '
                   f'this case would look at a document it cannot read')
    lead, tail = mark.split(probe)
    pat = re.escape(lead) + r'[a-z_][a-z._0-9]*' + re.escape(tail)
    for lang in ('en', 'ko', 'ja', 'es'):
        run('merge_desc.py', work, env={'ERD_LANG': lang})
        run('build_erd.py', work, env={'ERD_LANG': lang})
        r = run('build_html.py', work, env={'ERD_LANG': lang})
        text = (work / 'T.html').read_text(encoding='utf-8')
        eq(re.findall(pat, text), [], f'{lang}: unresolved keys in the document')
        # 콘솔로 새는 것도 마찬가지다 — 사용자가 먼저 보는 자리다
        eq(re.findall(pat, r.stdout + r.stderr), [], f'{lang}: unresolved keys on the console')


@case('artifacts: docx pictures fit the page')
def _(work):
    write_schema(work, {f't{i}': table(f't{i}', [col('id'), col('v', 'text')])
                        for i in range(12)})
    run('merge_desc.py', work)
    run('build_erd.py', work)
    r = run('build_docx.py', work)
    from docx import Document
    shapes = Document(str(work / 'T.docx')).inline_shapes
    # 그림이 한 장도 없어도 이 반복문은 조용히 지나갔다 — add_picture 를 통째로 지워도
    # 통과했다. '그림이 페이지에 맞는다' 와 '그림이 없다' 를 구분하지 못하는 검사다.
    # 그려 놓은 PNG 마다 한 장씩 들어가야 한다: 개요도 · 전체도 · 영역별 상세도.
    pngs = sorted(p.name for p in (work / 'out').glob('*.png'))
    eq(len(shapes), len(pngs), f'one picture per diagram drawn ({pngs})')
    if len(pngs) < 3:
        raise Fail(f'the fixture must draw more than a token diagram: {pngs}')
    if 'warn' in r.stdout:
        raise Fail(f'no diagram should have been left out:\n{r.stdout}')
    for s in shapes:
        if s.width.cm > 26.7 or s.height.cm > 18.0:
            raise Fail(f'picture {s.width.cm:.1f}×{s.height.cm:.1f}cm exceeds the page')
        if s.width.cm < 1 or s.height.cm < 1:
            raise Fail(f'picture {s.width.cm:.1f}×{s.height.cm:.1f}cm is not a diagram')


# ── 두 번째 실행 ─────────────────────────────────────────────────────────────
# 한 번 돌렸을 때는 다 맞는데 두 번째부터 어긋나는 것들. 첫 실행만 보면 안 보인다.
def with_manual(work, manual):
    """MANUAL 을 채워 둔 채로 merge_desc 를 돌린다 — 사용자가 사전에 적어 넣은 상태.

    사전은 소스에 적는 것이라 밖에서 넣을 길이 없다. 그래서 임시 디렉토리에 작은
    실행기를 하나 놓고 그것을 돌린다 (run() 은 절대경로면 그대로 쓴다).
    """
    drv = work / 'manual_run.py'
    drv.parent.mkdir(parents=True, exist_ok=True)
    drv.write_text('import sys\n'
                   f'sys.path.insert(0, {str(HERE)!r})\n'
                   'import merge_desc\n'
                   f'merge_desc.MANUAL = {manual!r}\n'
                   'merge_desc.main()\n', encoding='utf-8')
    return run(str(drv), work)


def undescribed(out):
    """'columns still without a description' 목록에 찍힌 키."""
    tail = out.split('without a description:')[-1]
    return re.findall(r'^\s+(\S+)\s+\(', tail, re.M)


@case('merge_desc: the key the tool prints is the key that works')
def _(work):
    write_schema(work, {
        'analytics.events': table('events', [col('kind', 'text')], schema='analytics'),
        'staging.events': table('events', [col('kind', 'text')], schema='staging')})
    keys = undescribed(with_manual(work, {}).stdout)
    eq(sorted(keys), ['analytics.events.kind', 'staging.events.kind'],
       'the list names each column by its own table key')
    out = with_manual(work, {k: f'desc of {k}' for k in keys}).stdout
    eq(undescribed(out), [], 'pasting those keys into MANUAL describes every column')
    s = json.loads((work / 'schema.json').read_text())
    eq({k: t['columns'][0]['comment'] for k, t in s.items()},
       {k.rsplit('.', 1)[0]: f'desc of {k}' for k in keys},
       'and each key lands on the table it names')


@case('merge_desc: a bare key does not bleed into a same-named table')
def _(work):
    write_schema(work, {
        'shop.users': table('users', [col('grade', 'text')], schema='shop'),
        'mart.users': table('users', [col('grade', 'text')], schema='mart'),
        'shop.orders': table('orders', [col('channel', 'text')], schema='shop')})
    out = with_manual(work, {'users.grade': 'shop grade',
                             'shop.users.grade': 'only shop',
                             'orders.channel': 'inbound channel'}).stdout
    s = json.loads((work / 'schema.json').read_text())
    eq({k: t['columns'][0]['comment'] for k, t in s.items()},
       {'shop.users': 'only shop', 'mart.users': '', 'shop.orders': 'inbound channel'},
       'the qualified key wins, the ambiguous bare key is dropped, '
       'and a bare key still works where the name is unique')
    has(out, 'shop.users.grade', 'the ignored bare key is reported with what to use instead')


@case('artifacts: a diagram older than the schema does not reach the document')
def _(work):
    write_schema(work, {'keep': table('keep', [col('id')]),
                        'legacy_audit': table('legacy_audit', [col('id')])})
    run('merge_desc.py', work)
    run('build_erd.py', work)
    run('build_html.py', work)
    has((work / 'T.html').read_text(encoding='utf-8'), 'legacy_audit',
        'the first edition describes both tables')

    # 시간이 흐른 척한다: 스키마만 새로 쓰고 그림은 한 시간 전으로 돌려 둔다
    write_schema(work, {'keep': table('keep', [col('id')])})
    old = (work / 'schema.json').stat().st_mtime - 3600
    for p in (work / 'out').iterdir():
        os.utime(p, (old, old))

    for script in ('build_html.py', 'build_docx.py'):
        r = run(script, work, expect_ok=False)
        if r.returncode == 0:
            raise Fail(f'{script} embedded diagrams older than the schema')
        if 'Traceback' in r.stderr:
            raise Fail(f'{script} should say what is wrong, not traceback:\n{r.stderr[-300:]}')
        has(r.stdout + r.stderr, 'build_erd.py', f'{script} says how to fix it')
    has((work / 'T.html').read_text(encoding='utf-8'), 'legacy_audit',
        'the refused build leaves the previous edition intact, not half-rewritten')

    run('build_erd.py', work)                      # 다시 그리면 지나간다
    run('build_html.py', work)
    html = (work / 'T.html').read_text(encoding='utf-8')
    if 'legacy_audit' in html:
        raise Fail('after redrawing, the dropped table must be gone from text and figures')


# ── 오류 경로 ────────────────────────────────────────────────────────────────
@case('errors: a missing database is explained, not tracebacked')
def _(work):
    r = run('introspect.py', work, expect_ok=False)
    if 'Traceback' in r.stderr:
        raise Fail(f'should be a message:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'ERD_PSQL', 'the message names what to set')


@case('errors: an unusable font is explained')
def _(work):
    write_schema(work, {'t': table('t', [col('id')])})
    r = run('build_erd.py', work, env={'ERD_FONT': '/etc/hosts'}, expect_ok=False)
    if 'Traceback' in r.stderr:
        raise Fail('a non-font file should be a message, not a PIL traceback')
    has(r.stdout + r.stderr, 'ERD_FONT', 'the message names the variable')


@case('errors: a diagram file that is simply missing is a message, not a traceback')
def _(work):
    # 신선도 관문(require_fresh)은 **없는 파일을 세지 않는다** — 일부러 그렇다. 그래서
    # 그림 하나를 지운 뒤 문서를 만들면 관문은 그대로 지나가고, build_docx.py 는 PIL 이
    # 없는 파일을 여는 자리에서 FileNotFoundError 를 사용자에게 그대로 뱉었다.
    # build_html.py 는 같은 상황을 도판만 빼고 경고 한 줄로 넘긴다. 둘이 같아야 한다.
    write_schema(work, {'a': table('a', [col('id')]), 'b': table('b', [col('id')])})
    run('merge_desc.py', work)
    run('build_erd.py', work)
    for ext in ('.png', '.svg'):     # HTML 은 PNG 가 없으면 SVG 로 떨어진다
        (work / 'out' / f'erd_full{ext}').unlink()
    # 빠진 도판이 조용히 빠지면 그림 없는 문서가 그림 있는 문서인 척 나간다 — 둘 다
    # 어느 그림을 못 넣었는지 이름을 대야 한다 (HTML 쪽은 영역 그림만 세고 있었다)
    for script in ('build_html.py', 'build_docx.py'):
        r = run(script, work)
        if 'Traceback' in r.stderr:
            raise Fail(f'{script} tracebacked on a missing diagram:\n{r.stderr[-400:]}')
        has(r.stdout, 'erd_full', f'{script} says which diagram it had to leave out')
    from docx import Document
    pngs = list((work / 'out').glob('*.png'))
    eq(len(Document(str(work / 'T.docx')).inline_shapes), len(pngs),
       'the document still carries every diagram that does exist')
    # 다시 그리면 아무 말 없이 원래대로
    run('build_erd.py', work)
    r = run('build_docx.py', work)
    if 'warn' in r.stdout:
        raise Fail(f'a complete set of diagrams must not warn:\n{r.stdout}')


@case('errors: an old schema.json without new keys still renders')
def _(work):
    # 예전엔 종료 코드 0 말고는 아무것도 보지 않았다. 그림을 한 장도 안 그리고 끝나도
    # 통과였다 — '죽지 않았다' 와 '렌더된다' 는 다른 말이다.
    work.mkdir(parents=True, exist_ok=True)
    (work / 'schema.json').write_text(json.dumps(
        {'t': {'name': 't', 'columns': [{'name': 'id', 'type': 'bigint', 'comment': ''}],
               'fks': [{'column': 'p', 'ref_table': 'u', 'ref_column': 'id'}]},
         'u': {'name': 'u', 'columns': [{'name': 'id', 'type': 'bigint', 'comment': ''}]}}))
    run('build_erd.py', work)
    from PIL import Image
    for stem in ('erd_overview', 'erd_full'):
        p = work / 'out' / f'{stem}.png'
        if not p.exists():
            raise Fail(f'{stem}.png was never drawn — exit 0 is not a rendered diagram')
        if min(Image.open(p).size) < 50:
            raise Fail(f'{stem}.png is {Image.open(p).size} — an empty canvas, not a diagram')
    if not list((work / 'out').glob('erd_area_*.png')):
        raise Fail('no area diagram came out of an old schema.json')
    # 새 키가 없어도 옛 스키마의 테이블·관계가 문서까지 간다
    run('build_html.py', work)
    html = (work / 'T.html').read_text(encoding='utf-8')
    for name in ('t', 'u'):
        has(html, f'<h4 id="tb_{name}">', f'{name} reached the document from an old schema')


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
    if FAILED:
        print(f'\033[31m{len(FAILED)} of {len(cases)} failed\033[0m')
        return 1
    print(f'\033[32mall {len(cases)} passed\033[0m')
    return 0


if __name__ == '__main__':
    sys.exit(main())
