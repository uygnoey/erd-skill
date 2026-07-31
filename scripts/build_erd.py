#!/usr/bin/env python3
"""ERD 산출물 생성 실행기"""
from pathlib import Path

from PIL import Image

import erd
from erd import AREAS, OUT, SCHEMA
from config import PROJ
from erd import SPEC

from config import DOCNAME as DOC

TITLE = SPEC.get('doc', {}).get('title', DOC)


def main():
    # 1) GraphML — 전체 22테이블 · 컬럼 설명 포함
    pos, boxes, groups = erd.layout_global()
    gpath = PROJ / f'{DOC}.graphml'   # 문서와 같은 위치에 둔다
    n_nodes, n_edges = erd.build_graphml(gpath, pos, boxes)
    print(f'GraphML  노드 {n_nodes} · 관계 {n_edges}  → {gpath.name}')

    # 2) PNG 전체 개요도 — 스키마 그룹 + ETL 흐름
    opos, oboxes, ogroups = erd.layout_overview()
    p = erd.draw_erd(OUT / 'erd_overview.png', list(SCHEMA), opos, oboxes,
                     f'[그림 1] {TITLE} — 전체 관계 개요',
                     subtitle='색 = 레이어 / 묶음 = 스키마·영역',
                     with_desc=False, scale=2, legend=True, edge_labels=False,
                     groups=ogroups, derives=True)
    print('PNG  개요도 →', Path(p).name, Image.open(p).size)

    # 3) PNG 전체 상세 ERD — 모든 테이블의 전 컬럼 + 설명
    p = erd.draw_erd(OUT / 'erd_full.png', list(SCHEMA), pos, boxes,
                     f'[그림 2] {TITLE} — 전체 (컬럼 · 설명 포함)',
                     subtitle=(f'테이블 {len(SCHEMA)}개 · '
                               f'컬럼 {sum(len(t["columns"]) for t in SCHEMA.values())}개 · '
                               f'외래키 {sum(len(t["fks"]) for t in SCHEMA.values())}건'
                               + (f' · ETL 흐름 {len(erd.DERIVES)}건' if erd.DERIVES else '')),
                     with_desc=True, scale=2, legend=True, groups=groups, derives=True)
    print('PNG  전체 ERD →', Path(p).name, Image.open(p).size)

    # 4) PNG 영역별 상세도
    for i, (code, name, schema, tables) in enumerate(AREAS, start=3):
        apos, aboxes, ext = erd.layout_area(tables, with_desc=True,
                                            max_cols=2 if len(tables) > 2 else 1)
        p = erd.draw_erd(OUT / f'erd_area_{code}.png', tables + ext, apos, aboxes,
                         f'[그림 {i}] 영역 {code} · {name}',
                         subtitle=f'{schema} 스키마 · 테이블 {len(tables)}개'
                                  + (f' · 외부 참조 {len(ext)}개' if ext else ''),
                         with_desc=True, scale=2, stubs=set(ext), legend=True)
        w, h = Image.open(p).size
        print(f'PNG  영역 {code} {name} ({len(tables)}개 + 참조 {len(ext)}) '
              f'→ {Path(p).name}  {w}×{h}')


if __name__ == '__main__':
    main()
