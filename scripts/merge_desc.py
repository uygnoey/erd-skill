#!/usr/bin/env python3
"""ORM 모델 주석 + 수기 사전을 schema.json 의 컬럼 설명으로 병합한다.

우선순위: 수기 사전(MANUAL) > DB 코멘트·DDL 주석 > 이전 판 문서 > ORM 주석 > 공통 사전(COMMON)
"""
import json
import os
import re
from html import unescape
from pathlib import Path

from config import MODEL_DIR, SCHEMA_JSON, clean
from i18n import t as T

SCHEMA = SCHEMA_JSON

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
    if not MODEL_DIR.is_dir():
        return out
    for path in MODEL_DIR.glob('*.py'):
        table, pending = None, []
        for raw in path.read_text().split('\n'):
            line = raw.strip()
            tm = re.match(r'__tablename__\s*=\s*["\'](\w+)["\']', line)
            if tm:
                table, pending = tm.group(1), []
                continue
            if line.startswith('#'):
                pending.append(line.lstrip('# ').strip())
                continue
            cm = re.match(r'(\w+):\s*Mapped\[', line)
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
        html = path.read_text(encoding='utf-8', errors='replace')
        n0 = len(out)
        # <h4 …>테이블명<span …> … <table>…</table>
        for m in re.finditer(r'<h4[^>]*>(.*?)</h4>(.*?)</table>', html, re.S):
            head, block = m.group(1), m.group(2)
            tname = re.sub(r'<[^>]+>.*', '', head)          # 배지 앞의 순수 텍스트
            tname = re.sub(r'<[^>]+>', '', tname).strip()
            if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.]*', tname):
                continue
            for row in re.findall(r'<tr>(.*?)</tr>', block, re.S):
                cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S)
                if len(cells) < 3:
                    continue
                col = unescape(re.sub(r'<[^>]+>', '', cells[1])).strip()
                desc = unescape(re.sub(r'<[^>]+>', ' ', cells[-1]))
                desc = re.sub(r'\s+', ' ', desc).strip()
                if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', col) and desc and desc != '-':
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
    schema = json.loads(SCHEMA.read_text())
    orm = parse_orm()
    doc = parse_doc_html()
    filled = {'ddl': 0, 'doc': 0, 'orm': 0, 'manual': 0, 'common': 0, 'none': 0}
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
    text = json.dumps(schema, ensure_ascii=False, indent=2)
    if not SCHEMA.exists() or SCHEMA.read_text() != text:
        SCHEMA.write_text(text)
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
