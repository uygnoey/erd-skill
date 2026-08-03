#!/usr/bin/env python3
"""ERD 산출물 생성 실행기"""
from pathlib import Path

from PIL import Image

import erd
from i18n import t as T
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
    print(T('log.graphml', nodes=n_nodes, edges=n_edges, name=gpath.name))

    # 2) PNG 전체 개요도 — 스키마 그룹 + ETL 흐름
    opos, oboxes, ogroups = erd.layout_overview()
    p = erd.draw_erd(OUT / 'erd_overview.png', list(SCHEMA), opos, oboxes,
                     T('word.fig_no', n=1) + ' ' + T('docx.fig_overview', title=TITLE),
                     subtitle=T('erd.sub_overview'),
                     with_desc=False, scale=2, legend=True, edge_labels=False,
                     groups=ogroups, derives=True, tolerate=('h_overlap',))
    print(T('log.png_overview', name=Path(p).name, size='%d×%d' % Image.open(p).size))

    # 3) PNG 전체 상세 ERD — 모든 테이블의 전 컬럼 + 설명
    p = erd.draw_erd(OUT / 'erd_full.png', list(SCHEMA), pos, boxes,
                     T('word.fig_no', n=2) + ' ' + T('docx.fig_full', title=TITLE),
                     subtitle=(T('erd.sub_full',
                                 tables=len(SCHEMA),
                                 columns=sum(len(x['columns']) for x in SCHEMA.values()),
                                 fks=sum(len(x['fks']) for x in SCHEMA.values()))
                               + (T('erd.sub_etl', n=len(erd.DERIVES)) if erd.DERIVES else '')),
                     # 전체도·개요도는 노드 진출 y 가 고정이라 가로선 중첩 소수는 허용
                     with_desc=True, scale=2, legend=True, groups=groups, derives=True,
                     tolerate=('h_overlap',))
    print(T('log.png_full', name=Path(p).name, size='%d×%d' % Image.open(p).size))

    # 4) PNG 영역별 상세도
    for i, (code, name, schema, tables) in enumerate(AREAS, start=3):
        apos, aboxes, ext = erd.layout_area(tables, with_desc=True)
        p = erd.draw_erd(OUT / f'erd_area_{code}.png', tables + ext, apos, aboxes,
                         T('word.fig_no', n=i) + ' '
                         + T('docx.fig_area', code=code, name=name),
                         subtitle=T('erd.sub_area', schema=schema, n=len(tables))
                                  + (T('erd.sub_ext', n=len(ext)) if ext else ''),
                         with_desc=True, scale=2, stubs=set(ext), legend=True)
        w, h = Image.open(p).size
        print(T('log.png_area', code=code, name=name, n=len(tables), ext=len(ext),
                file=Path(p).name, size=f'{w}×{h}'))


if __name__ == '__main__':
    main()
