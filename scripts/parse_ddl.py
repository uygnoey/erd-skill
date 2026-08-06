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

from i18n import t as T
# 경로 상수는 **부를 때** 묻는다. `from config import SCHEMA_JSON` 한 줄이 곧
# `config.WORK` 를 만들라는 뜻이라, 이 파일을 inspect 하려고 import 만 한 회귀 시험이
# 부르는 사람의 cwd 에 `erd-build/out` 을 남겼다 (config.py 의 '늦춰 두는 값' 참고).
# 여기서도 이름을 당겨오지 않아야 그 사슬이 끊긴다.
import config
from config import (QueryFailed, atomic_write_text, has_db as config_has_db,
                    psql_rows, safe_name)

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
    named = []
    for raw in os.environ.get('ERD_SQL_FILES', '').split(','):
        name = raw.strip()
        if name and name not in named:
            named.append(name)
    if named:
        root = config.SQL_DIR.resolve()
        outside = []
        unique, seen_paths = [], set()
        for name in named:
            resolved = (config.SQL_DIR / name).resolve()
            try:
                resolved.relative_to(root)
            except ValueError:
                outside.append(name)
                continue
            if resolved not in seen_paths:
                seen_paths.add(resolved)
                unique.append(name)
        if outside:
            raise SystemExit(T('err.sql_file_outside', env='ERD_SQL_FILES',
                               path=config.SQL_DIR, value=', '.join(outside[:6])))
        # 없는 파일·디렉토리를 적으면 read_text 가 `FileNotFoundError: [Errno 2]` 로
        # 죽는데, 그 줄은 ERD_SQL_FILES 라는 말을 하지 않는다 (게다가 앞의 파일은
        # 이미 읽은 뒤다). 하나라도 못 읽을 것이면 시작 자리에서 이름을 댄다.
        named = unique
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

    큰따옴표 식별자는 **가리지 않되 건너뛴다.** 가리지 않는 것은 `_IDC` 가 거기서
    이름을 읽어야 하기 때문이고(그래서 구분자를 셀 때만 `blank_quoted` 로 따로 덮는다),
    건너뛰는 것은 이름 **안**의 `'`·`--`·`/*`·`$$` 가 코드가 아니기 때문이다. 안 건너뛰던
    때는 `"a'b"` 라는 이름 하나가 그 자리부터 문자열이 시작한 것으로 읽혀 뒤가 전부
    어긋났고, `CREATE TABLE` 이 **통째로, 경고 한 줄 없이** 사라졌다 — `COLLATE "it's ok"`
    하나면 됐다. `"a--b"`·`"a/*b"` 도 같은 모양이었다. 세 사본 모두 그 구간을 원본
    그대로 두므로 ms·mc·msc 의 그 자리는 서로 같고, 예전과도 같다(예전에도 안 가렸다).
    바뀌는 것은 **그 구간을 지난 뒤 어디서부터 다시 읽느냐** 뿐이다.

    닫는 `"` 가 없으면 덮지도 건너뛰지도 않고 그 글자 하나만 지나간다 —
    `blank_quoted` 와 같은 선택이다. 여기서는 걸리는 것이 파일 **전체**라 더 그렇다:
    짝 없는 `"` 하나에 나머지 DDL 이 통째로 안 가려지는 것보다, 그 글자를 평범한
    글자로 두어 예전과 똑같이 읽히게 두는 편이 잃는 것이 적다.
    """
    ms, mc, msc, ran_off = _scan(sql, True)
    if ran_off:
        # 큰따옴표를 넘다가 **끝나지 않는 문자열 리터럴**이 생겼다. 이런 일은 코드
        # 자리의 `"` 가 진짜 식별자 시작이 아닐 때 벌어진다: `t (a "b text DEFAULT
        # 'has " quote', z int)` 에서 짝으로 집힌 `"` 가 리터럴 **안**의 것이라,
        # 건너뛴 뒤 남은 `'` 하나가 파일 끝까지 리터럴이 된다. 그러면 그 뒤의
        # `CREATE TABLE` 들까지 통째로 사라진다 — 손으로 쓰다 만 DDL 에서 뒤따르는
        # 문을 다 잃는 것은 이 저장소가 가장 싫어하는 모양이고, 큰따옴표를 알아본
        # 대가로 치를 것이 못 된다.
        #
        # 그래서 그때만 `"` 를 모르던 방식으로 한 번 더 읽어 보고, 그쪽이 성하면
        # 그것을 쓴다. 성한 입력에서는 첫 판이 이미 성하므로 이 길로 오지 않는다
        # (측정: 큰따옴표가 제대로 짝을 이루는 문서 6000건에서 결과가 달라진 칸 0).
        alt = _scan(sql, False)
        if not alt[3]:
            return alt[:3]
    return ms, mc, msc


def _scan(sql, skip_quoted):
    """mask() 의 훑기 한 판 → (ms, mc, msc, 끝나지 않은 리터럴이 있었나).

    `skip_quoted` 가 거짓이면 `"` 를 평범한 글자로 본다 — mask() 의 되돌림 판이다.
    """
    ms, mc, msc = list(sql), list(sql), list(sql)
    ran_off = False
    i, n = 0, len(sql)
    dollar = re.compile(r'\$([A-Za-z_]\w*)?\$')
    while i < n:
        c = sql[i]
        if c == '"' and skip_quoted:                  # 큰따옴표 식별자 — 남기되 건너뛴다
            # 이름 안의 `""`(따옴표 한 글자)를 여기서 따로 안 넘어도 된다: 짝지어
            # 건너뛰면 `"a""b"` 가 `"a"`+`"b"` 두 번에 나뉘지만 **지나는 자리는
            # 통째로 넘는 것과 같다** — 이름 속 `""` 는 늘 붙어 있어 틈이 없다.
            # 성한 입력 1,111,111개로 쟀다(`blank_quoted` 문서 참고). `_QID` 를
            # 고칠 때 여기까지 손대면 짝 안 맞는 입력의 예전 자리만 흔든다.
            j = sql.find('"', i + 1)
            i = (j + 1) if j >= 0 else i + 1          # 짝이 없으면 한 글자만
        elif c == "'":                                # 문자열 리터럴
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
            if j >= n:                                # 닫는 `'` 를 못 찾고 끝났다
                ran_off = True
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
    return ''.join(ms), ''.join(mc), ''.join(msc), ran_off


def blank_quoted(s):
    """큰따옴표 식별자를 같은 길이의 공백으로 덮은 사본 — **구분자를 셀 때만** 쓴다.

    `mask` 는 큰따옴표를 일부러 남긴다: 지우면 `_IDC` 가 이름을 못 읽는다. 그런데
    이름 안에는 무엇이든 들어갈 수 있어서, 가린 사본에서 괄호·대괄호·콤마를 세는
    자리마다 이름 안의 그 글자가 함께 세어졌다. 이름 안에는 **구분자가 있을 수 없으니**
    세는 사본에서만 덮는다. 길이가 같아 원본·다른 사본과 위치가 그대로 맞는다.

    같은 규칙을 쓰는 자리가 셋이 됐다 — `split_top_level` 의 자를 자리, `_default_end`
    의 깊이, `parse_create` 의 본문 괄호 짝. 세 벌로 적어 두면 다음 사람은 또 한쪽만
    고친다. 실제로 그렇게 됐었다: 앞의 둘은 이미 막고 있는데 `parse_create` 만 규율
    밖이라, `CREATE TABLE t (id int, c text COLLATE "a(b")` 하나가 그 문의 테이블을
    **통째로, 경고 한 줄 없이** 사라지게 했다(짝이 안 맞아 `if depth: continue`).

    닫는 `"` 가 없으면 덮지 않고 그 글자 하나만 지나간다. 짝 없는 `"` 하나에 나머지
    파일 전체가 안 세어지는 것보다, 그 글자를 평범한 글자로 두는 편이 덜 위험하다.
    (`"` 가 문자열·주석 안에 있는 경우는 여기까지 오지 않는다 — `mask` 가 이미 그
     구간을 공백으로 바꿔 놓았다.)

    **이름 안의 `""` 는 여기서 따로 안 다룬다 — 다룰 것이 없다.** `_QID` 를 고칠 때
    여기도 고쳐야 하나 재 봤다. `"a""b"` 는 따옴표가 넷이라, 짝지어 덮으면
    `"a"` + `"b"` 두 번에 나눠 덮히지만 **덮이는 자리는 통째로 덮는 것과 똑같다** —
    이름 속 `""` 는 언제나 서로 붙어 있어서 두 짝 사이에 안 덮인 틈이 안 생긴다.
    (측정: `" a , ( ) ' - $ /` 로 만든 길이 0~6 문자열 1,111,111개를 `""` 를 아는
     판과 맞대어, **성한 입력에서 달라진 것 0**.)
    `_scan` 의 `skip_quoted` 갈래도 같은 이유로 같은 결과다 — 함께 쟀다.

    달라지는 것은 **짝이 안 맞는** 따옴표가 든 입력이다. 거기서 이 자리를 안 고치는
    까닭은 **그쪽이 더 낫기 때문이 아니다** — 어느 쪽이 옳다는 근거가 없다. 재 보면
    양쪽으로 다 갈린다: `" "" a b ( ) , [ ] ' . -` 로 지은 무작위 DDL 3000건 × 씨앗
    4벌에서 결과가 갈린 것이 62~81건이고, 그중 지금 판이 더 건진 것 49~68 · `""` 를
    아는 판이 더 건진 것 1~4 · 동률 9~17 이었다. 기울기는 코퍼스를 어떻게 짓느냐로
    움직인다 — `""` 를 덜 섞은 다른 코퍼스에서는 41건이 갈려 15 대 12 로 거의 반반
    이었다. 그러니 여기서 말할 수 있는 것은 하나뿐이다: **성한 입력에서 0 인 자리를,
    깨진 입력에서 어느 쪽이 나은지도 모르면서 흔들지 않는다.** (덜 흔든다는 것이지
    더 낫다는 것이 아니다.)

    이 판단은 오래 무방비였다 — 여기와 `_scan` 을 `""` 아는 판으로 바꿔도 217개가
    전부 초록이었다. `selftest.py` 의 `parse: an unmatched " before a "" is masked
    from the left` 가 그 자리를 지킨다. 바꾸려면 그 케이스부터 마주해야 한다.
    """
    out, i, n = [], 0, len(s)
    while i < n:
        if s[i] == '"':
            j = s.find('"', i + 1)
            if j >= 0:
                out.append(' ' * (j - i + 1))
                i = j + 1
                continue
        out.append(s[i])
        i += 1
    return ''.join(out)


_PAIR = {'(': ')', '[': ']'}


def paren_depth(s):
    """자리마다의 괄호·대괄호 깊이 → 길이가 s 와 같은 목록.

    **짝이 맞는 기호만 센다.** 짝 없는 것은 아예 없는 셈 친다. 이것이 요점이다.

    그냥 세면서 지나가는 방식(`+1`/`-1`)은 짝이 안 맞는 입력에서 무너진다. 실제로
    무너졌다: `[`·`]` 를 세기 시작하면서 `a int DEFAULT 1], b text, c text` 의 depth
    가 `]` 에서 음수가 되고, 그러면 `depth == 0` 이 뒤로 영영 거짓이라 **b·c 가 통째로
    앞 컬럼의 기본값 속으로 사라졌다.** 예전엔 `]` 를 안 세서 안 밟혔을 뿐, `)` 로도
    같은 성질이었다.

    누르는 것(`max(0, depth - 1)`)으로는 반만 고쳐진다. 그것은 **닫는 쪽이 남는**
    경우만 막고 **여는 쪽이 남는** 경우 — `DEFAULT [1, b text, c text` — 는 depth 가
    1 에서 안 내려와 똑같이 뒤를 삼킨다. 그래서 누르지 않고 **짝을 먼저 맞춘다**:
    스택으로 짝을 찾고, 짝지어진 쌍만 깊이에 넣는다. 짝 없는 `[`·`]`·`(`·`)` 는
    구분자를 가리지 못하므로 그 뒤가 예전(그 기호를 안 세던 때)처럼 읽힌다.

    깊이는 **쌍 안쪽에만** 걸린다: `a(b)c` → `[0, 0, 1, 0, 0]`. 여는 기호와 닫는
    기호 자신은 바깥 깊이다. 구분자(콤마)나 제약 낱말은 기호가 아니므로 이 규칙에
    걸릴 일이 없고, 경계 판정은 '내가 어떤 쌍 **안**에 있는가' 만 물으면 된다.

    쓰는 곳은 둘 — `split_top_level` 의 자를 자리와 `_default_end` 의 값 경계. 두
    자리가 같은 성질로 무너지므로 규칙도 한 벌이다.
    """
    stack, inc = [], [0] * (len(s) + 1)
    for i, c in enumerate(s):
        if c in _PAIR:
            stack.append((i, _PAIR[c]))
        elif c in (')', ']') and stack and stack[-1][1] == c:
            j, _ = stack.pop()
            inc[j + 1] += 1                 # 여는 기호 **다음** 자리부터 한 겹 안
            inc[i] -= 1                     # 닫는 기호 자신은 다시 바깥
    # 스택에 남은 것은 짝 없는 여는 기호다 — inc 에 넣지 않았으므로 저절로 안 세어진다.
    out, d = [], 0
    for i in range(len(s)):
        d += inc[i]
        out.append(d)
    return out


def split_top_level(body_mc: str, body_ms: str, body_sc: str):
    """최상위 콤마로 항목을 나눈다 → [(코드, 주석), …]

    줄 단위가 아니라 콤마 단위다. 한 줄에 다 적은 정의도 제대로 나뉜다.
    """
    # ── 경계를 어디서 재는가 ────────────────────────────────────────────────
    # 자를 자리는 body_sc 가 아니라 **따옴표 친 이름까지 지운 사본** 에서 잰다
    # (`blank_quoted` 참고 — 같은 규칙을 쓰는 세 자리 중 하나다). 안 덮던 때는 이름
    # **안** 의 구분자가 그대로 세어졌다: `"a,b" int, x text` 는 이름 한가운데서
    # 쪼개졌고, `"a(b"`·`"a)b"` 는 depth 를 망가뜨려 뒤따르는 컬럼이 통째로 사라졌다.
    # 길이가 같아 body_mc·body_ms 와 위치가 맞고, 아래의 주석 소유 판정은 body_sc 를
    # 그대로 쓴다 — 거기서는 이름도 '코드가 있다' 는 증거라, 지우면 컬럼 위 주석의
    # 임자가 바뀐다.
    #
    # 괄호와 함께 **대괄호** 도 센다. 안 세던 때는 배열 리터럴 안의 콤마가 최상위로
    # 보여 `tags text[] DEFAULT ARRAY['a','b'] NOT NULL` 이 두 토막이 났다 — 기본값은
    # `ARRAY['a'` 로 잘리고 `NOT NULL` 은 뒷토막에 실려 사라졌다. 타입 표기의
    # `int[]`·`int[3][4]` 는 짝이 맞아 깊이가 제자리로 돌아오므로 무해하다.
    #
    # 깊이는 `paren_depth` 가 잰다 — **짝이 맞는 기호만** 센다. 그냥 세면서 지나가던
    # 때는 짝 없는 `]` 하나에 깊이가 음수가 되어 그 뒤 컬럼이 통째로 사라졌다.
    cut_src = blank_quoted(body_sc)
    depth = paren_depth(cut_src)
    cuts = [0]
    for i, c in enumerate(cut_src):
        if c == ',' and not depth[i]:
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
        # `--` 를 **찾는** 것은 이름을 덮은 사본에서 한다. `"a--b"` 라는 컬럼 이름
        # 안의 두 글자가 줄 주석의 시작으로 잡혀, 이름의 뒤쪽(`b" text`)까지 설명에
        # 딸려 들어갔다. 길이가 같아 자리가 그대로 맞으므로 **내용은 seg_ms 에서**
        # 원문대로 꺼낸다. 아래 소유 판정이 `code`(=body_sc)를 그대로 쓰는 것은
        # 일부러다 — 거기서는 이름도 '이 줄에 코드가 있다' 는 증거다.
        for mm in re.finditer(r'--[^\n]*', blank_quoted(seg_ms)):
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
#
# 이름 **안**의 따옴표는 두 개로 적는다 — Postgres 에서 `"a""b"` 는 `a"b` 라는 이름
# 하나다. `"[^"]*"` 로 재던 때는 첫 `""` 에서 이름이 끊겨 `"a"` 만 집혔고, 남은 `"b"`
# 가 뒤 규칙과 어긋나 그 컬럼이 **경고 한 줄 없이 사라졌다.** 이름 자리가 헤더면
# `CREATE TABLE "a""b" (…)` 가 통째로 사라졌다(문 하나가 없던 일이 된다). 벗기는 쪽
# (`unq`)은 처음부터 `""` 를 한 글자로 되돌리고 있었다 — **집는 쪽**만 못 집었다.
#
# 갈래가 **둘**인 데는 재 본 까닭이 있다.
#
# 첫 갈래가 `""` 를 넘는 판이다. 넘는 대가는 **닫는 따옴표를 더 멀리서 찾는다**는
# 것이고, 짝이 안 맞는 입력에서는 그 '더 멀리'가 파일 끝까지 간다. 재 보니 정말
# 그랬다: `CREATE TABLE """ (…); CREATE TABLE c (… REFERENCES """ (id));` 에서
# 이름 하나가 **두 문을 통째로 삼켜** 뒤의 `c` 가 사라졌다(HEAD 는 둘 다 냈다).
# 그래서 첫 갈래는 **줄을 안 넘는다**(`[^"\n]`). 이름 안의 줄바꿈은 문법으로는
# 되지만 pg_dump 는 안 내놓고, 삼킴은 언제나 줄을 넘어야 벌어진다.
#
# 그런데 줄을 막는 것만으로는 **HEAD 가 되던 것을 깬다** — `CREATE TABLE "a\nb" (…)`
# 를 HEAD 는 읽었는데 첫 갈래는 못 읽어 그 테이블이 사라졌다. 그래서 둘째 갈래로
# 예전 조각(`"[^"]*"`)을 그대로 뒤에 둔다: `""` 를 넘을 수 있으면 넘고, 못 넘으면
# **예전과 글자 하나까지 같은 것을 문다.** 새 갈래가 더는 못 잃게 하는 안전망이다.
#
# 안전망은 '더 잃지 않는다' 까지다 — **줄바꿈과 `""` 를 함께 든 이름은 둘 다 못
# 문다.** `CREATE TABLE "a\n""b" (…)` 는 ①이 줄에서 막히고 ②는 `"a\n"` 까지만 물어
# 헤더가 안 맞고, 그 문이 **경고 한 줄 없이** 사라진다(`dropped` 에도 안 들어가
# `parse_create` 가 '읽지 못했다' 를 못 적는다). PG16 이 받는 이름이다. HEAD 도
# 똑같이 잃었으므로 회귀는 아니지만, 고쳐지지 않은 채 남아 있는 구멍이다.
#
# `""` 는 두 글자를 함께 먹는다. `[^"\n]` 는 `"` 를 못 먹으므로 첫 갈래 안의 두
# 조각은 겹치지 않고, 되짚기가 갈라지지 않는다. 짝 없는 `"` 는 어느 쪽으로도 못
# 지나가므로 `"a" b "c"` 를 하나로 잇지 않는다(잇자면 `""` 가 필요한데 `" ` 는
# 그것이 아니다).
#
# 둘째 갈래에 **`\n` 을 못박아 넣은** 것은 속도 때문이다. 그냥 `"[^"]*"` 로 두면
# 줄바꿈이 없는 이름은 두 갈래가 **똑같은 것을 문다** — 겹치는 갈래는 되짚기를
# 두 배로 가른다. 이 조각은 `_INPAREN` 안에서 `(?:이름|[^)])+\)` 로 쓰이는데, 짝
# 없는 괄호를 만나면 정규식이 끝까지 되짚어 오고, 그때 갈래가 겹친 만큼 **글자 수에
# 지수로** 터진다(그 지수 성질 자체는 바깥 `[^)]` 도 `"` 를 물 수 있어서 생기는
# HEAD 부터의 것이다). 첫 갈래가 줄을 안 넘으므로, 둘째 갈래가 **줄을 반드시 하나
# 넘게** 하면 두 갈래는 같은 자리에서 절대 함께 안 물린다 — 그러면서 무는 것은
# `"[^"]*"` 를 뒤에 두던 판과 **한 글자도 다르지 않다**(확인: `" a \n 공백 ) ,` 로
# 만든 길이 0~7 문자열 335,923개 × 모든 시작 자리에서 무는 자리가 어긋난 곳 0).
#
# 겹침을 없앤 이득은 **상수배가 아니라 글자 수와 함께 자란다.** `PRIMARY KEY (`
# 뒤에 조각을 N 번 붙이고 괄호를 안 닫은 입력에서, 겹치는 판(둘째 갈래를 그냥
# `"[^"]*"` 로 둔 것) 대비 지금 판이:
#   조각 `""a` : N=6 6.3배 · N=10 24.5배 · N=12 49.7배 · N=15 135.9배
#   조각 `"a" `: N=6 8.1배 · N=10 46.5배 · N=12 108배  · N=14 244.8배
#
# 그래도 **HEAD 보다는 느리다.** 그 배수도 자란다 — 여기 수를 적는 것은 그 자람을
# 숨기지 않기 위해서다. `""` 가 **없는** 이름에서는 글자 수와 무관하게 평평한
# 1.5~1.8배다(N=6 1.48 · N=8~14 1.7~1.8). `""` 가 **촘촘한** 이름에서는 계속 오른다:
# N=6 2.4 · N=8 3.9 · N=10 4.8 · N=12 6.2 · N=14 8.8 · N=17 13.0. 절대값으로는
# N=17 에서 HEAD 1.03초 → 지금 13.4초다. 여기 적힌 배수는 **상한이 아니다.**
#
# (위 수는 전부 이 저장소에서 2026-08-05 에 다시 잰 것이다. 앞서 이 자리에 적혀
#  있던 "10~20배 빨라져 HEAD 의 2~7배 안" 은 둘 다 틀렸다 — 이득은 20배보다 훨씬
#  크고, 배수는 잰 범위(N≲12)를 벗어나면 7배를 넘는다.)
#
# 시간으로만 잴 수 있는 자리라 회귀 시험도 시계를 본다: `selftest.py` 의
# `parse: an unclosed name list packed with "" finishes in time` 이 N=14 를 2초
# 안에 끝내는지 본다(지금 0.52초, 겹치는 판 48초).
#
# 측정: 이름 자리 21곳 × 이름 1033가지(`" , ( ) [ ] ' - ; $ . 탭 -- /* */ ""` 의
# 곱집합) = 21693칸 + 무작위 문서 4000건(씨앗 5개) + 컬럼 이름 1031가지를 HEAD 와
# 맞대어, **성한 입력에서 달라진 칸 0**, `""` 가 든 이름은 자리마다 203가지가 새로
# 살았고, 테이블·컬럼이 줄어든 칸 0.
_QID = (r'(?:"[^"\n]*(?:""[^"\n]*)*"'   # ① 안의 `""` 를 넘는다 (줄은 안 넘는다)
        r'|"[^"]*\n[^"]*")')            # ② 줄을 넘는 이름만 — 예전 그대로, 안전망
_ID = r'(?:' + _QID + r'|\w+)'    # 이름 한 조각 (안 잡는다)
_IDC = r'(' + _QID + r'|\w+)'     # 같은 것, 잡는다


def unq(s):
    """따옴표 친 식별자에서 따옴표만 벗긴다. 안의 `""` 는 따옴표 한 개다."""
    if s is None:
        return None
    s = s.strip()
    return s[1:-1].replace('""', '"') if len(s) >= 2 and s[0] == s[-1] == '"' else s


def _names(text):
    """콤마로 갈라 이름 목록을 만든다 (PK·FK·UNIQUE 의 괄호 안).

    콤마는 **따옴표 밖의 것만** 구분자다. `text.split(',')` 이던 때는
    `PRIMARY KEY ("a,b")` 가 `a`·`b"` 두 컬럼으로 갈려, 있지도 않은 컬럼 이름이
    PK 칸에 실렸다 — `blank_quoted` 가 막는 것과 같은 부류다. 여기서는 잘라 낸
    조각을 **그대로 써야** 하므로 덮는 대신 따옴표 친 토막을 통째로 집는다.

    토막을 집는 갈래는 `_QID` 다 — 이름 안의 `""` 를 넘는다. 넘지 않던 때도 `"a""b"`
    는 `"a"` + `"b"` 로 **두 번에 나눠** 물려 결과가 같았지만(둘 다 같은 조각 안이라
    콤마가 안 새어 나왔다), 규칙이 자리마다 다르면 다음 사람이 한쪽만 고친다."""
    return [unq(c) for c in re.findall(r'(?:' + _QID + r'|[^,])+', text) if c.strip()]


# 컬럼이 아니라 테이블 전체에 걸리는 것들. 예전엔 CHECK·UNIQUE·LIKE 가 이름이
# 'CHECK' 인 가짜 컬럼으로 문서에 실렸다.
_TABLE_LEVEL = re.compile(
    r'(?:CONSTRAINT|PRIMARY\s+KEY|FOREIGN\s+KEY|UNIQUE|CHECK|EXCLUDE|LIKE|INHERITS|'
    r'PARTITION)\b', re.I)
_ON_DELETE = r'ON\s+DELETE\s+(CASCADE|RESTRICT|SET\s+NULL|SET\s+DEFAULT|NO\s+ACTION)'

# `PRIMARY KEY (…)`·`FOREIGN KEY (…)`·`UNIQUE (…)`·`REFERENCES t (…)` 의 **이름 목록**.
# 닫는 괄호는 따옴표 **밖**의 것만 끝이다 — `[^)]+` 이던 때는 `PRIMARY KEY ("a)b")` 가
# 이름 한가운데서 끊겨 `"a` 라는 있지도 않은 컬럼이 PK 칸에 실렸다. 짝이 되는 `_names`
# 가 콤마를 같은 규칙으로 보므로 둘을 함께 고쳐야 한다(한쪽만 고치면 여전히 틀린다).
#
# **따옴표가 없는 입력에서는 `[^)]+` 과 글자 하나까지 같은 것을 문다** — 첫 갈래가
# `"` 로 시작할 때만 켜지기 때문이다. 그래서 pg_dump 가 내놓는 흔한 DDL 의 결과는
# 안 바뀐다. 타입 표기(`numeric(10,2)`)와 `_decl` 의 REFERENCES 걷어내기는 이름
# 목록이 아니므로 여기 규칙을 대지 않는다.
#
# 따옴표 갈래는 `_names` 와 같은 `_QID` 다 — 이름 안의 `""` 를 넘는다. 여기도 넘지
# 않던 때와 **무는 자리는 같다**(`"a"` + `"b"` 로 나눠 물어도 둘 다 이 조각 안이라
# `)` 가 안 새어 나왔다). 그래도 셋을 한 조각으로 묶는다 — 규칙이 갈리면 반만 고친다.
#
# 뒷 갈래는 `[^")]` 가 **아니라** `[^)]` 다 — HEAD 그대로다. `"` 를 빼면 두 갈래의
# 첫 글자가 안 겹쳐 되짚기가 선형이 되고 그것이 탐나서 한 번 해 봤는데, 짝 없는
# 따옴표가 든 입력에서 이름 목록이 거기서 끊겨 **없는 UNIQUE 가 생겨났다**(무작위
# 문서 4000건 중 82건이 HEAD 와 달라졌고, 그 안에 없는 제약을 적은 것이 있었다).
# 있지도 않은 제약을 적느니 느린 편이 낫다. 속도는 `_QID` 쪽 `(?!")` 로 벌었다.
_INPAREN = r'((?:' + _QID + r'|[^)])+)'


_REF_HEAD = re.compile(r'\bREFERENCES\s+(?:' + _IDC + r'\s*\.\s*)?' + _IDC +
                       r'\s*(?:\(' + _INPAREN + r'\))?', re.I)


def _refs_all(code):
    """Every REFERENCES clause, each bounded before the next one."""
    matches = list(_REF_HEAD.finditer(code))
    out = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(code)
        cols = _names(match.group(3) or '')
        rule = re.search(_ON_DELETE, code[match.end():end], re.I)
        out.append((unq(match.group(1)), unq(match.group(2)), cols or ['id'],
                    ' '.join((rule.group(1) if rule else 'NO ACTION').split()).upper()))
    return out


def _refs(code):
    """REFERENCES … 첫 건 → (부모스키마, 부모, [부모컬럼…], 삭제규칙). 없으면 None.

    부모 컬럼을 하나만 받던 때는 복합 FK 의 두 컬럼이 모두 'id' 를 가리키는 것으로
    적혀, 있지도 않은 관계가 문서에 실렸다. introspect 는 자리끼리 짝짓는다.

    삭제 규칙은 낱말을 못박아 읽는다. `[A-Z ]+` 로 긁던 예전 방식은
    `ON DELETE CASCADE ON UPDATE CASCADE` 를 'CASCADE ON' 으로 만들어 문서에 실었다.
    """
    refs = _refs_all(code)
    return refs[0] if refs else None


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


def _default_constraint_name(table, columns, suffix):
    """PostgreSQL's usual name for an unnamed PK/UQ/FK constraint."""
    middle = '_'.join(columns)
    return f'{table}_{middle}_{suffix}' if middle else f'{table}_{suffix}'


# DEFAULT 값을 끊는 낱말들 — 컬럼 제약이 시작될 수 있는 자리.
#
# 앞의 lookbehind 가 이 식의 전부다. 여기서 두 번 넘어졌으므로 무엇을 지키는지 적어 둔다.
#   · `\s+(?:NOT\s+NULL|…)` — 매치가 **공백에서** 시작한다. 그런데 경계를 재는 것은
#     가린 사본이고 거기서 문자열 리터럴은 **같은 길이의 공백**이다. 그래서
#     `DEFAULT 'x, y' NOT NULL` 의 사본 `DEFAULT        NOT NULL` 에서는 그 `\s+` 가
#     리터럴이 있던 자리부터 물어, 기본값이 통째로 빈 값이 됐다 — 따옴표 친 기본값
#     뒤에 한 마디라도 더 붙으면 전부.
#   · `\b(?:NOT\s+NULL|…)` — 매치가 낱말에서 시작하지만 **앞에 무엇이 오는지 안 본다**.
#     그래서 `ARRAY[NULL]`·`(NULL)`·`coalesce(a,NULL)` 의 `NULL` 에도 걸려
#     `ARRAY[`·`(`·`coalesce(a` 로 잘렸다.
# 필요한 것은 '앞이 무엇인지 보되 매치는 낱말에서 시작' 이다. lookbehind 는 폭을
# 소비하지 않으므로 `.start()` 가 낱말 자리가 된다 — 리터럴이 있던 공백은 그 앞에 남는다.
# 뒤의 `\b` 는 낱말이 더 길어지는 경우를 지킨다: `NULLIF(a,b)` 의 `NULL` 은 경계가 아니다.
#
# 앞자리로 공백만이 아니라 `)`·`]` 도 받는다. Postgres 렉서는 그 뒤에 공백을 요구하지
# 않아 `DEFAULT now()NOT NULL` 은 멀쩡한 DDL 인데, 공백만 보던 HEAD 는 기본값을
# `now()NOT` 으로 읽었다. 여는 쪽(`(`·`[`)과 `,` 를 안 받는 것이 이 식의 요점이므로
# 닫는 쪽을 받아도 `ARRAY[NULL]`·`(NULL)`·`coalesce(a,NULL)` 은 그대로 안 걸린다.
_DFLT_STOP = re.compile(r'(?<=[\s)\]])(?:NOT\s+NULL|NULL|PRIMARY|UNIQUE|REFERENCES|'
                        r'CHECK|GENERATED|COLLATE)\b', re.I)


def _default_end(tail):
    """가린 사본 `tail` 에서 DEFAULT 값이 끝나는 자리 (끝까지면 None).

    공백 앞뒤만으로는 모자란다. 컬럼 제약은 **괄호 밖**에만 올 수 있는데 같은 낱말이
    식 **안**에도 공백을 앞세우고 나타난다 — `DEFAULT coalesce(a, NULL)`,
    `DEFAULT (CASE WHEN x THEN 1 ELSE NULL END)`. 그래서 깊이 0 인 매치만 경계로 센다.
    (`ELSE NULL END` 처럼 괄호 없이 쓴 식은 여전히 못 가린다 — 정규식으로 식을 끝까지
     읽는 일은 하지 않는다. 그건 파서가 할 일이고, 여기서는 HEAD 와 같게 둔다.)

    큰따옴표 식별자는 깊이를 셀 때만 덮는다 — 이름 안의 `(` 하나가 뒤따르는 제약을
    통째로 안 보이게 만들기 때문이다 (`blank_quoted` 참고).

    깊이는 `split_top_level` 과 **같은 함수**로 잰다. 예전엔 여기서 세면서 지나가되
    음수를 `depth <= 0` 으로 눌렀는데, 그러면 닫는 쪽이 남는 경우만 막고 **여는 쪽이
    남는** 경우는 못 막는다 — `DEFAULT [1 NOT NULL` 의 `NOT NULL` 이 깊이 1 로 보여
    경계가 아니게 되고, 기본값이 `[1 NOT NULL` 통째가 됐다. 짝을 먼저 맞추면 짝 없는
    `[` 는 아예 안 세어져 `[1` 로 끊긴다(그 기호를 안 세던 HEAD 와 같다).
    """
    scan = blank_quoted(tail)
    depth = paren_depth(scan)
    case_depth = [0] * len(scan)
    level, cursor = 0, 0
    for token in re.finditer(r'\b(?:CASE|END)\b', scan, re.I):
        for i in range(cursor, token.start()):
            case_depth[i] = level
        word = token.group(0).upper()
        if word == 'CASE':
            level += 1
        for i in range(token.start(), token.end()):
            case_depth[i] = level
        if word == 'END' and level:
            level -= 1
        cursor = token.end()
    for i in range(cursor, len(scan)):
        case_depth[i] = level
    for m in _DFLT_STOP.finditer(scan):
        if not depth[m.start()] and not case_depth[m.start()]:
            return m.start()
    return None


def _column(cname, rest, comment, added):
    """컬럼 선언 하나 → (컬럼, 인라인PK 인가, 인라인UNIQUE 인가, REFERENCES 또는 None)

    `CREATE TABLE (…)` 의 컬럼과 `ALTER TABLE … ADD COLUMN` 뒤에 오는 것은 **같은
    문법** 이다. 그런데 판정은 두 벌로 갈라져 있었고, ADD COLUMN 쪽만 규율 밖이었다:
    구조를 원본 문자열에서 봤다(`'NOT NULL' in rest.upper()`). 그래서
    `ADD COLUMN memo text DEFAULT 'NOT NULL 아님'` 은 NOT NULL 컬럼이 되고 기본값은
    `'NOT` 으로 잘렸으며, `DEFAULT 'IDENTITY 아님'` 은 identity 가 됐다. REFERENCES
    는 아예 읽지 않아 `ADD COLUMN user_id bigint REFERENCES users(id)` 의 관계가
    경고 한 줄 없이 사라졌다. 규칙을 복사해 두 벌로 두면 다음 사람은 또 한쪽만 고친다
    — 판정을 여기 한 자리로 모으고 양쪽이 이것만 부른다.

    규율은 parse_create 가 쓰던 것 그대로다:
      · 구조 판정(NOT NULL·PRIMARY KEY·UNIQUE·REFERENCES)은 반드시 **가린 사본** 에서
        한다. 원본에서 보면 DEFAULT 'PRIMARY KEY 설명' 같은 값이 진짜 제약이 된다.
      · 값의 **경계** 는 가린 사본에서 찾고 **값** 은 원본에서 꺼낸다. 가린 사본에서
        값까지 읽으면 문자열이 공백이라 빈 값이 되고, 원본에서 경계를 찾으면
        DEFAULT 'see REFERENCES users' 가 `'see` 로 잘린다.
      · not_null·identity 는 `_decl()` 로 REFERENCES 절을 걷어낸 뒤에 본다. 안 그러면
        `REFERENCES serial_numbers(id)` 의 부모 이름이 그 컬럼을 identity 로 만든다.
    """
    # 앞서 만든 사본은 공백을 접으면서 원본과 길이가 어긋났으므로, 이 선언부 하나만
    # 다시 가린다 — 같은 길이라야 값을 위치로 꺼낼 수 있다.
    rest_sc = mask(rest)[2]
    decl = _decl(rest_sc)

    dflt = None
    dm = re.search(r'\bDEFAULT\b', rest_sc, re.I)
    if dm:
        tail = rest_sc[dm.end():]
        # 경계는 **뒤에 오는 낱말이 시작하는 자리** 로 잰다 (`_DFLT_STOP` 참고).
        # 자른 뒤 남는 앞뒤 공백은 아래 strip 이 걷는다.
        stop = _default_end(tail)
        dflt = rest[dm.end():dm.end() + (len(tail) if stop is None else stop)]

    col = {
        'name': cname,
        'type': _type(rest),
        # IDENTITY·serial 은 NOT NULL 을 적지 않아도 NOT NULL 이다.
        # 낱말로 본다. 부분 문자열로 재면 REFERENCES serial_numbers(id) 가
        # 그 컬럼을 identity·NOT NULL 로 만든다.
        'not_null': bool(re.search(r'\bNOT\s+NULL\b|\bIDENTITY\b|\w*SERIAL\b(?!\s*_)',
                                   decl, re.I)),
        'default': dflt.strip().rstrip(',') if dflt else '',
        'identity': bool(re.search(r'\bIDENTITY\b|\b(?:BIG|SMALL)?SERIAL\b', decl, re.I)),
        'comment': comment,
        'added': added,
    }
    return (col,
            bool(re.search(r'\bPRIMARY\s+KEY\b', decl, re.I)),
            bool(re.search(r'\bUNIQUE\b', decl, re.I)),
            _refs_all(rest_sc))


def _inline_constraints(code, keyword):
    """Return names attached directly to column constraints of one kind."""
    return [unq(match.group(1)) for match in re.finditer(
        r'\bCONSTRAINT\s+' + _IDC + r'\s+(?=' + keyword + r'\b)', code, re.I)]


def parse_create(sql: str, src: str, tables: dict, dup: set, dropped: dict = None,
                 unread_out=None):
    """`dropped` 는 **읽지 못해 버린 CREATE TABLE** 을 내보내는 자리다 — {키: 스키마}.

    버리기만 하고 그 사실을 알리지 않으면, 같은 이름을 대는 뒤 문장들이 그 테이블을
    **다시 세운다** — 무엇이 왜 되살아나는지는 `parse_alter`·`main` 의 그 자리에 적었다.

    키는 성공했을 때 쓰였을 바로 그 키다(`f'{sch}.{name}' if name in dup else name`).
    묻는 쪽 둘이 '이 키로 tables 에 넣을까' 를 묻고 있어 같은 자로 재야 한다. 스키마를
    따로 들고 다니는 것은 **키만으로는 모자라기** 때문이다: 이름이 한 스키마에만 있으면
    키에 스키마가 안 붙어(`q`), 버린 `public.q` 와 성한 `audit.q` 가 같은 키가 된다.
    실제로 `CREATE TABLE q (…어긋남…); ALTER TABLE audit.q ADD COLUMN z;` 에서 키만
    보던 판은 **남의 테이블인 audit.q 를 함께 버렸다.** 스키마 글자가 양쪽에 다 있는
    자리(ALTER)에서는 그것까지 맞춰 본다.
    """
    ms, mc, msc = mask(sql)
    head_pat = re.compile(r'CREATE\s+(?:UNLOGGED\s+|TEMP(?:ORARY)?\s+)?TABLE\s+'
                          r'(?:IF\s+NOT\s+EXISTS\s+)?'
                          r'(?:' + _IDC + r'\s*\.\s*)?' + _IDC + r'\s*\(', re.I)
    # 짝을 세는 사본은 **이름까지 덮은 것** 이다 (`blank_quoted` 참고). msc 를 그대로
    # 세던 때는 이름 안의 괄호 하나가 그 `CREATE TABLE` 문을 통째로 삼켰다 —
    # `c text COLLATE "a(b"` 는 depth 가 안 닫혀 `if depth: continue` 로 빠지고,
    # `"a)b"` 는 본문이 거기서 끊겨 뒤 컬럼이 사라졌다. 둘 다 **경고 한 줄 없이** 다.
    # 이름을 읽는 head_pat 와 본문 슬라이스는 msc 를 그대로 쓴다 — 덮은 사본에서
    # 이름을 읽으면 `_IDC` 가 빈 자리를 보게 된다.
    msc_q = blank_quoted(msc)
    # 짝이 안 맞는 괄호로 **읽지 못한** CREATE TABLE — 아래 두 자리에서 모인다.
    # 이름을 대고 넘어가려고 들고 다닌다 (파일 하나가 끝날 때 한 줄로 낸다).
    unread = unread_out if unread_out is not None else []
    for m in head_pat.finditer(msc):
        sch, name = unq(m.group(1)) or 'public', unq(m.group(2))
        i, depth = m.end(), 1                     # 괄호 짝으로 본문을 자른다
        while i < len(msc_q) and depth:
            # 본문은 **제 문을 넘지 못한다.** 넘던 때는 짝 안 맞는 `(` 하나가 뒤
            # 문장을 통째로 빨아들였다 — `CREATE TABLE r ( a int DEFAULT (1, b text );`
            # 다음에 `CREATE TABLE u (…)` 가 오면 짝은 **u 의 닫는 괄호** 에서
            # 맞아떨어져, r 의 a 가 `(1, b text ); CREATE TABLE u ( a int DEFAULT 1)`
            # 을 기본값으로 들고 정의서에 실렸다. 경고는 한 줄도 없었다.
            # 성한 DDL 의 본문에는 `;` 가 있을 수 없다 — 리터럴·달러인용·주석 속의
            # 것은 mask 가, 큰따옴표 이름 속의 것은 blank_quoted 가 이미 지웠다.
            if msc_q[i] == ';':
                break                             # 짝을 못 찾은 채 문이 끝났다
            if msc_q[i] == '(':
                depth += 1
            elif msc_q[i] == ')':
                depth -= 1
                if not depth:
                    break
            i += 1
        # ── 짝이 안 맞으면 무엇을 하는가 ──────────────────────────────────────
        # 본문의 끝은 **여는 괄호의 짝** 이다. 짝이 맞는 DDL 에서는 위 순차 세기가
        # 그 자리를 정확히 짚으므로 아래 두 갈래는 **닿지 않는다** — 그래서 성한
        # 입력에서 달라지는 칸이 원리상 0 이다. 안 맞을 때만 여기로 온다.
        #
        # 대괄호와 왜 다르게 다루는가. `paren_depth` 는 짝 없는 기호를 **없는 셈 치고**
        # 넘어가는데(그 주석 참고), 그것이 옳은 이유는 대괄호가 본문의 **경계를 정하지
        # 않기** 때문이다 — `DEFAULT 1]` 의 `]` 는 컬럼 정의 안에 섞인 잡음일 뿐,
        # 테이블이 어디서 끝나는지는 여전히 괄호가 안다. 그래서 그 문은 끝까지 읽힌다
        # (`a, b, c`). 괄호는 그 경계 자체다. 짝이 어긋나면 **어느 컬럼이 이 테이블
        # 것인지를 알 방법이 없다** — 없는 셈 치는 처방을 여기에 그대로 대면 파서가
        # 경계를 스스로 지어내는 것이 되고, Postgres 가 거부한 DDL 이 정의서에서는
        # 멀쩡한 표로 실린다. 반쯤 읽은 것을 완성본처럼 내놓지 않는다는 것이 이 파일이
        # `_rows(core=True)`·`fetch_existing` 에서 이미 고른 답이라, 여기도 같게 둔다:
        # **짓지 않고 버리되, 이름을 대고 버린다.**
        #
        # 못 다루는 것은 적어 둔다. 아래 둘째 갈래는 `) ,` 라는 한 모양만 잡는다.
        # `DEFAULT 1)(,` 처럼 남는 `)` 뒤에 다시 `(` 가 오면 뒤가 통째로 짝이 맞아
        # 버려서, 본문은 `a` 에서 끊긴 채 아무 말도 못 한다. 넓히려면 '테이블 뒤에
        # 올 수 있는 것'(INHERITS·PARTITION BY·WITH·TABLESPACE …)을 다 알아야 하고,
        # 그것을 반만 알면 **성한 DDL 을 버리는** 쪽으로 틀린다.
        #
        # 대는 이름은 **DDL 이 적은 그대로** 다 — 스키마를 안 적었으면 안 붙인다.
        # 이 자리는 테이블이 만들어지기 전이라 키(`sch.name` 또는 `name`)가 없고,
        # 없는 키를 지어 대면 사람이 파일에서 찾을 수 없는 이름이 화면에 뜬다.
        # 어느 파일인지도 함께 댄다 — 한 번에 여러 파일을 읽으므로.
        said = f'{unq(m.group(1))}.{name}' if m.group(1) else name
        key = f'{sch}.{name}' if name in dup else name

        def give_up(_said=said, _key=key, _sch=sch):
            """이름을 대고 버린다 — 그리고 **버렸다는 것을 내보낸다.**"""
            unread.append(f'{_said} ({src})')
            if dropped is not None:
                dropped[_key] = _sch          # sch 는 이미 'public' 으로 채워진 실효값

        if depth:
            give_up()                             # 여는 괄호가 끝내 안 닫혔다
            continue
        # 남는 `)` 는 본문을 **너무 일찍** 끊는다: `a int DEFAULT 1), b text` 는
        # 그 `)` 를 닫는 괄호로 읽어 b 뒤가 통째로 문 밖으로 밀려났고, 테이블은
        # 컬럼 하나만 든 채 아무 말 없이 실렸다. 닫는 괄호 **바로 다음이 콤마** 인
        # 것은 성한 DDL 에 있을 수 없다 — 테이블 뒤에 오는 어떤 절도 콤마로
        # 시작하지 않는다(INHERITS·PARTITION BY·WITH·USING·ON COMMIT·TABLESPACE·
        # AS SELECT …). 그 한 모양만 보고, 그때는 이 문을 못 읽은 것으로 친다.
        # 이 꼬리는 문 끝(`;`)에서 끊지 않아도 된다 — 끊은 쪽이 공백뿐이면 안 끊은
        # 쪽의 첫 글자는 그 `;` 라 어차피 콤마가 아니고, 아니면 두 쪽의 첫 글자가
        # 같다. (한때 끊어 두었다가 지웠다. 뮤턴트로 재 보니 답이 달라지는 입력이
        # 하나도 없어, 지키는 것 없는 줄이 규칙만 둘로 보이게 했다.)
        #
        # 넓히면 안 된다. '콤마가 **어딘가** 있다' 로 재던 판은 세미콜론을 빠뜨린
        # `CREATE TABLE a (x int)` 뒤의 `ALTER TABLE a ADD COLUMN y int, …` 와
        # `WITH (fillfactor = 70, autovacuum_enabled = false)` 를 함께 물어
        # **성한 테이블을 버렸다**.
        if msc_q[i + 1:].lstrip().startswith(','):
            give_up()
            continue
        body_mc, body_ms, body_sc = mc[m.end():i], ms[m.end():i], msc[m.end():i]
        t = tables.setdefault(key, {
            'name': name, 'origin': 'new', 'src_file': src, 'schema': sch,
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
            '_constraints': {},
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
            if _TABLE_LEVEL.match(code):
                named = re.match(r'CONSTRAINT\s+' + _IDC + r'\s+', code, re.I)
                cname = unq(named.group(1)) if named else None
                pk = re.search(r'PRIMARY\s+KEY\s*\(' + _INPAREN + r'\)', code, re.I)
                if pk:
                    t['pk'] = _names(pk.group(1))
                    key = cname or _default_constraint_name(name, [], 'pkey')
                    t['_constraints'][key] = ('pk', list(t['pk']))
                fk = re.search(r'FOREIGN\s+KEY\s*\(' + _INPAREN + r'\)', code, re.I)
                ref = _refs(code)
                if fk and ref:
                    rt = _ref_key(ref, sch, dup)
                    kids = _names(fk.group(1))
                    if len(kids) == len(ref[2]):
                        for idx, c in enumerate(kids):
                            row = {'column': c, 'ref_table': rt,
                                   'ref_column': ref[2][idx], 'on_delete': ref[3]}
                            key = cname or _default_constraint_name(name, kids, 'fkey')
                            row['_constraint'] = key
                            t['fks'].append(row)
                        t['_constraints'][key] = ('fk', kids)
                uq = re.match(r'(?:CONSTRAINT\s+' + _ID + r'\s+)?UNIQUE\s*\(' + _INPAREN + r'\)',
                              code, re.I)
                if uq:
                    cols = _names(uq.group(1))
                    t['uniques'].append(cols)
                    key = cname or _default_constraint_name(name, cols, 'key')
                    t['_constraints'][key] = ('uq', cols)
                continue

            col = re.match(r'^' + _IDC + r'\s+(.+)$', raw_code)  # 따옴표 친 컬럼명도 받는다
            if not col:
                continue
            cname, rest = unq(col.group(1)), col.group(2).strip()
            c, is_pk, is_uq, refs = _column(cname, rest, comment, False)
            rest_sc = mask(rest)[2]
            t['columns'].append(c)
            if is_pk:
                t['pk'].append(cname)
                constraints = (_inline_constraints(rest_sc, r'PRIMARY\s+KEY')
                               or [_default_constraint_name(name, [], 'pkey')])
                for constraint in constraints:
                    t['_constraints'][constraint] = ('pk', list(t['pk']))
            if is_uq:
                t['uniques'].append([cname])
                constraints = (_inline_constraints(rest_sc, r'UNIQUE')
                               or [_default_constraint_name(name, [cname], 'key')])
                for constraint in constraints:
                    t['_constraints'][constraint] = ('uq', [cname])
            named_refs = _inline_constraints(rest_sc, r'REFERENCES')
            for idx, ref in enumerate(refs):
                key = (named_refs[idx] if idx < len(named_refs)
                       else _default_constraint_name(name, [cname], 'fkey'))
                t['fks'].append({'column': cname, 'ref_table': _ref_key(ref, sch, dup),
                                 'ref_column': ref[2][0], 'on_delete': ref[3],
                                 '_constraint': key})
                t['_constraints'][key] = ('fk', [cname])

    # 버린 것은 이름을 대고 버린다. 예전엔 `continue` 한 줄이 전부라, 괄호 하나가
    # 어긋난 파일은 테이블 0개에 rc 0 으로 조용히 끝났다 — 화면에는 '테이블 0개'
    # 말고는 아무 단서가 없어서 DDL 을 다시 들여다볼 이유조차 남지 않았다.
    # 문구는 `log.query_incomplete` 를 그대로 쓴다. 그 두 문장('읽지 못했다',
    # '문서에서 딱 그만큼이 빠진다')이 여기서 둘 다 참이어야 한다.
    # (fetch_existing 이 이 문구를 마다한 이유가 **앞**문장이 그쪽에서는 거짓이라서였다.
    # 여기서 앞문장은 참이다 — 정말로 못 읽었다.)
    #
    # **뒷**문장은 거저 참이 되지 않는다. 버리기만 하고 끝냈을 때 이랬다:
    #     CREATE TABLE q ( a int DEFAULT 1), b text );  ALTER TABLE q ADD COLUMN z int;
    #   → [warn] … q … 딱 그만큼이 빠진다
    #     [existing] q  컬럼 1개        ← 빠지지 않았다. 성격까지 바뀌어 남았다
    # `parse_alter` 가 없는 테이블에 스텁을 세우는 자리와 `main` 의 FK 대상 스텁이
    # 이름만 보고 q 를 **되살렸다**. 그래서 뒷문장이 이 자리에서 거짓이 됐다.
    # 세 가지가 한꺼번에 틀렸다: ⑴ 빠진다고 말해 놓고 안 빠졌다 ⑵ 배지가 `NEW` 에서
    # `기존` 으로 뒤집혔다(HEAD 는 origin='new' cols=[a,z], 그때는 'existing' cols=[z])
    # ⑶ 신규 테이블인데 `log.ddl_no_db` 가 'ERD_DB/ERD_PSQL 을 주면 채워진다' 고 안내해
    # 접속 문제를 쫓게 만들었다 — DB 에 있을 리 없는 테이블이다.
    #
    # 그래서 버린 키를 `dropped` 로 내보내고, 되살리는 두 자리에서 막는다. 고른 답은
    # **버린 것을 끝까지 버린다** 이다 — 남은 갈래(스텁을 인정하고 문구를 바꾼다)는
    # 어느 기존 카탈로그 키로도 참이 되지 않는다. `log.ddl_no_db` 는 'DDL 에 정의가
    # 없는' 이 거짓이고(정의는 있다, 못 읽었을 뿐이다), `log.ddl_not_in_db` 는 DB 를
    # 뒤진 적이 있다는 말이라 접속 없이 도는 실행에서 거짓이다. 새 키는 이 자리에서
    # 만들 수 없다. 무엇보다, 컬럼 한 줄만 든 상자를 완성본처럼 싣지 않는다는 것이
    # 바로 위 갈래·`_rows(core=True)`·`fetch_existing` 이 이미 고른 답이다.
    #
    # 버린 테이블을 가리키던 ALTER·COMMENT·FK 는 함께 사라진다. 따로 알리지 않는 것은
    # 이 한 줄이 **테이블 이름** 을 대기 때문이다 — 'q 를 못 읽었고 q 만큼이 빠진다'
    # 는 q 에 붙는 모든 문장을 포함한다. 두 번 말하면 같은 사실이 두 가지 일로 읽힌다.
    if unread and unread_out is None:
        print(T('log.query_incomplete', list=', '.join(unread)))


def _stmts(pat, msc, msc_q):
    r"""`pat` 로 문의 머리를 찾아 (머리 매치, 문을 끝내는 `;` 자리) 를 차례로 낸다.

    문을 자르는 자리가 `parse_alter` 안에만 둘이라(ADD COLUMN·ADD CONSTRAINT) 규칙을
    한 벌로 둔다. 두 벌로 적어 두면 다음 사람이 또 한쪽만 고친다 — 이 파일이 이미
    여러 번 겪은 모양이고, 여기가 바로 그렇게 절반만 고쳐진 채 남아 있던 자리다.

    ── 요점: 끝을 재는 사본이 다르다 ──────────────────────────────────────────
    머리는 `msc`(문자열·주석만 가린 사본)에서 찾고, 끝나는 `;` 는 `msc_q`
    (거기에 **큰따옴표 이름까지 덮은** 사본)에서 찾는다. 예전엔 `(ADD\s+COLUMN\b.*?);`
    한 줄로 둘을 함께 했고, 그래서 **이름 안의 `;` 가 문을 끊었다.** Postgres 에서
    `"a;b"` 는 `a;b` 라는 이름 하나인데, 파서는 거기서 문이 끝난 줄 알았다:
      · `ALTER TABLE t ADD COLUMN "a;b" int;`      → 컬럼이 통째로 사라졌다
      · `ALTER TABLE t ADD COLUMN "a;b" int, ADD COLUMN c text;`
                                                   → **성한 c 까지** 함께 사라졌다
      · `ALTER TABLE t ADD CONSTRAINT c PRIMARY KEY ("a;b");`  → PK 칸이 비었다
      · `… FOREIGN KEY (a) REFERENCES p ("i;d");`  → 없는 컬럼 `id` 를 가리키는
        관계가 생겼다 (`_refs` 의 기본값이 켜졌다). 잃는 것보다 나쁜, **짓는** 쪽이다
      · 테이블이 아직 없으면 컬럼 0개짜리 `origin='existing'` 상자만 남아,
        `log.ddl_no_db` 가 '접속을 주면 채워진다' 고 없는 문제를 쫓게 했다
    전부 경고 한 줄 없이 벌어졌다. `blank_quoted` 를 대는 네 번째 자리다.

    ── 어디서부터 다시 읽는가 ────────────────────────────────────────────────
    다음 판은 그 `;` **다음**부터 본다 — `finditer` 가 매치를 소비하며 나아가던
    예전과 **같은 자리**다. 그래서 성한 DDL 에서는 낼 것도 도는 자리도 예전과 같다.
    한 문 안에서 머리를 다시 찾지 않으므로, 이름 안에 문을 통째로 적은
    `ADD COLUMN "a int; ALTER TABLE u ADD COLUMN z text" bigint` 이 남의 테이블 u 에
    **없는 컬럼 z 를 짓던 것**도 함께 멎는다(PG16 대조: u 에는 아무것도 안 붙는다).

    `;` 가 더 없으면 끝낸다. 예전 정규식도 `.*?;` 가 `;` 를 **요구**했으므로 뒤에
    `;` 가 하나도 없으면 어느 머리에서도 매치가 안 됐다 — 같은 자리에서 멎는다.
    (그래서 세미콜론 없이 끝나는 마지막 문을 새로 읽어 주지도 **않는다**. 검출을
     넓히는 것은 이 자리에서 할 일이 아니다 — 넓히는 뮤턴트가 성한 DDL 을 버리는
     것을 이 파서가 이미 실측으로 겪었다.)
    """
    pos = 0
    while True:
        m = pat.search(msc, pos)
        if not m:
            return
        end = msc_q.find(';', m.end())
        if end < 0:
            return
        yield m, end
        pos = end + 1


def sql_statements(sql):
    """Yield SQL statements in source order without splitting quoted semicolons."""
    masked = blank_quoted(mask(sql)[2])
    start = 0
    for i, char in enumerate(masked):
        if char == ';':
            yield sql[start:i + 1]
            start = i + 1
    if sql[start:].strip():
        yield sql[start:]


def parse_drop_table(sql, tables):
    """Apply DROP TABLE and remove relationships whose referenced table vanished."""
    _ms, _mc, msc = mask(sql)
    match = re.match(r'\s*DROP\s+TABLE\s+(?:IF\s+EXISTS\s+)?(.+?)(?:\s+(?:CASCADE|RESTRICT))?\s*;?\s*$',
                     msc, re.I | re.S)
    if not match:
        return
    for raw in split_top_level(match.group(1), match.group(1), match.group(1)):
        code = raw[1].strip()
        if not re.fullmatch(r'(?:' + _ID + r'\s*\.\s*)?' + _ID, code):
            continue
        parts = [unq(part) for part in re.findall(_ID, code)]
        sch, name = (parts if len(parts) == 2 else (None, parts[0]))
        table = _find(tables, sch, name)
        if table is None:
            continue
        key = next((k for k, value in tables.items() if value is table), None)
        if key is None:
            continue
        tables.pop(key)
        for other in tables.values():
            other['fks'] = [fk for fk in other['fks'] if fk['ref_table'] != key]


def parse_alter_state(sql: str, src: str, tables: dict, dup: set, dropped: dict = None):
    """ALTER TABLE state changes, applied in statement and subcommand order.

    ``parse_alter`` historically grew as separate regex passes.  That is adequate for
    extracting ADD clauses, but it cannot model a final schema once DROP/RENAME/TYPE
    clauses are present: all ADDs run before every other family regardless of source
    order.  This ordered pass is the canonical ALTER implementation used by ``main``.
    """
    ms, mc, msc = mask(sql)
    msc_q = blank_quoted(msc)
    if dropped is None:
        dropped = {}
    head = (r'ALTER\s+TABLE\s+(?:IF\s+EXISTS\s+)?(?:ONLY\s+)?'
            r'(?:' + _IDC + r'\s*\.\s*)?' + _IDC + r'\s+')

    def key_of(t):
        return next((k for k, v in tables.items() if v is t), None)

    def find_or_stub(sch, name):
        t = _find(tables, sch, name)
        if t is not None:
            return t
        key = f'{sch}.{name}' if sch and (name in dup or name in tables) else name
        if dropped.get(key) == (sch or 'public'):
            return None
        return tables.setdefault(key, {
            'name': name, 'origin': 'existing', 'src_file': src,
            'schema': sch or 'public', 'columns': [], 'pk': [], 'fks': [],
            'uniques': [], 'note': '', '_constraints': {},
        })

    def rename_column(t, old, new):
        col = next((c for c in t['columns'] if c['name'] == old), None)
        if col is None or any(c['name'] == new for c in t['columns']):
            return
        col['name'] = new
        t['pk'] = [new if c == old else c for c in t['pk']]
        t['uniques'] = [[new if c == old else c for c in u] for u in t['uniques']]
        t['_constraints'] = {
            name: (kind, [new if c == old else c for c in cols])
            for name, (kind, cols) in t.setdefault('_constraints', {}).items()
        }
        for fk in t['fks']:
            if fk['column'] == old:
                fk['column'] = new
        own_key = key_of(t)
        for other in tables.values():
            for fk in other['fks']:
                if fk['ref_table'] == own_key and fk['ref_column'] == old:
                    fk['ref_column'] = new

    def drop_column(t, name):
        if not any(c['name'] == name for c in t['columns']):
            return
        t['columns'] = [c for c in t['columns'] if c['name'] != name]
        t['pk'] = [c for c in t['pk'] if c != name]
        t['uniques'] = [u for u in t['uniques'] if name not in u]
        t['fks'] = [fk for fk in t['fks'] if fk['column'] != name]
        t['_constraints'] = {
            key: value for key, value in t.setdefault('_constraints', {}).items()
            if name not in value[1]
        }
        own_key = key_of(t)
        for other in tables.values():
            other['fks'] = [fk for fk in other['fks']
                            if not (fk['ref_table'] == own_key and fk['ref_column'] == name)]

    def rename_table(t, new):
        old = key_of(t)
        if old is None:
            return
        t['name'] = new
        old_items = list(tables.items())
        counts = {}
        for _key, item in old_items:
            counts[item['name']] = counts.get(item['name'], 0) + 1
        dup.clear()
        dup.update(name for name, count in counts.items() if count > 1)
        rekey = {}
        tables.clear()
        for old_key, item in old_items:
            new_key = (f"{item.get('schema') or 'public'}.{item['name']}"
                       if counts[item['name']] > 1 else item['name'])
            tables[new_key] = item
            rekey[old_key] = new_key
        for other in tables.values():
            for fk in other['fks']:
                fk['ref_table'] = rekey.get(fk['ref_table'], fk['ref_table'])

    pat = re.compile(head, re.S | re.I)
    for m, end in _stmts(pat, msc, msc_q):
        sch, name = unq(m.group(1)), unq(m.group(2))
        t = find_or_stub(sch, name)
        if t is None:
            continue
        t['altered_by'] = src
        pieces = split_top_level(mc[m.end():end], ms[m.end():end], msc[m.end():end])
        for raw_code, code, comment in pieces:
            raw_code, code = raw_code.strip(), code.strip()

            am = re.match(r'ADD\s+COLUMN\s+(?:IF\s+NOT\s+EXISTS\s+)?' +
                          _IDC + r'\s+(.+)$', raw_code, re.I | re.S)
            if am:
                cname, rest = unq(am.group(1)), am.group(2).strip()
                if any(c['name'] == cname for c in t['columns']):
                    continue
                c, is_pk, is_uq, refs = _column(cname, rest, comment, True)
                rest_sc = mask(rest)[2]
                t['columns'].append(c)
                if is_pk and cname not in t['pk']:
                    t['pk'].append(cname)
                    constraints = (_inline_constraints(rest_sc, r'PRIMARY\s+KEY')
                                   or [_default_constraint_name(t['name'], [], 'pkey')])
                    for key in constraints:
                        t.setdefault('_constraints', {})[key] = ('pk', list(t['pk']))
                if is_uq and [cname] not in t['uniques']:
                    t['uniques'].append([cname])
                    constraints = (_inline_constraints(rest_sc, r'UNIQUE')
                                   or [_default_constraint_name(t['name'], [cname], 'key')])
                    for key in constraints:
                        t.setdefault('_constraints', {})[key] = ('uq', [cname])
                named_refs = _inline_constraints(rest_sc, r'REFERENCES')
                for idx, ref in enumerate(refs):
                    key = (named_refs[idx] if idx < len(named_refs) else
                           _default_constraint_name(t['name'], [cname], 'fkey'))
                    t['fks'].append({
                        'column': cname,
                        'ref_table': _ref_key(ref, t.get('schema') or 'public', dup),
                        'ref_column': ref[2][0], 'on_delete': ref[3],
                        '_constraint': key})
                    t.setdefault('_constraints', {})[key] = ('fk', [cname])
                continue

            cm = re.match(r'ADD\s+CONSTRAINT\s+' + _IDC + r'\s+(.+)$', code,
                          re.I | re.S)
            if cm:
                constraint = unq(cm.group(1))
                clause = cm.group(2)
                pk = re.search(r'PRIMARY\s+KEY\s*\(' + _INPAREN + r'\)', clause, re.I)
                if pk:
                    t['pk'] = _names(pk.group(1))
                    t.setdefault('_constraints', {})[constraint] = ('pk', list(t['pk']))
                fk = re.search(r'FOREIGN\s+KEY\s*\(' + _INPAREN + r'\)', clause, re.I)
                ref = _refs(clause)
                if fk and ref:
                    kids, rt = _names(fk.group(1)), _ref_key(
                        ref, t.get('schema') or 'public', dup)
                    if len(kids) == len(ref[2]):
                        for idx, child in enumerate(kids):
                            t['fks'].append({
                                'column': child, 'ref_table': rt,
                                'ref_column': ref[2][idx], 'on_delete': ref[3],
                                '_constraint': constraint})
                        t.setdefault('_constraints', {})[constraint] = ('fk', kids)
                uq = re.match(r'UNIQUE\s*\(' + _INPAREN + r'\)', clause, re.I)
                if uq:
                    cols = _names(uq.group(1))
                    if cols not in t['uniques']:
                        t['uniques'].append(cols)
                    t.setdefault('_constraints', {})[constraint] = ('uq', cols)
                continue

            dm = re.match(r'DROP\s+CONSTRAINT\s+(?:IF\s+EXISTS\s+)?' + _IDC, code, re.I)
            if dm:
                constraint = unq(dm.group(1))
                kind_cols = t.setdefault('_constraints', {}).pop(constraint, None)
                if kind_cols:
                    kind, cols = kind_cols
                    if kind == 'pk':
                        t['pk'] = []
                    elif kind == 'uq':
                        still_declared = any(
                            other_kind == 'uq' and other_cols == cols
                            for other_kind, other_cols in t['_constraints'].values())
                        if not still_declared:
                            t['uniques'] = [u for u in t['uniques'] if u != cols]
                    elif kind == 'fk':
                        t['fks'] = [fk for fk in t['fks']
                                    if fk.get('_constraint') != constraint]
                continue

            dm = re.match(r'DROP\s+COLUMN\s+(?:IF\s+EXISTS\s+)?' + _IDC, code, re.I)
            if dm:
                drop_column(t, unq(dm.group(1)))
                continue
            rm = re.match(r'RENAME\s+COLUMN\s+' + _IDC + r'\s+TO\s+' + _IDC,
                          code, re.I)
            if rm:
                rename_column(t, unq(rm.group(1)), unq(rm.group(2)))
                continue
            rm = re.match(r'RENAME\s+TO\s+' + _IDC, code, re.I)
            if rm:
                rename_table(t, unq(rm.group(1)))
                continue

            cm = re.match(r'ALTER\s+COLUMN\s+' + _IDC + r'\s+(.+)$', raw_code,
                          re.I | re.S)
            if not cm:
                print(T('log.ddl_alter_unsupported', table=t['name'], clause=code[:120]))
                continue
            cname, action = unq(cm.group(1)), cm.group(2).strip()
            col = next((c for c in t['columns'] if c['name'] == cname), None)
            if col is None:
                continue
            if re.match(r'SET\s+NOT\s+NULL\b', action, re.I):
                col['not_null'] = True
            elif re.match(r'DROP\s+NOT\s+NULL\b', action, re.I):
                col['not_null'] = False
            elif re.match(r'DROP\s+DEFAULT\b', action, re.I):
                col['default'] = ''
            elif (x := re.match(r'SET\s+DEFAULT\s+(.+)$', action, re.I | re.S)):
                col['default'] = x.group(1).strip()
                if re.search(r'\bnextval\s*\(', col['default'], re.I):
                    col['identity'] = col['not_null'] = True
            elif (x := re.match(r'(?:SET\s+DATA\s+)?TYPE\s+(.+)$', action,
                                re.I | re.S)):
                typ = re.split(r'\s+USING\s+', x.group(1), maxsplit=1, flags=re.I)[0]
                col['type'] = _type(typ.strip())
            elif re.match(r'ADD\s+GENERATED\b', action, re.I):
                col['identity'] = col['not_null'] = True
            elif re.match(r'DROP\s+IDENTITY\b', action, re.I):
                col['identity'] = False
            else:
                print(T('log.ddl_alter_unsupported', table=t['name'], clause=code[:120]))


def _comment_value(tail):
    """Parse NULL, ordinary/E strings, and PostgreSQL dollar-quoted comment values."""
    tail = tail.lstrip()
    if re.match(r'NULL\b', tail, re.I):
        return ''
    dollar = re.match(r'(\$[A-Za-z_][A-Za-z_0-9]*\$|\$\$)', tail)
    if dollar:
        mark = dollar.group(1)
        end = tail.find(mark, len(mark))
        return None if end < 0 else tail[len(mark):end]
    extended = len(tail) >= 2 and tail[0] in 'eE' and tail[1] == "'"
    start = 1 if extended else 0
    if start >= len(tail) or tail[start] != "'":
        return None
    out, i = [], start + 1
    escapes = {'n': '\n', 'r': '\r', 't': '\t', 'b': '\b', 'f': '\f'}
    while i < len(tail):
        if tail[i] == "'":
            if i + 1 < len(tail) and tail[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            return ''.join(out)
        if extended and tail[i] == '\\' and i + 1 < len(tail):
            nxt = tail[i + 1]
            if nxt == '\n':
                i += 2
                continue
            if nxt in '01234567':
                digits = re.match(r'[0-7]{1,3}', tail[i + 1:]).group(0)
                out.append(chr(int(digits, 8)))
                i += 1 + len(digits)
                continue
            if nxt in 'xX':
                digits = re.match(r'[0-9A-Fa-f]{1,2}', tail[i + 2:])
                if digits:
                    out.append(chr(int(digits.group(0), 16)))
                    i += 2 + len(digits.group(0))
                    continue
            if nxt in 'uU':
                width = 4 if nxt == 'u' else 8
                digits = tail[i + 2:i + 2 + width]
                if len(digits) == width and re.fullmatch(r'[0-9A-Fa-f]+', digits):
                    value = int(digits, 16)
                    if value <= 0x10ffff and not 0xd800 <= value <= 0xdfff:
                        out.append(chr(value))
                        i += 2 + width
                        continue
            out.append(escapes.get(nxt, nxt))
            i += 2
            continue
        out.append(tail[i])
        i += 1
    return None


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
        tail = sql[m.end():]
        text = _comment_value(tail)
        if text is None:
            continue
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
                         # 이름 목록은 `_INPAREN` 한 벌로 읽는다. `lower(email)` 같은
                         # 함수 인덱스는 예전처럼 여는 괄호가 남아 아래 판정이 걸러 낸다.
                         r'(?:\s+USING\s+\w+)?\s*\(' + _INPAREN + r'\)', msc, re.I):
        t = _find(tables, unq(m.group(1)), unq(m.group(2)))
        cols = _names(m.group(3))
        if t is not None and not any('(' in c for c in cols) and cols not in t['uniques']:
            t['uniques'].append(cols)      # 함수 인덱스(lower(email))는 컬럼 목록이 아니다


def _rows(what, query, n, core=True):
    """조회 하나를 읽어 n개 필드짜리 행 목록으로 (introspect.rows() 와 같은 규칙).

    예전엔 `config.psql()` 로 받아 구분자로 행을 갈랐다. 두 가지가 함께 틀렸다.
      ① psql() 은 returncode 를 버리고 stdout 만 준다. 조회가 중간에 죽어도(문
         타임아웃·서버 재기동) 파서는 **반쯤 읽은 결과** 로 정의서를 만들었다 —
         컬럼 몇 개가 통째로 빠진 문서가 완성본처럼, exit 0 으로 나왔다.
         introspect 는 같은 자리를 psql_rows() → QueryFailed 로 이미 막고 있었다.
      ② 어떤 바이트를 행 구분자로 골라도 값이 그 바이트를 품을 수 있다. 개행을
         피해 RS 로 옮겼지만, 값 하나에 \\x1e 가 들어 있으면 그 행이 둘로 쪼개져
         유령 컬럼이 생기는 것은 그대로였다. psql_rows 는 행마다 JSON 한 줄로 받아
         (제어문자는 \\uXXXX 로 적힌다) 구분자 문제 자체를 없앤다.

    core 는 introspect.rows() 와 같은 뜻이다. 기존 테이블의 실제 컬럼은 문서의
    본문이라 못 읽으면 멈춘다 — 반쯤 읽은 DB 로 만든 정의서는 완성본처럼 보이고
    완성본이 아니다. 선택 기능인 읽기 전용 원천(ERD_REF_SCHEMA)은 없어도 나머지
    그림이 나오므로, 무엇을 못 읽었는지 이름을 대고 넘어간다.
    """
    try:
        return psql_rows(query, n)
    except QueryFailed as e:
        if core:
            raise SystemExit(T('err.query_failed', what=what, err=e))
        print(T('log.query_incomplete', list=what))
        return []


REF_SCHEMA = os.environ.get('ERD_REF_SCHEMA', '').strip()
REF_SOURCES = [t.strip() for t in os.environ.get('ERD_REF_TABLES', '').split(',') if t.strip()]


def _lit(s):
    """SQL 문자열 리터럴 하나. 이름 속 따옴표가 남의 문법이 되지 않게 escape 한다.

    값 둘 다 환경변수(ERD_REF_SCHEMA·ERD_REF_TABLES)에서 그대로 와서 그대로 **살아
    있는 서버**로 나간다. escape 를 지우면 나가는 문장이 이렇게 된다:
        where c.table_schema='s1' or '1'='1' and c.table_name in ('x')
    15라운드 전에는 이 자리를 재는 항목이 introspect 쪽에만 있었고 여기는 0건이라,
    지워도 141개가 전부 초록이었다 (selftest_config.py 의 'parse: a quote in
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
    # 선택 기능이다 — 못 읽었다고 DDL 파싱 전체를 버리지 않는다. 대신 이름을 댄다.
    # 대는 이름은 **그 테이블들** 이다. log.query_incomplete 의 {list} 는 '문서에서
    # 딱 그만큼이 빠진다' 는 문장의 목적어라, 변수 이름이 아니라 빠진 것이 와야 한다.
    for tn, cn, ty, nul in _rows(', '.join(tables[:6]), q, 4, core=False):
        out.setdefault(tn, {
            'name': tn, 'origin': 'ref', 'schema': REF_SCHEMA, 'src_file': T('erd.readonly_src', schema=REF_SCHEMA),
            'columns': [], 'pk': [], 'fks': [], 'uniques': [], 'note': '',
        })['columns'].append({'name': cn, 'type': ty, 'not_null': nul == 'NO',
                              'default': '', 'identity': False, 'comment': '', 'added': False})
    return out


def fetch_existing(tables, names):
    """이미 DB 에 존재하는 테이블의 실제 컬럼을 가져온다 → {테이블 **키**: [컬럼…]}.

    두 가지가 겹쳐 이 조회는 조용히 빗나가고 있었다.

    ① `where c.table_schema='public'` 이 박혀 있어 ERD_SCHEMAS(config.SCHEMAS)를
       무시했다. `ERD_SCHEMAS=shop` 으로 돌려도 public 만 물으니 shop 의 기존
       테이블은 **영영** 컬럼을 못 채우는데, 화면에는 한 글자도 안 나왔다 — 이름만
       있는 빈 상자가 '컬럼이 없는 테이블' 인 양 정의서에 실렸다.
    ② `names` 는 `tables` 의 **키** 다. 이름이 두 스키마에 걸치면 키가 `shop.orders`
       인데(_ref_key·parse_create 의 규칙) 그것을 그대로 `c.table_name in (…)` 에
       넣었다. 그런 이름의 테이블은 DB 에 없으므로 그 테이블은 언제나 0 건이었다.
       조회는 **실제 이름** 으로 하고, 결과를 다시 키에 맞춰 돌려준다.

    스키마 후보는 '그 테이블이 스스로 적은 스키마' 를 먼저, 그다음 ERD_SCHEMAS 순으로
    본다. DDL 이 스키마를 안 적으면 parse_create 가 'public' 으로 채우는데, 그것은
    사용자가 고른 스키마가 아니라 파서의 기본값일 뿐이라 그 하나만 믿으면 ① 이 그대로
    돌아온다. 끝내 못 찾은 테이블은 이름을 대고 말한다.
    """
    if not names:
        return {}
    cand = {}                       # 키 → [후보 스키마…] (제 것 먼저, 그다음 ERD_SCHEMAS)
    for k in names:
        sch = tables[k].get('schema') or 'public'
        cand[k] = [sch] + [s for s in config.SCHEMAS if s != sch]
    schemas = sorted({s for v in cand.values() for s in v})
    real = sorted({tables[k]['name'] for k in names})
    q = f"""
    select c.table_schema, c.table_name, c.column_name,
      case when c.character_maximum_length is not null
             then replace(c.data_type,'character varying','varchar')||'('||c.character_maximum_length||')'
           when c.data_type='numeric' and c.numeric_precision is not null
             then 'numeric('||c.numeric_precision||','||coalesce(c.numeric_scale,0)||')'
           when c.data_type='timestamp with time zone' then 'timestamptz'
           else c.data_type end,
      c.is_nullable
    from information_schema.columns c
    where c.table_schema in ({','.join(_lit(s) for s in schemas)})
      and c.table_name in ({','.join(_lit(n) for n in real)})
    order by c.table_schema, c.table_name, c.ordinal_position"""
    got = {}
    for sn, tn, cn, ty, nul in _rows('columns', q, 5):
        got.setdefault((sn, tn), []).append(
            {'name': cn, 'type': ty, 'not_null': nul == 'NO', 'default': '',
             'identity': False, 'comment': '', 'added': False})
    out, miss = {}, []
    for k in names:
        name = tables[k]['name']
        for s in cand[k]:
            if (s, name) in got:
                out[k] = got[(s, name)]
                break
        else:
            miss.append(k)
    if miss:
        # log.query_incomplete 이 아니다 — 그 문구의 앞문장('읽지 못했다')이 여기서는
        # **거짓**이다. 조회는 rc 0 으로 끝났고, 그 테이블이 우리가 뒤진 스키마에
        # 없었을 뿐이다. 없는 DB 오류를 쫓게 만드느니 일어난 일을 그대로 적는다:
        # 어느 스키마를 뒤졌는지 대고, 그 테이블이 이름만 있는 상자가 된다고 말한다.
        # (_rows() 의 non-core 실패는 정말로 '읽지 못한' 것이라 그쪽은 그대로 둔다.)
        print(T('log.ddl_not_in_db', n=len(miss), schemas=', '.join(schemas),
                list=', '.join(miss[:6]) + (' …' if len(miss) > 6 else '')))
    return out


def main():
    # encoding 을 안 주면 로케일을 따른다. ascii 로케일(LC_ALL=C)에서 한글이 든 DDL
    # 하나에 UnicodeDecodeError 로 죽었다 — 같은 저장소의 build_html.py·svg_canvas.py
    # 는 이미 utf-8 을 못박아 준다. 파일 형식이 로케일에 따라 달라질 리 없다.
    files = [(f, (config.SQL_DIR / f).read_text(encoding='utf-8')) for f in sql_files()]

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
    # 읽지 못해 버린 CREATE TABLE — {키: 스키마}. 파일을 다 읽은 뒤에 쓰므로 한 파일이
    # 버린 이름을 다른 파일의 ALTER·FK 가 되살리는 길까지 막는다 (parse_create 끝 주석).
    dropped = {}
    for f, sql in files:
        file_unread = []
        for statement in sql_statements(sql):
            parse_create(statement, f, tables, dup, dropped, file_unread)
            for k in tables:
                dropped.pop(k, None)
            parse_alter_state(statement, f, tables, dup, dropped)
            parse_drop_table(statement, tables)
            parse_unique(statement, tables)
            parse_comments(statement, tables)
        if file_unread:
            print(T('log.query_incomplete', list=', '.join(file_unread)))
    if dup:
        print(T('log.dup_names', n=len(dup), list=', '.join(sorted(dup)[:6])))

    # 기존 테이블: DB 실제 컬럼을 앞에 붙이고, ALTER 로 추가되는 컬럼은 뒤에 유지
    existing_names = [n for n, t in tables.items() if t['origin'] == 'existing']
    # FK 참조 대상 중 신규가 아닌 것도 기존 테이블로 편입
    for t in list(tables.values()):
        for fk in t['fks']:
            rt = fk['ref_table']
            if rt in dropped:
                # 읽지 못해 버린 테이블을 FK 가 가리킨다. 여기서 상자를 세우면 그것이
                # `log.ddl_no_db` 의 목록에 들어가 'DDL 에 정의가 없고 참조만 되는
                # 테이블 — ERD_DB/ERD_PSQL 을 주면 컬럼을 채운다' 는 안내를 받는다.
                # 세 마디가 다 어긋난다: 정의는 **있고**(못 읽었을 뿐이다), 참조만 되는
                # 것이 아니며, 새로 만들 테이블이라 접속을 준들 DB 에 없다 — 사용자는
                # 있지도 않은 접속 문제를 쫓는다. 세우지 않는다.
                #
                # 이 FK 는 부모의 fks 에 그대로 남는다. DDL 이 정말로 적은 관계이고,
                # 없는 테이블을 가리키는 FK 는 이 저장소가 이미 다루는 모양이다 —
                # erd.py 가 그림에서 걷고(`ref_table in SCHEMA`), HTML 은 링크 없이
                # 이름만 적는다. 여기서 지우면 '못 읽었다' 밖의 사실까지 지우는 것이다.
                continue
            if rt not in tables:
                # 키(rt)는 _ref_key 가 만든 것이라 이름이 여러 스키마에 걸릴 때만
                # `<스키마>.<이름>` 이다. 그것을 'name' 에 그대로 넣던 탓에
                # `shop.orders` 라는 이름의 테이블이 그림에 실렸고, DB 에서 컬럼을
                # 채울 때도 그 이름으로 물어 언제나 0 건이었다. 키와 이름은 다르다.
                rsch, rname = 'public', rt
                for n in dup:
                    if rt.endswith('.' + n):
                        rsch, rname = rt[:-len(n) - 1], n
                        break
                tables[rt] = {'name': rname, 'origin': 'existing', 'src_file': '',
                              'schema': rsch,
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
    db = fetch_existing(tables, names) if has_db else {}
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
        t.pop('_constraints', None)
        for fk in t['fks']:
            fk.pop('_constraint', None)
    if REF_SOURCES and REF_SCHEMA:
        tables.update(fetch_ref(REF_SOURCES))
    elif REF_SOURCES:
        # 반쪽만 준 것은 안 준 것과 다르다 — 예전엔 아무 말 없이 무시했다.
        print(T('log.ref_tables_ignored', n=len(REF_SOURCES),
                list=', '.join(REF_SOURCES[:6])))

    tables = _relabel(tables)

    out = (config.SCHEMA_JSON.with_name(f'schema.{LABEL}.json') if LABEL
           else config.SCHEMA_JSON)
    # ensure_ascii=False 라 한글이 그대로 나간다 — encoding 을 안 주면 ascii 로케일
    # (LC_ALL=C)에서 UnicodeEncodeError 로 죽는다. 읽는 쪽도 utf-8 로 못박혀 있다.
    atomic_write_text(out, json.dumps(tables, ensure_ascii=False, indent=2))
    print(T('log.ddl_parsed', n=len(tables), path=out))
    for n, t in sorted(tables.items(), key=lambda x: (x[1]['origin'], x[0])):
        added = sum(1 for c in t['columns'] if c['added'])
        print(f"  [{t['origin']:8}] {n:32} "
              + T('log.ddl_row', columns=f"{len(t['columns']):3}",
                       added=(T('log.ddl_added', n=added) if added else '').ljust(12),
                       fks=len(t['fks']), note=t['note'][:40]))


if __name__ == '__main__':
    main()
