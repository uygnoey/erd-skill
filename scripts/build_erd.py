#!/usr/bin/env python3
"""ERD 산출물 생성 실행기

문서 빌더(build_html·build_docx)가 박으려는 그림이 아직 이 스키마의 것인지도
여기서 판별한다 — 그림을 만든 쪽이 그림의 나이도 안다.
"""
import os
from pathlib import Path

from PIL import Image

import erd
from i18n import t as T
from erd import AREAS, OUT, SCHEMA
from config import PROJ, SCHEMA_JSON, SPEC_JSON
from erd import SPEC

from config import DOCNAME as DOC

TITLE = SPEC.get('doc', {}).get('title', DOC)

# ── 그림의 나이 ──────────────────────────────────────────────────────────────
# 어디에서도 시각을 비교하지 않고 exists() 만 봤다. 그래서 지난주에 그린 ERD 가
# 오늘 뽑은 컬럼표 옆에 나란히 실렸다 — 캡션은 새 것이고 그림만 옛 것이라
# 받아 본 사람은 어긋난 줄도 모른다. 영역 코드가 밀리면 더 나쁘다:
# 옛 erd_area_E 가 새 E 영역 캡션 아래로 그대로 들어간다.
#
# 비교는 '엄격히 더 오래됐을 때' 만이다. mtime 이 1초 단위인 파일시스템에서도 같은
# 초에 쓴 파일은 같은 값이 되지 더 오래된 값이 되지는 않으므로, 여유분을 두면
# 잡아야 할 것(같은 초 안에 다시 뽑은 스키마)까지 놓친다.


def schema_mtime():
    """그림이 따라와야 할 시각 — 스키마와 뼈대(spec) 중 나중에 손댄 쪽.

    spec 까지 보는 이유는, 스키마가 그대로여도 영역 정의가 바뀌면 영역 그림의
    내용과 코드가 함께 달라지기 때문이다.
    """
    ts = [p.stat().st_mtime for p in (SCHEMA_JSON, SPEC_JSON) if p.exists()]
    return max(ts) if ts else 0.0


def stale_figures(stems, exts=('.svg', '.png')):
    """박으려는 그림 중 스키마보다 오래된 파일 이름. 없는 파일은 세지 않는다."""
    ref = schema_mtime()
    old = []
    for stem in stems:
        for ext in exts:
            p = OUT / f'{stem}{ext}'
            if p.exists() and p.stat().st_mtime < ref:
                old.append(p.name)
    return old


def require_fresh(stems, exts=('.svg', '.png')):
    """오래된 그림이 섞여 있으면 문서를 만들지 않는다.

    틀린 문서는 문서가 없는 것보다 나쁘다 — 컬럼표와 그림이 서로 다른 스키마를
    말하면 받아 본 사람은 어느 쪽을 믿을지 알 수 없고, HTML·docx·GraphML 끼리도
    어긋난다. 그래서 기본은 멈추고 build_erd.py 를 다시 돌리라고 말한다.
    그림이 바뀌지 않는 손질(문구만 고친 경우)까지 막지는 않게 ERD_STALE=warn 으로
    지날 수 있게 둔다 — 다만 그때도 조용히는 안 지나간다.
    """
    old = stale_figures(stems, exts)
    if not old:
        return
    lst = ', '.join(old[:6]) + (' …' if len(old) > 6 else '')
    if os.environ.get('ERD_STALE', '').strip().lower() in ('warn', 'ok', 'yes', '1'):
        print(T('log.stale_figs', n=len(old), list=lst))
        return
    raise SystemExit(T('err.stale_figs', n=len(old), list=lst, path=SCHEMA_JSON))


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
