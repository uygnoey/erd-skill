#!/usr/bin/env python3
"""DB 인트로스펙션 → schema.json

DDL 파일 없이 **실제 DB만으로** ERD 재료를 만든다. 테이블·컬럼·타입·NOT NULL·기본값·
PK·FK(삭제 규칙 포함)·유니크 인덱스, 그리고 테이블/컬럼 코멘트까지 가져온다.

  ERD_SCHEMAS  대상 스키마 (콤마 구분, 기본 public)
  ERD_LABEL    여러 DB 를 합칠 때 붙일 라벨. 테이블 키가 'l1.orders' 처럼 된다
  ERD_EXCLUDE  제외할 테이블 정규식
  ERD_DB       docker 경유 접속   또는
  ERD_PSQL     psql 명령 직접 지정
"""
import json
import os

from config import EXCLUDE, SCHEMA_JSON, SCHEMAS, SEP, excluded, psql

LABEL = os.environ.get('ERD_LABEL', '')


def key(tname):
    """여러 DB 를 합칠 때 이름이 부딪히므로 라벨로 구분한다."""
    return f'{LABEL}.{tname}' if LABEL else tname

Q_COLUMNS = """
select c.table_schema, c.table_name, c.column_name,
  case when c.character_maximum_length is not null
         then replace(c.data_type,'character varying','varchar')||'('||c.character_maximum_length||')'
       when c.data_type='numeric' and c.numeric_precision is not null
         then 'numeric('||c.numeric_precision||','||coalesce(c.numeric_scale,0)||')'
       when c.data_type='timestamp with time zone' then 'timestamptz'
       when c.data_type='timestamp without time zone' then 'timestamp'
       else c.data_type end,
  c.is_nullable,
  coalesce(c.column_default,''),
  replace(coalesce(col_description((quote_ident(c.table_schema)||'.'||
             quote_ident(c.table_name))::regclass::oid, c.ordinal_position), ''), chr(10), ' ')
from information_schema.columns c
join information_schema.tables t
  on t.table_schema=c.table_schema and t.table_name=c.table_name and t.table_type='BASE TABLE'
where c.table_schema in ({schemas})
order by c.table_schema, c.table_name, c.ordinal_position"""

Q_PK = """
select tc.table_schema, tc.table_name, kcu.column_name
from information_schema.table_constraints tc
join information_schema.key_column_usage kcu
  on kcu.constraint_name=tc.constraint_name and kcu.table_schema=tc.table_schema
where tc.constraint_type='PRIMARY KEY' and tc.table_schema in ({schemas})
order by kcu.ordinal_position"""

Q_FK = """
select tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name,
       coalesce(rc.delete_rule,'NO ACTION')
from information_schema.table_constraints tc
join information_schema.key_column_usage kcu
  on kcu.constraint_name=tc.constraint_name and kcu.table_schema=tc.table_schema
join information_schema.constraint_column_usage ccu
  on ccu.constraint_name=tc.constraint_name
join information_schema.referential_constraints rc
  on rc.constraint_name=tc.constraint_name
where tc.constraint_type='FOREIGN KEY' and tc.table_schema in ({schemas})"""

Q_TABLE_NOTE = """
select t.table_schema, t.table_name,
       replace(coalesce(obj_description((quote_ident(t.table_schema)||'.'||
                  quote_ident(t.table_name))::regclass::oid), ''), chr(10), ' ')
from information_schema.tables t
where t.table_schema in ({schemas}) and t.table_type='BASE TABLE'"""

# ── 아래 넷은 문서용 부가정보 — 없어도 ERD 는 그려진다 (권한이 없으면 조용히 건너뛴다)
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


def rows(query, n):
    """조회 결과를 n개 필드로 맞춰 돌려준다 (모자라면 빈 값으로 채움)."""
    for line in psql(query).strip().split('\n'):
        if not line.strip():
            continue
        f = line.split(SEP)
        yield (f + [''] * n)[:n]


def main():
    schemas = ', '.join(f"'{s}'" for s in SCHEMAS)
    q = lambda tpl: tpl.format(schemas=schemas)
    tables = {}

    for sch, tname, cname, ctype, nullable, default, comment in rows(q(Q_COLUMNS), 7):
        if excluded(tname):
            continue
        t = tables.setdefault(key(tname), {
            'name': tname, 'origin': 'existing', 'db': LABEL,
            'schema': f'{LABEL}.{sch}' if LABEL else sch, 'src_file': 'DB',
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
        })
        t['columns'].append({
            'name': cname, 'type': ctype, 'not_null': nullable == 'NO',
            'default': default, 'identity': 'nextval' in default or 'identity' in default.lower(),
            'comment': comment, 'added': False,
        })
        t.setdefault('rows', None)
        t.setdefault('size', '')
        t.setdefault('indexes', [])
        t.setdefault('checks', [])

    for sch, tname, cname in rows(q(Q_PK), 3):
        if key(tname) in tables:
            tables[key(tname)]['pk'].append(cname)

    for child, col, parent, refcol, rule in rows(q(Q_FK), 5):
        if key(child) in tables:
            tables[key(child)]['fks'].append({
                'column': col, 'ref_table': key(parent), 'ref_column': refcol,
                'on_delete': rule.upper(),
            })

    for sch, tname, note in rows(q(Q_TABLE_NOTE), 3):
        if key(tname) in tables and note:
            tables[key(tname)]['note'] = note

    # ── 문서용 부가정보 — 조회에 실패해도 ERD 생성은 계속한다 ──
    for sch, tname, n_rows, size in rows(q(Q_STATS), 4):
        t = tables.get(key(tname))
        if t:
            t['rows'] = int(n_rows) if n_rows.lstrip('-').isdigit() else None
            t['size'] = size

    for sch, tname, iname, idef in rows(q(Q_INDEX), 4):
        t = tables.get(key(tname))
        if t and idef:
            t['indexes'].append({'name': iname, 'def': idef})

    for sch, tname, cname, cdef in rows(q(Q_CHECK), 4):
        t = tables.get(key(tname))
        if t and cdef:
            t['checks'].append({'name': cname, 'def': cdef})

    for sch, tname, cname, cdef in rows(q(Q_UNIQUE), 4):
        t = tables.get(key(tname))
        if t and cdef:
            cols = cdef[cdef.find('(') + 1:cdef.rfind(')')]
            t['uniques'].append([c.strip() for c in cols.split(',')])

    dropped = 0
    for t in tables.values():                 # 제외된 테이블을 가리키는 FK 는 버린다
        keep = [fk for fk in t['fks'] if fk['ref_table'] in tables]
        dropped += len(t['fks']) - len(keep)
        t['fks'] = keep

    if not tables:
        raise SystemExit('테이블을 하나도 읽지 못했다. ERD_DB / ERD_PSQL / ERD_SCHEMAS 를 확인할 것.')

    out_path = SCHEMA_JSON.with_name(f'schema.{LABEL}.json') if LABEL else SCHEMA_JSON
    out_path.write_text(json.dumps(tables, ensure_ascii=False, indent=2))
    n_col = sum(len(t['columns']) for t in tables.values())
    n_fk = sum(len(t['fks']) for t in tables.values())  # noqa: E501  (dropped 반영 후)
    n_desc = sum(1 for t in tables.values() for c in t['columns'] if c['comment'])
    print(f'테이블 {len(tables)} · 컬럼 {n_col} · FK {n_fk} → {out_path}')
    print(f'  DB 코멘트로 채워진 컬럼 설명 {n_desc}/{n_col}'
          f'{"  → merge_desc.py 로 나머지를 채울 것" if n_desc < n_col else ""}')
    if EXCLUDE:
        print(f'  제외 규칙: {EXCLUDE}')
    if dropped:
        print(f'  대상 밖 테이블을 가리키는 FK {dropped}건 제외')
    for sch in sorted({t['schema'] for t in tables.values()}):
        ts = [n for n, t in tables.items() if t['schema'] == sch]
        print(f'  [{sch}] {len(ts)}개')


if __name__ == '__main__':
    main()
