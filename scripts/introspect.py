#!/usr/bin/env python3
"""DB 인트로스펙션 → schema.json

DDL 파일 없이 **실제 DB만으로** ERD 재료를 만든다. 테이블·컬럼·타입·NOT NULL·기본값·
PK·FK(삭제 규칙 포함)·유니크 인덱스, 그리고 테이블/컬럼 코멘트까지 가져온다.

  ERD_SCHEMAS  대상 스키마 (콤마 구분, 기본 public)
  ERD_LABEL    여러 DB 를 합칠 때 붙일 라벨. 테이블 키가 'l1.orders' 처럼 된다
  ERD_EXCLUDE  제외할 테이블 정규식
  ERD_DB       docker 경유 접속   또는
  ERD_PSQL     psql 명령 직접 지정

PostgreSQL 9.4 이상 (MIN_PG). 9.4·9.6·10·11·12·16·17 에서 같은 결과를 확인했다.
9.3 이하는 서브쿼리 별칭을 row_to_json 의 키로 쓰지 않아 모든 값이 빈 문자열로 오고
FK 조회의 WITH ORDINALITY 도 없다 — 버전을 먼저 보고 낮으면 그 자리에서 멈춘다.
"""
import json
import os

from i18n import t as T
from config import (EXCLUDE, SCHEMA_JSON, SCHEMAS, QueryFailed, clean, excluded,
                    psql_rows)

LABEL = os.environ.get('ERD_LABEL', '')


DUP = set()      # 이름이 두 스키마 이상에 걸쳐 있는 테이블


def key(tname, sch=''):
    """테이블 키.

    이름만으로는 `public.events` 와 `analytics.events` 를 구분하지 못해 둘이 한 테이블로
    합쳐졌었다. 그렇다고 늘 스키마를 붙이면 spec 이 테이블명으로 적혀 있던 기존 문서가
    전부 어긋난다. 그래서 **겹칠 때만** 스키마를 붙인다.
    """
    base = f'{sch}.{tname}' if sch and tname in DUP else tname
    return f'{LABEL}.{base}' if LABEL else base

Q_COLUMNS = """
select c.table_schema, c.table_name, c.column_name,
  case when c.data_type in ('USER-DEFINED','ARRAY')
         then format_type(a.atttypid, a.atttypmod)
       when c.character_maximum_length is not null
         then replace(c.data_type,'character varying','varchar')||'('||c.character_maximum_length||')'
       when c.data_type='numeric' and c.numeric_precision is not null
         then 'numeric('||c.numeric_precision||','||coalesce(c.numeric_scale,0)||')'
       when c.data_type='timestamp with time zone' then 'timestamptz'
       when c.data_type='timestamp without time zone' then 'timestamp'
       else c.data_type end,
  c.is_nullable,
  coalesce(c.column_default,''),
  c.is_identity,
  replace(coalesce(col_description((quote_ident(c.table_schema)||'.'||
             quote_ident(c.table_name))::regclass::oid, c.ordinal_position), ''), chr(10), ' ')
from information_schema.columns c
join information_schema.tables t
  on t.table_schema=c.table_schema and t.table_name=c.table_name and t.table_type='BASE TABLE'
left join pg_attribute a
  on a.attrelid=(quote_ident(c.table_schema)||'.'||quote_ident(c.table_name))::regclass
 and a.attname=c.column_name and a.attnum>0
where c.table_schema in ({schemas})
order by c.table_schema, c.table_name, c.ordinal_position"""

Q_PK = """
select tc.table_schema, tc.table_name, kcu.column_name
from information_schema.table_constraints tc
join information_schema.key_column_usage kcu
  on kcu.constraint_name=tc.constraint_name and kcu.table_schema=tc.table_schema
where tc.constraint_type='PRIMARY KEY' and tc.table_schema in ({schemas})
order by kcu.ordinal_position"""

# FK 는 pg_catalog 에서 읽는다.
#
# information_schema 로 읽으면 부모 쪽이 **유니크 제약** 일 때만 잡힌다.
# CREATE UNIQUE INDEX 로만 유니크를 걸어 둔 컬럼을 가리키는 FK 는
# referential_constraints.unique_constraint_name 이 NULL 이라 조인에서 통째로 빠진다 —
# 관계가 그림에서 소리 없이 사라졌다. 유니크 인덱스는 흔한 방식이다.
#
# conkey·confkey 를 자리끼리 풀어 복합 FK 도 자리로 짝짓는다.
#
# conparentid=0: 파티션 테이블의 FK 는 파티션마다 복제본이 생긴다(conparentid 가
# 원본을 가리킨다). 안 거르면 파티션 2개짜리 테이블이 같은 FK 를 세 번 그린다.
Q_FK = """
select cs.nspname, cl.relname, ca.attname,
       ps.nspname, pl.relname, pa.attname,
       case con.confdeltype when 'c' then 'CASCADE' when 'n' then 'SET NULL'
            when 'r' then 'RESTRICT' when 'd' then 'SET DEFAULT' else 'NO ACTION' end
from pg_constraint con
join pg_class cl on cl.oid=con.conrelid
join pg_namespace cs on cs.oid=cl.relnamespace
join pg_class pl on pl.oid=con.confrelid
join pg_namespace ps on ps.oid=pl.relnamespace
join lateral unnest(con.conkey) with ordinality as k(attnum, ord) on true
join lateral unnest(con.confkey) with ordinality as f(attnum, ord) on f.ord=k.ord
join pg_attribute ca on ca.attrelid=con.conrelid and ca.attnum=k.attnum
join pg_attribute pa on pa.attrelid=con.confrelid and pa.attnum=f.attnum
where con.contype='f' and con.conparentid=0 and cs.nspname in ({schemas})
order by cs.nspname, cl.relname, con.conname, k.ord"""

Q_TABLE_NOTE = """
select t.table_schema, t.table_name,
       replace(coalesce(obj_description((quote_ident(t.table_schema)||'.'||
                  quote_ident(t.table_name))::regclass::oid), ''), chr(10), ' ')
from information_schema.tables t
where t.table_schema in ({schemas}) and t.table_type='BASE TABLE'"""

# ── 아래 넷은 문서용 부가정보 — 없어도 ERD 는 그려진다 (실패하면 이름을 대고 넘어간다)
Q_STATS = """
select n.nspname, c.relname, greatest(c.reltuples,0)::bigint,
       pg_size_pretty(pg_total_relation_size(c.oid))
from pg_class c join pg_namespace n on n.oid=c.relnamespace
where c.relkind='r' and n.nspname in ({schemas})"""

Q_INDEX = """
select schemaname, tablename, indexname, indexdef
from pg_indexes where schemaname in ({schemas})
order by tablename, indexname"""

Q_CHECK = """
select n.nspname, rel.relname, con.conname,
       replace(pg_get_constraintdef(con.oid), chr(10), ' ')
from pg_constraint con
join pg_class rel on rel.oid=con.conrelid
join pg_namespace n on n.oid=rel.relnamespace
where con.contype='c' and n.nspname in ({schemas})
order by rel.relname, con.conname"""

Q_UNIQUE = """
select n.nspname, rel.relname, con.conname,
       replace(pg_get_constraintdef(con.oid), chr(10), ' ')
from pg_constraint con
join pg_class rel on rel.oid=con.conrelid
join pg_namespace n on n.oid=rel.relnamespace
where con.contype='u' and n.nspname in ({schemas})
order by rel.relname, con.conname"""


def q_fk(ver):
    """서버 버전에 맞춘 FK 조회.

    conparentid 는 PG 11 에서 생긴 컬럼이다. 10 이하에 그대로 보내면 조회가 통째로
    실패해 FK 가 하나도 안 잡히는데, 요약은 그것을 'FK 0' 이라고 참인 양 찍었다.
    10 이하에는 파티션마다 복제되는 FK 자체가 없으므로(파티션 FK 는 11 부터다)
    술어를 빼면 그만이다 — 거를 것이 없어서 거르지 않는 것이다.
    """
    return Q_FK if ver >= 110000 else Q_FK.replace('con.conparentid=0 and ', '')


MIN_PG = 90400        # PostgreSQL 9.4 — WITH ORDINALITY 와 별칭이 붙는 row_to_json 의 하한
MIN_PG_TEXT = '9.4'

SKIPPED = []          # 끝까지 읽지 못한 부가 조회 이름


def rows(what, query, n, core=True):
    """조회 하나를 읽는다. 핵심 조회가 실패하면 문서를 만들지 않고 멈춘다.

    일곱 조회 중 여섯만 성공해도 예전엔 완성본처럼 나왔다 — Q_PK 하나가 죽으면 모든
    테이블의 pk 가 []  인 문서가 요약도 멀쩡하게, exit 0 으로 나왔다. 못 읽은 것은
    비어 있는 것과 다르다. 핵심(컬럼·PK·FK·코멘트)은 멈추고, 없어도 그림이 나오는
    부가정보는 무엇이 빠졌는지 이름을 대고 넘어간다.
    """
    try:
        return psql_rows(query, n)
    except QueryFailed as e:
        if core:
            raise SystemExit(T('err.query_failed', what=what, err=e))
        SKIPPED.append(what)
        return []


def server_version():
    """서버 버전을 (보여 줄 문자열, 비교할 숫자) 로.

    9.3 이하는 서브쿼리 별칭을 row_to_json 의 키로 쓰지 않아 어떤 값도 이름으로 꺼내지
    못한다 — 버전 숫자마저 빈 문자열로 온다. int() 가 traceback 을 뱉게 두지 않고,
    그것 자체를 '너무 낮다' 는 답으로 읽는다.
    """
    v = rows('server version',
             "select current_setting('server_version'), "
             "current_setting('server_version_num')", 2)
    if not v:
        raise SystemExit(T('err.query_failed', what='server version', err='no row'))
    if not v[0][1].isdigit():
        raise SystemExit(T('err.pg_too_old', found=v[0][0] or '?', need=MIN_PG_TEXT))
    return v[0][0], int(v[0][1])


def main():
    schemas = ', '.join(f"'{s}'" for s in SCHEMAS)
    q = lambda tpl: tpl.format(schemas=schemas)
    tables = {}

    # 버전을 먼저 본다 — 조회문이 서버마다 다르고(q_fk), 너무 낮으면 무엇을 물어도
    # 반쯤만 답이 온다. 반쯤 온 답을 문서로 만드는 것보다 여기서 멈추는 편이 낫다.
    ver_text, ver = server_version()
    if ver < MIN_PG:
        raise SystemExit(T('err.pg_too_old', found=ver_text, need=MIN_PG_TEXT))

    # 컬럼을 먼저 다 읽어 이름이 겹치는 테이블을 가려낸다 — 키를 정한 뒤라야
    # PK·FK·인덱스를 제 테이블에 붙일 수 있다.
    cols = [r for r in rows('columns', q(Q_COLUMNS), 8) if not excluded(r[1])]
    by_name = {}
    for sch, tname, *_ in cols:
        by_name.setdefault(tname, set()).add(sch)
    DUP.update(n for n, schs in by_name.items() if len(schs) > 1)

    for sch, tname, cname, ctype, nullable, default, identity, comment in cols:
        t = tables.setdefault(key(tname, sch), {
            'name': tname, 'origin': 'existing', 'db': LABEL,
            'schema': f'{LABEL}.{sch}' if LABEL else sch, 'src_file': 'DB',
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
        })
        t['columns'].append({
            'name': cname, 'type': ctype, 'not_null': nullable == 'NO',
            'default': default,
            # GENERATED … AS IDENTITY 는 기본값이 비어 있다 — is_identity 를 같이 본다
            'identity': identity == 'YES' or 'nextval' in default,
            'comment': clean(comment), 'added': False,
        })
        t.setdefault('rows', None)
        t.setdefault('size', '')
        t.setdefault('indexes', [])
        t.setdefault('checks', [])

    for sch, tname, cname in rows('primary keys', q(Q_PK), 3):
        if key(tname, sch) in tables:
            tables[key(tname, sch)]['pk'].append(cname)

    # FK 부모는 실제로 읽어 온 테이블에서 (스키마, 이름) 으로 찾는다. pg_catalog 는
    # 목록 밖·권한 밖 스키마의 제약도 돌려주는데, key() 는 DUP 에 없는 이름에
    # 스키마를 안 붙여 보이지 않는 부모가 같은 이름의 다른 테이블로 둔갑했다 —
    # 없는 관계가 그려졌다. 못 찾으면 버리고 센다.
    real = {(sch, tname): key(tname, sch) for sch, tname, *_ in cols}
    dropped = 0
    for csch, child, col, psch, parent, refcol, rule in rows('foreign keys', q(q_fk(ver)), 7):
        ck, pk = real.get((csch, child)), real.get((psch, parent))
        if ck is None:
            continue
        if pk is None:
            dropped += 1
            continue
        tables[ck]['fks'].append({
            'column': col, 'ref_table': pk, 'ref_column': refcol,
            'on_delete': rule.upper(),
        })

    for sch, tname, note in rows('table comments', q(Q_TABLE_NOTE), 3):
        if key(tname, sch) in tables and note:
            tables[key(tname, sch)]['note'] = clean(note)

    # ── 문서용 부가정보 — 조회에 실패해도 ERD 생성은 계속한다 ──
    for sch, tname, n_rows, size in rows('row counts and sizes', q(Q_STATS), 4, core=False):
        t = tables.get(key(tname, sch))
        if t:
            t['rows'] = int(n_rows) if n_rows.lstrip('-').isdigit() else None
            t['size'] = size

    for sch, tname, iname, idef in rows('indexes', q(Q_INDEX), 4, core=False):
        t = tables.get(key(tname, sch))
        if t and idef:
            t['indexes'].append({'name': iname, 'def': idef})

    for sch, tname, cname, cdef in rows('check constraints', q(Q_CHECK), 4, core=False):
        t = tables.get(key(tname, sch))
        if t and cdef:
            t['checks'].append({'name': cname, 'def': cdef})

    for sch, tname, cname, cdef in rows('unique constraints', q(Q_UNIQUE), 4, core=False):
        t = tables.get(key(tname, sch))
        if t and cdef:
            cols = cdef[cdef.find('(') + 1:cdef.rfind(')')]
            t['uniques'].append([c.strip() for c in cols.split(',')])

    for t in tables.values():                 # 제외된 테이블을 가리키는 FK 는 버린다
        keep = [fk for fk in t['fks'] if fk['ref_table'] in tables]
        dropped += len(t['fks']) - len(keep)
        t['fks'] = keep

    if not tables:
        raise SystemExit(T('err.no_tables'))

    out_path = SCHEMA_JSON.with_name(f'schema.{LABEL}.json') if LABEL else SCHEMA_JSON
    out_path.write_text(json.dumps(tables, ensure_ascii=False, indent=2))
    n_col = sum(len(t['columns']) for t in tables.values())
    n_fk = sum(len(t['fks']) for t in tables.values())  # noqa: E501  (dropped 반영 후)
    n_desc = sum(1 for t in tables.values() for c in t['columns'] if c['comment'])
    print(T('log.introspected', tables=len(tables), columns=n_col, fks=n_fk,
            path=out_path))
    print(T('log.desc_from_db', n=n_desc, total=n_col)
          + (T('log.desc_rest') if n_desc < n_col else ''))
    if DUP:
        print(T('log.dup_names', n=len(DUP), list=', '.join(sorted(DUP)[:6])))
    if EXCLUDE:
        print(T('log.exclude_rule', rule=EXCLUDE))
    if dropped:
        print(T('log.fk_dropped', n=dropped))
    if SKIPPED:                # 빠진 것은 요약에서도 이름을 댄다 — 없는 것과 다르다
        print(T('log.query_incomplete', list=', '.join(SKIPPED)))
    for sch in sorted({tb['schema'] for tb in tables.values()}):
        ts = [n for n, tb in tables.items() if tb['schema'] == sch]
        print(T('log.per_schema', schema=sch, n=len(ts)))


if __name__ == '__main__':
    main()
