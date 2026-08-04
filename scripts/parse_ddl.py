#!/usr/bin/env python3
"""DDL 파서 → schema.json

`$ERD_SQL_DIR` 의 *.sql 에서 CREATE TABLE / ALTER TABLE 을 읽어 테이블·컬럼·타입·
제약·인라인주석·FK 를 구조화한다. **아직 DB 에 적용하지 않은 변경까지 그림에 넣고
싶을 때** 쓴다. 그냥 현재 DB 를 그릴 거라면 introspect.py 만으로 충분하다.

기존 테이블(이미 DB 에 있는 것)은 information_schema 조회 결과를 앞에 붙이고,
DDL 이 추가하는 컬럼을 뒤에 이어 `[추가]` 로 표시한다.

  ERD_SQL_DIR    파싱할 DDL 디렉토리 (기본 $ERD_PROJ/sql)
  ERD_SQL_FILES  읽을 파일을 직접 지정 (콤마 구분, 기본은 디렉토리의 *.sql 전부)
  ERD_LABEL      여러 DB 를 합칠 때 붙일 라벨. 키가 '<라벨>.orders' 가 되고
                 결과는 schema.<라벨>.json 으로 나간다 (introspect.py 와 같다)
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
# 경로 상수는 **부를 때** 묻는다. `from config import SCHEMA_JSON` 한 줄이 곧
# `config.WORK` 를 만들라는 뜻이라, 이 파일을 inspect 하려고 import 만 한 회귀 시험이
# 부르는 사람의 cwd 에 `erd-build/out` 을 남겼다 (config.py 의 '늦춰 두는 값' 참고).
# 여기서도 이름을 당겨오지 않아야 그 사슬이 끊긴다.
import config
from config import RS, SEP, has_db as config_has_db, psql, safe_name

# ERD_LABEL — SKILL.md·SKILL.ko.md 는 이것을 **범용 표**에 넣고 "여러 DB 를 합칠 때
# 붙일 라벨(schema.<라벨>.json)" 이라 적는데, 16라운드 전에는 introspect.py 만 보고
# 있었다. `ERD_LABEL=shop python3 parse_ddl.py` 는 라벨 없는 schema.json 에 라벨 없는
# 키를 쓰고 **경고 한 줄이 없었다.** 그 파일을 merge_schemas.py 로 섞으면 이름이 같은
# 테이블끼리 서로를 덮어쓴다(3라운드 발견) — 라벨이 있어야 안 부딪히는데, 라벨을
# 적은 사람은 제가 적었다고 믿는다. 문서를 따르는 쪽으로 맞춘다: 여기서도 붙인다.
#
# 검사도 introspect.py 와 같은 자리에서 한다 — 아무것도 파싱하기 전이다. `a/b` 는
# 마지막 쓰기에서 `ValueError: Invalid name` 이 되는데, 그때는 파일을 다 읽고 DB 까지
# 다녀온 뒤라 왕복이 통째로 버려진다.
LABEL = os.environ.get('ERD_LABEL', '').strip()
if LABEL and safe_name(LABEL) != LABEL:
    raise SystemExit(T('err.env_name', env='ERD_LABEL', value=LABEL,
                       safe=safe_name(LABEL) or 'db1'))


def _relabel(tables):
    """테이블 키·스키마에 ERD_LABEL 을 붙인다 — introspect.key() 와 **같은 규칙**.

    introspect 는 키를 `<라벨>.<스키마.이름 또는 이름>` 으로, `schema` 를
    `<라벨>.<스키마>` 로 적고 `db` 에 라벨을 남긴다. 두 경로가 서로 다른 모양을
    내면 merge_schemas 가 섞은 뒤 같은 DB 의 테이블이 두 규칙으로 흩어진다.

    FK 의 `ref_table` 도 함께 옮긴다. parse_ddl 은 DDL 안에 정의가 없는 참조 대상도
    반드시 `tables` 에 만들어 두므로(main 참고) 모든 `ref_table` 이 키다 — 하나라도
    빼먹으면 그림에서 관계가 통째로 사라진다.
    """
    if not LABEL:
        return tables
    out = {f'{LABEL}.{k}': t for k, t in tables.items()}
    for t in out.values():
        t['db'] = LABEL
        t['schema'] = f"{LABEL}.{t.get('schema') or 'public'}"
        for fk in t['fks']:
            fk['ref_table'] = f"{LABEL}.{fk['ref_table']}"
    return out


def sql_files():
    """읽을 DDL 파일 목록. 지정이 없으면 디렉토리의 *.sql 을 이름순으로 전부 읽는다."""
    named = [f.strip() for f in os.environ.get('ERD_SQL_FILES', '').split(',') if f.strip()]
    if named:
        # 없는 파일·디렉토리를 적으면 read_text 가 `FileNotFoundError: [Errno 2]` 로
        # 죽는데, 그 줄은 ERD_SQL_FILES 라는 말을 하지 않는다 (게다가 앞의 파일은
        # 이미 읽은 뒤다). 하나라도 못 읽을 것이면 시작 자리에서 이름을 댄다.
        bad = [f for f in named if not (config.SQL_DIR / f).is_file()]
        if bad:
            raise SystemExit(T('err.env_not_file', env='ERD_SQL_FILES',
                               path=', '.join(str(config.SQL_DIR / f) for f in bad[:6])))
        return named
    if not config.SQL_DIR.is_dir():
        raise SystemExit(T('err.no_sql_dir', path=config.SQL_DIR))
    return sorted(p.name for p in config.SQL_DIR.glob('*.sql'))


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
            # ms 에서도 가린다. 블록 주석 **안의** `--` 는 줄 주석이 아니다 — 남겨
            # 두었더니 `/* 내부 메모\n -- 내보내지 말 것 */` 의 그 줄이 아래 컬럼의
            # 설명이 되어 고객에게 나갔고, `/* was int -- see PR 12 */` 는 구분자까지
            # 달린 `see PR 12 */` 를 설명으로 실었다. 설명으로 쓰는 것은 줄 주석뿐이다.
            for k in range(i, j):
                ms[k] = mc[k] = msc[k] = ' '
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
            cuts.append(i + 1)          # 경계는 언제나 콤마다
    cuts.append(len(body_sc) + 1)

    items = []
    for a, b in zip(cuts, cuts[1:]):
        raw, code, seg_ms = body_mc[a:b - 1], body_sc[a:b - 1], body_ms[a:b - 1]
        # 주석은 위치도 내용도 ms(문자열만 가린 사본)에서 가져온다. 위치만 ms 에서
        # 찾고 내용을 mc(주석을 가린 사본)에서 떼어내던 탓에, 인라인 `-- 설명` 이
        # 전부 빈 문자열이 됐다 — DDL 경로의 간판 기능이 조용히 죽어 있었다.
        #
        # ── 소유 규칙: **주석은 아래로 붙는다** ────────────────────────────────
        #   · 같은 줄 앞에 코드가 있으면 그 코드 것이다 (`id bigint,  -- 행 식별자`
        #     의 주석은 콤마 뒤에 있어도 id 것, `id bigint  -- 행 식별자` 도 id 것)
        #   · 제 줄을 통째로 쓰는 주석은 **바로 아래** 코드 것이다 (컬럼 위에 적는 방식)
        #   · 아래에 코드가 없으면(마지막 컬럼 뒤·닫는 괄호 앞) 임자가 없다 — 버린다
        #   · 그래서 `-- 테넌트별 유일` 처럼 UNIQUE(...) 위에 적은 주석은 제약 것이 되고,
        #     제약은 컬럼이 아니므로 어느 컬럼 설명도 되지 않는다 (예전엔 앞 컬럼에 붙었다)
        #   · 여는 괄호와 **같은 줄** 의 주석은 헤더 것이라 컬럼이 아니다 — 테이블 설명으로
        #     쓰고 본문에서 지운다 (parse_create 에서 처리한다). 예전엔 첫 컬럼에 붙었다
        #   · 설명이 되는 것은 **줄 주석뿐** 이다. 블록 주석(/* */)은 mask 가 ms 에서도
        #     지우므로, 그 안의 `--` 도 줄 주석으로 잡히지 않는다
        #
        # 기준은 항목(콤마)이 아니라 **줄** 이다. 콤마로만 재던 두 판은 둘 다 한쪽을
        # 깨뜨렸다 — 콤마 뒤 주석을 무조건 앞 항목에 주면 컬럼 위 주석이 한 칸씩
        # 밀려 첫 설명이 사라지고 마지막이 비고, 경계를 줄 끝까지 늘리면 한 줄에
        # 여러 컬럼을 적은 정의가 통째로 한 덩어리가 된다. 줄로 재면 둘 다 산다.
        prev, own = [], []
        for mm in re.finditer(r'--[^\n]*', seg_ms):
            text = seg_ms[mm.start() + 2:mm.end()].strip()
            bol = code.rfind('\n', 0, mm.start()) + 1
            if code[bol:mm.start()].strip():
                own.append(text)                     # 같은 줄 앞의 코드 = 이 항목 것
            elif '\n' not in code[:mm.start()] and body_sc[
                    body_sc.rfind('\n', 0, a + mm.start()) + 1:a + mm.start()].strip():
                # 항목의 첫 줄이다 — 그 줄 앞에 있는 것은 콤마와 앞 항목의 코드다
                prev.append(text)
            elif code[mm.end():].strip():
                own.append(text)                     # 제 줄을 쓰는 주석 — 아래 코드 것
        prev = ' '.join(x for x in prev if x)
        if prev and items:
            items[-1] = (items[-1][0], items[-1][1],
                         ' '.join(x for x in (items[-1][2], prev) if x))
        note = ' '.join(x for x in own if x)
        # 값(타입·기본값)은 주석만 가린 사본에서, 구조 판정은 둘 다 가린 사본에서.
        raw_code = ' '.join(raw.split()).rstrip(', ')
        code = ' '.join(code.split()).rstrip(', ')
        if code:
            items.append((raw_code, code, note))
    return items


# ── 식별자 ──────────────────────────────────────────────────────────────────
# 따옴표 친 이름은 공백·대문자·예약어를 담을 수 있고, pg_dump 는 그런 이름을 언제나
# 따옴표째 내놓는다. 이름을 낱말(\w+)로 재던 예전 방식은 `"Unit Price" numeric(12,2)`
# 를 이름 `Unit`·타입 `price` 로 읽었다 — 있지도 않은 컬럼이 문서에 실리고 진짜
# 컬럼은 사라진다. 이름 자리는 전부 이 조각으로 재서 한 번에 같은 규칙을 쓴다.
_ID = r'(?:"[^"]*"|\w+)'          # 이름 한 조각 (안 잡는다)
_IDC = r'("[^"]*"|\w+)'           # 같은 것, 잡는다


def unq(s):
    """따옴표 친 식별자에서 따옴표만 벗긴다. 안의 `""` 는 따옴표 한 개다."""
    if s is None:
        return None
    s = s.strip()
    return s[1:-1].replace('""', '"') if len(s) >= 2 and s[0] == s[-1] == '"' else s


def _names(text):
    """콤마로 갈라 이름 목록을 만든다 (PK·FK·UNIQUE 의 괄호 안)."""
    return [unq(c) for c in text.split(',') if c.strip()]


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
    m = re.search(r'\bREFERENCES\s+(?:' + _IDC + r'\s*\.\s*)?' + _IDC +
                  r'\s*(?:\(([^)]*)\))?', code, re.I)
    if not m:
        return None
    cols = _names(m.group(3) or '')
    rule = re.search(_ON_DELETE, code[m.end():], re.I)
    return (unq(m.group(1)), unq(m.group(2)), cols or ['id'],
            ' '.join((rule.group(1) if rule else 'NO ACTION').split()).upper())


_TYPE_HEAD = re.compile(
    r'^(character\s+varying|character|bit\s+varying|double\s+precision|'
    r'timestamp\s+with\s+time\s+zone|timestamp\s+without\s+time\s+zone|'
    r'time\s+with\s+time\s+zone|time\s+without\s+time\s+zone|'
    r'[A-Za-z_][\w]*(?:\s*\.\s*[A-Za-z_][\w]*)?)'
    r'(\s*\([^)]*\))?((?:\s*\[\s*\d*\s*\])*)', re.I)


_REF_CLAUSE = re.compile(
    r'\bREFERENCES\s+(?:' + _ID + r'\s*\.\s*)?' + _ID + r'\s*(?:\([^)]*\))?'
    r'(?:\s+MATCH\s+\w+)?'
    r'(?:\s+ON\s+(?:DELETE|UPDATE)\s+'
    r'(?:CASCADE|RESTRICT|NO\s+ACTION|SET\s+NULL|SET\s+DEFAULT))*', re.I)


def _decl(rest):
    """REFERENCES 절**만** 걷어낸 선언부.

    부모 테이블 이름이 판정에 끼어들면 안 되지만(REFERENCES serial_numbers 가
    identity 가 됐다), REFERENCES 에서 뒤를 통째로 잘라 내면 그 뒤에 적은 제약을
    놓친다 — `parent_id int REFERENCES users(id) NOT NULL` 이 nullable 이 됐다.
    """
    return _REF_CLAUSE.sub(' ', rest)


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
                          r'(?:' + _IDC + r'\s*\.\s*)?' + _IDC + r'\s*\(', re.I)
    for m in head_pat.finditer(msc):
        sch, name = unq(m.group(1)) or 'public', unq(m.group(2))
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

        # `CREATE TABLE t (  -- 한 줄 설명` 의 주석은 **여는 괄호와 같은 줄** 에 있다.
        # '주석은 아래로 붙는다' 는 규칙을 그대로 태우면 이것이 첫 컬럼 것이 되어,
        # 테이블 이야기가 id 의 설명으로 실렸다. 이 줄의 임자는 테이블 헤더이고
        # 헤더는 컬럼이 아니다 — 테이블 설명으로 쓰고, 본문에서는 지워 아래로
        # 흘러가지 못하게 한다. 문장 안에 있으니 위에서 읽은 헤더 주석보다 우선한다.
        eol = body_ms.find('\n')
        eol = len(body_ms) if eol < 0 else eol
        if not body_sc[:eol].strip():                 # 그 줄에 코드가 없을 때만
            hm = re.search(r'--[^\n]*', body_ms[:eol])
            if hm:
                if hm.group(0)[2:].strip():
                    t['note'] = hm.group(0)[2:].strip()
                body_ms = body_ms[:hm.start()] + ' ' * len(hm.group(0)) + body_ms[hm.end():]

        for raw_code, code, comment in split_top_level(body_mc, body_ms, body_sc):
            up = code.upper()
            if _TABLE_LEVEL.match(code):
                pk = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', code, re.I)
                if pk:
                    t['pk'] = _names(pk.group(1))
                fk = re.search(r'FOREIGN\s+KEY\s*\(([^)]+)\)', code, re.I)
                ref = _refs(code)
                if fk and ref:
                    rt = _ref_key(ref, sch, dup)
                    kids = _names(fk.group(1))
                    for idx, c in enumerate(kids):
                        t['fks'].append({
                            'column': c, 'ref_table': rt,
                            'ref_column': ref[2][idx] if idx < len(ref[2]) else ref[2][-1],
                            'on_delete': ref[3]})
                uq = re.match(r'(?:CONSTRAINT\s+' + _ID + r'\s+)?UNIQUE\s*\(([^)]+)\)',
                              code, re.I)
                if uq:
                    t['uniques'].append(_names(uq.group(1)))
                continue

            col = re.match(r'^' + _IDC + r'\s+(.+)$', raw_code)  # 따옴표 친 컬럼명도 받는다
            if not col:
                continue
            cname, rest = unq(col.group(1)), col.group(2).strip()
            # 구조 판정(NOT NULL·PRIMARY KEY·REFERENCES)은 반드시 가린 사본에서 한다.
            # 원본에서 보면 DEFAULT 'PRIMARY KEY 설명' 같은 값이 진짜 제약이 된다.
            # 앞서 만든 사본은 공백을 접으면서 원본과 길이가 어긋났으므로, 이 선언부
            # 하나만 다시 가린다 — 같은 길이라야 값을 위치로 꺼낼 수 있다.
            rest_sc = mask(rest)[2]

            up_rest = rest_sc.upper()
            # 값의 **경계** 는 가린 사본에서 찾고 **값** 은 원본에서 꺼낸다.
            # 가린 사본에서 값까지 읽으면 문자열이 공백이라 빈 값이 되고,
            # 원본에서 경계를 찾으면 DEFAULT 'see REFERENCES users' 가 `'see` 로 잘린다.
            dflt = None
            dm = re.search(r'\bDEFAULT\b', rest_sc, re.I)
            if dm:
                tail = rest_sc[dm.end():]
                stop = re.search(r'\s+(?:NOT\s+NULL|NULL|PRIMARY|UNIQUE|REFERENCES|'
                                 r'CHECK|GENERATED|COLLATE)\b', tail, re.I)
                dflt = rest[dm.end():dm.end() + (stop.start() if stop else len(tail))]
            t['columns'].append({
                'name': cname,
                'type': _type(rest),
                # IDENTITY·serial 은 NOT NULL 을 적지 않아도 NOT NULL 이다
                # 낱말로 본다. 부분 문자열로 재면 REFERENCES serial_numbers(id) 가
                # 그 컬럼을 identity·NOT NULL 로 만든다.
                'not_null': bool(re.search(r'\bNOT\s+NULL\b|\bIDENTITY\b|\w*SERIAL\b(?!\s*_)',
                                           _decl(rest_sc), re.I)),
                'default': dflt.strip().rstrip(',') if dflt else '',
                'identity': bool(re.search(r'\bIDENTITY\b|\b(?:BIG|SMALL)?SERIAL\b',
                                           _decl(rest_sc), re.I)),
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
    head = (r'ALTER\s+TABLE\s+(?:ONLY\s+)?(?:' + _IDC + r'\s*\.\s*)?' + _IDC + r'\s+')

    def find(sch, name):
        return _find(tables, sch, name)

    for m in re.finditer(head + r'(ADD\s+COLUMN\b.*?);', msc, re.S | re.I):
        sch, name = unq(m.group(1)), unq(m.group(2))
        t = find(sch, name)
        if t is None:
            # 스키마를 적어 준 ALTER 는 그 스키마의 테이블로 새로 만든다. 이름만으로
            # 가져다 쓰면 audit.users 의 컬럼이 public.users 에 붙는다.
            key = f'{sch}.{name}' if sch and (name in dup or name in tables) else name
            t = tables.setdefault(key, {
                'name': name, 'origin': 'existing', 'src_file': src,
                'schema': sch or 'public',
                'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
            })
        t['altered_by'] = src
        for raw_code, code, comment in split_top_level(mc[m.start(3):m.end(3)],
                                                       ms[m.start(3):m.end(3)],
                                                       msc[m.start(3):m.end(3)]):
            am = re.match(r'ADD\s+COLUMN\s+' + _IDC + r'\s+(.+)$', raw_code, re.I)
            if not am:
                continue
            rest = am.group(2).strip()
            t['columns'].append({
                'name': unq(am.group(1)),
                'type': _type(rest),
                'not_null': 'NOT NULL' in rest.upper(),
                'default': (re.search(r'DEFAULT\s+(.+?)(?=\s+(?:NOT\s+NULL|NULL)\b|$)',
                                      rest, re.I).group(1).strip().rstrip(',')
                            if re.search(r'DEFAULT\s+', rest, re.I) else ''),
                'identity': 'IDENTITY' in rest.upper(),
                'comment': comment,
                'added': True,
            })

    for m in re.finditer(head + r'ADD\s+CONSTRAINT\s+' + _ID + r'\s+(.*?);',
                         msc, re.S | re.I):
        t = find(unq(m.group(1)), unq(m.group(2)))
        if t is None:
            continue
        code = ' '.join(sql[m.start(3):m.end(3)].split())
        pk = re.search(r'PRIMARY\s+KEY\s*\(([^)]+)\)', code, re.I)
        if pk:
            t['pk'] = _names(pk.group(1))
        fk = re.search(r'FOREIGN\s+KEY\s*\(([^)]+)\)', code, re.I)
        ref = _refs(code)
        if fk and ref:
            rt = _ref_key(ref, t.get('schema', 'public'), dup)
            kids = _names(fk.group(1))
            for idx, c in enumerate(kids):
                t['fks'].append({
                    'column': c, 'ref_table': rt,
                    'ref_column': ref[2][idx] if idx < len(ref[2]) else ref[2][-1],
                    'on_delete': ref[3]})
        uq = re.match(r'UNIQUE\s*\(([^)]+)\)', code, re.I)
        if uq:
            t['uniques'].append(_names(uq.group(1)))

    # pg_dump 는 IDENTITY 를 별도 문으로 내고, serial 은 시퀀스 기본값으로 푼다.
    # 둘 다 여기서 되살리지 않으면 DB 를 직접 읽은 결과와 어긋난다.
    for m in re.finditer(head + r'ALTER\s+COLUMN\s+' + _IDC + r'\s+'
                         r'(?:ADD\s+GENERATED\b|SET\s+DEFAULT\s+nextval)',
                         msc, re.S | re.I):
        t = find(unq(m.group(1)), unq(m.group(2)))
        if t:
            for c in t['columns']:
                if c['name'] == unq(m.group(3)):
                    c['identity'] = c['not_null'] = True


def parse_comments(sql: str, tables: dict):
    """COMMENT ON TABLE/COLUMN — pg_dump 가 설명을 싣는 유일한 자리다.

    이름 조각을 먼저 다 받아 두고 개수로 갈라 읽는다. 스키마 자리를 선택 그룹으로
    두었더니 `COMMENT ON COLUMN users.email` 에서 users 를 스키마로 먹어 버려 손으로
    쓴 DDL 의 컬럼 설명이 전부 사라졌다.
    """
    _ms, _mc, msc = mask(sql)

    def find(sch, name):
        return _find(tables, sch, name)

    for m in re.finditer(r'COMMENT\s+ON\s+(TABLE|COLUMN)\s+'
                         r'((?:' + _ID + r'\s*\.\s*){0,2}' + _ID + r')\s+IS\b', msc, re.I):
        lit = re.match(r"\s*'((?:[^']|'')*)'", sql[m.end():])
        if not lit:
            continue
        text = lit.group(1).replace("''", "'")
        # 점으로 자르지 않는다 — 따옴표 친 이름 안의 점은 구분자가 아니다
        parts = [unq(x) for x in re.findall(_ID, m.group(2))]
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


def _find(tables, sch, name):
    """스키마까지 보고 테이블을 찾는다. 스키마를 무시하면 이름이 겹칠 때
    pg_dump 가 먼저 내놓은 쪽에 남의 제약이 붙는다."""
    if sch and f'{sch}.{name}' in tables:
        return tables[f'{sch}.{name}']
    if name in tables and (not sch or tables[name].get('schema') == sch):
        return tables[name]
    if not sch:
        return tables.get(name) or next(
            (tables[k] for k in tables if k.endswith('.' + name)), None)
    return None


def parse_unique(sql: str, tables: dict):
    """CREATE UNIQUE INDEX → uniques.

    introspect 와 같은 '컬럼 이름 목록' 형식이어야 한다. dict 로 넣던 때는 HTML 이
    그 키를 이어 붙여 `UNIQUE (columns, where)` 라고 찍었다.
    """
    _ms, _mc, msc = mask(sql)
    for m in re.finditer(r'CREATE\s+UNIQUE\s+INDEX\s+(?:CONCURRENTLY\s+)?'
                         r'(?:IF\s+NOT\s+EXISTS\s+)?' + _ID + r'\s+ON\s+(?:ONLY\s+)?'
                         r'(?:' + _IDC + r'\s*\.\s*)?' + _IDC +
                         r'(?:\s+USING\s+\w+)?\s*\(([^)]+)\)', msc, re.I):
        t = _find(tables, unq(m.group(1)), unq(m.group(2)))
        cols = _names(m.group(3))
        if t is not None and not any('(' in c for c in cols):
            t['uniques'].append(cols)      # 함수 인덱스(lower(email))는 컬럼 목록이 아니다


def _rows(query, n):
    """조회 결과를 n개 필드로 맞춰 돌려준다 (introspect.rows() 와 같은 규칙).

    행은 개행이 아니라 RS 로 가른다. 개행으로 가르면 개행이 든 값 하나가 — 컬럼
    이름에도 들어갈 수 있다 — 행을 둘로 쪼개고, 4-튜플 풀기가 ValueError 로 죽었다.
    필드도 모자라면 채운다. 파서가 DB 값 하나에 통째로 멈춰서는 안 된다.
    """
    for line in psql(query, rs=RS).removesuffix('\n').split(RS):
        if not line.strip():
            continue
        yield (line.split(SEP) + [''] * n)[:n]


REF_SCHEMA = os.environ.get('ERD_REF_SCHEMA', '').strip()
REF_SOURCES = [t.strip() for t in os.environ.get('ERD_REF_TABLES', '').split(',') if t.strip()]


def _lit(s):
    """SQL 문자열 리터럴 하나. 이름 속 따옴표가 남의 문법이 되지 않게 escape 한다.

    값 둘 다 환경변수(ERD_REF_SCHEMA·ERD_REF_TABLES)에서 그대로 와서 그대로 **살아
    있는 서버**로 나간다. escape 를 지우면 나가는 문장이 이렇게 된다:
        where c.table_schema='s1' or '1'='1' and c.table_name in ('x')
    15라운드 전에는 이 자리를 재는 항목이 introspect 쪽에만 있었고 여기는 0건이라,
    지워도 141개가 전부 초록이었다 (selftest_r14_config.py 의 'parse: a quote in
    ERD_REF_SCHEMA…' 가 이제 그것을 문다).
    """
    return "'" + str(s).replace("'", "''") + "'"


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
    where c.table_schema={_lit(REF_SCHEMA)} and c.table_name in ({','.join(_lit(t) for t in tables)})
    order by c.table_name, c.ordinal_position"""
    out = {}
    for tn, cn, ty, nul in _rows(q, 4):
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
    where c.table_schema='public' and c.table_name in ({','.join(_lit(n) for n in names)})
    order by c.table_name, c.ordinal_position"""
    out = {}
    for tn, cn, ty, nul in _rows(q, 4):
        out.setdefault(tn, []).append(
            {'name': cn, 'type': ty, 'not_null': nul == 'NO', 'default': '',
             'identity': False, 'comment': '', 'added': False})
    return out


def main():
    files = [(f, (config.SQL_DIR / f).read_text()) for f in sql_files()]

    # 이름이 두 스키마에 걸치면 키에 스키마를 붙인다 (introspect 와 같은 규칙).
    # 예전엔 shop.orders 와 mart.orders 가 한 테이블로 합쳐져 컬럼이 뒤섞였다.
    seen = {}
    head = re.compile(r'CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+'
                      r'(?:IF\s+NOT\s+EXISTS\s+)?'
                      r'(?:' + _IDC + r'\s*\.\s*)?' + _IDC + r'\s*\(', re.I)
    for _f, sql in files:
        for m in head.finditer(mask(sql)[2]):
            seen.setdefault(unq(m.group(2)), set()).add(unq(m.group(1)) or 'public')
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
    #
    # 16R. 물을 것이 없어도 `config_has_db()` 를 불렀다. 그 한 줄이 곧 ERD_PSQL 을
    # 분해하라는 뜻이라, FK 가 밖을 안 가리키는 **순수 DDL** —
    # `create table t (id bigint primary key);` — 도 `ERD_PSQL='psql "unclosed'`
    # 하나로 rc 1 이었다. 14라운드가 config 의 지연으로, 15라운드가 그 범위를 좁히며
    # 고친 것이 바로 '안 묻는 실행이 접속 설정에 걸려 죽는다' 인데, 이 자리까지는
    # 오지 않았다. 물을 것이 있을 때만 묻는다.
    has_db = config_has_db() if names else False
    if names and not has_db:
        print(T('log.ddl_no_db', n=len(names), list=', '.join(names[:6])))
    db = fetch_existing(names) if has_db else {}
    for n in existing_names:
        if n not in db:
            continue
        added = tables[n]['columns']
        added_names = {c['name'] for c in added}
        base = [c for c in db[n] if c['name'] not in added_names]
        tables[n]['columns'] = base + added

    # ERD_DEFAULT_PK 는 위 루프 **안**에 있었다. `if n not in db: continue` 아래라
    # 접속이 없으면 db={} 로 루프가 한 번도 안 돌아, DDL 만으로 그리는 사람에게는
    # 영원히 무효인 스위치였다 — 그런데 화면에는 한 글자도 안 나왔다. SKILL.md 도
    # DB 가 필요하다는 말을 하지 않는다. 이제 접속과 무관하게 돌고, 붙이지 못한 것은
    # 이름을 대어 말한다. (그 이름의 컬럼이 없는데도 PK 로 적던 것도 함께 멈춘다 —
    # 정의서의 PK 칸이 있지도 않은 컬럼을 가리켰다.)
    default_pk = os.environ.get('ERD_DEFAULT_PK', '').strip()
    if default_pk:
        no_col = []
        for n in sorted(set(existing_names)):
            if tables[n]['pk']:
                continue
            if any(c['name'] == default_pk for c in tables[n]['columns']):
                tables[n]['pk'] = [default_pk]
            else:
                no_col.append(n)
        if no_col:
            print(T('log.default_pk_skipped', column=default_pk, n=len(no_col),
                    list=', '.join(no_col[:6])))

    # PRIMARY KEY 컬럼은 Postgres 가 NOT NULL 을 자동으로 건다. DDL 에 따로 적지 않은
    # PK 를 nullable 로 두면 같은 테이블을 DB 에서 읽은 결과(introspect)와 어긋난다 —
    # 그림은 PK 아이콘이 앞서 가려 주지만, 정의서 표의 NULL 칸은 그대로 틀린다.
    # 인라인 PK · 테이블 수준 복합 PK · ALTER 로 붙인 PK 를 여기서 한 번에 채운다.
    for t in tables.values():
        for c in t['columns']:
            if c['name'] in t['pk']:
                c['not_null'] = True

    for t in tables.values():
        t.setdefault('schema', 'public')
    if REF_SOURCES and REF_SCHEMA:
        tables.update(fetch_ref(REF_SOURCES))
    elif REF_SOURCES:
        # 반쪽만 준 것은 안 준 것과 다르다 — 예전엔 아무 말 없이 무시했다.
        print(T('log.ref_tables_ignored', n=len(REF_SOURCES),
                list=', '.join(REF_SOURCES[:6])))

    tables = _relabel(tables)

    out = (config.SCHEMA_JSON.with_name(f'schema.{LABEL}.json') if LABEL
           else config.SCHEMA_JSON)
    Path(out).write_text(json.dumps(tables, ensure_ascii=False, indent=2))
    print(T('log.ddl_parsed', n=len(tables), path=out))
    for n, t in sorted(tables.items(), key=lambda x: (x[1]['origin'], x[0])):
        added = sum(1 for c in t['columns'] if c['added'])
        print(f"  [{t['origin']:8}] {n:32} "
              + T('log.ddl_row', columns=f"{len(t['columns']):3}",
                       added=(T('log.ddl_added', n=added) if added else '').ljust(12),
                       fks=len(t['fks']), note=t['note'][:40]))


if __name__ == '__main__':
    main()
