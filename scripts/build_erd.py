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
# `config` 의 PROJ·WORK·OUT·SCHEMA_JSON·SPEC_JSON 은 **처음 물어볼 때** 만들어진다
# (PEP 562 모듈 __getattr__). `from config import SCHEMA_JSON` 은 그 물음을 import
# 시점에 던지므로, 이름 하나를 가져오는 것만으로 mkdir 이 돌고 부르는 사람의 cwd 에
# erd-build/ 가 생긴다. 15라운드가 세운 '**import 는 아무것도 안 만든다**' 를 이
# 파일에서도 지키려면 값을 **쓰는 자리에서** 물어야 한다 — `config.SCHEMA_JSON`.
# (함수가 아닌 `env_flag`·`DOCNAME` 은 늦출 것이 없는 보통 이름이라 그대로 가져온다.)
import config
from config import env_flag
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
    ts = [p.stat().st_mtime for p in (config.SCHEMA_JSON, config.SPEC_JSON)
          if p.exists()]
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


# ERD_STALE 은 켜짐/꺼짐이 아니라 **모드**다 — 'warn' 은 '멈추지 말고 경고만 하라' 는
# 뜻이고, 그 밖의 값은 결국 켜짐/꺼짐이다. 그래서 모드 이름만 여기서 알아듣고 나머지는
# 저장소가 가진 한 규칙(`env_flag`)에 넘긴다.
#
# 예전엔 이 자리가 `in ('warn','ok','yes','1')` 라는 **제 규칙**이었다. 14라운드가
# 다른 다섯 자리를 `env_flag` 로 묶을 때 여기만 빠졌고, 그래서 `ERD_STALE=true`·`on`·
# `y` 는 켰다고 생각한 사람에게 **조용히 안 먹었다**(문서가 안 나오고 멈춘다). 오타도
# 조용했다 — 이제 `env_flag` 가 변수 이름을 대고 알린 뒤 기본값(멈춤)으로 간다.
# 'ok' 는 예전 판이 받아 주던 말이라 계속 받는다.
_STALE_MODES = ('warn', 'ok')


def _stale_passes():
    """오래된 그림을 안고 문서를 낼 것인가."""
    if os.environ.get('ERD_STALE', '').strip().lower() in _STALE_MODES:
        return True
    return env_flag('ERD_STALE', False)


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
    if _stale_passes():
        print(T('log.stale_figs', n=len(old), list=lst))
        return
    raise SystemExit(T('err.stale_figs', n=len(old), list=lst,
                       path=config.SCHEMA_JSON))


# ── 두 문서가 함께 쓰는 규칙 ─────────────────────────────────────────────────
# build_html.py 와 build_docx.py 는 같은 재료로 서로 다른 문서를 만든다. 그런데 같은
# 재료를 **다르게 읽던 자리**가 둘 있었고 둘 다 조용히 갈렸다: 표지 정보표의 행 폭(docx
# 는 4칸, HTML 은 2칸 언팩 → 배포 예제에서 HTML 만 ValueError 로 죽었다)과, 문서가
# 세는 테이블 집합(본문은 영역을 돌고 개수는 len(SCHEMA) 를 셌다). 규칙을 두 builder
# 가 함께 import 하는 이 자리에 한 벌만 둔다 — 한쪽만 고쳐서는 갈릴 수 없게.


def meta_cells(rows, width=4):
    """`doc.meta` 의 한 행을 표 폭에 맞춘다 — 모자라면 채우고 남으면 자른다.

    표지 정보표는 (구분, 내용) 을 두 벌 담는 4칸 표다. spec 은 사람이 손으로 쓰는
    파일이라 칸 수가 안 맞는 것은 오타 축에도 못 끼고, 실제로 **함께 배포하는
    examples/minimal.spec.json 과 SKILL.md 의 예제가 둘 다 4칸**이다.
    """
    out = []
    for r in rows or []:
        cells = [r] if isinstance(r, (str, bytes)) or not hasattr(r, '__iter__') else list(r)
        cells = ['' if c is None else c for c in cells]
        out.append((cells + [''] * width)[:width])
    return out


def meta_pairs(rows, width=4):
    """`meta_cells` 를 (구분, 내용) 쌍으로 편다. 내용이 빈 쌍은 싣지 않는다."""
    return [(c[i], c[i + 1]) for c in meta_cells(rows, width)
            for i in range(0, width - 1, 2) if str(c[i + 1]).strip()]


def doc_text(doc, key, fallback):
    """`doc.<key>` 로 손으로 적은 문단 하나 — 비면 카탈로그 문구로 간다.

    두 문서가 이 값을 **다르게 읽고 있었다.**
      HTML   `DOC.get('mapping_intro') or T('docx.ch6_intro')`
      docx   `DOC.get('mapping_intro', T('docx.ch6_intro'))`
    `"mapping_intro": ""` 를 적으면 docx 는 빈 문단을, HTML 은 카탈로그 문구를 실었다 —
    같은 spec 을 준 사람이 두 문서에서 다른 6장을 받는다. 빈 값의 뜻은 저장소가 이미
    정해 뒀다: **빈 값·공백뿐인 값은 '설정하지 않은 것'** 이다 (config 첫머리의 경로
    규칙과 같다). 그 규칙을 두 builder 가 함께 import 하는 이 자리에 한 벌만 둔다.
    """
    v = doc.get(key)
    return v if v is not None and str(v).strip() else fallback


def doc_tables():
    """문서가 실제로 절을 내주는 테이블 — 영역에 든 순서 그대로.

    두 문서 다 본문은 `AREAS` 를 돌면서 개수는 `len(SCHEMA)` 를 셌다. 영역에 안 든
    테이블이 하나라도 있으면 표지·요약이 말하는 수와 실린 절의 수가 어긋났고, 그
    어긋남을 아무도 말하지 않았다. **싣는 것과 세는 것을 같은 자리에서 뽑는다.**
    그림 캡션만은 그림이 그린 것(SCHEMA)을 센다 — 숫자는 제가 가리키는 것을 센다.
    """
    return [t for a in AREAS for t in a[3]]


def doc_counts(tables=None):
    """(테이블, 컬럼, FK) 수 — 문서가 싣는 것만."""
    ts = doc_tables() if tables is None else list(tables)
    return (len(ts),
            sum(len(SCHEMA[t]['columns']) for t in ts if t in SCHEMA),
            sum(len(SCHEMA[t]['fks']) for t in ts if t in SCHEMA))


def main():
    # 1) GraphML — 전체 22테이블 · 컬럼 설명 포함
    pos, boxes, groups = erd.layout_global()
    gpath = config.PROJ / f'{DOC}.graphml'   # 문서와 같은 위치에 둔다
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
