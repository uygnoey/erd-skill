#!/usr/bin/env python3
"""여러 DB의 schema.*.json 을 하나로 합친다 — 여러 DB를 한 장의 ERD로 그릴 때.

    ERD_LABEL=shop python3 introspect.py    # → schema.shop.json
    ERD_LABEL=mart python3 introspect.py    # → schema.mart.json
    python3 merge_schemas.py shop mart      # → schema.json

테이블 키는 `<라벨>.<테이블명>` 이라 이름이 같아도 부딪히지 않는다.
DB 사이에는 물리 FK 가 있을 수 없으므로, 두 DB 를 잇는 관계는 spec 의 derives 로 적는다.
"""
import json
import sys

from config import SCHEMA_JSON, WORK


def main():
    labels = sys.argv[1:]
    if not labels:
        raise SystemExit('사용법: python3 merge_schemas.py <라벨> <라벨> …')

    merged = {}
    for label in labels:
        path = WORK / f'schema.{label}.json'
        if not path.exists():
            raise SystemExit(f'{path} 가 없다. ERD_LABEL={label} 로 introspect.py 를 먼저 돌릴 것.')
        part = json.loads(path.read_text())
        merged.update(part)
        n_col = sum(len(t['columns']) for t in part.values())
        print(f'  {label:8} 테이블 {len(part):3} · 컬럼 {n_col:4}')

    # 합친 뒤에도 대상에 없는 테이블을 가리키는 FK 는 버린다
    dropped = 0
    for t in merged.values():
        keep = [fk for fk in t['fks'] if fk['ref_table'] in merged]
        dropped += len(t['fks']) - len(keep)
        t['fks'] = keep

    SCHEMA_JSON.write_text(json.dumps(merged, ensure_ascii=False, indent=2))
    n_col = sum(len(t['columns']) for t in merged.values())
    n_fk = sum(len(t['fks']) for t in merged.values())
    print(f'합계 테이블 {len(merged)} · 컬럼 {n_col} · FK {n_fk} → {SCHEMA_JSON}')
    if dropped:
        print(f'  대상 밖을 가리키는 FK {dropped}건 제외')


if __name__ == '__main__':
    main()
