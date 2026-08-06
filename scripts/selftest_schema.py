#!/usr/bin/env python3
"""스키마 영역 회귀 시험 — DDL 파싱·DB 인트로스펙션·병합·ERD 구조.

    python3 selftest_schema.py            여기 있는 것 전부
    python3 selftest_schema.py introspect  이름에 'introspect' 가 든 것만

`selftest_kit.CASES` 에 등록된다 — `selftest.py` 를 돌리면 `load_extras()` 가 이 파일을
끌어오므로 두 파일이 한 벌로 돈다. 이 파일만 따로 돌리면 여기 것만 목록에 올라와
있으니 여기 것만 돈다.

여기 담는 기준은 저쪽과 같다 — **한 번이라도 조용히 깨졌던 것**. 다만 저쪽이
'고칠 때 함께 남긴 것' 이라면 이쪽은 '고쳤는데 남기지 않은 것' 이다. 그래서 항목마다
어느 라운드의 무슨 결함을 지키는지 적는다. 커밋 메시지가 원문이다.

받아 적은 순서는 심각도다: 문서를 **틀리게** 만든 것 → 사용자가 실제로 만들 수 있는
입력에서 **죽은** 것 → 보기 싫은 것.
"""
import json
import os
import re
import shlex
import shutil
import subprocess
import sys

from selftest_kit import (CASES, NOTES, Fail, HERE, case, col, ddl, eq, has, main, run,
                          table, verify_recs, write_schema)


# ── 가짜 psql (2) ────────────────────────────────────────────────────────────
# selftest.py 의 것은 행 내용이 코드에 박혀 있어 한 가지 DB 밖에 못 흉내 낸다.
# 여기서는 FAKE_ROWS(JSON) 로 행을 넣는다 — 조회문 조각 → 행 목록.
#
# 진짜 서버가 하는 것만 한다: psql_rows() 가 씌우는 `_r(c0, c1, …)` 별칭을 그대로
# 읽어 **행마다 JSON 한 줄**로 내놓는다. 값에 무엇이 들어 있어도 한 행은 한 줄이다.
_FAKE_PSQL_JSON = '''\
import json
import os
import re
import sys
a = sys.argv
q = a[a.index('-c') + 1]
NL = chr(10)
ver = int(os.environ.get('FAKE_PG_VER', '160000'))
spec = json.loads(os.environ.get('FAKE_ROWS', '[]'))
rows = []
if 'server_version' in q:
    # 별칭을 쓸 줄 아는가. 기본값은 '9.4 부터' 인데, 그것과 introspect 의 하한(MIN_PG)
    # 이 **같은 숫자**라 두 관문이 하나처럼 묶여 있었다 — 낮은 값을 넣으면 언제나
    # 앞엣것(빈 값)에 먼저 걸려서 `if ver < MIN_PG` 는 한 번도 지나가지 않았고,
    # 하한을 0 으로 내려도 시험이 전부 초록이었다. FAKE_PG_ALIAS 로 둘을 떼어 놓아
    # '숫자로 제대로 답하는데 하한 미만인 서버' 를 만들 수 있게 한다.
    alias = os.environ.get('FAKE_PG_ALIAS', '')
    speaks = (alias not in ('0', 'no', 'off')) if alias else (ver >= 90400)
    if not speaks:
        # 9.3 이하는 서브쿼리 별칭을 row_to_json 의 키로 쓰지 않는다 — 이름으로
        # 꺼내면 아무것도 안 나온다. 그 모양 그대로 흉내 낸다.
        rows = [{}]
    else:
        rows = [['%d.%d' % (ver // 10000, ver % 100), str(ver)]]
else:
    for frag, rs in spec:
        if frag in q:
            rows = rs
            break
m = re.search(r'_r\\(([^()]*)\\)\\s*$', q)
names = [c.strip() for c in m.group(1).split(',')] if m else []
out = []
for r in rows:
    out.append(json.dumps(r if isinstance(r, dict) else dict(zip(names, r))))
if out:
    sys.stdout.write(NL.join(out) + NL)
'''


def db_rows(work, spec, **env):
    """FAKE_ROWS 를 넣은 introspect 실행 환경. spec 은 [(조회문 조각, [행…]), …]."""
    work.mkdir(parents=True, exist_ok=True)
    fake = work / 'fake_psql_json.py'
    fake.write_text(_FAKE_PSQL_JSON, encoding='utf-8')
    e = {'ERD_PSQL': f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}',
         'ERD_SCHEMAS': 's1,s2',
         'FAKE_ROWS': json.dumps(spec)}
    e.update({k: str(v) for k, v in env.items()})
    return e


COLQ, PKQ, FKQ = 'information_schema.columns', 'PRIMARY KEY', "contype='f'"


def schema_of(work):
    return json.loads((work / 'schema.json').read_text(encoding='utf-8'))


# ── 1. 문서를 틀리게 만든 것 ─────────────────────────────────────────────────

@case('parse: destructive ALTER COLUMN changes the final schema instead of being ignored')
def _(work):
    s = ddl(work, '''
CREATE TABLE t (
  id bigint PRIMARY KEY,
  obsolete text,
  amount integer DEFAULT 1,
  code text NOT NULL,
  UNIQUE (code, amount)
);
ALTER TABLE t ALTER COLUMN amount TYPE numeric(12,2);
ALTER TABLE t ALTER COLUMN amount SET DEFAULT 0.00;
ALTER TABLE t ALTER COLUMN code DROP NOT NULL;
ALTER TABLE t DROP COLUMN obsolete;
''')
    t = s['t']
    eq([(c['name'], c['type'], c['not_null'], c['default']) for c in t['columns']],
       [('id', 'bigint', True, ''), ('amount', 'numeric(12,2)', False, '0.00'),
        ('code', 'text', False, '')],
       'DROP/TYPE/DEFAULT/NULL changes must describe the final table')


@case('parse: CREATE ALTER DROP and recreate follow SQL statement order')
def _(work):
    s = ddl(work, '''
CREATE TABLE gone (id bigint PRIMARY KEY);
CREATE TABLE extra (id bigint PRIMARY KEY);
CREATE TABLE parent (id bigint PRIMARY KEY);
CREATE TABLE child (parent_id bigint REFERENCES parent(id));
DROP TABLE gone, extra;
DROP TABLE parent CASCADE;
CREATE TABLE parent (new_id bigint PRIMARY KEY);
ALTER TABLE parent ADD COLUMN note text;
''')
    eq(sorted(s), ['child', 'parent'], 'a dropped table leaves no ghost behind')
    eq([c['name'] for c in s['parent']['columns']], ['new_id', 'note'],
       'a recreated table starts fresh before later ALTER statements')
    eq(s['child']['fks'], [], 'DROP TABLE CASCADE removes inbound relationships')


@case('parse: NULL inside an unparenthesized CASE stays in the default expression')
def _(work):
    s = ddl(work, '''
CREATE TABLE t (
  amount integer DEFAULT CASE WHEN 1 = 1 THEN 10 ELSE NULL END NOT NULL
);
''')
    c = s['t']['columns'][0]
    eq((c['default'], c['not_null']),
       ('CASE WHEN 1 = 1 THEN 10 ELSE NULL END', True),
       'CASE expression keywords must not be mistaken for following column constraints')


@case('parse: column and table renames move every dependent relationship')
def _(work):
    s = ddl(work, '''
CREATE TABLE parent (old_id bigint PRIMARY KEY);
CREATE TABLE child (
  parent_id bigint REFERENCES parent(old_id),
  UNIQUE (parent_id)
);
ALTER TABLE parent RENAME COLUMN old_id TO id;
ALTER TABLE child RENAME COLUMN parent_id TO owner_id;
ALTER TABLE parent RENAME TO accounts;
''')
    eq(sorted(s), ['accounts', 'child'], 'a renamed table keeps no ghost under its old name')
    eq(s['accounts']['pk'], ['id'], 'a column rename updates its primary key')
    eq(s['child']['uniques'], [['owner_id']], 'a column rename updates unique constraints')
    fk = s['child']['fks'][0]
    eq((fk['column'], fk['ref_table'], fk['ref_column']),
       ('owner_id', 'accounts', 'id'),
       'both ends of an FK follow column and table renames')


@case('parse: COMMENT IS NULL removes an earlier description')
def _(work):
    s = ddl(work, '''
-- old table note
CREATE TABLE t (
  -- old column note
  id bigint PRIMARY KEY
);
COMMENT ON TABLE t IS NULL;
COMMENT ON COLUMN t.id IS NULL;
''')
    eq((s['t']['note'], s['t']['columns'][0]['comment']), ('', ''),
       'NULL means remove the comment, not ignore the statement')


@case('parse: PostgreSQL extended and dollar-quoted comments keep their text')
def _(work):
    s = ddl(work, r'''
CREATE TABLE t (id bigint PRIMARY KEY, note text);
COMMENT ON TABLE t IS E'owner\'s\nrecord';
COMMENT ON COLUMN t.note IS $doc$line one's
line two$doc$;
COMMENT ON COLUMN t.id IS E'\x41\101\u0042';
''')
    eq(s['t']['note'], "owner's\nrecord", 'E strings decode escaped quote and newline')
    eq(s['t']['columns'][1]['comment'], "line one's\nline two",
       'dollar quotes preserve quotes and newlines')
    eq(s['t']['columns'][0]['comment'], 'AAB',
       'E strings decode hexadecimal, octal, and Unicode escapes')


@case('parse: DROP CONSTRAINT removes named PK, unique and foreign keys')
def _(work):
    s = ddl(work, '''
CREATE TABLE p (id bigint PRIMARY KEY);
CREATE TABLE q (id bigint PRIMARY KEY);
CREATE TABLE c (id bigint, parent_id bigint);
CREATE TABLE d (code text);
ALTER TABLE c ADD CONSTRAINT c_pk PRIMARY KEY (id);
ALTER TABLE c ADD CONSTRAINT c_uq UNIQUE (parent_id);
ALTER TABLE c ADD CONSTRAINT c_fk FOREIGN KEY (parent_id) REFERENCES p(id);
ALTER TABLE c DROP CONSTRAINT c_pk, DROP CONSTRAINT c_uq, DROP CONSTRAINT c_fk;
ALTER TABLE d ADD CONSTRAINT d_uq1 UNIQUE (code), ADD CONSTRAINT d_uq2 UNIQUE (code);
ALTER TABLE d DROP CONSTRAINT d_uq1;
''')
    eq((s['c']['pk'], s['c']['uniques'], s['c']['fks']), ([], [], []),
       'a dropped named constraint must not survive in the final schema')
    eq(s['d']['uniques'], [['code']],
       'dropping one of two named unique constraints keeps the one still declared')


@case('parse: DROP CONSTRAINT recognizes PostgreSQL default constraint names')
def _(work):
    s = ddl(work, '''
CREATE TABLE p (id bigint PRIMARY KEY);
CREATE TABLE c (
  id bigint PRIMARY KEY,
  code text UNIQUE,
  parent_id bigint REFERENCES p(id)
);
CREATE TABLE e (
  id bigint CONSTRAINT e_named_pk PRIMARY KEY,
  code text CONSTRAINT e_named_uq UNIQUE,
  parent_id bigint CONSTRAINT e_named_fk REFERENCES p(id)
);
CREATE TABLE f (seed text);
CREATE TABLE g (
  keep_code text CONSTRAINT g_keep1 UNIQUE CONSTRAINT g_keep2 UNIQUE,
  gone_code text CONSTRAINT g_gone1 UNIQUE CONSTRAINT g_gone2 UNIQUE
);
CREATE TABLE h (
  parent_id bigint
    CONSTRAINT h_p_fk REFERENCES p(id)
    CONSTRAINT h_q_fk REFERENCES q(id) ON DELETE CASCADE
);
ALTER TABLE c DROP CONSTRAINT c_pkey;
ALTER TABLE c DROP CONSTRAINT c_code_key;
ALTER TABLE c DROP CONSTRAINT c_parent_id_fkey;
ALTER TABLE e DROP CONSTRAINT e_named_pk;
ALTER TABLE e DROP CONSTRAINT e_named_uq;
ALTER TABLE e DROP CONSTRAINT e_named_fk;
ALTER TABLE f ADD COLUMN id bigint CONSTRAINT f_named_pk PRIMARY KEY;
ALTER TABLE f ADD COLUMN code text CONSTRAINT f_named_uq UNIQUE;
ALTER TABLE f ADD COLUMN parent_id bigint CONSTRAINT f_named_fk REFERENCES p(id);
ALTER TABLE f DROP CONSTRAINT f_named_pk;
ALTER TABLE f DROP CONSTRAINT f_named_uq;
ALTER TABLE f DROP CONSTRAINT f_named_fk;
ALTER TABLE g DROP CONSTRAINT g_keep1;
ALTER TABLE g DROP CONSTRAINT g_gone1;
ALTER TABLE g DROP CONSTRAINT g_gone2;
ALTER TABLE h DROP CONSTRAINT h_p_fk;
''')
    eq((s['c']['pk'], s['c']['uniques'], s['c']['fks']), ([], [], []),
       'unnamed constraints use the names PostgreSQL assigns to them')
    eq((s['e']['pk'], s['e']['uniques'], s['e']['fks']), ([], [], []),
       'inline CONSTRAINT names survive until a later DROP names them')
    eq((s['f']['pk'], s['f']['uniques'], s['f']['fks']), ([], [], []),
       'ADD COLUMN preserves inline constraint names by the same rule')
    eq(s['g']['uniques'], [['keep_code']],
       'one column may retain another named UNIQUE after its sibling is dropped')
    eq([(fk['ref_table'], fk['on_delete']) for fk in s['h']['fks']],
       [('q', 'CASCADE')],
       'multiple inline references keep separate names and deletion rules')


@case('parse: a rename may create the same table name in another schema')
def _(work):
    s = ddl(work, '''
CREATE TABLE public.account (id bigint PRIMARY KEY);
CREATE TABLE audit.event (id bigint PRIMARY KEY);
CREATE TABLE audit.log (account_id bigint);
ALTER TABLE audit.event RENAME TO account;
ALTER TABLE audit.log ADD CONSTRAINT log_account_fk
  FOREIGN KEY (account_id) REFERENCES audit.account(id);
''')
    eq(sorted(s), ['audit.account', 'log', 'public.account'],
       'same basenames in different schemas must remain distinct after rename')
    eq(s['log']['fks'][0]['ref_table'], 'audit.account',
       'a later FK uses the duplicate-name index produced by the rename')


@case('parse: a malformed composite FK is not invented by repeating a parent column')
def _(work):
    s = ddl(work, '''
CREATE TABLE p (x bigint PRIMARY KEY);
CREATE TABLE c (a bigint, b bigint,
  CONSTRAINT bad_fk FOREIGN KEY (a, b) REFERENCES p(x));
''')
    eq(s['c']['fks'], [], 'mismatched FK arity must not create fictional pairs')


@case('parse: a parent name in REFERENCES is not this column own key')
def _(work):
    s = ddl(work, '''
CREATE TABLE p ("PRIMARY KEY" bigint, "UNIQUE" text);
CREATE TABLE t (id bigint PRIMARY KEY,
  x int REFERENCES p ("PRIMARY KEY"),
  y int REFERENCES p ("UNIQUE"));
''')
    eq(s['t']['pk'], ['id'], 'a referenced parent name cannot invent a local PK')
    eq(s['t']['uniques'], [], 'a referenced parent name cannot invent a local UNIQUE')


@case('parse: the same unique index written twice is one constraint')
def _(work):
    s = ddl(work, '''
CREATE TABLE t (id bigint PRIMARY KEY, code text UNIQUE, a int, b int);
CREATE UNIQUE INDEX i1 ON t (code);
CREATE UNIQUE INDEX IF NOT EXISTS i1 ON t (code);
CREATE UNIQUE INDEX i2 ON t (a, b);
''')
    eq(s['t']['uniques'], [['code'], ['a', 'b']], 'unique column lists are de-duplicated')


@case('introspect: a primary key join includes its table identity')
def _(work):
    sys.path.insert(0, str(HERE))
    import introspect
    query = ' '.join(introspect.Q_PK.split())
    join = query[query.index('key_column_usage'):query.index('where')]
    for pair in ('kcu.constraint_schema=tc.constraint_schema',
                 'kcu.constraint_name=tc.constraint_name',
                 'kcu.table_schema=tc.table_schema',
                 'kcu.table_name=tc.table_name'):
        has(join, pair, f'PK join contains {pair}')


@case('parse: an unsupported ALTER clause is reported instead of silently ignored')
def _(work):
    (work / 'sql').mkdir(parents=True, exist_ok=True)
    (work / 'sql' / 'schema.sql').write_text(
        'CREATE TABLE t (id bigint); ALTER TABLE t SET SCHEMA audit;', encoding='utf-8')
    r = run('parse_ddl.py', work)
    has(r.stdout + r.stderr, 'SET SCHEMA audit', 'the unsupported state change is named')
    has(r.stdout + r.stderr, 't', 'the affected table is named')


@case('spec: every derives row has exactly two endpoints and one label')
def _(work):
    write_schema(work, {'a': table('a', [col('id')], pk=['id']),
                        'b': table('b', [col('id')], pk=['id'])})
    (work / 'erd.spec.json').write_text(json.dumps({'derives': [['a', 'b']]}),
                                             encoding='utf-8')
    r = run('build_erd.py', work, expect_ok=False)
    if 'Traceback' in r.stderr or 'ValueError' in r.stderr:
        raise Fail('a short derives row reached tuple unpacking instead of spec validation')
    has(r.stdout + r.stderr, 'derives', 'the error names the malformed spec key')


@case('introspect: an unresponsive database query stops at ERD_QUERY_TIMEOUT')
def _(work):
    fake = work / 'slow_psql.py'
    work.mkdir(parents=True, exist_ok=True)
    fake.write_text('import time\ntime.sleep(2)\n', encoding='utf-8')
    env = {'ERD_PSQL': f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}',
           'ERD_QUERY_TIMEOUT': '0.05'}
    r = run('introspect.py', work, env=env, expect_ok=False)
    text = r.stdout + r.stderr
    has(text, '0.05', 'the failure states the limit that stopped the query')
    if 'Traceback' in text:
        raise Fail('a database timeout escaped as a raw traceback')


@case('artifacts: a failed atomic write leaves the last good file intact')
def _(work):
    sys.path.insert(0, str(HERE))
    import config
    real_os_name = config.os.name
    try:
        config.os.name = 'nt'
        config._fsync_directory(work)
    finally:
        config.os.name = real_os_name

    from config import atomic_output
    target = work / 'schema.json'
    work.mkdir(parents=True, exist_ok=True)
    target.write_text('last-good', encoding='utf-8')
    try:
        with atomic_output(target) as tmp:
            tmp.write_text('partial-new', encoding='utf-8')
            raise RuntimeError('simulated build failure')
    except RuntimeError:
        pass
    eq(target.read_text(encoding='utf-8'), 'last-good',
       'the canonical output changes only after its producer succeeds')
    eq([p.name for p in work.iterdir()], ['schema.json'],
       'a failed write also cleans its same-directory temporary file')


@case('introspect: the same table name in two schemas stays two tables')
def _(work):
    # 3라운드. 테이블 키가 이름뿐이라 public.events 와 analytics.events 가 한
    # 테이블로 합쳐졌다 — 컬럼이 뒤섞이고 PK 가 ['id','id'] 가 되고 한쪽은 그림에서
    # 사라졌다. 경고도 없었다. parse_ddl 쪽에는 시험이 있었지만 정작 그 버그가 난
    # introspect 쪽에는 없었다.
    env = db_rows(work, [
        (COLQ, [['s1', 'events', 'id', 'bigint', 'NO', '', 'NO', ''],
                ['s1', 'events', 'kind', 'text', 'YES', '', 'NO', ''],
                ['s2', 'events', 'id', 'bigint', 'NO', '', 'NO', ''],
                ['s2', 'events', 'loaded_at', 'timestamptz', 'YES', '', 'NO', ''],
                ['s1', 'solo', 'id', 'bigint', 'NO', '', 'NO', '']]),
        (PKQ, [['s1', 'events', 'id'], ['s2', 'events', 'id'], ['s1', 'solo', 'id']]),
    ])
    r = run('introspect.py', work, env=env)
    s = schema_of(work)
    eq(sorted(s), ['s1.events', 's2.events', 'solo'],
       'a name that spans two schemas is keyed by schema; a unique name is not')
    eq([c['name'] for c in s['s1.events']['columns']], ['id', 'kind'],
       'the columns of the two tables must not be poured into one')
    eq([c['name'] for c in s['s2.events']['columns']], ['id', 'loaded_at'], 'and the other way')
    eq((s['s1.events']['pk'], s['s2.events']['pk']), (['id'], ['id']),
       "the primary key must not become ['id','id']")
    has(r.stdout, 'events', 'the summary names the table whose name collides')


@case('introspect: a comma inside a quoted unique column name stays one column')
def _(work):
    sys.path.insert(0, str(HERE))
    import introspect
    has(introspect.q_unique(160000), 'i.indisvalid',
        'an invalid leftover index is not presented as an enforced unique rule')
    env = db_rows(work, [
        (COLQ, [['s1', 'contacts', 'last,first', 'text', 'NO', '', 'NO', '']]),
        ('i.indisunique', [['s1', 'contacts', 'contacts_name_key', 'last,first'],
                           ['s1', 'contacts', 'contacts_name_uq2', 'last,first']]),
    ])
    run('introspect.py', work, env=env)
    eq(schema_of(work)['contacts']['uniques'], [['last,first']],
       'catalog attnums, not commas in rendered SQL, define unique columns; duplicate '
       'indexes on the same set still describe one structural uniqueness rule')


@case('introspect: a composite FK is not multiplied into pairs that do not exist')
def _(work):
    # 3라운드. 자식 컬럼과 부모 컬럼을 constraint_name 만으로 이어서 2컬럼짜리 FK
    # 하나가 4개가 됐고, 그중 둘은 있지도 않은 조합이었다 — 그림에 없는 관계선이
    # 그려지고 docx 의 FK 표에도 실렸다. 지금은 conkey·confkey 를 자리끼리 푼다.
    # 그 자리 맞춤이 살아 있는지, 서버가 자리대로 돌려준 것을 그대로 싣는지 본다.
    env = db_rows(work, [
        (COLQ, [['s1', 'lines', 'order_id', 'bigint', 'NO', '', 'NO', ''],
                ['s1', 'lines', 'line_no', 'int', 'NO', '', 'NO', ''],
                ['s1', 'notes', 'id', 'bigint', 'NO', '', 'NO', ''],
                ['s1', 'notes', 'o', 'bigint', 'YES', '', 'NO', ''],
                ['s1', 'notes', 'l', 'int', 'YES', '', 'NO', '']]),
        (FKQ, [['s1', 'notes', 'o', 's1', 'lines', 'order_id', 'CASCADE'],
               ['s1', 'notes', 'l', 's1', 'lines', 'line_no', 'CASCADE']]),
    ])
    run('introspect.py', work, env=env)
    s = schema_of(work)
    eq([(f['column'], f['ref_column']) for f in s['notes']['fks']],
       [('o', 'order_id'), ('l', 'line_no')],
       'two column pairs, not the four the cross join used to invent')


@case('introspect: enum and array columns keep their real type name')
def _(work):
    # 3라운드. enum 은 'USER-DEFINED', 배열은 'ARRAY' 로 뭉개져 있었다. 타입을 보려고
    # 보는 문서에서 그 두 글자는 아무것도 알려 주지 않는다. format_type 으로 바꿨는데
    # 재는 것이 없었다 — 조회가 다시 information_schema.data_type 으로 돌아가면
    # 그 자리는 조용히 도로 뭉개진다.
    #
    # ⚠ 이 항목이 실제로 재는 것은 **조회문 문자열** 이다. 가짜 psql 은 우리가 준 행을
    # 그대로 돌려주므로, 조회를 information_schema 로 되돌려도 같은 답이 온다 —
    # 아래 eq() 는 introspect 가 문자열을 흘려보내는지만 본다. 원리상 그렇다.
    # 이 결함을 **행동으로** 재는 것은 진짜 서버가 있어야 하는
    # `db: enum, array and identity come back as themselves` 쪽이다.
    # 그래서 문자열 검사는 두 갈래를 다 못박는다: format_type 을 쓰는 것과,
    # 뭉개지는 두 이름을 **둘 다** 갈아 끼우는 것. 한쪽만 지우는 반쪽 회귀가
    # 실제로 있었는데 예전 검사는 그것을 통과시켰다.
    sys.path.insert(0, str(HERE))
    import introspect
    has(introspect.Q_COLUMNS, 'format_type',
        "the real type name comes from format_type() — information_schema's data_type "
        "says only 'USER-DEFINED' and 'ARRAY'")
    for smudged in ('USER-DEFINED', 'ARRAY'):
        has(introspect.Q_COLUMNS, smudged,
            f"the query must still replace {smudged!r} — dropping just one of the two "
            'is a half regression that leaves enums or arrays smudged')
    env = db_rows(work, [
        (COLQ, [['s1', 't', 'id', 'bigint', 'NO', '', 'NO', ''],
                ['s1', 't', 'state', 'order_state', 'YES', '', 'NO', ''],
                ['s1', 't', 'tags', 'text[]', 'YES', '', 'NO', '']]),
    ])
    run('introspect.py', work, env=env)
    eq({c['name']: c['type'] for c in schema_of(work)['t']['columns']},
       {'id': 'bigint', 'state': 'order_state', 'tags': 'text[]'},
       'whatever the server names the type is what the document says')


@case('introspect: GENERATED AS IDENTITY is an identity column')
def _(work):
    # 3라운드. IDENTITY 는 기본값이 비어 있어 'nextval' 만 보던 판정이 놓쳤다.
    # serial 은 잡히고 identity 는 안 잡혀, 같은 뜻인 두 컬럼이 문서에서 달라 보였다.
    env = db_rows(work, [
        (COLQ, [['s1', 't', 'a', 'bigint', 'NO', '', 'YES', ''],
                ['s1', 't', 'b', 'bigint', 'NO', "nextval('t_b_seq'::regclass)", 'NO', ''],
                ['s1', 't', 'c', 'bigint', 'YES', '', 'NO', '']]),
    ])
    run('introspect.py', work, env=env)
    eq({c['name']: c['identity'] for c in schema_of(work)['t']['columns']},
       {'a': True, 'b': True, 'c': False},
       'GENERATED … AS IDENTITY counts, and so does a serial default')


@case('parse: a schema-qualified ALTER does not land on another schema')
def _(work):
    # 7라운드. ALTER 와 COMMENT 가 스키마를 버리고 이름 끝만 맞으면 아무 테이블이나
    # 잡았다. pg_dump 는 mart 를 먼저 내놓으므로 `ALTER TABLE ONLY public.orders …`
    # 가 mart.orders 에 붙었다 — mart 에 있지도 않은 컬럼의 FK 가 생기고 public 쪽은
    # PK 도 FK 도 잃었다. 8라운드에서 '스키마를 적어 준 ALTER 가 그 테이블이 없을
    # 때 남의 테이블에 붙는' 나머지 반쪽을 마저 고쳤다.
    #
    # **순서가 요점이다** — 엉뚱한 테이블이 dict 에 먼저 들어 있어야 잘못이 드러난다.
    s = ddl(work, """
CREATE TABLE mart.orders (id bigint, loaded_at timestamptz);
CREATE TABLE public.orders (id bigint, buyer_id bigint);
CREATE TABLE public.buyers (id bigint);
ALTER TABLE ONLY public.orders ADD CONSTRAINT orders_pkey PRIMARY KEY (id);
ALTER TABLE ONLY public.orders ADD CONSTRAINT orders_buyer_fk FOREIGN KEY (buyer_id)
    REFERENCES public.buyers(id) ON DELETE CASCADE;
COMMENT ON TABLE public.orders IS 'the real one';
COMMENT ON COLUMN public.orders.buyer_id IS 'who bought it';
ALTER TABLE audit.orders ADD COLUMN who text;
""")
    eq(s['public.orders']['pk'], ['id'], 'the PK lands on the schema the ALTER names')
    eq(s['mart.orders']['pk'], [], 'and not on the table that merely shares its name')
    eq([f['column'] for f in s['public.orders']['fks']], ['buyer_id'], 'so does the FK')
    eq(s['mart.orders']['fks'], [], 'mart.orders never had that column')
    eq(s['public.orders']['note'], 'the real one', 'COMMENT ON TABLE too')
    eq(s['mart.orders']['note'], '', 'and it does not leak sideways')
    eq([c['comment'] for c in s['public.orders']['columns'] if c['name'] == 'buyer_id'],
       ['who bought it'], 'COMMENT ON COLUMN too')
    eq([c['name'] for c in s['public.orders']['columns']], ['id', 'buyer_id'],
       "an ALTER naming a schema that has no such table must not add its column here")
    eq([c['name'] for c in s['mart.orders']['columns']], ['id', 'loaded_at'],
       'nor there — audit.orders is not either of these')


@case('parse: CREATE UNIQUE INDEX attaches by schema, whichever table came first')
def _(work):
    # 8라운드. `CREATE UNIQUE INDEX` 가 스키마를 무시해 mart.orders 가 public.orders
    # 의 UQ 를 가져갔다 — 그 테이블에 없는 컬럼에 대한 유니크였다.
    #
    # 이 항목이 따로 있는 이유: 이미 있는 시험은 인덱스를 **먼저 정의된** 테이블에
    # 걸어서, 스키마를 통째로 무시해도 우연히 정답이 나온다. 스키마를 지운 채로도
    # 통과하는 것을 확인했다. 여기서는 **나중** 테이블에 건다.
    s = ddl(work, """
CREATE TABLE shop.orders (id bigint PRIMARY KEY, amount numeric(10,2));
CREATE TABLE mart.orders (id bigint PRIMARY KEY, loaded_at timestamptz);
CREATE UNIQUE INDEX uq_mart ON mart.orders (loaded_at);
""")
    eq(s['mart.orders']['uniques'], [['loaded_at']], 'the index belongs to the schema it names')
    eq(s['shop.orders']['uniques'], [],
       'and not to the same-named table that happened to be defined first')


@case('parse: a serial column is identity and NOT NULL')
def _(work):
    # 6라운드. IDENTITY·serial 이 NOT NULL 로 잡히지 않아 DB 를 직접 읽은 결과와
    # 어긋났다. 있는 시험은 `REFERENCES serial_numbers` 가 identity 가 **되지 않는**
    # 쪽만 지킨다 — 낱말 경계를 아예 없애 버려도 그 항목은 통과한다(확인했다).
    # 되는 쪽이 없으면 판정을 통째로 꺼도 아무도 모른다.
    # 이 판정은 방어가 **둘**이다 — `_decl()` 이 REFERENCES 절을 걷어내는 것과,
    # 정규식의 낱말 경계. `REFERENCES serial_numbers(id)` 하나로는 둘 중 어느 쪽을
    # 빼도 드러나지 않는다(다른 쪽이 받아 준다). 그래서 각각을 홀로 지키는 입력을
    # 함께 넣는다 —
    #   · `sn app.serial_number`  REFERENCES 가 없으니 낱말 경계가 유일한 방어다
    #   · `pa … REFERENCES identity(id)` 부모 이름이 낱말째로 IDENTITY 라
    #     경계는 도움이 안 된다. _decl() 이 유일한 방어다 (부모를 `serial` 이라
    #     부르는 것도 마찬가지다)
    s = ddl(work, """
CREATE TABLE t (
  a serial PRIMARY KEY,
  b bigserial,
  c smallserial,
  d bigint GENERATED ALWAYS AS IDENTITY,
  e bigint,
  sn app.serial_number,
  ref bigint REFERENCES serial_numbers(id),
  pa bigint REFERENCES identity(id),
  pb bigint REFERENCES serial(id)
);
CREATE TABLE later (id bigint, v text);
ALTER TABLE later ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY;
""")
    got = {c['name']: (c['identity'], c['not_null']) for c in s['t']['columns']}
    eq(got, {'a': (True, True), 'b': (True, True), 'c': (True, True),
             'd': (True, True), 'e': (False, False),
             'sn': (False, False), 'ref': (False, False),
             'pa': (False, False), 'pb': (False, False)},
       'serial and IDENTITY are identity and NOT NULL — and nothing that merely '
       'contains the letters is: not the type app.serial_number, not a parent '
       'table called identity or serial')
    eq([(c['identity'], c['not_null']) for c in s['later']['columns']
        if c['name'] == 'id'], [(True, True)],
       'and an IDENTITY attached by ALTER (the shape pg_dump writes)')


@case('parse: a table-level constraint does not become a column')
def _(work):
    # 6라운드. 테이블 단위 CHECK·UNIQUE·LIKE 가 'CHECK' 라는 이름의 가짜 컬럼으로
    # 문서에 실렸다. 반대편(키워드로 시작하는 진짜 컬럼명)에는 시험이 있는데
    # 이쪽에는 없었다 — 필터를 넓히면 컬럼이 죽고, 좁히면 유령 컬럼이 산다.
    s = ddl(work, """
CREATE TABLE base (id bigint PRIMARY KEY, amount numeric);
CREATE TABLE t (
  LIKE base INCLUDING DEFAULTS,
  id bigint PRIMARY KEY,
  amount numeric,
  tenant text,
  CONSTRAINT amount_positive CHECK (amount > 0),
  CHECK (tenant <> ''),
  UNIQUE (tenant, id),
  EXCLUDE USING gist (tenant WITH =)
);
""")
    eq([c['name'] for c in s['t']['columns']], ['id', 'amount', 'tenant'],
       'CHECK / UNIQUE / LIKE / EXCLUDE are constraints, not columns')
    eq(s['t']['uniques'], [['tenant', 'id']], 'the UNIQUE itself is still read')


@case('parse: array types keep their brackets')
def _(work):
    # 6라운드에서 함께 고친 것들 — 따옴표 친 이름, 배열 타입. 재는 것이 없었다.
    s = ddl(work, """
CREATE TABLE "order_item" (
  "id" bigint PRIMARY KEY,
  "unit_price" numeric(12,2),
  tags text[],
  grid int[][],
  fixed numeric(5,2)[3]
);
""")
    t = s['order_item']
    eq([c['name'] for c in t['columns']],
       ['id', 'unit_price', 'tags', 'grid', 'fixed'], 'a quoted name loses its quotes only')
    eq({c['name']: c['type'] for c in t['columns'] if '[' in c['type']},
       {'tags': 'text[]', 'grid': 'int[][]', 'fixed': 'numeric(5,2)[3]'},
       'an array type keeps its brackets — introspect writes them the same way')
    eq(t['pk'], ['id'], 'and the quoted PK is still the PK')


@case('parse: a quoted name containing a space is one name')
def _(work):
    # ⚠ 지금 **빨간** 항목이다. 고치지 않고 자리를 잡아 둔다.
    #
    # `"Unit Price" numeric(12,2)` 가 이름 `Unit`·타입 `price` 로 읽힌다. 있지도 않은
    # 컬럼이 문서에 실리고 진짜 컬럼은 사라진다 — 6라운드가 '따옴표 친 컬럼명' 을
    # 고쳤다고 적은 자리인데, 공백이 든 식별자는 그때도 지금도 안 된다. 공백이 든
    # 식별자는 합법이고 pg_dump 가 그대로 내놓는다(그러라고 따옴표를 친다).
    s = ddl(work, """
CREATE TABLE t (
  id bigint PRIMARY KEY,
  "Unit Price" numeric(12,2),
  "order date" date
);
""")
    eq([c['name'] for c in s['t']['columns']], ['id', 'Unit Price', 'order date'],
       'a quoted identifier is one name, spaces and all')
    eq({c['name']: c['type'] for c in s['t']['columns']},
       {'id': 'bigint', 'Unit Price': 'numeric(12,2)', 'order date': 'date'},
       'and the word after the space is the type, not part of the name')


@case('parse: a functional unique index is not filed as a column list')
def _(work):
    # 7라운드. 함수 인덱스가 `['lower(email']` 처럼 잘려 문서에 실렸다. 있지도 않은
    # 컬럼 이름이 유니크 제약으로 적히는 것이라 읽는 사람이 그대로 믿는다.
    s = ddl(work, """
CREATE TABLE t (id bigint PRIMARY KEY, email text, tenant text);
CREATE UNIQUE INDEX uq_lower ON t (lower(email));
CREATE UNIQUE INDEX uq_plain ON t (tenant, email);
""")
    eq(s['t']['uniques'], [['tenant', 'email']],
       'a plain index is a column list; a functional one is not a column list at all')
    for u in s['t']['uniques']:
        for c in u:
            if '(' in c or ')' in c:
                raise Fail(f'a truncated expression reached the document as a column: {c!r}')


@case('parse: the pg_dump structure header is not a table description')
def _(work):
    # 6라운드. COMMENT ON 을 안 읽으니 pg_dump 가 붙이는 구조 헤더
    # ("Name: orders; Type: TABLE; Schema: public; Owner: app") 가 테이블 설명이 됐다.
    # 사람이 CREATE TABLE 위에 적은 한 줄은 설명으로 쓰는 것이 맞으므로, 둘을
    # 가르는 판정이 살아 있어야 한다.
    s = ddl(work, """
--
-- Name: orders; Type: TABLE; Schema: public; Owner: app
--
CREATE TABLE public.orders (id bigint);

-- 회원이 남긴 주문
CREATE TABLE public.wishes (id bigint);
""")
    eq(s['orders']['note'], '', "pg_dump's structure header is not a description")
    eq(s['wishes']['note'], '회원이 남긴 주문', 'a line a person wrote above the table is')


@case('erd: an excluded table takes the relationships pointing at it with it')
def _(work):
    # 4라운드. ERD_EXCLUDE 를 그리는 단계에서 주면 KeyError 였다 — spec 만 거르고
    # 정작 그리는 쪽은 안 걸렀다. 이제 한자리에서 걷어내고 그 테이블을 가리키던
    # FK 도 같이 뗀다. 안 떼면 없는 테이블로 가는 관계가 남는다.
    write_schema(work, {
        'keep': table('keep', [col('id'), col('gone_id')], pk=['id'],
                      fks=[{'column': 'gone_id', 'ref_table': 'legacy_gone',
                            'ref_column': 'id', 'on_delete': 'CASCADE'}]),
        'legacy_gone': table('legacy_gone', [col('id')], pk=['id'])})
    r = run('build_erd.py', work, env={'ERD_EXCLUDE': '^legacy_'})
    if 'Traceback' in r.stderr:
        raise Fail(f'ERD_EXCLUDE at draw time must not raise:\n{r.stderr[-400:]}')
    run('build_html.py', work, env={'ERD_EXCLUDE': '^legacy_'})
    html = (work / 'T.html').read_text(encoding='utf-8')
    if 'legacy_gone' in html:
        raise Fail('an excluded table still reached the document')
    graphml = (work / 'T.graphml').read_text(encoding='utf-8')
    if 'legacy_gone' in graphml:
        raise Fail('an excluded table still reached the GraphML — '
                   'the edge pointing at it must go too')


@case('spec: a table listed in two areas is drawn once')
def _(work):
    # 4라운드. 한 테이블을 두 영역에 적으면 문서에 두 번 나온다. 무엇이 이상한지
    # 말해 주고 그릴 수 있는 만큼 그리기로 했는데, 말해 주는지 재는 것이 없었다.
    write_schema(work, {'a': table('a', [col('id')]), 'b': table('b', [col('id')]),
                        'c': table('c', [col('id')])})
    (work / 'erd.spec.json').write_text(json.dumps(
        {'areas': [['A', 'one', 'public', ['a', 'b']],
                   ['B', 'two', 'public', ['b', 'c']]]}), encoding='utf-8')
    out = run('build_erd.py', work).stdout
    has(out, 'b', 'the table that appears twice is named')
    run('build_html.py', work)
    html = (work / 'T.html').read_text(encoding='utf-8')
    eq(html.count('<h4'), 3, 'each table gets exactly one column table, not two')


@case('render: a crowded area is not a vertical ribbon either')
def _(work):
    # 4·5라운드. 열 수를 고정해 두어 테이블이 많은 영역이 세로로 한없이 길어졌다
    # (60개면 30행). 있는 시험은 **전체도**(layout_global)만 잰다 — layout_area 의
    # 열 수를 2로 되돌려도 통과하는 것을 확인했다. 영역 상세도가 문서에서 실제로
    # 읽히는 그림인데 그쪽은 재는 것이 없었다.
    write_schema(work, {f'shop_t{i:02d}': table(f'shop_t{i:02d}', [col('id'), col('v', 'text')])
                        for i in range(40)})
    run('build_erd.py', work)
    from PIL import Image
    for p in sorted((work / 'out').glob('erd_area_*.png')):
        w, h = Image.open(p).size
        if h / w > 4:
            raise Fail(f'{p.name}: aspect ratio 1:{h / w:.1f} — '
                       'shrunk to fit a page this is a strip nobody can read')


@case('erd: more than 26 areas keep filename-safe codes')
def _(work):
    # 5라운드. 영역이 26개를 넘으면 코드가 '[' 로 넘어가 erd_area_[.png 같은 파일이
    # 나왔다. macOS 는 넘어가지만 Windows 에서는 만들 수 없는 이름이고, 문서가
    # 가리키는 그림과 실제 파일 이름이 어긋난다.
    sys.path.insert(0, str(HERE))
    import config
    eq([config._code(i) for i in (0, 25, 26, 27, 51, 52)],
       ['A', 'Z', 'AA', 'AB', 'AZ', 'BA'], 'A…Z then AA — never [ or \\')
    for i in range(120):
        c = config._code(i)
        if not re.fullmatch(r'[A-Z]+', c):
            raise Fail(f'area {i} got code {c!r} — not usable in a file name')


@case('erd: ERD_MAX_AREAS is a cap the document actually respects')
def _(work):
    # ⚠ 지금 **빨간** 항목이다. 고치지 않고 자리를 잡아 둔다.
    #
    # 5라운드가 '스키마마다 따로 세던 상한' 을 고쳤다. 절반만 고쳐졌다 — 상한 4 에
    # 스키마 하나면 5개, 둘이면 7개, 셋이면 9개가 나온다. 스키마마다 `room` 이 최소
    # 1 을 보장하고, 거기에 '기타' 영역이 상한과 무관하게 하나씩 더 붙는다.
    # SKILL.md 는 이 값을 "cap on the number of auto-classified areas" 라고 적는다.
    # 영역 수가 곧 문서의 목차라, 4를 적은 사람에게 9장이 나온다.
    def areas_for(n_schemas):
        w = work.parent / f'w{n_schemas}'
        t = {}
        for si in range(n_schemas):
            sch = f's{si}'
            for grp in ('order', 'user', 'item', 'log', 'meta'):
                for i in range(3):
                    t[f'{sch}.{grp}_{grp}_{i}'] = table(f'{grp}_{grp}_{i}', [col('id')],
                                                        schema=sch)
        write_schema(w, t)
        run('build_erd.py', w, env={'ERD_MAX_AREAS': '4'})
        return len(list((w / 'out').glob('erd_area_*.png')))

    got = {n: areas_for(n) for n in (1, 2, 3)}
    over = {n: v for n, v in got.items() if v > 4}
    if over:
        raise Fail(f'ERD_MAX_AREAS=4 produced {got} areas — the cap does not hold, '
                   'and each extra schema adds two more')


@case('render: nothing is drawn past the right edge of the canvas')
def _(work):
    # ⚠ 지금 **빨간** 항목이다. 고치지 않고 자리를 잡아 둔다.
    #
    # 5라운드가 '캔버스 측정이 본체만 재고 제목·부제·범례는 재지 않아 긴 이름이
    # 잘린다' 를 고쳤다. 절반만 고쳐졌다 — 범례에서 잰 것은 **레이어 라벨** 뿐이고,
    # 그 아래 고정 줄(배지 뜻풀이: `extended  existing table · colum…`)은 재지 않는다.
    # 테이블이 적어 그림이 좁으면 그 줄이 오른쪽에서 잘려 나간다. 특별한 입력이
    # 아니라 **테이블 두 개짜리 평범한 스키마**에서 en·ko 둘 다 잘린다.
    #
    # 픽셀 대신 기하로 재고 싶지만 범례는 draw_legend 안에서 그려지므로, 캔버스
    # 오른쪽 한 줄에 배경색 아닌 점이 있는지로 잰다 — 잘렸다는 것은 곧 글자가
    # 마지막 열까지 닿아 있다는 뜻이다.
    long_name = ('extremely_long_area_name_that_a_prefix_could_actually_produce'
                 '_and_then_some_more_because_nobody_shortens_these')
    write_schema(work, {'a': table('a', [col('id')]), 'b': table('b', [col('id')])})
    probe = work / 'probe_canvas.py'
    probe.write_text(
        "import erd\n"
        "from PIL import Image\n"
        "import glob, os\n"
        "for p in glob.glob(os.path.join(str(erd.OUT), '*.png')):\n"
        "    im = Image.open(p).convert('RGB')\n"
        "    w, h = im.size\n"
        "    edge = [im.getpixel((w - 1, y)) for y in range(0, h, max(1, h // 200))]\n"
        "    bg = im.getpixel((w - 1, 0))\n"
        "    off = [c for c in edge if c != bg]\n"
        "    assert not off, f'{os.path.basename(p)}: ink touches the right edge — '\\\n"
        "                    f'the canvas was measured without the title or legend'\n",
        encoding='utf-8')

    bad = []
    for what, spec, lang in (
            ('two tables, no spec at all', None, 'en'),
            ('the same in Korean', None, 'ko'),
            ('a long area name (it becomes the legend label)',
             {'areas': [['AA', long_name, 'public', ['a', 'b']]],
              'doc': {'title': 'T'}}, 'en'),
            ('a long document title',
             {'areas': [['AA', 'x', 'public', ['a', 'b']]],
              'doc': {'title': long_name, 'subtitle': long_name}}, 'en')):
        for p in (work / 'out').glob('*.png'):
            p.unlink()
        sp = work / 'erd.spec.json'
        sp.write_text(json.dumps(spec), encoding='utf-8') if spec else sp.unlink(missing_ok=True)
        run('build_erd.py', work, env={'ERD_LANG': lang})
        r = run(str(probe), work, env={'PYTHONPATH': str(HERE)}, expect_ok=False)
        if r.returncode:
            bad.append(f'{what}: {r.stderr.strip().splitlines()[-1]}')
    if bad:
        raise Fail('drawing runs off the canvas:\n      ' + '\n      '.join(bad))


# ETL 흐름이 **그림에** 실제로 그어졌는지 세는 자. `ImageDraw` 를 감싸 칠한 것을
# 받아 적는다 — erd.py 안에 자를 넣지 않는다(재는 코드가 재는 대상 안에 있으면 같이
# 죽는다). 색은 erd.py 가 ETL 선에만 쓰는 값이라 소스에서 그대로 읽어 온다.
_ETL_PROBE = '''\
import json
import re
import sys
from pathlib import Path

from PIL import ImageDraw as RID

import erd

SRC = Path(erd.__file__).read_text(encoding='utf-8')
m = re.search(r"pending\\.append\\(\\(src, dst, '(#[0-9A-Fa-f]{6})'", SRC)
if not m:
    print('the ETL colour is no longer written where this probe reads it', file=sys.stderr)
    raise SystemExit(2)
ETL = m.group(1)
N = {'dashed': 0, 'labels': []}


class Rec:
    def __init__(self, img):
        self._d = RID.Draw(img)
        self._on = img.size != (1, 1)     # 1x1 은 자리를 재는 판이지 칠하는 판이 아니다

    def __getattr__(self, name):
        fn = getattr(self._d, name)
        if not self._on:
            return fn
        if name == 'line':
            def ln(xy, **kw):
                if kw.get('fill') == ETL:
                    N['dashed'] += 1
                return fn(xy, **kw)
            return ln
        if name == 'text':
            def txt(xy, text, **kw):
                if 'stroke_width' in kw and text == 'nightly load':
                    N['labels'].append(text)
                return fn(xy, text, **kw)
            return txt
        return fn


erd.ImageDraw = type('m', (), {'Draw': Rec})
_code, _name, _schema, tables = erd.AREAS[0]
apos, aboxes, ext = erd.layout_area(tables, with_desc=True)
erd.draw_erd(erd.OUT / 'etl_probe.png', tables + ext, apos, aboxes, 'probe',
             with_desc=True, scale=2, stubs=set(ext), legend=True, derives=True)
print(json.dumps(N))
'''


@case('artifacts: graphml carries the ETL flows the diagram draws')
def _(work):
    # 7라운드. GraphML 에 derives 가 빠져 있었다. 문서는 yEd 로 열어 재배치하고
    # 다시 뽑는 사용법을 권하는데, 그러면 그림에 있던 흐름이 소리 없이 사라진다.
    # 같은 커밋에서 '없는 테이블을 가리키는 derives 가 그림엔 없으면서 docx 표엔
    # 실리던 것' 도 고쳤다 — 둘은 같은 자리의 앞뒤라 함께 지킨다.
    write_schema(work, {'src': table('src', [col('id')]), 'dst': table('dst', [col('id')])})
    (work / 'erd.spec.json').write_text(json.dumps(
        {'areas': [['A', 'one', 'public', ['src', 'dst']]],
         'derives': [['src', 'dst', 'nightly load'], ['src', 'nowhere', 'ghost flow']]}), encoding='utf-8')
    run('merge_desc.py', work)
    run('build_erd.py', work)
    run('build_docx.py', work)
    graphml = (work / 'T.graphml').read_text(encoding='utf-8')
    has(graphml, 'nightly load', 'the ETL flow is in the GraphML, not only in the PNG')
    if 'ghost flow' in graphml:
        raise Fail('a flow whose endpoint does not exist must not be in the GraphML')
    from docx import Document
    text = '\n'.join(c.text for tb in Document(str(work / 'T.docx')).tables
                     for r in tb.rows for c in r.cells)
    has(text, 'nightly load', 'and the docx table lists the same flow')
    if 'ghost flow' in text:
        raise Fail('a flow missing from every diagram must not be listed in the docx — '
                   'a reader with only the document would take it for a real one')

    # 14라운드. 이 케이스의 이름은 "the diagram draws" 인데 정작 그림 쪽은 한 번도
    # 안 봤다 — `erd.py` 의 ETL 블록을 `if False:` 로 막아 그림에서 흐름을 통째로
    # 지워도 101개가 전부 통과했다. GraphML 만 지우면 잡히고 그림만 지우면 안 잡히니,
    # 이름이 주장하는 것의 절반이 검사 밖에 있었다 — 11라운드가 이름 붙인 **'안 한
    # 검사를 통과로 적었다'** 의 축소판이다. 그래서 칠한 것을 센다: ETL 색으로 그은
    # 점선 세그먼트가 몇 개이고, 그 라벨이 실제로 찍혔는가.
    probe = work.parent / 'etl_probe.py'
    probe.write_text(_ETL_PROBE, encoding='utf-8')
    r = run(str(probe), work, env={'PYTHONPATH': str(HERE)})
    got = json.loads(r.stdout.strip().splitlines()[-1])
    if got['dashed'] < 2:
        raise Fail(f'the diagram painted {got["dashed"]} ETL segment(s) — the flow this '
                   f'case is named after is only in the GraphML, not on the picture')
    eq(got['labels'], ['nightly load'],
       'and the flow the diagram draws is labelled, once, with the real flow')


@case('artifacts: html names the schema when two tables share a name')
def _(work):
    # 7라운드. HTML 의 테이블 제목이 이름뿐이라 mart.orders 와 public.orders 가
    # 구분되지 않았다. 그래서 이전 판에서 설명을 물려받을 때 지워진 테이블의 설명이
    # 다른 테이블에 되살아났다 (docx 는 이미 키를 쓰고 있었다).
    write_schema(work, {
        'shop.orders': table('orders', [col('id'), col('channel', 'text')], schema='shop'),
        'mart.orders': table('orders', [col('id'), col('loaded_at', 'timestamptz')],
                             schema='mart')})
    run('merge_desc.py', work)
    run('build_erd.py', work)
    run('build_html.py', work)
    html = (work / 'T.html').read_text(encoding='utf-8')
    heads = re.findall(r'<h4[^>]*>(.*?)</h4>', html, re.S)
    keys = sorted(h.split('<')[0].strip() for h in heads)
    eq(keys, ['mart.orders', 'shop.orders'],
       'each heading says which table it is — two <h4>orders</h4> made the '
       'previous edition hand its descriptions to the wrong table')


# ── 2. 사용자가 만들 수 있는 입력에서 죽은 것 ────────────────────────────────

@case('docx: a spec row with extra cells does not kill the build')
def _(work):
    # 6라운드. spec 의 표 행에 칸이 더 많으면 docx 생성이 IndexError 로 죽었다.
    # spec 은 사람이 손으로 쓰는 파일이다 — 칸을 하나 더 적는 것은 오타 축에도 못 낀다.
    write_schema(work, {'t': table('t', [col('id')])})
    (work / 'erd.spec.json').write_text(json.dumps({
        'areas': [['A', 'one', 'public', ['t']]],
        'doc': {'meta': [['name', 'v', 'k', 'v2', 'one cell too many'],
                         ['short']],
                'mapping': [['1', 'a', 'b', 'c', 'd', 'e', 'f'], ['2', 'a']],
                'open_items': [['x'], ['y', 'z', 'w', 'q', 'r']]}}), encoding='utf-8')
    run('merge_desc.py', work)
    run('build_erd.py', work)
    r = run('build_docx.py', work)
    if 'Traceback' in r.stderr:
        raise Fail(f'a hand-written spec row must not IndexError:\n{r.stderr[-400:]}')
    if not (work / 'T.docx').exists():
        raise Fail('no docx produced')


@case('merge_schemas: a broken part is explained, not tracebacked')
def _(work):
    # 6라운드. 합칠 schema.json 이 깨졌을 때 raw traceback 이 나왔다. 여러 DB 를
    # 합치는 흐름은 문서가 권하는 사용법이고, 그 파일은 앞 단계가 쓰다 만 것일 수 있다.
    work.mkdir(parents=True, exist_ok=True)
    (work / 'schema.shop.json').write_text(json.dumps(
        {'orders': table('orders', [col('id'), col('m')], pk=['id'],
                         fks=[{'column': 'm', 'ref_table': 'nowhere', 'ref_column': 'id',
                               'on_delete': 'CASCADE'}])}), encoding='utf-8')
    (work / 'schema.mart.json').write_text('{ "orders": ', encoding='utf-8')

    def merge(labels, ok=True):
        # 라벨은 argv 로 받는다. run() 은 인자를 붙일 자리가 없으니 작은 실행기를 둔다.
        drv = work / f'merge_{len(list(work.glob("merge_*.py")))}.py'
        drv.write_text(f'import sys\nsys.path.insert(0, {str(HERE)!r})\n'
                       f'sys.argv = ["merge_schemas.py"] + {labels!r}\n'
                       'import merge_schemas\nmerge_schemas.main()\n', encoding='utf-8')
        return run(str(drv), work, expect_ok=ok)

    r = merge([], ok=False)                                # 인자 없음 → 쓰는 법
    if 'Traceback' in r.stderr:
        raise Fail(f'no argument should be a usage message:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'merge_schemas', 'the message says how to call it')

    r = merge(['../../outside'], ok=False)                 # 경로가 되는 라벨
    if 'Traceback' in r.stderr:
        raise Fail(f'an unsafe label should be a message:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, '../../outside', 'the message names the invalid label')

    r = merge(['shop', 'nosuch'], ok=False)                # 없는 라벨
    if 'Traceback' in r.stderr:
        raise Fail(f'a missing part should be a message:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'nosuch', 'the message names the part it could not find')

    r = merge(['shop', 'mart'], ok=False)                  # 깨진 JSON
    if 'Traceback' in r.stderr:
        raise Fail(f'a truncated schema.*.json must not traceback:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'schema.mart.json', 'the message names the file that is broken')

    (work / 'schema.mart.json').write_text('[]', encoding='utf-8')
    r = merge(['mart'], ok=False)                          # JSON 이지만 스키마 객체가 아님
    if 'Traceback' in r.stderr:
        raise Fail(f'a non-object schema must not traceback:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'schema.mart.json', 'the message names the malformed schema')

    (work / 'schema.mart.json').write_text('{"missing_columns": {}}', encoding='utf-8')
    r = merge(['mart'], ok=False)
    if 'Traceback' in r.stderr:
        raise Fail(f'a part without columns must not traceback:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'columns', 'the missing required part field is named')

    (work / 'schema.a.json').write_text(json.dumps(
        {'b.orders': table('orders', [col('id')])}), encoding='utf-8')
    (work / 'schema.a.b.json').write_text(json.dumps(
        {'orders': table('orders', [col('id')])}), encoding='utf-8')
    r = merge(['a', 'a.b'], ok=False)                      # 둘 다 a.b.orders 가 됨
    if 'Traceback' in r.stderr:
        raise Fail(f'colliding labelled keys must not traceback:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'a.b.orders', 'the message names the colliding table key')

    (work / 'schema.mart.json').write_text(json.dumps(
        {'gone': table('gone', [col('id')])}), encoding='utf-8')
    out = merge(['shop', 'mart']).stdout
    s = schema_of(work)
    # 16R — 기대값이 `['gone', 'orders']` 였다. merge_schemas.py 가 라벨을 안 붙이고
    # `merged.update(part)` 만 하던 시절의 값이다. 그 한 줄 때문에 두 DB 에 같은 이름의
    # 테이블이 있으면 하나가 **말없이 삼켜졌고**(합계까지 1+1=1 로 찍혔다), 정작 이
    # 파일의 docstring·README·SKILL 은 셋 다 "테이블 키는 `<라벨>.<테이블명>`" 이라고
    # 적고 있었다. 라벨을 붙이는 쪽으로 고쳤으므로 기대값도 문서가 약속하는 값으로
    # 옮긴다 — 이 케이스가 재는 것(깨진 part 를 역추적 없이 설명하는가, 갈 곳 없는
    # FK 를 버리는가)은 그대로다. 새 동작 자체는 selftest_build.py 의
    # `merge_schemas: two databases that share a table name stay two tables` 가 잰다.
    eq(sorted(s), ['mart.gone', 'shop.orders'], 'both parts land in one schema')
    eq(s['shop.orders']['fks'], [],
       'an FK whose parent is in neither part is dropped, not left dangling')
    has(out, '1', 'and the summary counts what it dropped')


@case('parse: a DDL-only project never reaches for a database')
def _(work):
    # 6라운드. 채울 것이 없어도 무조건 DB 에 접속하려 들어서, 접속 정보가 없으면
    # 거기서 죽고 있으면 `table_name in ()` 이라는 빈 SQL 을 던져 경고를 찍었다.
    # 접속 정보를 **일부러 못 쓰게** 해 두고 돌린다 — 손을 뻗으면 그 자리에서 드러난다.
    boom = work / 'never.py'
    work.mkdir(parents=True, exist_ok=True)
    boom.write_text('import sys\nsys.stderr.write("parse_ddl reached for the database\\n")\n'
                    'sys.exit(9)\n', encoding='utf-8')
    d = work / 'sql'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text(
        'CREATE TABLE orders (id bigint PRIMARY KEY, amount numeric(10,2));\n'
        'CREATE TABLE items (id bigint PRIMARY KEY, order_id bigint REFERENCES orders(id));\n',
        encoding='utf-8')
    r = run('parse_ddl.py', work, sql_dir=d,
            env={'ERD_PSQL': f'{shlex.quote(sys.executable)} {shlex.quote(str(boom))}'})
    # 죽은 psql 의 stderr 는 parse_ddl 이 받아서 자기 stdout 에 요약으로 찍는다 —
    # 둘 다 본다. 한쪽만 보면 '안 불렀다' 와 '부르고 삼켰다' 를 구분하지 못한다.
    both = r.stdout + r.stderr
    if 'reached for the database' in both:
        raise Fail(f'nothing needed filling in — parse_ddl must not connect at all:\n{both}')
    if 'in ()' in both:
        raise Fail(f'an empty IN () was sent to the server:\n{both}')
    s = schema_of(work)
    eq(sorted(s), ['items', 'orders'], 'and the DDL alone still produced the schema')


@case('introspect: a server too old to answer is refused, not half-read')
def _(work):
    # 이번 작업분. 9.3 이하는 서브쿼리 별칭을 row_to_json 의 키로 쓰지 않아 **모든
    # 값이 빈 문자열**로 온다 — 버전 숫자마저 빈 문자열이다. int() 가 traceback 을
    # 뱉거나, 더 나쁘게는 컬럼이 하나도 없는 문서가 조용히 나온다.
    r = run('introspect.py', work, expect_ok=False,
            env=db_rows(work, [], FAKE_PG_VER='90300'))
    if 'Traceback' in r.stderr:
        raise Fail(f'an old server should be a message, not a traceback:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, '9.4', 'the message names the version this needs')
    if (work / 'schema.json').exists():
        raise Fail('a server that cannot answer must not leave a schema behind')

    # 9.4 는 답한다 — 하한을 올려 잡아 멀쩡한 서버를 막지는 않는지 함께 지킨다
    run('introspect.py', work, env=db_rows(work, [
        (COLQ, [['s1', 't', 'id', 'bigint', 'NO', '', 'NO', '']])], FAKE_PG_VER='90400'))
    eq(sorted(schema_of(work)), ['t'], 'PostgreSQL 9.4 is supported, not refused')

    # 14라운드. 위 두 벌은 **숫자 비교 관문을 한 번도 지나가지 않는다.** 9.3 쪽은
    # 값이 빈 문자열로 오는 바람에 `isdigit()` 분기에서 먼저 걸리고, 9.4 쪽은 통과하는
    # 쪽이다. 그래서 `if ver < MIN_PG` 의 하한을 0 으로 내려 잡아도 101개가 전부
    # 통과했다 — 케이스 주석은 '하한을 올려 잡지는 않는지 지킨다' 고 적어 놓고
    # **내려** 잡는 쪽은 아무도 안 보고 있었다.
    #
    # 두 관문이 하필 같은 숫자(9.4)를 쓰는 탓에 가짜 서버로는 뒤엣것에 닿을 수가
    # 없었다. FAKE_PG_ALIAS 로 '별칭은 제대로 쓰는데 버전은 하한 미만' 인 서버를
    # 만들어 관문 자체를 지나가게 한다. 오늘의 두 숫자가 같다는 것은 우연이고,
    # 하한이 언젠가 올라가면(MIN_PG 는 문서가 약속하는 값이다) 그때 실제로 갈린다 —
    # 여기서 멈추지 않으면 반쯤 읽은 문서가 나온다.
    (work / 'schema.json').unlink(missing_ok=True)
    r = run('introspect.py', work, expect_ok=False, env=db_rows(
        work, [(COLQ, [['s1', 't', 'id', 'bigint', 'NO', '', 'NO', '']])],
        FAKE_PG_VER='90399', FAKE_PG_ALIAS='1'))
    if r.returncode == 0:
        raise Fail('a server just below the floor answered every query and was '
                   'documented — the version gate never actually compares numbers')
    if 'Traceback' in r.stderr:
        raise Fail(f'the floor must be a message, not a traceback:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, '9.4', 'and the message still names the version this needs')
    if (work / 'schema.json').exists():
        raise Fail('a refused server must not leave a schema behind either')


@case('config: an empty ERD_DOCNAME does not make a hidden file')
def _(work):
    # 4라운드. 빈 값이면 '.html' 같은 숨김 파일이 되어 만든 사람이 찾지 못했다.
    # 슬래시 쪽은 시험이 있는데 빈 값 쪽은 없었다 — 같은 함수의 다른 반쪽이다.
    write_schema(work, {'t': table('t', [col('id')])})
    for raw in ('', '   ', '...', '/'):
        run('merge_desc.py', work, env={'ERD_DOCNAME': raw})
        run('build_erd.py', work, env={'ERD_DOCNAME': raw})
        run('build_html.py', work, env={'ERD_DOCNAME': raw})
        made = [p.name for p in work.parent.rglob('*.html')] + \
               [p.name for p in work.rglob('*.html')]
        if not made:
            raise Fail(f'ERD_DOCNAME={raw!r}: no document was produced')
        if any(n.startswith('.') for n in made):
            raise Fail(f'ERD_DOCNAME={raw!r} made a hidden file: {made}')


@case('errors: ERD_PROJ pointing at a path that does not exist is created up front')
def _(work):
    # 4라운드. 없는 경로를 주면 마지막 저장 단계에서야 죽었다 — 몇 분 걸려 그림을
    # 다 그린 뒤다. 지금은 config 가 시작할 때 만든다.
    proj = work.parent / 'not' / 'there' / 'yet'
    write_schema(work, {'t': table('t', [col('id')])})
    run('merge_desc.py', work, proj=proj)
    run('build_erd.py', work, proj=proj)
    run('build_html.py', work, proj=proj)
    if not (proj / 'T.html').exists():
        raise Fail(f'nothing landed in {proj}')


# ── 3. 보기의 문제 ───────────────────────────────────────────────────────────

@case('render: a read-only source table wears its badge')
def _(work):
    # 6라운드. '원천' 배지는 아무도 세팅하지 않는 키를 보고 있어 한 번도 나오지
    # 않았다. 배지는 '이 테이블은 우리가 만들지 않는다' 는 표시라 없으면 읽는 사람이
    # 오해한다. parse_ddl 은 origin='ref' 로 표시한다.
    sys.path.insert(0, str(HERE))
    write_schema(work, {
        'plain': table('plain', [col('id')]),
        'brand_new': table('brand_new', [col('id')], origin='new'),
        'from_source': table('from_source', [col('id')], origin='ref')})
    probe = work / 'probe_badge.py'
    probe.write_text(
        "import erd\n"
        "got = {n: erd.badge(n)[0] for n in erd.SCHEMA}\n"
        "assert got['from_source'], 'a ref-origin table shows no badge at all'\n"
        "assert got['brand_new'], 'a new table shows no badge'\n"
        "assert len({got['plain'], got['brand_new'], got['from_source']}) == 3, (\n"
        "    'the three origins must read differently: ' + repr(got))\n",
        encoding='utf-8')
    run(str(probe), work, env={'PYTHONPATH': str(HERE)})

    # 위는 **읽는 쪽** 만 잰다. 정작 6라운드의 결함은 '배지가 아무도 세팅하지 않는 키를
    # 본다' 였으니, 쓰는 쪽이 그 값을 그만 내놓으면 배지는 도로 사라진다. 그런데
    # schema.json 을 이 시험이 손으로 쓰므로 그 절반은 영영 안 잡힌다 — 실제로
    # parse_ddl 쪽 'ref' 를 다른 글자로 바꿔도 여기 89개가 전부 초록이었다.
    # ref 경로는 진짜 서버가 있어야 도는지라, 두 쪽이 같은 낱말을 쓰는지만 못박는다.
    # 문자열 검사인 것을 알고 쓴다 — 없는 것보다는 낫고, 있는 척하지는 않는다.
    import inspect

    import parse_ddl
    has(inspect.getsource(parse_ddl.fetch_ref), "'origin': 'ref'",
        "parse_ddl.fetch_ref must keep producing the very value badge() reads — "
        'the badge is only as real as the two halves agreeing')


@case('i18n: a latin-only font is never chosen for a language that needs more')
def _(work):
    # 2라운드가 만든 것. 폴백 목록에 라틴 전용 폰트를 넣는 순간, 한글 폰트가 없는
    # 환경에서 **명확한 실패**가 **조용한 두부(□)** 로 바뀐다. 성공이라 찍고 글자가
    # 전부 □ 인 문서가 나오는 것보다 못 찾고 죽는 편이 낫다.
    write_schema(work, {'t': table('t', [col('id')])})
    probe = work / 'probe_font.py'
    probe.write_text(
        "import erd, json, os, sys\n"
        "latin = ('helvetica', 'dejavu', 'liberation', 'arial')\n"
        "flat = ' '.join(str(x) for pair in erd._SANS_CANDIDATES for x in pair).lower()\n"
        "hit = [f for f in latin if f in flat]\n"
        "wide = erd.LANG in ('ko', 'ja')\n"
        "assert bool(hit) != wide, (\n"
        "    f'{erd.LANG}: latin-only fallbacks {hit} present={bool(hit)} '\n"
        "    f'but a CJK language must have none (and a latin one must have some)')\n",
        encoding='utf-8')
    for lang in ('ko', 'ja', 'en', 'es'):
        run(str(probe), work, env={'PYTHONPATH': str(HERE), 'ERD_LANG': lang})


@case('render: a relationship label does not erase the line under it')
def _(work):
    # 5라운드가 만든 것. 라벨을 배경색 **사각형**으로 깔고 그 위에 글자를 얹고
    # 있었다. 그 사각형이 아래를 지나가던 다른 선을 지워, 선 다발에 군데군데 틈이
    # 생겼다 — 허브 시험에서 라벨 40개 중 34개가 남의 선 위에 앉아 있었다.
    # 지금은 글자 둘레만 두른다. SVG 는 paint-order=stroke 라야 테두리가 글자 뒤로
    # 가서 PNG 와 같은 그림이 된다 — 그것이 빠지면 SVG 만 글자가 뭉개진다.
    #
    # ⚠ 한계를 적어 둔다 — 재는 것은 '테두리가 **있다**' 이지 '아래를 지우는 것이
    # **없다**' 가 아니다. 테두리를 그대로 둔 채 그 앞에 배경색 사각형을 다시 깔면
    # 선은 도로 지워지는데(svg_canvas.rectangle 은 SVG 에도 진짜 <rect> 를 낸다)
    # 여기 검사는 전부 통과한다. PNG 도 보지 않고, 선이 실제로 이어져 있는지도
    # 보지 않는다. 이름이 말하는 것을 재려면 라벨 아래 픽셀을 훑어야 한다.
    t = {'hub': table('hub', [col('id'), col('name', 'text')], pk=['id'])}
    for i in range(12):
        n = f'c{i:02d}'
        t[n] = table(n, [col('id'), col('hub_id')], pk=['id'],
                     fks=[{'column': 'hub_id', 'ref_table': 'hub', 'ref_column': 'id',
                           'on_delete': 'CASCADE'}])
    write_schema(work, t)
    run('build_erd.py', work)
    svg = (work / 'out' / 'erd_area_A.svg').read_text(encoding='utf-8')
    if 'hub_id' not in svg:
        raise Fail('the area diagram drew no relationship label at all')
    haloed = re.findall(r'<text[^>]*paint-order="stroke"[^>]*>[^<]*hub_id', svg)
    if not haloed:
        raise Fail('no relationship label carries paint-order=stroke — either the '
                   'halo is gone, or it is painted over the glyphs and the SVG '
                   'no longer matches the PNG')
    has(svg, 'stroke-linejoin="round"',
        'the halo is drawn around the glyphs, not as a box behind them')


@case('i18n: a catalog that cannot be read says so instead of quietly speaking English')
def _(work):
    # 초기 라운드. 카탈로그를 못 읽으면 조용히 영어로 떨어졌다 — 번역이 깨진 것을
    # 아무도 모른다. 지금은 그림은 계속 그리되 왜 말이 바뀌었는지 알려 준다.
    #
    # 15라운드. 이 케이스는 깨진 카탈로그를 **검사 대상 트리 안**(`scripts/lang/zz.py`)
    # 에 쓰고 `finally` 에서 지웠다. 시험 벌 전체에서 공유 가변 상태를 쓰는 유일한
    # 자리였고, 그래서 시험을 두 벌 동시에 돌리면 한쪽의 `unlink` 가 다른 쪽의
    # `build_erd` 가 `lang.zz` 를 읽기 전에 파일을 지워 **이 케이스만** 간헐로 붉었다
    # (병렬 16회 중 7회, 매번 여기). 프로세스가 중간에 죽으면 `zz.py` 가 트리에 남아
    # 그다음 사람의 `git status` 를 더럽혔다. 14라운드 내내 수정자 둘이 본 '가끔 나는
    # 실패' 의 정체가 이것이다.
    #
    # 그래서 카탈로그 트리째 임시 디렉터리에 복사해 거기서 잰다. `run()` 은 절대
    # 경로를 그대로 받으므로(`HERE / '/abs'` 는 `/abs`), 복사본의 `build_erd.py` 를
    # 부르면 그 프로세스의 `sys.path[0]` 이 복사본 쪽이 되어 `lang` 도 복사본 것을
    # 읽는다. **시험은 검사 대상 트리에 아무것도 쓰지 않는다.**
    tree = work.parent / 'scripts'
    shutil.copytree(HERE, tree, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', 'out', 'erd-build'))
    (tree / 'lang' / 'zz.py').write_text('M = {  # 일부러 깨뜨린다\n', encoding='utf-8')
    if (HERE / 'lang' / 'zz.py').exists():
        raise Fail('the broken catalog was written into the tree under test, not the copy')
    write_schema(work, {'t': table('t', [col('id')])})
    r = run(str(tree / 'build_erd.py'), work, env={'ERD_LANG': 'zz'})
    has(r.stdout + r.stderr, 'zz',
        'a catalog that will not load must name itself, not fall through in silence')


@case('verify: every check on a diagram that routes lines is a real number')
def _(work):
    # 팀이 이미 두 번 당한 모양이다 — 재지 않은 것을 0 으로 찍으면 나머지 시험이
    # 다 통과해도 아무것도 지켜지지 않는다. 선을 그리는 그림에서는 다섯 항목이
    # 전부 숫자여야 하고, 항목 자체가 사라지지도 않아야 한다.
    #
    # ⚠ 한계를 적어 둔다 — 이 항목은 이름이 말하는 것을 절반만 잰다. 잡는 것은
    # '재지 않았다' 의 **정직한 형태**(null)와 항목이 통째로 사라진 것뿐이다.
    # 정작 위 주석이 말하는 결함 — 재지도 않고 0 을 찍는 것 — 은 그냥 지난다.
    # `('thru', thru_nodes())` 를 `('thru', 0)` 으로 바꿔 봤는데 여기 것도 저쪽 것도
    # 전부 초록이었다. '적어도 하나는 0 이 아니어야 한다' 로도 못 잡는다: 라우터가
    # 제 일을 하면 평범한 입력에서 다섯 항목은 늘 0 이라(무작위 200판을 재 봤다)
    # 그 규칙은 참인 채로 아무것도 걸러 내지 못한다. 이 자리를 진짜로 재려면
    # 라우터를 건너뛰고 좌표를 직접 겹치게 넣은 판이 있어야 한다. 아직 없다.
    write_schema(work, {
        'a': table('a', [col('id'), col('b_id')], pk=['id'],
                   fks=[{'column': 'b_id', 'ref_table': 'b', 'ref_column': 'id',
                         'on_delete': 'CASCADE'}]),
        'b': table('b', [col('id')], pk=['id'])})
    run('build_erd.py', work)
    want = {'label_table', 'label_x', 'thru', 'v_overlap', 'h_overlap'}
    for r in verify_recs(work):
        eq(set(r['counts']), want, f'{r["file"]}: the set of checks')
        never_na = want - {'label_table', 'label_x'}      # 라벨은 안 그릴 수 있다
        for k in never_na:
            if r['counts'][k] is None:
                raise Fail(f'{r["file"]}: {k} says "not measured" — every diagram '
                           'that draws lines can and must measure it')
    for r in verify_recs(work, 'area'):
        for k in want:
            if r['counts'][k] is None:
                raise Fail(f'{r["file"]} draws labels and lines — {k} must be a number')


@case('render: a self-reference does not draw one line on top of another')
def _(work):
    # 10라운드. 자기참조 루프의 팔 높이(cy±dy)가 entry_ys() 보다 **먼저** 정해졌고,
    # 팔은 used_vx 에만 등록되고 used_hy 에는 들어가지 않았다 — '진출입 y 를 다 잡고
    # 나서 경로를 만든다' 는 두 단계 분리를 통로 lane 에만 적용하고 루프에는 적용하지
    # 않은 자리다. 자기참조가 든 평범한 스키마 여덟에 하나꼴로 [경고] 가 났고, 그것은
    # 세는 실수가 아니라 실제로 겹쳐 그린 선이었다 (팔과 다른 선의 꼬리가 1px 차이로
    # 50px 넘게 나란히 달렸다). SKILL.md 는 [경고] 를 회귀로 읽으라고 적는다 —
    # 평범한 입력에서 흔히 나면 그 글자는 신호가 아니라 소음이 된다.
    #
    # 아래는 그때 실제로 깨진 배치 그대로다. 자기참조 셋(tb0 둘·tb2·tb5 둘)이
    # 서로 다른 크기의 테이블에 섞여 있어야 재현된다.
    def fk(c, r):
        return {'column': c, 'ref_table': r, 'ref_column': 'id', 'on_delete': 'NO ACTION'}

    write_schema(work, {
        'tb0': table('tb0', [col('id'), col('r0'), col('r1'), col('r2')],
                     fks=[fk('r0', 'tb0'), fk('r1', 'tb0'), fk('r2', 'tb1')]),
        'tb1': table('tb1', [col('id'), col('r0'), col('r1')],
                     fks=[fk('r0', 'tb3'), fk('r1', 'tb5')]),
        'tb2': table('tb2', [col('id'), col('r0'), col('r1')],
                     fks=[fk('r0', 'tb3'), fk('r1', 'tb2')]),
        'tb3': table('tb3', [col('id'), col('r0'), col('r1')],
                     fks=[fk('r0', 'tb4'), fk('r1', 'tb2')]),
        'tb4': table('tb4', [col('id'), col('r0')], fks=[fk('r0', 'tb5')]),
        'tb5': table('tb5', [col('id'), col('r0'), col('r1')],
                     fks=[fk('r0', 'tb5'), fk('r1', 'tb5')]),
    })
    run('build_erd.py', work)
    for r in verify_recs(work):
        if r['warn']:
            raise Fail(f'{r["file"]}: {", ".join(r["warn"])} != 0 — a self-loop arm was '
                       f'placed before the entry rows existed\n      counts: {r["counts"]}')


@case('parse: a block comment never becomes a column description')
def _(work):
    # 10라운드. mask() 가 블록 주석을 mc·msc 에서만 가리고 ms 에는 남겼는데,
    # split_top_level() 은 ms 에서 `--` 를 찾는다. 그래서 블록 주석 **안의** 줄이
    # 아래 컬럼의 설명이 됐다 — 내부 메모가 고객이 받는 문서에 그대로 실린다.
    # 구분자까지 딸려 나오기도 했다(`see PR 12 */`).
    s = ddl(work, """
CREATE TABLE t (
  id bigint,  /* legacy: was int -- see PR 12 */
  /* internal design note
     -- do not ship this line
   */
  name text  -- display name
);
""")
    got = {c['name']: c['comment'] for c in s['t']['columns']}
    eq(got, {'id': '', 'name': 'display name'},
       'only a line comment is a description; a block comment is not, and neither is '
       'a line inside one')
    for c in s['t']['columns']:
        if '*/' in c['comment'] or 'do not ship' in c['comment']:
            raise Fail(f'a block comment leaked into the document: {c["comment"]!r}')


@case('parse: a comment on the CREATE TABLE line belongs to the table')
def _(work):
    # 10라운드. '주석은 아래로 붙는다' 는 규칙을 여는 괄호와 같은 줄에도 그대로
    # 태우는 바람에, 테이블 이야기가 첫 컬럼(대개 PK)의 설명이 되어 실렸다.
    # 그 줄의 임자는 테이블 헤더이고 헤더는 컬럼이 아니다.
    s = ddl(work, """
CREATE TABLE t (  -- one row per order
  id bigint PRIMARY KEY,
  name text  -- display name
);
""")
    eq(s['t']['note'], 'one row per order', 'the header line is the table note')
    eq({c['name']: c['comment'] for c in s['t']['columns']},
       {'id': '', 'name': 'display name'},
       'and it must not become the first column description')


@case('errors: a verify log that cannot be written does not cost the figures')
def _(work):
    # 10라운드. verify_log() 가 img.save() 보다 **먼저** 불렸고 open() 은 무방비였다.
    # 쓸 수 없는 경로를 주면 '검증했다' 는 줄만 찍힌 채 PNG 한 장 없이 exit 1 이었다 —
    # 재는 도구가 재려는 것을 부수면 안 된다. introspect 쪽에서 이미 한 번 고친 모양이다.
    write_schema(work, {'a': table('a', [col('id')]), 'b': table('b', [col('id')])})
    bad = work / 'no_such_dir' / 'v.jsonl'
    r = run('build_erd.py', work, env={'ERD_VERIFY_LOG': str(bad)}, expect_ok=False)
    if r.returncode:
        raise Fail(f'an unwritable ERD_VERIFY_LOG killed the build (exit {r.returncode})')
    pngs = sorted(p.name for p in (work / 'out').glob('*.png'))
    if not pngs:
        raise Fail('the run said it verified the diagrams and then saved none of them')
    has(r.stdout, 'ERD_VERIFY_LOG', 'and it says out loud that the log was not written')

    # 이어 붙이기만 하면 두 판 뒤 6줄이 남아 어느 3줄이 이번 것인지 알 수 없다.
    good = work / 'v.jsonl'
    counts = []
    for _ in range(2):
        run('build_erd.py', work, env={'ERD_VERIFY_LOG': str(good)})
        counts.append(len(good.read_text(encoding='utf-8').strip().splitlines()))
    eq(counts[0], counts[1], 'the log holds one run, not every run ever')


@case('errors: a control character in a name does not kill the build')
def _(work):
    # 10라운드. clean() 은 설명·역할명에만 걸려 있었다. 이름에 개행이 들면 PIL 이
    # 폭을 못 재고 죽어 산출물이 **0개** 가 되고(그림도 문서도 없다), \x1e 가 들면
    # erd·html 은 넘어간 뒤 build_docx 가 lxml 에서 죽어 사용자에게 반 벌만 남는다.
    # 기본값은 아무도 안 씻어서 raw \x1f 가 HTML 까지 갔다. introspect 가 값을 있는
    # 그대로 실어 오는 것은 제 일이 맞다 — 받고도 안 무너지는 것이 쓰는 쪽 몫이다.
    #
    # 14라운드. 여기가 쓰던 문자는 `\n`·`\x1e`·`\x1f`·`\x0b` 넷뿐이었는데, 파이썬
    # `str.split()` 이 그 넷을 이미 공백으로 쳐서 **`config._CTRL` 을 통째로 비워도**
    # 이 케이스가 초록이었다. `_CTRL` 이 실제로 일하는 자리는 `split()` 이 손대지
    # 않는 문자들이다 — `'a\x1eb\x00c\x07d'.split()` 은 `\x00`·`\x07` 를 그대로
    # 통과시킨다. 그 셋(`\x00`·\x07`·`\x7f`)을 fixture 와 아래 검사 목록에 함께 넣는다.
    write_schema(work, {
        'ok': table('ok', [col('id')]),
        'bad\nname': table('bad\nname', [col('id')]),
        'nul\x00bell\x07': table('nul\x00bell\x07', [col('id')]),
        'rs': table('rs', [col('id'),
                           col('c\x1ed\x00e\x07f', 'text', default='x\x1fy\x7fz')])})
    for script in ('merge_desc.py', 'build_erd.py', 'build_html.py', 'build_docx.py'):
        r = run(script, work, expect_ok=False)
        if r.returncode:
            raise Fail(f'{script} died on a control character in a name (exit '
                       f'{r.returncode})\n      {r.stderr.strip().splitlines()[-1]}')
    if not list((work / 'out').glob('erd_area_*.png')):
        raise Fail('no diagram came out — a half set is worse than a clear failure')
    for name in ('T.html', 'T.graphml'):
        text = (work / name).read_text(encoding='utf-8')
        stray = [repr(ch) for ch in '\x1e\x1f\x0b\x00\x07\x7f' if ch in text]
        if stray:
            raise Fail(f'{name} carries raw control characters {", ".join(stray)} — '
                       'yEd and browsers reject the file')
    if not (work / 'T.docx').exists():
        raise Fail('the docx was never written')

    # 두 위험한 키를 같은 안전한 키로 바꿀 수는 없다. 예전에는 충돌을 알아챈 뒤에도
    # 원래 제어문자 키를 그대로 렌더러에 넘겨, 조용한 유실 대신 뒤 단계의 크래시가 났다.
    write_schema(work, {
        'same\nkey': table('same\nkey', [col('id')]),
        'same key': table('same key', [col('id')]),
    })
    r = run('build_erd.py', work, expect_ok=False)
    if 'Traceback' in r.stderr:
        raise Fail(f'clean-key collision must be a message:\n{r.stderr[-300:]}')
    has(r.stdout + r.stderr, 'same key', 'the collision message names the resulting key')

    # JSON 문법만 맞고 최상위가 배열인 파일도 입력 스키마는 아니다. 설명 병합과
    # 렌더러 어느 쪽을 먼저 실행하든 같은 파일 이름을 대고 멈춰야 한다.
    (work / 'schema.json').write_text('[]', encoding='utf-8')
    for script in ('merge_desc.py', 'build_erd.py'):
        r = run(script, work, expect_ok=False)
        if 'Traceback' in r.stderr:
            raise Fail(f'{script} must explain a non-object schema:\n{r.stderr[-300:]}')
        has(r.stdout + r.stderr, 'schema.json', 'the malformed schema is named')

    malformed = (
        {'t': {'columns': 'id'}},
        {'t': {'columns': [{'name': 1}]}},
        {'t': {'columns': [], 'pk': [1]}},
        {'t': {'columns': [], 'fks': [{}]}},
        {'t': {'columns': [], 'uniques': ['id']}},
        {'t': {'schema': 1, 'columns': []}},
        {'t': {'columns': [{'name': 'id', 'not_null': 'NO'}]}},
        {'t': {'columns': [], 'indexes': [{'name': 'i', 'def': 1}]}},
    )
    for i, schema in enumerate(malformed):
        (work / 'schema.json').write_text(json.dumps(schema), encoding='utf-8')
        for script in ('merge_desc.py', 'build_erd.py'):
            r = run(script, work, expect_ok=False)
            if 'Traceback' in r.stderr:
                raise Fail(f'{script} tracebacked on malformed schema field {i}: '
                           f'{r.stderr[-300:]}')
            has(r.stdout + r.stderr, 't', 'the malformed table is named')


# ── 그린 것을 픽셀로 되짚는 자리 ─────────────────────────────────────────────
# 14라운드. 다섯 카운터는 전부 **계획한 좌표**를 읽는다 — 어디에 그리기로 했는지.
# 그러니 결함이 좌표가 아니라 **칠하는 순서**에 있으면 다섯 다 0 을 찍는다. 자기참조
# 라벨이 노드보다 먼저 칠해져 테이블에 지워지고 있었는데, 카운터는 '라벨을 거기
# 뒀다' 만 알고 '그 라벨이 아직 보이는가' 는 아무도 묻지 않았다. 눈으로도 못 잡는다 —
# 지워진 라벨은 그냥 없는 라벨처럼 보인다.
#
# 그래서 ImageDraw 를 감싸 **무엇을 어떤 순서로 칠했는지** 받아 적고, 같은 그림을
# 라벨만 빼고 한 번 더 그려 두 PNG 를 뺀다. 남는 픽셀이 그 라벨이 실제로 보이는
# 분량이다. 색을 따지지 않으므로 팔레트가 바뀌어도 그대로 잰다.
#
# 자를 erd.py 안에 넣지 않는다 — 재는 코드가 재는 대상 안에 있으면 같이 죽는다.
_PAINT_PROBE = '''\
import json
import sys

from PIL import Image, ImageChops, ImageDraw as RID

import erd

MODE = sys.argv[1]
EV, SUP = [], [False]
NODE_FILL = ({v[0] for v in erd.LAYERS.values()}
             | {v[1] for v in erd.LAYERS.values()})
LINE_COL = {erd.EDGE, erd.EDGE_CASCADE}


class Rec:
    """ImageDraw 래퍼 — 무엇을 어떤 차례로 칠했는지 받아 적는다."""

    def __init__(self, img):
        self._d = RID.Draw(img)
        self._on = img.size != (1, 1)      # 1×1 은 자리를 재는 판이지 칠하는 판이 아니다

    def __getattr__(self, name):
        fn = getattr(self._d, name)
        if not self._on:
            return fn
        if name == 'text':
            def txt(xy, text, font=None, anchor=None, **kw):
                if 'stroke_width' in kw:           # 테두리를 두른 글자 = 관계 라벨
                    EV.append(['label', len(EV), text,
                               [float(v) for v in
                                self._d.textbbox(xy, text, font=font, anchor=anchor)]])
                    if SUP[0]:
                        return None
                return fn(xy, text, font=font, anchor=anchor, **kw)
            return txt
        if name == 'rectangle':
            def rect(xy, **kw):
                if kw.get('fill') in NODE_FILL:
                    b = ([xy[0][0], xy[0][1], xy[1][0], xy[1][1]]
                         if isinstance(xy[0], (list, tuple)) else list(xy))
                    EV.append(['node', len(EV), '', [float(v) for v in b]])
                return fn(xy, **kw)
            return rect
        if name == 'line':
            def ln(xy, **kw):
                if kw.get('fill') in LINE_COL:
                    EV.append(['line', len(EV), '',
                               [float(xy[0][0]), float(xy[0][1]),
                                float(xy[1][0]), float(xy[1][1])]])
                return fn(xy, **kw)
            return ln

        def other(*a, **kw):
            EV.append([name, len(EV), '', []])
            return fn(*a, **kw)
        return other


erd.ImageDraw = type('m', (), {'Draw': Rec})
_code, _name, _schema, tables = erd.AREAS[0]
apos, aboxes, ext = erd.layout_area(tables, with_desc=True)
png = erd.OUT / 'probe.png'
erd.draw_erd(png, tables + ext, apos, aboxes, 'probe', with_desc=True, scale=2,
             stubs=set(ext), legend=True)
ev = list(EV)

nodes = [e[3] for e in ev if e[0] == 'node']
labels = [e for e in ev if e[0] == 'label']
res = {'n_labels': len(labels), 'n_lines': sum(1 for e in ev if e[0] == 'line'),
       'last_node': max((e[1] for e in ev if e[0] == 'node'), default=-1),
       'first_label': min((e[1] for e in labels), default=-1),
       'self_labels': sum(1 for e in labels if e[2].startswith('parent_')),
       'thru': [], 'ratios': [], 'dead': []}

# 계획이 아니라 **칠한 것**으로 센다 — d.line() 이 테이블 상자 안을 지났는가.
for e in ev:
    if e[0] != 'line':
        continue
    x0, y0, x1, y1 = e[3]
    for n in nodes:
        ix0, ix1 = max(min(x0, x1), n[0] + 2), min(max(x0, x1), n[2] - 2)
        iy0, iy1 = max(min(y0, y1), n[1] + 2), min(max(y0, y1), n[3] - 2)
        if abs(x1 - x0) < 1 and n[0] + 2 < x0 < n[2] - 2 and iy1 - iy0 > 8:
            res['thru'].append(['V', x0, iy0, iy1, n])
        elif abs(y1 - y0) < 1 and n[1] + 2 < y0 < n[3] - 2 and ix1 - ix0 > 8:
            res['thru'].append(['H', y0, ix0, ix1, n])

if MODE == 'pixels':
    # 같은 그림을 **라벨 글자만 빼고** 한 번 더. 자리 잡기는 그대로 도므로 좌표는
    # 한 점도 다르지 않고, 두 PNG 가 다른 픽셀이 곧 그 라벨이 실제로 보이는 분량이다.
    SUP[0] = True
    EV.clear()
    bare = erd.OUT / 'probe_bare.png'
    erd.draw_erd(bare, tables + ext, apos, aboxes, 'probe', with_desc=True, scale=2,
                 stubs=set(ext), legend=True)
    A = Image.open(png).convert('RGB')
    B = Image.open(bare).convert('RGB')
    D = ImageChops.difference(A, B).convert('L')
    for e in labels:
        g = e[3]
        x0, y0 = max(int(g[0]), 0), max(int(g[1]), 0)
        x1, y1 = min(int(g[2]), A.size[0]), min(int(g[3]), A.size[1])
        ink = 0 if x1 <= x0 or y1 <= y0 else sum(
            D.crop((x0, y0, x1, y1)).histogram()[1:])
        area = max((x1 - x0) * (y1 - y0), 1)
        res['ratios'].append([e[2], ink, area])

print(json.dumps(res))
'''


def _long_name_fixture(work, n=9):
    """자기참조 둘 · 이름이 긴 컬럼 — 팔이 통로보다 길어지고 싶어 하는 모양.

    이 모양이라야 '팔이 테이블을 피하는가' 를 실제로 묻는다. 짧은 이름이면 팔이
    통로 안에 그냥 들어가서, 피하는 장치를 통째로 들어내도 그림이 멀쩡하다 —
    수정을 되돌려 확인했다(짧은 이름 판은 초록, 이 판은 관통 31개).
    """
    def fk(c, r):
        return {'column': c, 'ref_table': r, 'ref_column': 'id', 'on_delete': 'CASCADE'}

    longs = ['parent_organization_unit_registry_identifier',
             'root_organization_unit_registry_identifier']
    names = [f'organization_unit_registry_{i:02d}' for i in range(n)]
    t = {}
    for i, nm in enumerate(names):
        cols, fks = [col('id')], []
        for c in longs:
            cols.append(col(c))
            fks.append(fk(c, nm))
        if i:
            cols.append(col('reference_to_first_identifier'))
            fks.append(fk('reference_to_first_identifier', names[0]))
        t[nm] = table(nm, cols, pk=['id'], fks=fks)
    write_schema(work, t)
    return t


def _self_ref_fixture(work, n=11, k=3):
    """자기참조가 테이블마다 k 개 — 14라운드의 재현 스키마 그대로.

    하나로는 안 난다. 라운드 13·14 의 퍼저가 테이블당 자기참조를 **하나만** 뒀고,
    그래서 '무작위 200판에 경고 0' 이 셋 이상에서 거짓인 것을 두 라운드가 못 봤다.
    """
    def fk(c, r):
        return {'column': c, 'ref_table': r, 'ref_column': 'id', 'on_delete': 'CASCADE'}

    names = [f't{i:02d}' for i in range(n)]
    t = {}
    for nm in names:
        cols = [col('id')] + [col(f'parent_{j}_id') for j in range(k)]
        t[nm] = table(nm, cols, pk=['id'],
                      fks=[fk(f'parent_{j}_id', nm) for j in range(k)])
    for src, dst in (('t01', 't05'), ('t05', 't10'), ('t06', 't10'),
                     ('t07', 't03'), ('t09', 't07')):
        t[src]['columns'].append(col(f'{dst}_id'))
        t[src]['fks'].append(fk(f'{dst}_id', dst))
    write_schema(work, t)
    return t


def _paint(work, mode):
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e.update({'ERD_WORK': str(work), 'ERD_PROJ': str(work), 'ERD_LANG': 'en',
              'ERD_DOCNAME': 'T', 'ERD_SVG': '0'})
    r = subprocess.run([sys.executable, '-c', _PAINT_PROBE, mode],
                       capture_output=True, text=True, encoding='utf-8', env=e, cwd=str(HERE))
    if r.returncode != 0:
        raise Fail(f'the paint probe died:\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}')
    return json.loads(r.stdout.strip().splitlines()[-1])


@case('render: a self-reference label is still there after the tables are painted')
def _(work):
    # 14라운드. README 는 '라벨은 노드 **다음에** 그린다. 안 그러면 노드가 덮는다' 고
    # 못박아 두었고, 자기참조 라벨 옆 주석은 '다른 라벨과 같은 대우' 라고 적어 두었다.
    # 둘 다 거짓이었다 — 그 라벨만 노드 블록 **앞에서** 바로 그려졌고, 자리도
    # pts[1][0]-6 에 못박혀 후보 탐색이 없었다. 테이블에 걸친 라벨은 그대로 지워졌다.
    #
    # 다섯 카운터 중 어느 것도 이것을 볼 수 없다. 전부 '어디에 그리기로 했는가' 를
    # 읽지 '그것이 아직 보이는가' 를 읽지 않는다 — 그래서 이 케이스는 카운터를 묻지
    # 않고 **칠한 차례와 픽셀**을 본다.
    #
    # 되돌리면 빨강인 것을 확인하고 남긴다: 수정 전 이 그림은 라벨 38개 중 하나가
    # 잉크 0(2486px 짜리 상자에 한 점도 없음), 하나가 성한 것들의 3분의 2 미만이었고,
    # 라벨 첫 붓질이 노드 마지막 붓질보다 **앞**이었다(265 대 399).
    _self_ref_fixture(work)
    got = _paint(work, 'pixels')
    if got['n_labels'] < 20 or got['self_labels'] < 20:
        raise Fail(f'nothing to measure — the fixture drew {got["n_labels"]} labels '
                   f'({got["self_labels"]} of them self-references)')
    if got['first_label'] <= got['last_node']:
        raise Fail('a relationship label is painted before the tables are '
                   f'(first label {got["first_label"]}, last table '
                   f'{got["last_node"]}) — whatever lands on a box is erased')
    inked = sorted(ink / area for _t, ink, area in got['ratios'])
    mid = inked[len(inked) // 2]
    if mid < 0.05:
        raise Fail(f'even the median label is nearly blank ({mid:.3f}) — the probe '
                   'is measuring the wrong pixels, not the labels')
    # 절대값 대신 **같은 그림의 다른 라벨**과 견준다 (글꼴이 바뀌어도 성립한다).
    faint = [(t, ink, area) for t, ink, area in got['ratios']
             if ink / area < mid * 0.7]
    if faint:
        raise Fail('a label reaches the page rubbed out — its glyph box holds far '
                   f'less ink than the rest of this diagram (median {mid:.3f}): '
                   + ', '.join(f'{t!r} {ink}/{area}' for t, ink, area in faint[:5]))


@case('render: a self-reference loop is not painted through a table')
def _(work):
    # 14라운드. `slot()` 은 **다른 선**만 피하고 테이블은 피하지 않는다. 통로 라우터는
    # gutter_bounds() 로 테이블을 피하는데 자기참조 팔은 그 장치를 쓰지 않아,
    # x 가 x1-600..x1-12 라는 넓은 창 안에서 아무 데나 잡혔다 — 그 '아무 데' 가
    # 왼쪽 테이블 속이었다. 선은 노드보다 먼저 칠하므로 눈에도 안 보인다.
    #
    # 여기서 세는 것은 `thru` 카운터가 아니라 **실제 d.line() 호출**이다. 카운터가
    # 계획을 잘못 읽어도(또는 자기참조를 빼먹어도 — 한 번 그랬다) 이 케이스는 잡는다.
    #
    # **판을 둘 건다.** 한 판으로는 모자란 것을 되돌려 보고 알았다:
    #   · 자기참조 셋짜리 판은 옛 결함(600px 창)을 잡는다 — 그때 관통 4개.
    #     그런데 지금 코드에서 테이블 피하기를 들어내도 이 판은 초록이다.
    #   · 이름이 긴 판은 그 반대다. 팔은 제 라벨만큼 길어지려 하므로 통로 밖까지
    #     뻗고 싶어 하고, 피하기를 들어내면 관통 31개가 난다. 대신 옛 코드에서는
    #     팔이 짧아서(30+k·22) 이 판이 0 이다.
    # 둘 다 걸어야 '어느 쪽으로 되돌려도 빨강' 이 된다.
    for name, fixture in (('long column names', _long_name_fixture),
                          ('three self-references each', _self_ref_fixture)):
        w = work if fixture is _long_name_fixture else work.parent / 'work2'
        fixture(w)
        got = _paint(w, 'lines')
        if got['n_lines'] < 50:
            raise Fail(f'nothing to measure ({name}) — only {got["n_lines"]} '
                       'relationship line segments were painted')
        if got['thru']:
            first = got['thru'][0]
            raise Fail(f'{len(got["thru"])} painted line segment(s) run inside a table '
                       f'box ({name}); first: {first[0]} at {first[1:4]} '
                       f'through node {first[4]}')
    # 계획을 읽는 카운터도 같은 말을 해야 한다 — 둘이 갈리면 하나가 거짓말 중이다.
    run('build_erd.py', work)
    for r in verify_recs(work):
        if r['counts'].get('thru'):
            raise Fail(f'{r["file"]}: the thru counter says {r["counts"]["thru"]} '
                       'while the paint probe found none — they read the same figure')


@case('verify: the two label checks use one box and one rule')
def _(work):
    # 14라운드. `라벨↔라벨` 만 잉크로 재도록 고치고 `라벨↔테이블` 은 자리 잡기용 여백
    # 상자를 그대로 뒀다. 게다가 맞닿음 규칙이 **서로 반대**였다 — 라벨↔테이블은
    # `b[2] < o[0]` 라 스치기만 해도 세고, 라벨↔라벨은 `<=` 라 안 셌다. 같은 것을
    # 재면서 다른 자를 쓴 것이고, 이 저장소가 다섯 번 되풀이한 '같은 버그를 반만
    # 고쳤다' 의 모양 그대로다.
    #
    # 그리고 테두리를 어느 쪽에 넣을지도 여기서 못박는다. 라벨은 글자 둘레를 배경색
    # 으로 두르고 그려지므로 그 테두리도 **칠하는 것**이다 — 남의 글자 위에 얹히면
    # 지운다. 그래서 잉크 상자는 글자 + 테두리의 절반이다. 절반인 이유는 두 상자가
    # 겹친다는 것이 곧 '한쪽 테두리가 다른 쪽 **글자**에 닿는다' 가 되기 때문이다.
    #
    # ⚠ 한계: 아래 (2) 는 코드 본문을 읽는다. 규칙이 다시 갈라지는 것은 잡지만,
    # 두 검사가 같은 자로 **틀린** 것을 재는 것은 못 잡는다.
    write_schema(work, {'a': table('a', [col('id')])})
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e.update({'ERD_WORK': str(work), 'ERD_PROJ': str(work), 'ERD_LANG': 'en',
              'ERD_DOCNAME': 'T'})
    probe = '''
import json, erd
S = 2
f = erd.load_fonts(S)['edge']
P, halo = erd.LABEL_PAD_X, max(2, 2 * S) / S / 2


def placed(cx, cy, w=60.0):
    return (cx - w / 2 - P, cy - 8, cx + w / 2 + P, cy + 8)


ink = erd.label_ink_box(placed(100.0, 100.0), f, S)
print(json.dumps({
    # (1) 규칙: 맞닿은 것은 겹친 것이 아니다 — 양쪽 검사가 이 함수 하나를 쓴다
    'touch_edge': erd.boxes_touch((0, 0, 10, 10), (10, 0, 20, 10)),
    'touch_over': erd.boxes_touch((0, 0, 10, 10), (9.5, 0, 20, 10)),
    # (2) 테두리가 상자에 들어 있는가 — 글자 잉크보다 halo 만큼 넓어야 한다
    'halo_in_box': [ink[0] <= placed(100.0, 100.0)[0] + P - halo + 1e-9,
                    ink[2] >= placed(100.0, 100.0)[2] - P + halo - 1e-9],
    # 글자끼리 테두리 폭보다 가까우면 서로 지운다 — 세어야 한다.
    # (ink 높이 = 글자 높이 + 테두리 절반씩. 중심 거리에서 글자 높이를 빼면 틈이다.)
    'apart_half_halo': erd.boxes_touch(ink, erd.label_ink_box(
        placed(100.0, 100.0 + (ink[3] - ink[1]) - halo), f, S)),
    # 테두리 폭보다 멀면 안 센다 (두 줄로 멀쩡히 읽힌다 — 14라운드가 재 본 자리)
    'apart_two_halo': erd.boxes_touch(ink, erd.label_ink_box(
        placed(100.0, 100.0 + (ink[3] - ink[1]) + halo), f, S)),
}))
'''
    r = subprocess.run([sys.executable, '-c', probe], capture_output=True, text=True, encoding='utf-8',
                       env=e, cwd=str(HERE))
    if r.returncode != 0:
        raise Fail(f'the label rule probe died:\n{r.stdout}\n{r.stderr}')
    got = json.loads(r.stdout.strip().splitlines()[-1])
    eq(got['touch_edge'], False, 'boxes that merely touch do not overlap')
    eq(got['touch_over'], True, 'boxes that really overlap do')
    eq(got['halo_in_box'], [True, True],
       'the measured box must include the background halo the label paints')
    eq(got['apart_half_halo'], True,
       'glyphs closer than one halo erase each other — that must still be counted')
    eq(got['apart_two_halo'], False,
       'and further apart they read as two lines, which is not a defect')

    src = (HERE / 'erd.py').read_text(encoding='utf-8')
    shared = src[src.index('lab_boxes = '):src.index('def thru_nodes')]
    if shared.count('lab_boxes') < 2 or 'boxes_touch' not in shared:
        raise Fail('label↔table and label↔label no longer read the same box list — '
                   'that split is exactly how the round before left one half fixed')
    body = src[src.index('def lab_hits'):src.index('    checks = [')]
    if 'label_ink_box(' in body or 'boxes_touch' not in body:
        raise Fail('lab_hits() builds its own boxes or its own rule again')


# ── 진짜 서버가 있어야만 재는 것 ─────────────────────────────────────────────
# 가짜 psql 은 introspect 의 **판단**은 재현하지만 **조회문**은 재현하지 못한다.
# 행을 코드가 내주므로, SQL 에서 술어 하나를 지워도 같은 행이 돌아온다. 그래서
# 아래 넷은 가짜로는 원리상 못 잡는다 —
#
#   · 유니크 **인덱스**를 가리키는 FK (information_schema 로는 조인에서 통째로 빠진다)
#   · 파티션마다 복제되는 FK (conparentid 술어)  ← 지금 있는 항목은 SQL 문자열만 grep 해서
#     술어를 지우면 잡지만, 그 술어가 PG 10 을 통째로 깨뜨리는 것은 못 본다
#   · 복합 FK 의 자리 짝맞춤 (conkey·confkey 를 ordinality 로 푸는 자리)
#   · 서버 버전마다 달라지는 조회 (q_fk)
#
# docker 가 있을 때만 돈다. **없으면 조용히 통과하지 않는다** — 등록 자체를 하지 않고,
# 아래 main() 이 몇 개를 안 돌렸는지 말한다. '못 재서 깨끗하다' 는 이 저장소가 몇 판째
# 되풀이한 잘못이다.
DOCKER = os.environ.get('ERD_SELFTEST_DOCKER', '').strip()

_FIXTURE = """
create schema app;
create schema hidden;
create table app.devices (id bigint primary key, serial text not null);
create unique index devices_serial_uq on app.devices (serial);
create table app.readings (
  id bigint primary key,
  dev_serial text references app.devices(serial) on delete cascade);
create table app.lines (order_id bigint, line_no int, primary key (order_id, line_no));
create table app.notes (id bigint primary key, o bigint, l int,
  foreign key (o, l) references app.lines(order_id, line_no) on delete cascade);
create table hidden.owners (id bigint primary key, tag text);
create table app.owners (id bigint primary key);
create table app.claims (id bigint primary key,
                         owner_id bigint references hidden.owners(id));
create type app.state as enum ('new', 'done');
create table app.mixed (
  id bigint generated always as identity primary key,
  st app.state, tags text[], amount numeric(12,2), label varchar(30));
comment on table app.devices is 'the things that report';
comment on column app.devices.serial is 'printed on the case';
"""

_FIXTURE_PART = """
create table app.tenants (id bigint primary key);
create table app.events (id bigint, tenant_id bigint references app.tenants(id),
                         at date not null) partition by range (at);
create table app.events_2024 partition of app.events
  for values from ('2024-01-01') to ('2025-01-01');
create table app.events_2025 partition of app.events
  for values from ('2025-01-01') to ('2026-01-01');
"""

_LIVE = {}


def _sh(*argv, **kw):
    import subprocess
    return subprocess.run(argv, capture_output=True, text=True, encoding='utf-8', **kw)


def pg(image, partitions=False):
    """이미지 하나에 서버를 띄우고 시험용 스키마를 넣는다. 한 번 띄우면 재사용한다."""
    import atexit
    import time
    if image in _LIVE:
        # 항목 순서에 기대지 않는다 — 먼저 돈 항목이 파티션 없이 띄웠어도
        # 파티션이 필요한 항목은 그 자리에서 마저 넣는다.
        if partitions and image not in _PARTED:
            _load(_LIVE[image], image, _FIXTURE_PART)
            _PARTED.add(image)
        return _LIVE[image]
    name = 'erd-selftest-' + re.sub(r'\W', '-', image) + f'-{os.getpid()}'
    _sh('docker', 'rm', '-f', name)
    r = _sh('docker', 'run', '-d', '--name', name, '-e', 'POSTGRES_PASSWORD=p',
            '-e', 'POSTGRES_USER=u', '-e', 'POSTGRES_DB=d', image)
    if r.returncode:
        raise Fail(f'could not start {image}: {r.stderr.strip()[:200]}')
    atexit.register(lambda: _sh('docker', 'rm', '-f', name))
    for _ in range(90):
        if _sh('docker', 'exec', name, 'pg_isready', '-U', 'u', '-d', 'd').returncode == 0:
            break
        time.sleep(1)
    else:
        raise Fail(f'{image} never became ready')
    _load(name, image, _FIXTURE)
    _LIVE[image] = name
    if partitions:
        _load(name, image, _FIXTURE_PART)
        _PARTED.add(image)
    return name


_PARTED = set()


def _load(name, image, sql):
    r = _sh('docker', 'exec', '-i', name, 'psql', '-U', 'u', '-d', 'd', '-q',
            '-v', 'ON_ERROR_STOP=1', input=sql)
    if r.returncode:
        raise Fail(f'{image} refused the fixture: {r.stderr.strip()[:300]}')


def introspect_live(work, image, partitions=False, **env):
    e = {'ERD_DB': f'{pg(image, partitions)}:u:d', 'ERD_SCHEMAS': 'app'}
    e.update(env)
    r = run('introspect.py', work, env=e)
    return r, schema_of(work)


def fks_of(s, tkey):
    return sorted((f['column'], f['ref_table'], f['ref_column'], f['on_delete'])
                  for f in s[tkey]['fks'])


def _register_db_cases():
    @case('db: an FK to a column made unique by an index is not lost')
    def _(work):
        # 8라운드. information_schema 로 FK 를 읽으면 부모가 **유니크 제약** 일 때만
        # 잡힌다. CREATE UNIQUE INDEX 로만 유일하게 해 둔 컬럼을 가리키는 FK 는
        # unique_constraint_name 이 NULL 이라 조인에서 통째로 빠졌다 — 관계가 그림에서
        # 소리 없이 사라진다. 유니크 인덱스는 흔한 방식이다.
        #
        # 가짜 psql 로는 못 잡는다. 행을 우리가 내주므로 조회를 information_schema 로
        # 되돌려도 같은 답이 온다. 진짜 서버라야 조인이 실제로 빠진다.
        _r, s = introspect_live(work, DB_NEW)
        eq(fks_of(s, 'readings'), [('dev_serial', 'devices', 'serial', 'CASCADE')],
           'an FK whose parent is unique only by index must still be a relationship')
        eq(s['devices']['uniques'], [['serial']],
           'the standalone unique index is also documented as a unique key')

    @case('db: a composite FK pairs its columns by position')
    def _(work):
        # 3라운드. constraint_name 만으로 이으면 2컬럼짜리 FK 하나가 4개가 되고
        # 그중 둘은 있지도 않은 조합이다. 지금은 conkey·confkey 를 ordinality 로
        # 자리끼리 푼다 — 그 `on f.ord=k.ord` 를 지워도 가짜 psql 은 아무 말이 없다.
        _r, s = introspect_live(work, DB_NEW)
        eq(fks_of(s, 'notes'), [('l', 'lines', 'line_no', 'CASCADE'),
                                ('o', 'lines', 'order_id', 'CASCADE')],
           'two pairs, not the four a cross join invents')

    @case('db: an FK into a schema outside the target is dropped, not rewired')
    def _(work):
        # 9라운드. 부모가 대상 밖 스키마(hidden)면 같은 이름의 **보이는** 테이블
        # (app.owners) 로 갈아탔다 — app.owners 에는 그 컬럼이 아예 없다. 경고도 없었다.
        r, s = introspect_live(work, DB_NEW)
        eq(fks_of(s, 'claims'), [],
           'app.claims → hidden.owners must not become app.claims → app.owners')
        has(r.stdout, 'outside the target: 1', 'and the drop is counted out loud')

    @case('db: a partitioned table reports its FK once, not once per partition')
    def _(work):
        # 9라운드. pg_constraint 는 파티션에 복제된 제약을 그대로 돌려준다 —
        # 파티션 2개면 같은 FK 가 3번 그려지고 표지의 FK 개수도 부풀었다.
        #
        # 지금 있는 항목은 `introspect.Q_FK` 문자열에 'conparentid=0' 이 있는지만 본다.
        # 술어를 지우면 잡지만, **그 술어가 PG 10 이하를 통째로 깨뜨린다는 것**은
        # 못 본다 — 실제로 그렇게 한 라운드가 지나갔다. 진짜 서버로 잰다.
        _r, s = introspect_live(work, DB_NEW, partitions=True)
        eq(fks_of(s, 'events'), [('tenant_id', 'tenants', 'id', 'NO ACTION')],
           'the partitioned parent keeps its one foreign key')
        for part in ('events_2024', 'events_2025'):
            eq(fks_of(s, part), [], f'{part} must not carry a copy of it')

    @case('db: enum, array and identity come back as themselves')
    def _(work):
        # 3라운드. enum·배열이 'USER-DEFINED'·'ARRAY' 로 뭉개지고, GENERATED AS
        # IDENTITY 가 identity 로 안 잡혔다. 타입 정규화는 서버가 하는 일이라
        # 가짜로는 재현되지 않는다 — format_type 이 실제로 무엇을 돌려주는지가 요점이다.
        _r, s = introspect_live(work, DB_NEW)
        eq({c['name']: c['type'] for c in s['mixed']['columns']},
           {'id': 'bigint', 'st': 'app.state', 'tags': 'text[]',
            'amount': 'numeric(12,2)', 'label': 'varchar(30)'},
           'the document names the real type, not two useless words')
        eq([c['identity'] for c in s['mixed']['columns'] if c['name'] == 'id'], [True],
           'GENERATED ALWAYS AS IDENTITY is an identity column')
        eq(s['devices']['note'], 'the things that report', 'COMMENT ON TABLE arrives')
        eq([c['comment'] for c in s['devices']['columns'] if c['name'] == 'serial'],
           ['printed on the case'], 'and COMMENT ON COLUMN too')

    @case('db: a server without conparentid still reports its foreign keys')
    def _(work):
        # 이번 작업분. conparentid 는 PG 11 부터다. 10 이하에 그대로 물으면 FK 조회가
        # 통째로 실패하는데 요약은 그것을 'FK 0' 이라고 참인 양 찍었다 — 관계가 하나도
        # 없는 문서가 exit 0 으로 나왔다. 가짜 psql 도 이 자리를 흉내 내지만, 진짜
        # 10 서버가 그 SQL 을 실제로 받아들이는지는 진짜 10 서버라야 안다.
        _r, s = introspect_live(work, DB_OLD)
        eq(fks_of(s, 'readings'), [('dev_serial', 'devices', 'serial', 'CASCADE')],
           'PostgreSQL 10 must not lose every relationship to a column it does not have')
        eq(fks_of(s, 'notes'), [('l', 'lines', 'line_no', 'CASCADE'),
                                ('o', 'lines', 'order_id', 'CASCADE')],
           'including the composite one')


DB_NEW, DB_OLD = 'postgres:16-alpine', 'postgres:10-alpine'


def _db_case_count():
    """`_register_db_cases()` 안에 `@case` 가 몇 개인지 — 손으로 적지 않는다.

    14라운드. 이 수는 `_DB_CASES = 6` 이라고 손으로 적혀 있었고, 안에서 케이스를
    하나 더하거나 지워도 아무도 몰랐다. '여섯 개는 안 돌렸다' 는 줄은 사용자가
    보는 유일한 안내라, 그 줄의 숫자가 함수와 어긋나면 조용한 거짓말이 된다.
    """
    import inspect
    src = inspect.getsource(_register_db_cases)
    return sum(1 for ln in src.splitlines() if ln.strip().startswith('@case('))


_DB_CASES = _db_case_count()
_DB_RAN = False
if DOCKER and DOCKER.lower() not in ('0', 'no', 'off'):
    if DOCKER not in ('1', 'yes', 'on'):
        DB_NEW = DOCKER.split(',')[0].strip()
        if ',' in DOCKER:
            DB_OLD = DOCKER.split(',')[1].strip()
    _before_db = len(CASES)
    _register_db_cases()
    if len(CASES) - _before_db != _DB_CASES:
        raise RuntimeError(f'_register_db_cases() registered {len(CASES) - _before_db} '
                           f'cases but its source holds {_DB_CASES} @case lines')
    _DB_RAN = True
else:
    # 안 돌린 것을 결과 옆에 적어 둔다. 함께 돌 때도 보여야 한다 — 그러지 않으면
    # `install.sh --check` 를 본 사람은 여섯 개가 있다는 것을 영영 모른다.
    NOTES.append(f'{_DB_CASES} cases need a real server and were NOT run '
                 f'(ERD_SELFTEST_DOCKER=1 runs them against {DB_NEW} and {DB_OLD}).')


@case('selftest: the line that says what was skipped is itself checked')
def _(work):
    # 14라운드. 그 줄을 만드는 `NOTES.append(...)` 를 통째로 지워도 101개가 전부
    # 통과했다 — 줄만 조용히 사라진다. 집계 자체는 정직하다(도커 케이스는 등록이
    # 안 되므로 분모에 안 들어가고, 건너뜀이 통과로 세어지지 않는다). 정직하지 않은
    # 것은 **안 돌렸다는 사실을 말하지 않게 되는 것**이라, 그 말을 여기서 지킨다.
    #
    # 15라운드. 그런데 세는 쪽과 확인하는 쪽이 **같은 함수**를 읽고 있었다.
    # `_db_case_count()` 의 `ln.strip().startswith('@case(')` 에서 `.strip()` 하나만
    # 빼면(줄이 들여쓰여 있으므로) 수가 0 이 되는데, 이 케이스도 그 0 을 읽으니
    # 자기일관이라 초록이었다 — 사용자에게는 `0 cases need a real server and were
    # NOT run` 이 찍힌다. 손으로 적은 `6` 의 문제를 없앤 것이 아니라 **한 겹 안으로
    # 옮긴** 것이다. 그래서 확인하는 쪽은 **다른 근거**를 쓴다: 줄을 훑는 대신
    # 소스를 AST 로 파싱해 `_register_db_cases()` 안의 `@case` 데코레이터를 센다.
    # 두 수가 어긋나면 어느 쪽이 틀렸든 여기서 죽는다.
    import ast
    fn = next((n for n in ast.walk(ast.parse(
                   (HERE / 'selftest_schema.py').read_text(encoding='utf-8')))
               if isinstance(n, ast.FunctionDef) and n.name == '_register_db_cases'), None)
    if fn is None:
        raise Fail('selftest_schema.py no longer defines _register_db_cases()')
    by_ast = sum(1 for n in ast.walk(fn)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n is not fn
                 and any(isinstance(d, ast.Call) and getattr(d.func, 'id', '') == 'case'
                         for d in n.decorator_list))
    if by_ast <= 0:
        raise Fail('no @case lives inside _register_db_cases() — then the line that '
                   'tells the reader "N cases need a real server" is describing nothing')
    eq(_DB_CASES, by_ast,
       'the number the skipped-cases line prints must be read from a different place '
       'than the one that prints it — a counter checked by itself can lie quietly')
    mine = [n for n in NOTES if 'need a real server' in n]
    if _DB_RAN:
        if mine:
            raise Fail(f'the database cases ran, so nothing may claim they did not: '
                       f'{mine}')
        got = sum(1 for n, _f in CASES if n.startswith('db: '))
        eq(got, _DB_CASES, 'and every case the register function holds is on the list')
        return
    eq(len(mine), 1, 'exactly one line tells the reader that some cases did not run')
    # 16라운드. 여기가 `has(mine[0], str(_DB_CASES), …)` 였다 — **부분 문자열**이다.
    # `NOTES.append(f'{_DB_CASES - 5} …')` 로 바꾸면 화면에 `1 cases need a real
    # server` 가 찍히는데도 초록이었다: 같은 줄에 `postgres:16-alpine` 이 있어서
    # 바늘 `'6'` 이 그 16 안에서 찾아졌다. `_DB_CASES` 는 AST 로 지켰는데 **사용자가
    # 읽는 문장**은 아무도 안 지키고 있었다 — 15라운드가 '자기일관적 거짓말' 이라
    # 이름 붙인 결함이 한 겹 바깥에 그대로 남아 있었다. 문장이 말하는 수를 문장에서
    # 도로 뽑아 수로 맞춘다.
    said = re.match(r'\s*(\d+) cases need a real server\b', mine[0])
    if not said:
        raise Fail(f'the skipped-cases line no longer starts with the number of cases '
                   f'it is talking about: {mine[0]!r}')
    eq(int(said.group(1)), _DB_CASES,
       'the number printed in front of the reader is the number of cases that did not '
       'run — a count checked only as a substring is found inside "postgres:16-alpine"')
    for piece in ('ERD_SELFTEST_DOCKER=1', DB_NEW, DB_OLD):
        has(mine[0], piece, 'the skipped-cases line names what it takes to run them')
    if any(n.startswith('db: ') for n, _f in CASES):
        raise Fail('a db case is on the list although no server was asked for — then '
                   'the tally would count a skip as a pass')


# 이 파일이 올리는 케이스 수. 등록이 조용히 반만 되는 자리를 `load_extras()` 가 여기서
# 막는다 — 숫자가 어긋나면 그 자리에서 죽는다. 케이스를 더하면 이 수도 함께 고친다.
BASE_CASES = 58
EXPECT_CASES = BASE_CASES + (_DB_CASES if _DB_RAN else 0)


if __name__ == '__main__':
    sys.exit(main(load_all=False))
