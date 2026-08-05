#!/usr/bin/env python3
"""여러 DB의 schema.*.json 을 하나로 합친다 — 여러 DB를 한 장의 ERD로 그릴 때.

    ERD_LABEL=shop python3 introspect.py    # → schema.shop.json
    ERD_LABEL=mart python3 introspect.py    # → schema.mart.json
    python3 merge_schemas.py shop mart      # → schema.json

테이블 키는 `<라벨>.<테이블명>` 이라 이름이 같아도 부딪히지 않는다.
DB 사이에는 물리 FK 가 있을 수 없으므로, 두 DB 를 잇는 관계는 spec 의 derives 로 적는다.

**라벨을 붙이는 것은 여기다.** 15라운드까지 이 파일은 `merged.update(part)` 한 줄이
전부였고, 라벨을 붙이는 코드는 `introspect.py` 에만 있었다. 그래서 위 docstring 이
약속하는 것이 `ERD_LABEL` 을 켜고 introspect 를 돈 경우에만 참이었다 —
`parse_ddl.py` 가 만든 `schema.*.json` 이나 라벨 없이 뽑아 둔 예전 파일을 섞으면
같은 이름의 테이블이 **말 한 마디 없이 하나로 합쳐졌다.** 두 부분이 각각 '테이블 1'
이라고 찍힌 바로 다음 줄에 '합계 테이블 1' 이 찍혔고, 사라진 쪽 DB 의 컬럼·FK·설명이
문서 어디에도 안 실렸다. 3라운드가 단일 DB 에서 고친 그 결함이 다중 DB 경로에
그대로 남아 있었던 셈이다.

라벨은 **부분 단위로** 붙인다 — 한 파일의 키를 전부 붙이거나 전부 안 붙인다.
  · 이미 그 라벨로 키가 적혀 있으면(introspect 가 만든 파일) 손대지 않는다.
  · 아니면 그 파일의 **모든** 키에 `<라벨>.` 을 붙인다.
키마다 따로 판정하면 한 파일에 `orders` 와 `shop.orders` 가 섞여 있을 때 둘이 같은
키가 되어 여기서 다시 하나가 삼켜진다. 부분 단위 판정은 그 사상이 언제나 단사라
합계가 부분의 합과 어긋날 수 없다.
"""
import json
import sys

import config
from i18n import t as T


def label_part(label, part):
    """한 파일의 테이블에 라벨을 입힌다 — 키·FK 대상·db·schema 칸을 함께 옮긴다.

    FK 의 `ref_table` 은 **키를 가리키는 값**이라 키를 바꾸면 같이 바꿔야 한다.
    안 바꾸면 합친 뒤 '대상에 없는 FK' 로 몰려 조용히 버려진다 — 관계가 사라진
    ERD 는 관계가 없는 ERD 처럼 보인다.

    `db` 칸도 채운다. 키만 갈라 놓고 `db` 를 빈 채로 두면 HTML 의 DB 요약·목차·본문이
    두 DB 를 여전히 한 묶음(빈 라벨)으로 싣는다 — 키에서 막은 합쳐짐이 문서에서 다시
    일어난다. introspect 가 `'db': LABEL` 로 적는 것과 같은 값을 여기서도 적는다.

    `schema` 칸도 같은 이유로 옮긴다. 이 칸을 빈 채로 두면 두 DB 의 테이블이 모두
    `public` 하나가 되어, `config.load_spec` 의 영역 자동 분류(`schema[t].get('schema',
    'public')` 로 묶는다)와 docx 4장 메타표가 두 DB 를 다시 한 묶음으로 싣는다.
    모양은 `introspect.py`(`f'{LABEL}.{sch}'`)·`parse_ddl.py`(`_relabel`)와 같게
    `<라벨>.<스키마>` 로 맞춘다 — 세 경로가 서로 다른 모양을 내면 합친 뒤 같은 DB 의
    테이블이 두 규칙으로 흩어진다.
    """
    keys = list(part)
    already = bool(keys) and all(k == label or k.startswith(label + '.') for k in keys)
    ren = {k: k for k in keys} if already else {k: f'{label}.{k}' for k in keys}
    out = {}
    for k, t in part.items():
        t = dict(t)
        t['db'] = t.get('db') or label
        # `schema` 는 **값마다** 판정한다 — 키와 다르다.
        #   · 키를 값마다 판정하면 안 되는 이유는 단사성이다: 한 파일에 `orders` 와
        #     `shop.orders` 가 섞여 있을 때 값마다 붙이면 둘이 **같은 키**가 되어
        #     하나가 삼켜진다. 그래서 키는 부분 단위다(docstring 참고).
        #   · `schema` 는 키가 아니라 **묶는 이름**이라 두 값이 같아져도 아무것도
        #     사라지지 않는다 — 같은 영역으로 묶일 뿐이다. 그러니 값마다 판정해도
        #     안전하고, 그래야 섞인 파일(키에만 라벨이 붙어 `shop.public` 과
        #     `public` 이 한 파일에 있는 경우)에서 `shop.shop.public` 이 안 나온다.
        #     값마다 판정은 몇 번을 돌려도 같은 값이 된다.
        # 붙은 모양은 introspect(`f'{LABEL}.{sch}'`)·parse_ddl 모두 `<라벨>.<스키마>`
        # 라 접두어만 본다. 홑 `shop` 은 라벨이 아니라 **shop 이라는 스키마**이므로
        # 여기 안 걸린다 — introspect 도 그 경우 `shop.shop` 을 적는다.
        sch = t.get('schema') or 'public'
        t['schema'] = sch if sch.startswith(label + '.') else f'{label}.{sch}'
        t['fks'] = [dict(fk, ref_table=ren.get(fk['ref_table'], fk['ref_table']))
                    for fk in t.get('fks', [])]
        out[ren[k]] = t
    return out


def main():
    # 같은 라벨을 두 번 적어도 읽을 파일은 하나다. 예전엔 그 파일을 두 번 읽고
    # 부분 줄을 두 번 찍은 뒤 합계는 한 번만 세서, 여기서도 1+1 이 1 로 보였다.
    labels = []
    for a in sys.argv[1:]:
        if a not in labels:
            labels.append(a)
    if not labels:
        raise SystemExit(T('err.merge_usage'))

    merged = {}
    for label in labels:
        path = config.WORK / f'schema.{label}.json'
        if not path.exists():
            raise SystemExit(T('err.merge_missing', path=path, label=label))
        try:
            # 인코딩을 안 주면 로케일이 정한다 — ascii 로케일(LC_ALL=C)에서 한글
            # 코멘트가 든 부분 파일이 UnicodeDecodeError 로 죽는다. 이 파일들은
            # 언제나 utf-8 로 쓰므로(아래 write_text) 읽기도 utf-8 로 못 박는다.
            part = json.loads(path.read_text(encoding='utf-8'))
        except json.JSONDecodeError as e:
            raise SystemExit(T('err.spec_json', path=path, err=e))
        part = label_part(label, part)
        merged.update(part)
        n_col = sum(len(t['columns']) for t in part.values())
        print(T('log.merge_part', label=f'{label:8}', tables=f'{len(part):3}',
                columns=f'{n_col:4}'))

    # 합친 뒤에도 대상에 없는 테이블을 가리키는 FK 는 버린다
    dropped = 0
    for t in merged.values():
        keep = [fk for fk in t['fks'] if fk['ref_table'] in merged]
        dropped += len(t['fks']) - len(keep)
        t['fks'] = keep

    schema_json = config.SCHEMA_JSON
    # `ensure_ascii=False` 라 결과에 한글이 그대로 들어간다 — 로케일이 ascii 면
    # 쓰는 자리에서 UnicodeEncodeError 로 죽는다. 인코딩을 값으로 못 박는다.
    schema_json.write_text(json.dumps(merged, ensure_ascii=False, indent=2),
                           encoding='utf-8')
    n_col = sum(len(t['columns']) for t in merged.values())
    n_fk = sum(len(t['fks']) for t in merged.values())
    print(T('log.merge_total', tables=len(merged), columns=n_col, fks=n_fk,
            path=schema_json))
    if dropped:
        print(T('log.fk_dropped', n=dropped))


if __name__ == '__main__':
    main()
