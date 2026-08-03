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
    if needle not in hay:
        raise Fail(f'{what}\n      {needle!r} not in {hay!r}')


def run(script, work, proj=None, env=None, sql_dir=None, expect_ok=True):
    """스크립트 하나를 별도 프로세스로 돌린다 (import 시점 상태가 섞이지 않게)."""
    e = dict(os.environ)
    e.update({'ERD_WORK': str(work), 'ERD_PROJ': str(proj or work),
              'ERD_LANG': 'en', 'ERD_DOCNAME': 'T'})
    e.pop('ERD_DB', None)
    e.pop('ERD_PSQL', None)
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
    r = run('build_erd.py', work, env={'ERD_DOCNAME': 'a/b:c'}, expect_ok=False)
    write_schema(work, {'t': table('t', [col('id')])})
    run('build_erd.py', work, env={'ERD_DOCNAME': 'a/b:c'})
    names = [p.name for p in work.parent.glob('*.graphml')] + \
            [p.name for p in work.glob('*.graphml')]
    if any('/' in n for n in names):
        raise Fail(f'slash survived into a filename: {names}')


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
# 진짜 DB 없이 introspect 의 **판단**을 재현하는 가짜 psql. 받은 -F·-R 을 그대로
# 존중하므로, 행 구분이 개행으로 퇴행하면 개행 든 값이 행을 쪼개는 것까지 재현된다.
_FAKE_PSQL = '''\
import sys
a = sys.argv
sep = a[a.index('-F') + 1]
rs = a[a.index('-R') + 1] if '-R' in a else chr(10)
q = a[a.index('-c') + 1]
NL = chr(10)
rows = []
if 'information_schema.columns' in q:
    rows = [['s1', 'claims', 'id', 'bigint', 'NO', '', 'NO', ''],
            ['s1', 'claims', 'owner_id', 'bigint', 'YES', '', 'NO', ''],
            ['s2', 'owners', 'id', 'bigint', 'NO', '', 'NO', ''],
            ['s1', 'tricky', 'id', 'bigint', 'NO', '', 'NO', ''],
            ['s1', 'tricky', 'note', 'text', 'YES',
             "'line1" + NL + "line2'::text", 'NO', '']]
elif 'PRIMARY KEY' in q:
    rows = [['s1', 'claims', 'id'], ['s2', 'owners', 'id'], ['s1', 'tricky', 'id']]
elif "contype='f'" in q:
    rows = [['s1', 'claims', 'owner_id', 'hidden', 'owners', 'id', 'NO ACTION']]
if rows:
    sys.stdout.write(rs.join(sep.join(r) for r in rows) + NL)
'''


def db_fake(work):
    import shlex
    work.mkdir(parents=True, exist_ok=True)
    fake = work / 'fake_psql.py'
    fake.write_text(_FAKE_PSQL, encoding='utf-8')
    return {'ERD_PSQL': f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}',
            'ERD_SCHEMAS': 's1,s2'}


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


# ── 그림 ─────────────────────────────────────────────────────────────────────
@case('render: two self-references draw as two loops')
def _(work):
    write_schema(work, {'cat': table(
        'cat', [col('id'), col('parent_id'), col('root_id')], pk=['id'],
        fks=[{'column': 'parent_id', 'ref_table': 'cat', 'ref_column': 'id',
              'on_delete': 'SET NULL'},
             {'column': 'root_id', 'ref_table': 'cat', 'ref_column': 'id',
              'on_delete': 'SET NULL'}])})
    out = run('build_erd.py', work).stdout
    for line in [x for x in out.split('\n') if 'verify' in x]:
        nums = re.findall(r'(\d+)(?=\s*(?:·|$))', line)
        if any(n != '0' for n in nums):
            raise Fail(f'self-loops must not overlap: {line.strip()}')
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
    out = run('build_erd.py', work).stdout
    for line in [x for x in out.split('\n') if 'verify' in x and 'area' in x]:
        if not re.search(r'line↔table 0', line):
            raise Fail(f'a line runs through a table: {line.strip()}')


@case('render: many unrelated tables do not become a vertical ribbon')
def _(work):
    write_schema(work, {f't{i:02d}': table(f't{i:02d}', [col('id'), col('v', 'text')])
                        for i in range(60)})
    run('build_erd.py', work)
    from PIL import Image
    w, h = Image.open(work / 'out' / 'erd_full.png').size
    if h / w > 4:
        raise Fail(f'aspect ratio 1:{h / w:.1f} — unreadable once fitted into a document')


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
    html = (work / 'T.html').read_text(encoding='utf-8')
    for name in t:
        has(html, f'>{name}<', f'{name} appears in the HTML')
    graphml = (work / 'T.graphml').read_text(encoding='utf-8')
    for name in t:
        has(graphml, name, f'{name} appears in the GraphML')
    from docx import Document
    text = '\n'.join(p.text for p in Document(str(work / 'T.docx')).paragraphs)
    for name in t:
        has(text, name, f'{name} appears in the docx')


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
    write_schema(work, {'t': table('t', [col('id')])})
    for lang in ('en', 'ko', 'ja', 'es'):
        run('merge_desc.py', work, env={'ERD_LANG': lang})
        run('build_erd.py', work, env={'ERD_LANG': lang})
        run('build_html.py', work, env={'ERD_LANG': lang})
        text = (work / 'T.html').read_text(encoding='utf-8')
        left = re.findall(r'⟨[a-z._]+⟩', text)
        eq(left, [], f'{lang}: unresolved keys in the document')


@case('artifacts: docx pictures fit the page')
def _(work):
    write_schema(work, {f't{i}': table(f't{i}', [col('id'), col('v', 'text')])
                        for i in range(12)})
    run('merge_desc.py', work)
    run('build_erd.py', work)
    run('build_docx.py', work)
    from docx import Document
    for s in Document(str(work / 'T.docx')).inline_shapes:
        if s.width.cm > 26.7 or s.height.cm > 18.0:
            raise Fail(f'picture {s.width.cm:.1f}×{s.height.cm:.1f}cm exceeds the page')


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


@case('errors: an old schema.json without new keys still renders')
def _(work):
    work.mkdir(parents=True, exist_ok=True)
    (work / 'schema.json').write_text(json.dumps(
        {'t': {'name': 't', 'columns': [{'name': 'id', 'type': 'bigint', 'comment': ''}]}}))
    run('build_erd.py', work)


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
