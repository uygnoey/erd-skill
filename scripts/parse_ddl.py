#!/usr/bin/env python3
"""DDL 파서 → schema.json

`$ERD_SQL_DIR` 의 *.sql 에서 CREATE TABLE / ALTER TABLE 을 읽어 테이블·컬럼·타입·
제약·인라인주석·FK 를 구조화한다. **아직 DB 에 적용하지 않은 변경까지 그림에 넣고
싶을 때** 쓴다. 그냥 현재 DB 를 그릴 거라면 introspect.py 만으로 충분하다.

기존 테이블(이미 DB 에 있는 것)은 information_schema 조회 결과를 앞에 붙이고,
DDL 이 추가하는 컬럼을 뒤에 이어 `[추가]` 로 표시한다.

  ERD_SQL_DIR    파싱할 DDL 디렉토리 (기본 $ERD_PROJ/sql)
  ERD_SQL_FILES  읽을 파일을 직접 지정 (콤마 구분, 기본은 디렉토리의 *.sql 전부)
  ERD_REF_SCHEMA 읽기 전용 원천 스키마를 함께 넣을 때 (선택)
  ERD_REF_TABLES 그 스키마에서 가져올 테이블 (콤마 구분, 선택)
  ERD_DEFAULT_PK PK 를 못 찾은 기존 테이블에 가정할 컬럼명 (선택)
"""
import json
import os
import re
import subprocess
from pathlib import Path

from i18n import t as T
from config import SCHEMA_JSON, SEP, SQL_DIR, psql

OUT = SCHEMA_JSON

def sql_files():
    """읽을 DDL 파일 목록. 지정이 없으면 디렉토리의 *.sql 을 이름순으로 전부 읽는다."""
    named = [f.strip() for f in os.environ.get('ERD_SQL_FILES', '').split(',') if f.strip()]
    if named:
        return named
    if not SQL_DIR.is_dir():
        raise SystemExit(T('err.no_sql_dir', path=SQL_DIR))
    return sorted(p.name for p in SQL_DIR.glob('*.sql'))


def split_top_level(body: str):
    """줄 단위로 코드와 주석을 먼저 분리한 뒤, 괄호 깊이를 보며 정의 단위로 묶는다.

    주석 안의 괄호·콤마(-- status (ACTIVE/DEPRECATED) 등)가 분리를 깨뜨리므로
    depth 계산은 반드시 주석을 제거한 코드에서만 한다.
    """
    items, code, comments, depth = [], [], [], 0
    for raw in body.split('\n'):
        line = raw.strip()
        if not line:
            continue
        if line.startswith('--'):          # 독립 주석 줄은 버린다
            continue
        cpos = line.find('--')
        if cpos >= 0:
            comments.append(line[cpos + 2:].strip())
            line = line[:cpos].rstrip()
        if not line:
            continue
        depth += line.count('(') - line.count(')')
        code.append(line)
        if depth <= 0 and line.endswith(','):
            items.append((' '.join(code).rstrip(','), ' '.join(comments)))
            code, comments, depth = [], [], 0
    if code:
        items.append((' '.join(code).rstrip(','), ' '.join(comments)))
    return items


def parse_create(sql: str, src: str, tables: dict):
    for m in re.finditer(r'CREATE TABLE (\w+)\s*\((.*?)\n\);', sql, re.S):
        name, body = m.group(1), m.group(2)
        t = tables.setdefault(name, {
            'name': name, 'origin': 'new', 'src_file': src,
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
        })
        # CREATE TABLE 직전의 ── 주석 헤더를 테이블 설명으로 쓴다
        head = sql[:m.start()].rstrip().split('\n')
        for line in reversed(head[-3:]):
            hm = re.match(r'^--\s*[─\-]*\s*(.+?)\s*[─\-]*\s*$', line.strip())
            if hm and hm.group(1).strip('- '):
                t['note'] = hm.group(1).strip('- ').strip()
                break

        for line, comment in split_top_level(body):
            line = ' '.join(line.split())
            if not line:
                continue
            up = line.upper()
            if up.startswith('CONSTRAINT') or up.startswith('PRIMARY KEY') or up.startswith('FOREIGN KEY'):
                pk = re.search(r'PRIMARY KEY \(([^)]+)\)', line, re.I)
                if pk:
                    t['pk'] = [c.strip() for c in pk.group(1).split(',')]
                fk = re.search(
                    r'FOREIGN KEY \(([^)]+)\)\s*REFERENCES\s+(\w+)\s*\(([^)]+)\)(?:\s*ON DELETE\s+([A-Z ]+))?',
                    line, re.I)
                if fk:
                    t['fks'].append({
                        'column': fk.group(1).strip(),
                        'ref_table': fk.group(2),
                        'ref_column': fk.group(3).strip(),
                        'on_delete': (fk.group(4) or 'NO ACTION').strip(),
                    })
                continue

            col = re.match(r'^(\w+)\s+(.+)$', line)
            if not col:
                continue
            cname, rest = col.group(1), col.group(2).strip()
            typ = re.match(
                r'^((?:varchar|character varying|char|text|bigint|integer|int|smallint|boolean|'
                r'numeric|timestamptz|timestamp with time zone|date|uuid)\s*(?:\([^)]*\))?)',
                rest, re.I)
            t['columns'].append({
                'name': cname,
                'type': (typ.group(1).strip() if typ else rest.split()[0]),
                'not_null': 'NOT NULL' in rest.upper(),
                'default': (re.search(r'DEFAULT\s+([^\s,]+)', rest, re.I).group(1)
                            if re.search(r'DEFAULT\s+', rest, re.I) else ''),
                'identity': 'IDENTITY' in rest.upper(),
                'comment': comment,
                'added': False,
            })


def parse_alter(sql: str, src: str, tables: dict):
    """ALTER TABLE … ADD COLUMN (기존 테이블 확장) / ADD CONSTRAINT … FOREIGN KEY"""
    for m in re.finditer(r'ALTER TABLE (\w+)\s+(ADD COLUMN.*?);', sql, re.S):
        name, body = m.group(1), m.group(2)
        t = tables.setdefault(name, {
            'name': name, 'origin': 'existing', 'src_file': src,
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
        })
        t['altered_by'] = src
        for line, comment in split_top_level(body):
            line = ' '.join(line.split())
            am = re.match(r'ADD COLUMN\s+(\w+)\s+(\S+(?:\([^)]*\))?)(.*)$', line, re.I)
            if not am:
                continue
            rest = ' '.join(am.group(3).split())
            t['columns'].append({
                'name': am.group(1),
                'type': am.group(2).rstrip(','),
                'not_null': 'NOT NULL' in rest.upper(),
                'default': (re.search(r'DEFAULT\s+([^\s,]+)', rest, re.I).group(1)
                            if re.search(r'DEFAULT\s+', rest, re.I) else ''),
                'identity': False,
                'comment': comment,
                'added': True,
            })

    for m in re.finditer(
            r'ALTER TABLE (\w+)\s+ADD CONSTRAINT \w+ FOREIGN KEY \(([^)]+)\)\s*'
            r'REFERENCES\s+(\w+)\s*\(([^)]+)\)(?:\s*ON DELETE\s+([A-Z ]+?))?;', sql, re.S | re.I):
        t = tables.get(m.group(1))
        if t is not None:
            t['fks'].append({
                'column': m.group(2).strip(), 'ref_table': m.group(3),
                'ref_column': m.group(4).strip(),
                'on_delete': (m.group(5) or 'NO ACTION').strip(),
            })


def parse_unique(sql: str, tables: dict):
    for m in re.finditer(r'CREATE UNIQUE INDEX \w+ ON (\w+)\s*\(([^;]+?)\)(\s*WHERE[^;]+)?;', sql, re.S):
        t = tables.get(m.group(1))
        if t is not None:
            cols = ' '.join(m.group(2).split())
            t['uniques'].append({'columns': cols, 'where': ' '.join((m.group(3) or '').split())})


REF_SCHEMA = os.environ.get('ERD_REF_SCHEMA', '')
REF_SOURCES = [t.strip() for t in os.environ.get('ERD_REF_TABLES', '').split(',') if t.strip()]


def fetch_ref(tables):
    """읽기 전용 원천 스키마의 테이블을 가져온다 (FK 없음).

    외부에서 받아 그대로 적재만 하는 원천(참조 어휘·코드 마스터 등)을 그림에 같이
    넣고 싶을 때 쓴다. ERD_REF_SCHEMA 가 없으면 아무것도 하지 않는다.
    """
    if not (REF_SCHEMA and tables):
        return {}
    q = f"""
    select c.table_name, c.column_name,
      case when c.character_maximum_length is not null
             then replace(c.data_type,'character varying','varchar')||'('||c.character_maximum_length||')'
           else c.data_type end,
      c.is_nullable
    from information_schema.columns c
    where c.table_schema='{REF_SCHEMA}' and c.table_name in ({','.join("'"+t+"'" for t in tables)})
    order by c.table_name, c.ordinal_position"""
    out = {}
    for line in psql(q).strip().split('\n'):
        if not line.strip():
            continue
        tn, cn, ty, nul = line.split(SEP)
        out.setdefault(tn, {
            'name': tn, 'origin': 'ref', 'schema': REF_SCHEMA, 'src_file': T('erd.readonly_src', schema=REF_SCHEMA),
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
        })['columns'].append({'name': cn, 'type': ty, 'not_null': nul == 'NO',
                              'default': '', 'identity': False, 'comment': '', 'added': False})
    return out


def fetch_existing(names):
    """이미 DB 에 존재하는 테이블의 실제 컬럼을 가져온다."""
    q = f"""
    select c.table_name, c.column_name,
      case when c.character_maximum_length is not null
             then replace(c.data_type,'character varying','varchar')||'('||c.character_maximum_length||')'
           when c.data_type='numeric' and c.numeric_precision is not null
             then 'numeric('||c.numeric_precision||','||coalesce(c.numeric_scale,0)||')'
           when c.data_type='timestamp with time zone' then 'timestamptz'
           else c.data_type end,
      c.is_nullable
    from information_schema.columns c
    where c.table_schema='public' and c.table_name in ({','.join("'"+n+"'" for n in names)})
    order by c.table_name, c.ordinal_position"""
    out = {}
    for line in psql(q).strip().split('\n'):
        if not line.strip():
            continue
        tn, cn, ty, nul = line.split(SEP)
        out.setdefault(tn, []).append(
            {'name': cn, 'type': ty, 'not_null': nul == 'NO', 'default': '',
             'identity': False, 'comment': '', 'added': False})
    return out


def main():
    tables = {}
    for f in sql_files():
        sql = (SQL_DIR / f).read_text()
        parse_create(sql, f, tables)
        parse_alter(sql, f, tables)
        parse_unique(sql, tables)

    # 기존 테이블: DB 실제 컬럼을 앞에 붙이고, ALTER 로 추가되는 컬럼은 뒤에 유지
    existing_names = [n for n, t in tables.items() if t['origin'] == 'existing']
    # FK 참조 대상 중 신규가 아닌 것도 기존 테이블로 편입
    for t in list(tables.values()):
        for fk in t['fks']:
            rt = fk['ref_table']
            if rt not in tables:
                tables[rt] = {'name': rt, 'origin': 'existing', 'src_file': '',
                              'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': ''}
                existing_names.append(rt)
    db = fetch_existing(sorted(set(existing_names)))
    for n in existing_names:
        if n not in db:
            continue
        added = tables[n]['columns']
        added_names = {c['name'] for c in added}
        base = [c for c in db[n] if c['name'] not in added_names]
        tables[n]['columns'] = base + added
        default_pk = os.environ.get('ERD_DEFAULT_PK', '')
        if not tables[n]['pk'] and default_pk:
            tables[n]['pk'] = [default_pk]

    for t in tables.values():
        t.setdefault('schema', 'public')
    tables.update(fetch_ref(REF_SOURCES))

    Path(OUT).write_text(json.dumps(tables, ensure_ascii=False, indent=2))
    print(T('log.ddl_parsed', n=len(tables), path=OUT))
    for n, t in sorted(tables.items(), key=lambda x: (x[1]['origin'], x[0])):
        added = sum(1 for c in t['columns'] if c['added'])
        print(f"  [{t['origin']:8}] {n:32} "
              + T('log.ddl_row', columns=f"{len(t['columns']):3}",
                       added=(T('log.ddl_added', n=added) if added else '').ljust(12),
                       fks=len(t['fks']), note=t['note'][:40]))


if __name__ == '__main__':
    main()
