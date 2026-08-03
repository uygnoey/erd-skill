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


def main():
    schema = json.loads(SCHEMA.read_text())
    orm = parse_orm()
    doc = parse_doc_html()
    filled = {'ddl': 0, 'doc': 0, 'orm': 0, 'manual': 0, 'common': 0, 'none': 0}

    for tname, t in schema.items():
        base = t.get('name', tname)          # 라벨 접두어를 뗀 실제 테이블명
        for c in t['columns']:
            # 여러 DB 를 합치면 shop.orders 와 mart.orders 가 둘 다 <h4>orders</h4> 로
            # 나온다. 이름만으로 찾으면 먼저 나온 쪽 설명이 양쪽에 덮어씌워진다 —
            # 키가 붙은 쪽을 먼저 보고, 없을 때만 이름으로 떨어진다.
            key = f"{tname}.{c['name']}" if f"{tname}.{c['name']}" in doc \
                else f"{base}.{c['name']}"
            # 수기 사전이 최우선 — DDL 주석이 '필수' 처럼 너무 짧은 경우를 덮어쓴다
            if key in MANUAL:
                c['comment'], src = clean(MANUAL[key]), 'manual'
                filled['manual'] += 1
            elif c['comment']:
                c['comment'] = clean(c['comment'])
                # 두 번째 실행부터는 앞선 실행이 채워 넣은 설명이 이미 자리에 있다.
                # 그걸 전부 'DB 코멘트' 로 세면 통계가 거짓말이 된다 — 앞서 적어 둔
                # 출처가 있으면 그대로 물려받는다.
                src = c.get('desc_src') or 'ddl'
                filled[src if src in filled else 'ddl'] += 1
            elif key in doc:                 # 이전 판 문서에서 물려받은 설명
                c['comment'], src = clean(doc[key]), 'doc'
                filled['doc'] += 1
            elif key in orm:
                c['comment'], src = clean(orm[key]), 'orm'
                filled['orm'] += 1
            elif c['name'] in COMMON:
                c['comment'], src = clean(COMMON[c['name']]), 'common'
                filled['common'] += 1
            else:
                src = 'none'
                filled['none'] += 1
            c['desc_src'] = src

    SCHEMA.write_text(json.dumps(schema, ensure_ascii=False, indent=2))
    print(T('log.by_source'), filled)
    if filled['none']:
        print('\n' + T('log.no_desc'))
        for tname, t in schema.items():
            for c in t['columns']:
                if c['desc_src'] == 'none':
                    print(f"  {tname}.{c['name']}  ({c['type']})")


if __name__ == '__main__':
    main()
