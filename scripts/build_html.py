#!/usr/bin/env python3
"""schema.json + ERD → 단일 HTML 스키마 정의서.

docx 와 같은 재료로 만들지만 쓰임이 다르다. docx 는 제출·인쇄용이고, 이건
**읽고 찾는 용도**다 — 목차에서 테이블로 바로 뛰고, ERD 는 벡터(SVG)라 확대해도
안 뭉갠다. 이미지가 파일 안에 들어가므로 HTML 한 개만 보내면 된다.

구성
  ① 표지 · DB 요약 · 범례        ② 목차
  ③ [그림1] 전체 구조 개요도      ④ DB > 영역 > 테이블  (영역마다 그 영역 ERD)
  ⑤ 부록: 전체 상세 ERD

  ERD_DOCNAME    산출 파일명            ERD_HTML_FULL=0   부록(전체 상세도) 생략
  ERD_HTML_OUT   경로를 직접 지정        ERD_HTML_SVG=0    SVG 대신 PNG 를 넣는다
  ERD_HTML_STATS=1  테이블 배지에 행수·용량 표시 (기본은 뺀다 — 볼 때마다 바뀌는 값이다)
"""
import base64
import json
import os
import re
from html import escape
from pathlib import Path

from config import DOCNAME, OUT, PROJ
from erd import AREAS, AREA_NAME, AREA_SCHEMA, LAYERS, SCHEMA, SPEC, layer
from i18n import LANG, t as T

DOC = SPEC.get('doc', {})
TITLE = DOC.get('title', DOCNAME)
AREA_DESC = DOC.get('area_desc', {})       # {영역코드: 설명}
DB_NAMES = DOC.get('db_names', {})         # {라벨: 사람이 읽는 이름}
USE_SVG = os.environ.get('ERD_HTML_SVG', '1') not in ('0', 'false', 'no')
WANT_FULL = os.environ.get('ERD_HTML_FULL', '1') not in ('0', 'false', 'no')
SHOW_STATS = os.environ.get('ERD_HTML_STATS', '0') not in ('0', 'false', 'no')

# 한자를 쓰는 말이면 그 글리프를 가진 폰트를 앞에 세운다. 반대로 한국어 문서에서
# 일본어 폰트가 앞서면 한자가 일본식 자형으로 나온다 — 언어에 따라 순서를 바꾼다.
FONT_STACK = ("'Hiragino Sans','Yu Gothic','Noto Sans JP','Meiryo',"
              "'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif"
              if LANG == 'ja' else
              "'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',"
              "'Helvetica Neue',sans-serif")

CSS = """
*{box-sizing:border-box}
body{font-family:__FONTS__;margin:0;
     color:#1a2330;background:#fff;line-height:1.5}
.wrap{max-width:1180px;margin:0 auto;padding:32px 28px 80px}
h1{color:#1F4E78;font-size:24px;margin:0 0 4px}
.sub{color:#5b6b80;font-size:13px;margin-bottom:20px}
h2{color:#fff;background:#1F4E78;padding:10px 14px;border-radius:6px;font-size:18px;margin:34px 0 6px}
h3{color:#1F4E78;font-size:16px;margin:26px 0 6px;background:#eef3fa;border:1px solid #d7dee8;
   border-left:5px solid #2E75B6;border-radius:5px;padding:7px 10px}
h4{color:#1F4E78;font-size:14.5px;margin:20px 0 5px;border-left:4px solid #2E75B6;padding-left:8px;
   scroll-margin-top:12px}
.meta{font-size:12px;color:#5b6b80;margin:2px 0 8px}
.cmt{font-size:12.5px;color:#334;background:#f7f9fc;border:1px solid #d7dee8;border-radius:5px;
     padding:6px 10px;margin:4px 0 8px}
.gdesc{font-size:12.5px;color:#33445a;margin:4px 0 10px;padding-left:4px}
table{border-collapse:collapse;width:100%;font-size:12.5px;margin-bottom:8px}
th,td{border:1px solid #d7dee8;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#2E75B6;color:#fff;font-weight:600}
tr:nth-child(even) td{background:#fafcff}
.pk{color:#b8860b;font-weight:700}.fk{color:#2E75B6;font-weight:600}.uq{color:#7a4fbf;font-weight:600}
.badge{display:inline-block;font-size:11px;background:#eef3fa;border:1px solid #d7dee8;
       border-radius:4px;padding:1px 6px;margin-left:6px;color:#33445a;font-weight:400}
.toc{background:#f7f9fc;border:1px solid #d7dee8;border-radius:8px;padding:14px 18px;margin:18px 0 10px;
     font-size:13px}
.toc a{color:#1F4E78;text-decoration:none}.toc a:hover{text-decoration:underline}
.toc ul{margin:4px 0 10px;padding-left:18px;columns:2}
.toc li{margin:1px 0;break-inside:avoid}
.toc .g{font-weight:600;color:#1F4E78;margin-top:6px;display:block}
.null{color:#a00}.nn{color:#080}
code{background:#eef3fa;padding:1px 4px;border-radius:3px;font-size:11.5px}
details{font-size:12px;color:#33445a;margin:2px 0 10px}
details summary{cursor:pointer;color:#2E75B6;font-weight:600;outline:none}
details .body{padding:6px 10px;background:#fbfcfe;border:1px solid #e3e9f1;border-radius:5px;
              margin-top:4px;white-space:pre-wrap}
.note{background:#fff8e6;border:1px solid #f0dca8;border-radius:6px;padding:10px 14px;
      font-size:12.5px;margin:12px 0}
.small{font-size:11.5px;color:#5b6b80}
.legend{font-size:12px;color:#33445a;margin:6px 0 14px}.legend span{margin-right:14px}
/* ── ERD 도판 ── */
.fig{background:#222;border:1px solid #33383f;border-radius:8px;padding:12px;margin:10px 0 6px;
     overflow-x:auto}
.fig svg,.fig img{max-width:100%;height:auto;display:block;cursor:zoom-in}
.figcap{font-size:12px;color:#5b6b80;margin:0 0 16px;text-align:center}
.figcap b{color:#1F4E78}
#zoom{position:fixed;inset:0;background:rgba(10,12,16,.94);display:none;z-index:99;
      overflow:auto;cursor:zoom-out;padding:20px}
#zoom.on{display:block}
#zoom .inner{min-width:100%;min-height:100%;display:flex;align-items:flex-start;justify-content:center}
#zoom svg,#zoom img{max-width:none;height:auto}
#zoomhint{position:fixed;top:12px;right:16px;color:#9AA0A6;font-size:12px;z-index:100;display:none}
#zoom.on+#zoomhint{display:block}
@media print{.fig{break-inside:avoid}h4{break-after:avoid}}
"""

CSS = CSS.replace('__FONTS__', FONT_STACK)

JS = """
(function(){
 var z=document.getElementById('zoom'),i=z.querySelector('.inner');
 document.querySelectorAll('.fig svg,.fig img').forEach(function(el){
   el.addEventListener('click',function(){
     i.innerHTML='';
     var c=el.cloneNode(true);
     c.removeAttribute('style');
     if(c.tagName.toLowerCase()==='svg'){          // 원본 좌표계 크기로 되돌린다
       var vb=(c.getAttribute('viewBox')||'').split(/\\s+/);
       if(vb.length===4){c.setAttribute('width',vb[2]);c.setAttribute('height',vb[3]);}
     }
     i.appendChild(c); z.classList.add('on');
   });
 });
 z.addEventListener('click',function(){z.classList.remove('on');i.innerHTML='';});
 document.addEventListener('keydown',function(e){
   if(e.key==='Escape'){z.classList.remove('on');i.innerHTML='';}});
})();
"""


# ── 도판 ────────────────────────────────────────────────────────────────────
_FIG_N = [0]


def figure(stem, caption):
    """out/<stem>.svg 를 본문에 인라인으로 박는다. 없으면 PNG, 그것도 없으면 건너뛴다."""
    svg, png = OUT / f'{stem}.svg', OUT / f'{stem}.png'
    if USE_SVG and svg.exists():
        body = svg.read_text(encoding='utf-8')
        body = body[body.index('<svg'):]                  # xml 선언 제거
        # 폭은 CSS 가 정하게 하고 비율은 viewBox 가 지킨다
        body = re.sub(r'^<svg([^>]*?)\swidth="[\d.]+"\s+height="[\d.]+"', r'<svg\1', body, count=1)
    elif png.exists():
        b64 = base64.b64encode(png.read_bytes()).decode()
        body = f'<img src="data:image/png;base64,{b64}" alt="{escape(caption)}">'
    else:
        return ''
    _FIG_N[0] += 1
    return (f'<div class="fig">{body}</div>'
            f'<p class="figcap"><b>{escape(T("word.fig_no", n=_FIG_N[0]))}</b> {escape(caption)}'
            f' <span class="small">{escape(T("html.fig_zoom"))}</span></p>')


# ── 조각 ────────────────────────────────────────────────────────────────────
def anchor(tkey):
    return 'tb_' + re.sub(r'[^a-zA-Z0-9_]', '_', tkey)


def db_of(tkey):
    return SCHEMA[tkey].get('db', '') or ''


def db_label(db):
    return DB_NAMES.get(db, db or T('html.single_db'))


def col_flags(t, c):
    """키/참조 칸 — PK · FK(삭제규칙) · UQ 를 한 칸에 모은다."""
    out = []
    if c['name'] in t['pk']:
        out.append('<span class="pk">● PK</span>')
    for fk in t['fks']:
        if fk['column'] == c['name']:
            ref = SCHEMA.get(fk['ref_table'], {}).get('name', fk['ref_table'])
            rule = fk.get('on_delete', 'NO ACTION')
            tail = f' <span class="small">{escape(rule)}</span>' if rule not in ('NO ACTION', '') else ''
            out.append(f'<span class="fk">→ <a href="#{anchor(fk["ref_table"])}">'
                       f'{escape(ref)}.{escape(fk["ref_column"])}</a></span>{tail}')
    if any(c['name'] in u for u in t.get('uniques', [])):
        out.append('<span class="uq">UQ</span>')
    return '<br>'.join(out) or '-'


def table_block(tkey):
    t = SCHEMA[tkey]
    badges = [f'cols {len(t["columns"])}']
    # 행수·용량은 볼 때마다 달라지는 통계값이라 기본으론 뺀다 (ERD_HTML_STATS=1 로 켠다)
    if SHOW_STATS:
        if t.get('rows') is not None:
            badges.insert(0, f'rows ≈ {t["rows"]:,}')
        if t.get('size'):
            badges.append(t['size'])
    # 제목에 테이블 키를 쓴다. 이름만 쓰면 mart.orders 와 public.orders 가 둘 다
    # <h4>orders</h4> 가 되어, 이전 판에서 설명을 물려받을 때 한쪽 설명이 다른
    # 테이블로 옮겨 붙는다 (docx 는 이미 키를 쓴다). 단일 DB 면 키가 곧 이름이다.
    h = [f'<h4 id="{anchor(tkey)}">{escape(tkey)}'
         + ''.join(f'<span class="badge">{escape(b)}</span>' for b in badges) + '</h4>']

    lay = LAYERS.get(layer(tkey))
    if lay:
        h.append('<div class="meta">' + escape(T(
            'html.meta_area_layer',
            area=AREA_NAME.get(area_of(tkey), ''), layer=lay[3])) + '</div>')
    role = SPEC['roles'].get(tkey) or t.get('note', '')
    if role:
        h.append(f'<div class="cmt"><b>{escape(T("html.role"))}</b> · {escape(role)}</div>')

    h.append('<table><thead><tr>'
             "<th style='width:32px'>#</th>"
             f"<th style='width:190px'>{escape(T('col.name'))}</th>"
             f"<th style='width:150px'>{escape(T('col.type'))}</th>"
             "<th style='width:64px'>Null</th>"
             f"<th style='width:120px'>{escape(T('col.default'))}</th>"
             f"<th style='width:200px'>{escape(T('col.key'))}</th>"
             f"<th>{escape(T('col.desc'))}</th></tr></thead><tbody>")
    for i, c in enumerate(t['columns'], 1):
        name = (f'<span class="pk">{escape(c["name"])}</span>'
                if c['name'] in t['pk'] else escape(c['name']))
        nn = ('<span class="nn">NOT NULL</span>' if c['not_null']
              else '<span class="null">NULL</span>')
        dflt = f'<code>{escape(c["default"])}</code>' if c['default'] else '-'
        h.append(f'<tr><td>{i}</td><td>{name}</td><td><code>{escape(c["type"])}</code></td>'
                 f'<td>{nn}</td><td>{dflt}</td><td>{col_flags(t, c)}</td>'
                 f'<td>{escape(c.get("comment") or "")}</td></tr>')
    h.append('</tbody></table>')

    # 제약 · 인덱스 — 접어 둔다. 평소엔 안 보고, 필요할 때만 편다.
    lines = [f'UNIQUE ({", ".join(u)})' for u in t.get('uniques', [])]
    lines += [f'CHECK {c["name"]}: {c["def"]}' for c in t.get('checks', [])]
    lines += [ix['def'] for ix in t.get('indexes', [])]
    if lines:
        h.append(f'<details><summary>{escape(T("html.constraints", n=len(lines)))}</summary>'
                 f'<div class="body">{escape(chr(10).join(lines))}</div></details>')
    return '\n'.join(h)


_AREA_OF = {t: a[0] for a in AREAS for t in a[3]}


def area_of(tkey):
    return _AREA_OF.get(tkey, '')


# ── 문서 ────────────────────────────────────────────────────────────────────
def build():
    dbs = []
    for a in AREAS:
        db = db_of(a[3][0]) if a[3] else ''
        if db not in dbs:
            dbs.append(db)

    h = [f'<h1>{escape(TITLE)}</h1>']
    meta = ' &nbsp;|&nbsp; '.join(
        f'{escape(k)}: {escape(str(v))}' for k, v in (DOC.get('meta') or []) if v)
    h.append(f'<div class="sub">{meta}</div>' if meta else '')
    if DOC.get('intro'):
        h.append(f'<div class="cmt">{DOC["intro"]}</div>')

    # DB 요약
    h.append('<table><thead><tr><th>DB</th>'
             f'<th>{escape(T("word.areas"))}</th><th>{escape(T("word.tables"))}</th>'
             f'<th>{escape(T("word.columns"))}</th><th>FK</th></tr></thead><tbody>')
    for db in dbs:
        ts = [t for t in SCHEMA if db_of(t) == db]
        h.append(f'<tr><td><b>{escape(db_label(db))}</b></td>'
                 f'<td>{sum(1 for a in AREAS if a[3] and db_of(a[3][0]) == db)}</td>'
                 f'<td>{len(ts)}</td><td>{sum(len(SCHEMA[t]["columns"]) for t in ts)}</td>'
                 f'<td>{sum(len(SCHEMA[t]["fks"]) for t in ts)}</td></tr>')
    h.append('</tbody></table>')
    h.append('<div class="legend">'
             f'<span><span class="pk">● PK</span> {escape(T("word.pk"))}</span>'
             f'<span><span class="fk">→</span> {escape(T("word.fk"))}</span>'
             f'<span><span class="uq">UQ</span> {escape(T("word.unique"))}</span>'
             + (f'<span>{escape(T("html.rows_note"))}</span>' if SHOW_STATS else '')
             + '</div>')

    # 목차
    h.append(f'<div class="toc"><b>{escape(T("html.toc"))}</b>')
    for db in dbs:
        areas = [a for a in AREAS if a[3] and db_of(a[3][0]) == db]
        n = sum(len(a[3]) for a in areas)
        h.append('<div class="g">' + escape(T('html.db_tables', db=db_label(db), n=n))
                 + '</div>')
        for a in areas:
            h.append(f'<div class="g">&nbsp;&nbsp;<a href="#area_{a[0]}">'
                     f'{escape(AREA_NAME[a[0]])}</a></div><ul>')
            for t in a[3]:
                h.append(f'<li><a href="#{anchor(t)}">{escape(SCHEMA[t]["name"])}</a></li>')
            h.append('</ul>')
    h.append('</div>')

    # 첫 장 — 전체 구조 한눈에
    h.append(f'<h2>{escape(T("html.overall"))}</h2>')
    h.append(figure('erd_overview',
                    T('html.overview_cap', title=TITLE, n=len(SCHEMA))))
    if LAYERS:
        h.append('<div class="legend">' + ''.join(
            f'<span><span class="badge" style="background:{v[0]};border-color:{v[2]};'
            f'color:#fff">&nbsp;</span> {escape(v[3])}</span>' for v in LAYERS.values())
            + '</div>')

    # 본문
    for db in dbs:
        areas = [a for a in AREAS if a[3] and db_of(a[3][0]) == db]
        h.append('<h2>' + escape(T('html.db_tables', db=db_label(db),
                                     n=sum(len(a[3]) for a in areas))) + '</h2>')
        for a in areas:
            code, name, _sch, tables = a
            h.append(f'<h3 id="area_{code}">{escape(name)}'
                     f'<span class="badge">{len(tables)} tables</span></h3>')
            if AREA_DESC.get(code):
                h.append(f'<div class="gdesc">{escape(AREA_DESC[code])}</div>')
            h.append(figure(f'erd_area_{code}', T('html.area_cap', name=name)))
            for t in tables:
                h.append(table_block(t))

    # 부록 — 전체 상세도
    if WANT_FULL:
        fig = figure('erd_full', T('html.full_cap', title=TITLE))
        if fig:
            h.append(f'<h2>{escape(T("html.appendix"))}</h2>')
            h.append(f'<div class="gdesc">{escape(T("html.appendix_desc"))}</div>')
            h.append(fig)

    body = '\n'.join(x for x in h if x)
    return (f'<!DOCTYPE html><html lang="{LANG}"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{escape(TITLE)}</title><style>{CSS}</style></head><body>'
            f'<div class="wrap">{body}</div>'
            f'<div id="zoom"><div class="inner"></div></div>'
            f'<div id="zoomhint">{escape(T("html.zoomhint"))}</div>'
            f'<script>{JS}</script></body></html>')


def main():
    out = Path(os.environ.get('ERD_HTML_OUT', PROJ / f'{DOCNAME}.html')).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    html = build()
    out.write_text(html, encoding='utf-8')
    n_fig = _FIG_N[0]
    print(T('log.html_done', tables=len(SCHEMA), areas=len(AREAS), figs=n_fig,
            mb=f'{len(html) / 1e6:.1f}', name=out.name))
    missing = [f'erd_area_{a[0]}' for a in AREAS
               if not (OUT / f'erd_area_{a[0]}.svg').exists()
               and not (OUT / f'erd_area_{a[0]}.png').exists()]
    if missing:
        print(T('log.html_missing', n=len(missing),
                list=', '.join(missing[:6]) + (' …' if len(missing) > 6 else '')))


if __name__ == '__main__':
    main()
