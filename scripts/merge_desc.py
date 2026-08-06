#!/usr/bin/env python3
"""ORM 모델 주석 + 수기 사전을 schema.json 의 컬럼 설명으로 병합한다.

우선순위: 수기 사전(MANUAL) > DB 코멘트·DDL 주석 > 이전 판 문서 > ORM 주석 > 공통 사전(COMMON)
"""
import json
import os
import re
from html import unescape
from pathlib import Path

# 경로 상수는 **부를 때** 묻는다 — `from config import SCHEMA_JSON` 한 줄이 곧
# 'erd-build/out 을 만들라' 는 뜻이었다 (config.py 의 '늦춰 두는 값' 참고).
import config
from config import as_file, atomic_write_text, clean, validate_schema
from i18n import t as T

# ── 공통 컬럼 (테이블 무관 · 최후 폴백) ────────────────────────────────────────
# 어느 DB에나 있는 것만 둔다. 프로젝트 공통 컬럼은 여기에 덧붙여 쓰면
# 테이블마다 반복해 적을 필요가 없다.
# 설명 문구는 산출 문서에 그대로 실리므로 ERD_LANG 을 따른다 (lang/<코드>.py).
COMMON = {name: T(f'common.{name}') for name in (
    'id', 'seq', 'uuid', 'created_at', 'updated_at', 'deleted_at',
    'created_by', 'updated_by', 'loaded_at', 'started_at', 'ended_at',
    'status', 'note', 'remark', 'sort_order', 'rank', 'version',
    'is_active', 'active_yn',
)}

# ── 테이블.컬럼 수기 설명 ─────────────────────────────────────────────────────
# DB 코멘트에도 ORM 에도 없는 설명을 여기에 적는다. 우선순위가 가장 높아서
# '필수' 같은 성의 없는 DB 코멘트를 덮어쓸 때도 쓴다. 키는 `테이블.컬럼`.
#
#   MANUAL = {
#       'orders.status': '주문 상태 (PAID/SHIPPED/CANCELLED)',
#       'orders.channel': '유입 경로 · 정산 기준이라 값이 바뀌면 안 된다',
#   }
#
# 이름이 여러 스키마·DB 에 걸친 테이블은 앞을 붙여 정확히 하나를 가리킨다.
# '아직 설명 없는 컬럼' 목록이 찍어 주는 키가 곧 여기 붙여 넣으면 되는 키다.
#
#   MANUAL = {
#       'analytics.events.kind': '이벤트 종류',   # analytics.events 에만 붙는다
#       'shop.users.id': '쇼핑몰 회원 번호',      # mart.users 에는 안 붙는다
#   }
#
# 프로젝트마다 다른 내용이므로 스킬에는 비워 둔다.
MANUAL = {
}



def parse_orm():
    """ORM 모델의 컬럼 주석을 {table.column: comment} 로 뽑는다."""
    out = {}
    if not config.MODEL_DIR.is_dir():
        return out
    for path in config.MODEL_DIR.glob('*.py'):
        table, pending = None, []
        # 인코딩을 안 주면 로케일이 정한다 — ascii 로케일(LC_ALL=C)에서 한글 주석이
        # 든 모델 파일이 UnicodeDecodeError 로 죽는다. 주석을 읽으러 온 자리가
        # 주석 때문에 죽는 셈이다.
        for raw in path.read_text(encoding='utf-8').split('\n'):
            line = raw.strip()
            tm = re.match(r'__tablename__\s*=\s*["\'](\w+)["\']', line)
            if tm:
                table, pending = tm.group(1), []
                continue
            if line.startswith('#'):
                pending.append(line.lstrip('# ').strip())
                continue
            # SQLAlchemy 2.x uses ``name: Mapped[...]``; the still-common 1.x
            # declarative style assigns ``name = Column(...)`` (or
            # ``mapped_column(...)``).  Both forms carry the same inline or
            # preceding comment and must feed the same description map.
            cm = re.match(r'(\w+):\s*Mapped\[', line)
            if not cm:
                cm = re.match(r'(\w+)\s*=\s*(?:[\w.]+\.)?'
                              r'(?:mapped_column|Column)\s*\(', line)
            if cm and table:
                inline = re.search(r'#\s*(.+)$', raw)
                desc = inline.group(1).strip() if inline else ' '.join(pending)
                if desc:
                    out[f'{table}.{cm.group(1)}'] = desc
                pending = []
                continue
            if line and not line.startswith(')'):
                pending = []
    return out


# HTML 에서 긁은 글자가 **이름인지** 거르는 그물. 표가 아닌 h4·설명문이 키가 되는 것을
# 막는 자리라 그물 자체는 있어야 하지만, 코가 ASCII 로만 짜여 있었다:
# `[A-Za-z_][A-Za-z0-9_.]*`. 그래서 따옴표로 지은 한글 이름이 통째로 걸러졌다.
#
#   CREATE TABLE "주문" (id bigint primary key, amt numeric(10,2));
#   → 이전 판 문서에 손으로 다듬어 둔 설명 2건이 하나도 안 넘어온다(실측).
#     같은 문서의 `orders` 는 2건 다 넘어온다.
#
# 이 기능이 있는 이유가 **사람이 다듬은 설명을 다시 뽑을 때 잃지 않는 것**인데, 그
# 설명을 잃는다. 게다가 조용하다 — '2건 인계' 라고 찍히니 넘어온 줄 알고, 빠진 것은
# '아직 설명 없는 컬럼' 목록에 섞여 처음 만든 컬럼처럼 보인다. 한국어·일본어로 쓰는
# 스킬(ERD_LANG 이 네 말을 받는다)에서 하필 그 말로 지은 이름만 못 받아 왔다.
#
# `\w` 는 파이썬3 에서 유니코드를 기본으로 매칭하므로 한글·한자·키릴이 다 든다.
# 첫 글자에서 숫자만 빼는 것(`[^\W\d]`)은 예전 규칙(`[A-Za-z_]` 는 숫자로 시작하지
# 않는다)을 그대로 옮긴 것이다. 넓히는 것은 거기까지다 — 공백·따옴표·괄호가 든 이름은
# 여전히 안 받는다. 그런 것까지 받으면 표 없는 h4 의 문장이 키가 되고, 이 그물이
# 막으라고 있던 자리가 열린다.
_NAME = re.compile(r'[^\W\d]\w*')            # 컬럼 이름
_NAME_DOT = re.compile(r'[^\W\d][\w.]*')     # 테이블 키 (라벨·스키마가 점으로 붙는다)


def parse_doc_html():
    """이전 판 문서(HTML)의 컬럼 설명을 {table.column: comment} 로 물려받는다.

    사람이 다듬어 둔 설명을 문서를 다시 뽑을 때마다 잃지 않기 위한 것이다.
    `<h4>테이블명</h4>` 다음에 오는 첫 표에서 2번째 칸(컬럼)과 마지막 칸(설명)을 읽는다 —
    이 스킬이 만드는 HTML 과 흔한 스키마 정의서가 모두 이 모양이다.

      ERD_DOC_HTML=이전문서.html            (콤마로 여러 개도 가능)
    """
    paths = [p.strip() for p in os.environ.get('ERD_DOC_HTML', '').split(',') if p.strip()]
    out = {}
    for p in paths:
        path = Path(p).expanduser()
        if not path.exists():
            print(T('log.doc_missing', path=path))
            continue
        # 없는 파일은 넘어가도 되지만 **디렉토리**는 아니다 — read_text 가
        # `IsADirectoryError: [Errno 21]` 을 던지는데, 그 줄은 어느 변수 탓인지
        # 말하지 않는다. 여기서 이름을 댄다.
        as_file(path, 'ERD_DOC_HTML')
        html = path.read_text(encoding='utf-8', errors='replace')
        n0 = len(out)
        # <h4 …>테이블명<span …></h4> … <table>…</table>  (다음 제목 전까지가 한 몫)
        #
        # 예전 정규식은 끝을 `</table>` 로 잡았다(`<h4…>(.*?)</h4>(.*?)</table>`).
        # 그래서 표가 없는 h4 를 만나면 그 매치가 **다음 h4 의 표까지** 한 덩어리로
        # 먹고, finditer 는 먹은 자리를 건너뛰므로 그 다음 h4 는 아예 매치되지
        # 않았다 — 그 테이블의 설명이 통째로, 아무 말 없이 유실됐다. 사람이 다듬어
        # 둔 설명을 지키자는 기능이 바로 그 설명을 잃는 셈이었다.
        # 그래서 경계를 **다음 제목(h1~h4) 앞**으로 잡아 h4 단위로 자르고, 그 몫
        # 안에서 첫 표만 읽는다. 이 스킬이 내는 HTML(h4 → div 몇 개 → table)도
        # 흔한 스키마 정의서도 그대로 걸린다.
        for m in re.finditer(r'<h4[^>]*>(.*?)</h4>(.*?)(?=<h[1-4][^>]*>|\Z)',
                             html, re.S):
            head, sect = m.group(1), m.group(2)
            tbl = re.search(r'<table[^>]*>(.*?)</table>', sect, re.S)
            if tbl is None:          # 표가 없는 h4 는 여기서만 넘어간다 — 다음 h4 는 산다
                continue
            block = tbl.group(1)
            tname = re.sub(r'<[^>]+>.*', '', head)          # 배지 앞의 순수 텍스트
            tname = re.sub(r'<[^>]+>', '', tname).strip()
            if not _NAME_DOT.fullmatch(tname):
                continue
            for row in re.findall(r'<tr>(.*?)</tr>', block, re.S):
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                if len(cells) < 3:
                    continue
                col = unescape(re.sub(r'<[^>]+>', '', cells[1])).strip()
                desc = unescape(re.sub(r'<[^>]+>', ' ', cells[-1]))
                desc = re.sub(r'\s+', ' ', desc).strip()
                if _NAME.fullmatch(col) and desc and desc != '-':
                    out.setdefault(f'{tname}.{col}', desc)
        print(T('log.doc_inherited', n=len(out) - n0, name=path.name))
    return out


def ambiguous_names(schema):
    """이름 하나가 두 테이블 이상을 가리키는 경우 {테이블명: [정식 키…]}.

    shop.users 와 mart.users 처럼 이름이 겹치면 `users.id` 는 어느 쪽을 말하는지
    알 수 없다. 그런 이름을 미리 모아 두고, 홑이름 키는 여기 없는 이름에만 쓴다.
    """
    by_name = {}
    for tkey, t in schema.items():
        by_name.setdefault(t.get('name', tkey), []).append(tkey)
    return {n: ks for n, ks in by_name.items() if len(ks) > 1}


def main():
    # 인코딩을 안 주면 로케일이 정한다 — ascii 로케일에서 한글 설명이 든 schema.json
    # 을 읽다 UnicodeDecodeError 로 죽는다. 아래 write_text 와 짝을 맞춘다.
    try:
        schema = json.loads(config.SCHEMA_JSON.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise SystemExit(T('err.spec_json', path=config.SCHEMA_JSON, err=e))
    except (UnicodeDecodeError, OSError) as e:
        raise SystemExit(T('err.env_bad', env='ERD_WORK', value=config.SCHEMA_JSON, why=e))
    validate_schema(schema, config.SCHEMA_JSON)
    orm = parse_orm()
    doc = parse_doc_html()
    # 'edit' 는 사람이 schema.json 을 손으로 고쳐 채운 설명이다 — DB 코멘트도(ddl),
    # 수기 사전도(manual) 아니라 둘 중 어디에 세도 통계가 거짓말이 된다. 이 이름은
    # 카탈로그를 안 거치는 내부 이름이라 여기서 하나 늘리는 것으로 끝난다.
    filled = {'ddl': 0, 'doc': 0, 'orm': 0, 'manual': 0, 'edit': 0, 'common': 0,
              'none': 0}
    dup = ambiguous_names(schema)
    has_col = {k: {c['name'] for c in t['columns']} for k, t in schema.items()}
    vague = {}          # 이름이 겹쳐 못 쓴 홑이름 키 {키: [정식 키…]}

    def find(src_dict, tkey, base, cname):
        """설명 사전에서 이 컬럼의 값을 찾는다. 없으면 None.

        정식 키(`analytics.events.kind`)를 먼저 본다 — '아직 설명 없는 컬럼' 목록이
        찍는 것이 이 키이므로, 그대로 MANUAL 에 붙여 넣었을 때 들어야 한다.
        예전에는 이전 판 문서에 그 키가 있는지로 키를 한 번 고르고 그 선택을 MANUAL·ORM
        에까지 돌려썼다. 그래서 문서가 없으면 정식 키는 영영 안 걸렸다.

        홑이름 키(`events.kind`)는 그 이름의 테이블이 하나뿐일 때만 쓴다. 겹치는데도
        쓰면 shop.users 에 적은 설명이 mart.users 에도 붙는다 — 실제로 그랬다.
        """
        full = f'{tkey}.{cname}'
        if full in src_dict:
            return src_dict[full]
        bare = f'{base}.{cname}'
        if bare in src_dict:
            if base not in dup:
                return src_dict[bare]
            # 대신 쓸 키를 일러 줄 때 그 컬럼이 실제로 있는 테이블만 든다 —
            # 이름만 같고 컬럼은 없는 테이블까지 적으면 안 되는 키를 권하게 된다.
            owners = [q for q in dup[base] if cname in has_col[q]]
            vague.setdefault(bare, owners or dup[base])
        return None

    for tname, t in schema.items():
        base = t.get('name', tname)          # 라벨 접두어를 뗀 실제 테이블명
        for c in t['columns']:
            # 수기 사전이 최우선 — DDL 주석이 '필수' 처럼 너무 짧은 경우를 덮어쓴다
            man = find(MANUAL, tname, base, c['name'])
            if man is not None:
                c['comment'], src = clean(man), 'manual'
                filled['manual'] += 1
            elif c['comment']:
                c['comment'] = clean(c['comment'])
                # 두 번째 실행부터는 앞선 실행이 채워 넣은 설명이 이미 자리에 있다.
                # 그걸 전부 'DB 코멘트' 로 세면 통계가 거짓말이 된다 — 앞서 적어 둔
                # 출처가 있으면 그대로 물려받는다.
                src = c.get('desc_src') or 'ddl'
                # 앞선 실행이 '설명 없음'(none)이라 적어 둔 자리에 설명이 있으면,
                # 그 사이에 사람이 schema.json 을 손으로 채운 것이다. `or` 로는 안
                # 걸러진다 — 'none' 은 빈 문자열이 아니라 truthy 다. 그대로 물려받으면
                # 설명이 **있는** 컬럼이 계속 '아직 설명 없는 컬럼' 목록에 오른다.
                if src == 'none':
                    src = 'edit'
                filled[src if src in filled else 'ddl'] += 1
            elif (prev := find(doc, tname, base, c['name'])) is not None:
                c['comment'], src = clean(prev), 'doc'   # 이전 판 문서에서 물려받음
                filled['doc'] += 1
            elif (mdl := find(orm, tname, base, c['name'])) is not None:
                c['comment'], src = clean(mdl), 'orm'
                filled['orm'] += 1
            elif c['name'] in COMMON:
                c['comment'], src = clean(COMMON[c['name']]), 'common'
                filled['common'] += 1
            else:
                src = 'none'
                filled['none'] += 1
            c['desc_src'] = src

    # 내용이 그대로면 파일을 다시 쓰지 않는다. 시각만 새로 찍히면 멀쩡한 ERD 가
    # 낡은 것으로 보여(문서 빌더가 시각으로 판별한다) 헛되이 다시 그리게 된다.
    # 읽기와 쓰기가 **같은** 인코딩이어야 이 비교가 뜻을 갖는다 — 한쪽만 로케일에
    # 맡기면 같은 내용을 다르다고 읽어 파일을 헛되이 다시 쓰고, mtime 이 새로 찍혀
    # 멀쩡한 ERD 가 낡은 것이 된다(build_erd.require_fresh 는 mtime 으로 판정한다).
    # 위 read_text 와 함께 utf-8 로 못 박아 그 짝을 로케일에서 떼어 놓는다.
    text = json.dumps(schema, ensure_ascii=False, indent=2)
    if (not config.SCHEMA_JSON.exists()
            or config.SCHEMA_JSON.read_text(encoding='utf-8') != text):
        atomic_write_text(config.SCHEMA_JSON, text)
    print(T('log.by_source'), filled)
    # 조용히 버리면 '왜 안 들어가지' 로 끝난다 — 대신 쓸 정식 키를 그대로 보여 준다.
    if vague:
        items = sorted(vague.items())
        print(T('log.desc_ambiguous', n=len(items), list='; '.join(
            '{} → {}'.format(k, ', '.join(f'{q}.{k.rsplit(".", 1)[1]}' for q in qs))
            for k, qs in items[:4]) + (' …' if len(items) > 4 else '')))
    if filled['none']:
        print('\n' + T('log.no_desc'))
        for tname, t in schema.items():
            for c in t['columns']:
                if c['desc_src'] == 'none':
                    print(f"  {tname}.{c['name']}  ({c['type']})")


if __name__ == '__main__':
    main()
