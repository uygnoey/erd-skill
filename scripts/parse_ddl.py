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


def mask(sql):
    """가린 사본 셋을 만든다 — (문자열만, 주석만, 둘 다).

      ms   문자열·달러인용을 가린 것   → 주석이 어디서 시작하는지 찾을 때
      mc   주석을 가린 것              → 값(타입·기본값)을 꺼낼 때
      msc  둘 다 가린 것               → 괄호·콤마·키워드를 볼 때

    괄호 세기·콤마 나누기·키워드 찾기는 전부 가린 사본 위에서 하고, 값이 필요하면
    같은 위치를 원본에서 꺼낸다. 정규식마다 따로 문자열을 피하려 들면 반드시 샌다 —
    `DEFAULT '('` 하나에 다음 컬럼이 통째로 사라졌고, 문자열 안의 `--` 에 그 뒤
    컬럼이 사라졌다. 함수 본문($$…$$) 안의 CREATE TABLE 이 유령 테이블로 잡히기도 했다.

    가린 자리는 같은 길이의 공백이라 위치가 원본과 그대로 맞는다.
    """
    ms, mc, msc = list(sql), list(sql), list(sql)
    i, n = 0, len(sql)
    dollar = re.compile(r'\$([A-Za-z_]\w*)?\$')
    while i < n:
        c = sql[i]
        if c == "'":                                  # 문자열 리터럴
            # 바로 앞이 E 면 백슬래시 이스케이프가 산다 — E'it\'s' 를 여기서 끊으면
            # 그 뒤가 전부 어긋나 테이블 하나가 통째로 사라졌다.
            esc = i and sql[i - 1] in 'eE' and (i < 2 or not sql[i - 2].isalnum())
            j = i + 1
            while j < n:
                if esc and sql[j] == '\\':
                    j += 2
                    continue
                if sql[j] == "'":
                    if j + 1 < n and sql[j + 1] == "'":
                        j += 2
                        continue
                    break
                j += 1
            j = min(j, n - 1)
            for k in range(i, j + 1):
                ms[k] = msc[k] = ' '
            i = j + 1
        elif c == '$' and dollar.match(sql, i):       # $$ … $$ 와 $tag$ … $tag$
            tag = dollar.match(sql, i).group(0)
            j = sql.find(tag, i + len(tag))
            j = n if j < 0 else j + len(tag)
            for k in range(i, j):
                ms[k] = msc[k] = ' '
            i = j
        elif sql.startswith('--', i):                 # 줄 주석 — 설명으로 쓰므로 ms 엔 남긴다
            j = sql.find('\n', i)
            j = n if j < 0 else j
            for k in range(i, j):
                mc[k] = msc[k] = ' '
            i = j
        elif sql.startswith('/*', i):                 # 블록 주석 — 중첩된다
            depth, j = 1, i + 2
            while j < n and depth:
                if sql.startswith('/*', j):
                    depth += 1
                    j += 2
                elif sql.startswith('*/', j):
                    depth -= 1
                    j += 2
                else:
                    j += 1
            for k in range(i, j):
                mc[k] = msc[k] = ' '
            i = j
        else:
            i += 1
    return ''.join(ms), ''.join(mc), ''.join(msc)


def split_top_level(body_mc: str, body_ms: str, body_sc: str):
    """최상위 콤마로 항목을 나눈다 → [(코드, 주석), …]

    줄 단위가 아니라 콤마 단위다. 한 줄에 다 적은 정의도 제대로 나뉜다.
    """
    cuts, depth = [0], 0
    for i, c in enumerate(body_sc):
        if c == '(':
            depth += 1
        elif c == ')':
            depth -= 1
        elif c == ',' and depth == 0:
            cuts.append(i + 1)
    cuts.append(len(body_sc) + 1)

    items = []
    for a, b in zip(cuts, cuts[1:]):
        raw, code = body_mc[a:b - 1], body_sc[a:b - 1]
        # 주석의 '위치' 는 문자열을 가린 사본에서 찾는다. 원본을 그대로 뒤지면
        # DEFAULT '--none--' 같은 값이 주석으로 둔갑한다.
        notes = [raw[mm.start() + 2:mm.end()]
                 for mm in re.finditer(r'--[^\n]*', body_ms[a:b - 1])]
        note = ' '.join(x.strip() for x in notes if x.strip())
        # 값(타입·기본값)은 주석만 가린 사본에서, 구조 판정은 둘 다 가린 사본에서.
        raw_code = ' '.join(raw.split())
        code = ' '.join(code.split())
        if code:
            items.append((raw_code, code, note))
    return items


# 컬럼이 아니라 테이블 전체에 걸리는 것들. 예전엔 CHECK·UNIQUE·LIKE 가 이름이
# 'CHECK' 인 가짜 컬럼으로 문서에 실렸다.
_TABLE_LEVEL = re.compile(
    r'(?:CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|EXCLUDE|LIKE|INHERITS|'
    r'PARTITION)\b', re.I)
_ON_DELETE = r'ON\s+DELETE\s+(CASCADE|RESTRICT|SET\s+NULL|SET\s+DEFAULT|NO\s+ACTION)'


def _refs(code):
    """REFERENCES … 한 건 → (부모스키마, 부모, [부모컬럼…], 삭제규칙). 없으면 None.

    부모 컬럼을 하나만 받던 때는 복합 FK 의 두 컬럼이 모두 'id' 를 가리키는 것으로
    적혀, 있지도 않은 관계가 문서에 실렸다. introspect 는 자리끼리 짝짓는다.

    삭제 규칙은 낱말을 못박아 읽는다. `[A-Z ]+` 로 긁던 예전 방식은
    `ON DELETE CASCADE ON UPDATE CASCADE` 를 'CASCADE ON' 으로 만들어 문서에 실었다.
    """
    m = re.search(r'\bREFERENCES\s+(?:"?(\w+)"?\s*\.\s*)?"?(\w+)"?\s*(?:\(([^)]*)\))?',
                  code, re.I)
    if not m:
        return None
    cols = [c.strip().strip('"') for c in (m.group(3) or '').split(',') if c.strip()]
    rule = re.search(_ON_DELETE, code[m.end():], re.I)
    return (m.group(1), m.group(2), cols or ['id'],
            ' '.join((rule.group(1) if rule else 'NO ACTION').split()).upper())


_TYPE_HEAD = re.compile(
    r'^(character\s+varying|character|bit\s+varying|double\s+precision|'
    r'timestamp\s+with\s+time\s+zone|timestamp\s+without\s+time\s+zone|'
    r'time\s+with\s+time\s+zone|time\s+without\s+time\s+zone|'
    r'[A-Za-z_][\w]*(?:\s*\.\s*[A-Za-z_][\w]*)?)'
    r'(\s*\([^)]*\))?((?:\s*\[\s*\d*\s*\])*)', re.I)


def _type(rest):
    """컬럼 타입을 introspect 와 같은 이름으로 정규화한다.

    pg_dump 는 varchar 를 언제나 `character varying(255)` 로 쓴다. 낱말 하나만 떼던
    예전 코드는 이걸 'character' 로 만들어, 길이도 잃고 DB 를 직접 읽은 결과와도
    달라졌다 — 문서의 타입 칸이 통째로 틀렸다.
    """
    m = _TYPE_HEAD.match(rest.strip())
    if not m:
        return rest.split()[0] if rest.split() else ''
    base = ' '.join(m.group(1).split()).lower()
    args, arr = (m.group(2) or '').strip(), (m.group(3) or '').replace(' ', '')
    named = {'character varying': 'varchar',
             'timestamp with time zone': 'timestamptz',
             'timestamp without time zone': 'timestamp',
             'time with time zone': 'timetz',
             'time without time zone': 'time',
             'double precision': 'double precision'}
    if base in named:
        base = named[base]
        if base in ('timestamptz', 'timestamp', 'timetz', 'time'):
            args = ''                       # timestamp(6) 의 정밀도는 introspect 도 안 쓴다
    elif base == 'character' and args:
        base = 'char'
    return base + args + arr


def _ref_key(ref, own_schema, dup):
    """FK 가 가리키는 테이블의 키. 이름이 여러 스키마에 걸칠 때만 스키마를 붙인다."""
    rsch, rname = ref[0] or own_schema, ref[1]
    return f'{rsch}.{rname}' if rname in dup else rname


def parse_create(sql: str, src: str, tables: dict, dup: set):
    ms, mc, msc = mask(sql)
    head_pat = re.compile(r'CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+'
                          r'(?:IF\s+NOT\s+EXISTS\s+)?'
                          r'(?:"?(\w+)"?\s*\.\s*)?"?(\w+)"?\s*\(', re.I)
    for m in head_pat.finditer(msc):
        sch, name = m.group(1) or 'public', m.group(2)
        i, depth = m.end(), 1                     # 괄호 짝으로 본문을 자른다
        while i < len(msc) and depth:
            if msc[i] == '(':
                depth += 1
            elif msc[i] == ')':
                depth -= 1
                if not depth:
                    break
            i += 1
        if depth:
            continue                              # 안 닫혔다 — 잘린 파일
        body_mc, body_ms, body_sc = mc[m.end():i], ms[m.end():i], msc[m.end():i]
        key = f'{sch}.{name}' if name in dup else name
        t = tables.setdefault(key, {
            'name': name, 'origin': 'new', 'src_file': src, 'schema': sch,
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
        })
        # CREATE TABLE 바로 앞의 ── 헤더 주석을 테이블 설명으로 쓴다. 단 pg_dump 가
        # 붙이는 구조 헤더(Name: …; Type: TABLE; …)는 설명이 아니다.
        head = sql[:m.start()].rstrip().split('\n')
        for line in reversed(head[-3:]):
            hm = re.match(r'^--\s*[─\-]*\s*(.+?)\s*[─\-]*\s*$', line.strip())
            if hm and hm.group(1).strip('- ') and not re.search(r'Type:\s*TABLE', hm.group(1)):
                t['note'] = hm.group(1).strip('- ').strip()
                break

        for raw_code, code, comment in split_top_level(body_mc, body_ms, body_sc):
            up = code.upper()
            if _TABLE_LEVEL.match(code):
                pk = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', code, re.I)
                if pk:
                    t['pk'] = [c.strip().strip('"') for c in pk.group(1).split(',')]
                fk = re.search(r'FOREIGN\s+KEY\s*\(([^)]+)\)', code, re.I)
                ref = _refs(code)
                if fk and ref:
                    rt = _ref_key(ref, sch, dup)
                    kids = [c.strip().strip('"') for c in fk.group(1).split(',')]
                    for idx, c in enumerate(kids):
                        t['fks'].append({
                            'column': c, 'ref_table': rt,
                            'ref_column': ref[2][idx] if idx < len(ref[2]) else ref[2][-1],
                            'on_delete': ref[3]})
                uq = re.match(r'(?:CONSTRAINT\s+"?\w+"?\s+)?UNIQUE\s*\(([^)]+)\)', code, re.I)
                if uq:
                    t['uniques'].append([c.strip().strip('"') for c in uq.group(1).split(',')])
                continue

            col = re.match(r'^"?(\w+)"?\s+(.+)$', raw_code)  # 따옴표 친 컬럼명도 받는다
            if not col:
                continue
            cname, rest = col.group(1), col.group(2).strip()
            # 구조 판정(NOT NULL·PRIMARY KEY·REFERENCES)은 반드시 가린 사본에서 한다.
            # 원본에서 보면 DEFAULT 'PRIMARY KEY 설명' 같은 값이 진짜 제약이 된다.
            col_sc = re.match(r'^"?\w+"?\s+(.+)$', code)
            rest_sc = col_sc.group(1).strip() if col_sc else ''

            up_rest = rest_sc.upper()
            dflt = re.search(r'DEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL|PRIMARY|UNIQUE|'
                             r'REFERENCES|CHECK|GENERATED|COLLATE)\b|$)', rest, re.I)
            t['columns'].append({
                'name': cname,
                'type': _type(rest),
                # IDENTITY·serial 은 NOT NULL 을 적지 않아도 NOT NULL 이다
                'not_null': ('NOT NULL' in up_rest or 'IDENTITY' in up_rest
                             or 'SERIAL' in up_rest),
                'default': dflt.group(1).strip().rstrip(',') if dflt else '',
                'identity': 'IDENTITY' in up_rest or 'SERIAL' in up_rest,
                'comment': comment,
                'added': False,
            })
            if re.search(r'\bPRIMARY\s+KEY\b', rest_sc, re.I):
                t['pk'].append(cname)
            if re.search(r'\bUNIQUE\b', rest_sc, re.I):
                t['uniques'].append([cname])
            ref = _refs(rest_sc)
            if ref:
                t['fks'].append({'column': cname, 'ref_table': _ref_key(ref, sch, dup),
                                 'ref_column': ref[2][0], 'on_delete': ref[3]})


def parse_alter(sql: str, src: str, tables: dict, dup: set):
    r"""ALTER TABLE … ADD COLUMN / ADD CONSTRAINT.

    pg_dump 는 제약을 전부 `ALTER TABLE ONLY public.t ADD CONSTRAINT …` 로 내놓는다.
    `ALTER TABLE (\w+)` 만 보던 예전 코드는 ONLY 도 스키마도 못 넘어, pg_dump 로 뽑은
    DDL 에서는 PK 와 FK 가 하나도 잡히지 않았다.
    """
    ms, mc, msc = mask(sql)
    head = r'ALTER\s+TABLE\s+(?:ONLY\s+)?(?:"?(\w+)"?\s*\.\s*)?"?(\w+)"?\s+'

    def find(sch, name):
        """스키마까지 보고 찾는다.

        스키마를 버리고 이름만으로 찾던 때는 `ALTER TABLE ONLY public.orders` 가
        mart.orders 에 붙었다 — pg_dump 가 mart 를 먼저 내놓기 때문이다. 그 결과
        public 의 FK 와 PK 가 통째로 남의 테이블에 실렸다.
        """
        if sch and f'{sch}.{name}' in tables:
            return tables[f'{sch}.{name}']
        if name in tables and (not sch or tables[name].get('schema') == sch):
            return tables[name]
        if not sch:
            return tables.get(name) or next(
                (tables[k] for k in tables if k.endswith('.' + name)), None)
        return None

    for m in re.finditer(head + r'(ADD\s+COLUMN\b.*?);', msc, re.S | re.I):
        sch, name = m.group(1), m.group(2)
        t = find(sch, name)
        if t is None:
            key = f'{sch}.{name}' if sch and name in dup else name
            t = tables.setdefault(key, {
                'name': name, 'origin': 'existing', 'src_file': src,
                'schema': sch or 'public',
                'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
            })
        t['altered_by'] = src
        for raw_code, code, comment in split_top_level(mc[m.start(3):m.end(3)],
                                                       ms[m.start(3):m.end(3)],
                                                       msc[m.start(3):m.end(3)]):
            am = re.match(r'ADD\s+COLUMN\s+"?(\w+)"?\s+(.+)$', raw_code, re.I)
            if not am:
                continue
            rest = am.group(2).strip()
            t['columns'].append({
                'name': am.group(1),
                'type': _type(rest),
                'not_null': 'NOT NULL' in rest.upper(),
                'default': (re.search(r'DEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL)\b|$)',
                                      rest, re.I).group(1).strip().rstrip(',')
                            if re.search(r'DEFAULT\s+', rest, re.I) else ''),
                'identity': 'IDENTITY' in rest.upper(),
                'comment': comment,
                'added': True,
            })

    for m in re.finditer(head + r'ADD\s+CONSTRAINT\s+"?\w+"?\s+(.*?);', msc, re.S | re.I):
        t = find(m.group(1), m.group(2))
        if t is None:
            continue
        code = ' '.join(sql[m.start(3):m.end(3)].split())
        pk = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', code, re.I)
        if pk:
            t['pk'] = [c.strip().strip('"') for c in pk.group(1).split(',')]
        fk = re.search(r'FOREIGN\s+KEY\s*\(([^)]+)\)', code, re.I)
        ref = _refs(code)
        if fk and ref:
            rt = _ref_key(ref, t.get('schema', 'public'), dup)
            kids = [c.strip().strip('"') for c in fk.group(1).split(',')]
            for idx, c in enumerate(kids):
                t['fks'].append({
                    'column': c, 'ref_table': rt,
                    'ref_column': ref[2][idx] if idx < len(ref[2]) else ref[2][-1],
                    'on_delete': ref[3]})
        uq = re.match(r'UNIQUE\s*\(([^)]+)\)', code, re.I)
        if uq:
            t['uniques'].append([c.strip().strip('"') for c in uq.group(1).split(',')])

    # pg_dump 는 IDENTITY 를 별도 문으로 내고, serial 은 시퀀스 기본값으로 푼다.
    # 둘 다 여기서 되살리지 않으면 DB 를 직접 읽은 결과와 어긋난다.
    for m in re.finditer(head + r'ALTER\s+COLUMN\s+"?(\w+)"?\s+'
                         r'(?:ADD\s+GENERATED\b|SET\s+DEFAULT\s+nextval)',
                         msc, re.S | re.I):
        t = find(m.group(1), m.group(2))
        if t:
            for c in t['columns']:
                if c['name'] == m.group(3):
                    c['identity'] = c['not_null'] = True


def parse_comments(sql: str, tables: dict):
    """COMMENT ON TABLE/COLUMN — pg_dump 가 설명을 싣는 유일한 자리다.

    이름 조각을 먼저 다 받아 두고 개수로 갈라 읽는다. 스키마 자리를 선택 그룹으로
    두었더니 `COMMENT ON COLUMN users.email` 에서 users 를 스키마로 먹어 버려 손으로
    쓴 DDL 의 컬럼 설명이 전부 사라졌다.
    """
    _ms, _mc, msc = mask(sql)

    def find(sch, name):
        if sch and f'{sch}.{name}' in tables:
            return tables[f'{sch}.{name}']
        if name in tables and (not sch or tables[name].get('schema') == sch):
            return tables[name]
        if not sch:
            return tables.get(name) or next(
                (tables[k] for k in tables if k.endswith('.' + name)), None)
        return None

    for m in re.finditer(r'COMMENT\s+ON\s+(TABLE|COLUMN)\s+'
                         r'((?:"?\w+"?\s*\.\s*){0,2}"?\w+"?)\s+IS\b', msc, re.I):
        lit = re.match(r"\s*'((?:[^']|'')*)'", sql[m.end():])
        if not lit:
            continue
        text = lit.group(1).replace("''", "'")
        parts = [x.strip().strip('"') for x in m.group(2).split('.')]
        is_col = m.group(1).upper() == 'COLUMN'
        col = parts.pop() if is_col else None
        name = parts.pop() if parts else None
        sch = parts.pop() if parts else None
        if name is None:
            continue
        t = find(sch, name)
        if t is None:
            continue
        if is_col:
            for c in t['columns']:
                if c['name'] == col:
                    c['comment'] = text
        else:
            t['note'] = text


def parse_unique(sql: str, tables: dict):
    """CREATE UNIQUE INDEX → uniques.

    introspect 와 같은 '컬럼 이름 목록' 형식이어야 한다. dict 로 넣던 때는 HTML 이
    그 키를 이어 붙여 `UNIQUE (columns, where)` 라고 찍었다.
    """
    _ms, _mc, msc = mask(sql)
    for m in re.finditer(r'CREATE\s+UNIQUE\s+INDEX\s+(?:CONCURRENTLY\s+)?'
                         r'(?:IF\s+NOT\s+EXISTS\s+)?"?\w+"?\s+ON\s+(?:ONLY\s+)?'
                         r'(?:"?\w+"?\s*\.\s*)?"?(\w+)"?'
                         r'(?:\s+USING\s+\w+)?\s*\(([^)]+)\)', msc, re.I):
        t = next((tables[k] for k in tables
                  if k == m.group(1) or k.endswith('.' + m.group(1))), None)
        cols = [c.strip().strip('"') for c in m.group(2).split(',')]
        if t is not None and not any('(' in c for c in cols):
            t['uniques'].append(cols)      # 함수 인덱스(lower(email))는 컬럼 목록이 아니다


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
    files = [(f, (SQL_DIR / f).read_text()) for f in sql_files()]

    # 이름이 두 스키마에 걸치면 키에 스키마를 붙인다 (introspect 와 같은 규칙).
    # 예전엔 shop.orders 와 mart.orders 가 한 테이블로 합쳐져 컬럼이 뒤섞였다.
    seen = {}
    head = re.compile(r'CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+'
                      r'(?:IF\s+NOT\s+EXISTS\s+)?'
                      r'(?:"?(\w+)"?\s*\.\s*)?"?(\w+)"?\s*\(', re.I)
    for _f, sql in files:
        for m in head.finditer(mask(sql)[2]):
            seen.setdefault(m.group(2), set()).add(m.group(1) or 'public')
    dup = {n for n, schs in seen.items() if len(schs) > 1}

    tables = {}
    for f, sql in files:
        parse_create(sql, f, tables, dup)
    for f, sql in files:                      # 제약·주석은 테이블이 다 모인 뒤에
        parse_alter(sql, f, tables, dup)
        parse_unique(sql, tables)
        parse_comments(sql, tables)
    if dup:
        print(T('log.dup_names', n=len(dup), list=', '.join(sorted(dup)[:6])))

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
    # DDL 만으로 그리는 프로젝트도 있다. 채울 것이 없으면 DB 를 찾지 않는다 —
    # 예전엔 무조건 접속을 시도해, 접속 정보가 없으면 거기서 죽고
    # 있으면 `table_name in ()` 라는 빈 SQL 을 던져 경고를 찍었다.
    names = sorted(set(existing_names))
    # DDL 안에 정의가 없는 테이블을 FK 가 가리키면 DB 에서 컬럼을 채워 넣는다.
    # 접속 정보가 없으면 그것대로 진행한다 — 이름만 있는 상자로 그려진다.
    has_db = bool(os.environ.get('ERD_PSQL') or os.environ.get('ERD_DB'))
    if names and not has_db:
        print(T('log.ddl_no_db', n=len(names), list=', '.join(names[:6])))
    db = fetch_existing(names) if names and has_db else {}
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
    if REF_SOURCES and REF_SCHEMA:
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
