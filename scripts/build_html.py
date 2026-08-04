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
import hashlib
import json
import os
import re
from html import escape
from pathlib import Path

from build_erd import doc_tables, doc_text, meta_cells, meta_pairs, require_fresh
# 경로를 받는 환경변수는 전부 한 규칙을 쓴다 — 디렉토리를 가리키면 그 변수의 이름을
# 대고 멈춘다. 규칙은 config 에 **한 벌만** 둔다.
#
# 여기엔 예전에 `try: from config import as_file / except ImportError:` 로 제 사본을
# 둔 폴백이 있었다. 이 트리에서는 도달할 수 없는 죽은 코드였고(config 는 늘 그 이름을
# 준다), 도달했다면 카탈로그를 안 거친 **영어 문자열**을 뱉어 `ERD_LANG=ko` 에서도
# 영어가 나왔다 — 말없이 규칙이 갈리는 자리였다. 사본을 지우고 규칙 하나만 쓴다.
# (사람에게 나가는 모든 줄이 카탈로그를 거치는지는 시험이 소스에서 직접 센다.)
#
# 경로 값(OUT·PROJ)은 `config` 를 통해 **쓰는 자리에서** 묻는다. 그 이름들은 PEP 562
# 모듈 __getattr__ 로 늦춰져 있어서, `from config import OUT` 한 줄이 import 시점에
# 그 물음을 던지고 mkdir 을 돌린다 — DB 도 안 보고 그림도 안 그리는 import 하나가
# 부르는 사람의 cwd 에 `erd-build/out` 을 만들었다. 15라운드가 config·i18n·parse_ddl·
# introspect 에 세운 '**import 는 아무것도 안 만든다**' 를 이 파일도 지킨다.
import config
from config import DOCNAME, as_file, env_flag
from erd import AREAS, AREA_NAME, AREA_SCHEMA, LAYERS, SCHEMA, SPEC, layer
from i18n import LANG, t as T

DOC = SPEC.get('doc', {})
TITLE = DOC.get('title', DOCNAME)
AREA_DESC = DOC.get('area_desc', {})       # {영역코드: 설명}
DB_NAMES = DOC.get('db_names', {})         # {라벨: 사람이 읽는 이름}
# 6·7장 재료 — docx 와 **같은 자리**에서 읽는다. 없으면 그 장을 통째로 생략한다.
MAPPING = [list(r) for r in DOC.get('mapping', [])]
OPEN_ITEMS = [list(r) for r in DOC.get('open_items', [])]
USE_SVG = env_flag('ERD_HTML_SVG', True)
WANT_FULL = env_flag('ERD_HTML_FULL', True)
SHOW_STATS = env_flag('ERD_HTML_STATS', False)

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
    out = config.OUT
    svg, png = out / f'{stem}.svg', out / f'{stem}.png'
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
# id 는 테이블 키마다 **달라야** 하고, **그 키만 보고 정해져야** 한다. 이건 읽는
# 사람이 URL 로 쓰는 값이고, 어제 보낸 `#tb_x_y` 가 오늘 남의 테이블로 가면 그 링크는
# 틀렸다고 말해 주지도 않는다.
#
# 두 판이 있었고 둘 다 한쪽만 지켰다.
#   · `'tb_' + re.sub(r'[^a-zA-Z0-9_]', '_', k)` — 뭉개는 함수라 **단사가 아니다**.
#     `order-items` 와 `order_items` 가 같은 `tb_order_items` 가 됐고, 다중 DB 에서는
#     `a.b_c` 와 `a_b.c` 가 부딪혔다. 같은 id 가 둘이면 목차도 FK 상호참조도 전부
#     앞엣것으로 가서, 문서가 조용히 남의 테이블을 가리킨다.
#   · 겹칠 때마다 `_2`·`_3` 꼬리를 붙이던 판 — 단사이긴 한데 **꼬리가 옮겨 앉는다**.
#     `x-y`·`x.y` 뿐이던 문서에 `x y` 하나가 늘면 `tb_x_y` 도 `tb_x_y_2` 도 어제와
#     다른 테이블로 간다. 스키마가 자라기만 해도 발행한 URL 이 전부 틀려진다.
#
# 그래서 꼬리를 **키에서 결정적으로 뽑는다**. 다른 키가 무엇이 있든, 어떤 순서로
# 오든, 한 키의 id 는 늘 같은 값이다 — 순수 함수다.
#   · 뭉개지지 않는 키(영숫자·밑줄만)는 제 이름을 그대로 갖는다. 이 사상은 항등이라
#     서로 부딪힐 수가 없다.
#   · 나머지는 뭉갠 이름 뒤에 `-` 와 키의 sha1 앞 12자리를 붙인다. `-` 는 뭉갠 이름에도
#     안전한 이름에도 들어갈 수 없는 글자라, 두 갈래가 서로 부딪히는 일이 없다.
#     남는 것은 '같은 이름으로 뭉개지면서 sha1 48비트까지 같은 두 키' 뿐이다.
# 단사성은 여전히 시험이 직접 센다 — 값의 개수와 키의 개수가 같은지, 그리고 모든
# href 가 정확히 하나의 id 에 앉는지.
_SAFE = re.compile(r'[A-Za-z0-9_]*')


def _ident(prefix, raw):
    raw = str(raw)
    if _SAFE.fullmatch(raw):
        return prefix + raw
    tail = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]
    return f'{prefix}{re.sub(r"[^A-Za-z0-9_]", "_", raw)}-{tail}'


def anchor(tkey):
    """테이블 키 → 절의 id. SCHEMA 밖의 키(FK 가 가리키는 남의 테이블)도 같은 규칙."""
    return _ident('tb_', tkey)


LISTED = doc_tables()                    # 이 문서가 절을 내주는 테이블 (실리는 순서)
LISTED_SET = set(LISTED)


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
            ref_txt = f'{escape(ref)}.{escape(fk["ref_column"])}'
            # 절이 없는 테이블로는 링크를 걸지 않는다 — 누르면 아무 데도 안 가는 링크가
            # 되고, '모든 href 가 정확히 하나의 id 에 맞는다' 도 거짓이 된다.
            body = (f'<a href="#{anchor(fk["ref_table"])}">{ref_txt}</a>'
                    if fk['ref_table'] in LISTED_SET else ref_txt)
            out.append(f'<span class="fk">→ {body}</span>{tail}')
    if any(c['name'] in u for u in t.get('uniques', [])):
        out.append('<span class="uq">UQ</span>')
    return '<br>'.join(out) or '-'


def table_block(tkey):
    t = SCHEMA[tkey]
    # 배지의 말도 카탈로그를 거친다. 예전엔 `f'cols {n}'` 이라 **네 언어 전부**
    # `cols 3` 이었다 — 같은 값을 docx 는 `T('word.columns')` 로 내므로, 한 사람이
    # 받은 두 문서가 같은 칸을 다른 말로 불렀다.
    badges = [f'{T("word.columns")} {len(t["columns"])}']
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
             # 이 칸만 카탈로그를 못 거친다 — 카탈로그에 `col.null` 이 없다.
             # (16라운드 수정자 C 에게 넘긴 키다. 나머지 여섯 칸은 전부 `col.*` 을
             #  쓴다.) 그때까지는 네 언어에서 같은 낱말이 나오고, 그 사실을
             #  `html: every label … goes through the catalog` 케이스가 **이름을
             #  대고** 봐준다 — 다른 낱말로 바뀌면 그 케이스가 빨강이다.
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


# ── DB 묶음 — 영역이 아니라 테이블마다의 db 로 정한다 ───────────────────────
# 예전엔 `db_of(a[3][0])`, 곧 영역의 **첫 테이블**이 그 영역 전체의 DB 였다. 그런데
# 개수는 `db_of(t)`, 곧 테이블마다 제 DB 로 셌다. SKILL.md 가 권하는 다중 DB 흐름에서
# 영역을 기능별로 적으면 한 영역에 두 DB 가 섞이고, 그때
#   (a) <h2>·목차가 남의 DB 테이블까지 이 DB 것으로 적었고
#   (b) 어느 영역의 첫 테이블도 아닌 DB 는 요약표에서 **행 자체가 사라졌다**
#       — doc.db_names 로 이름까지 적어 준 DB 인데도.
# 묶는 기준을 세는 기준에 맞춘다. 한 영역이 두 DB 에 걸치면 절이 DB 마다 하나씩
# 생기고, 그 절은 제 배지로 어느 DB 의 몫인지 말한다.
def area_slices():
    """[(db, [(영역, 그 DB 에 속한 그 영역의 테이블), …]), …] — DB 는 처음 나온 순서."""
    dbs = []
    for t in LISTED:
        if db_of(t) not in dbs:
            dbs.append(db_of(t))
    out = []
    for db in dbs:
        parts = []
        for a in AREAS:
            ts = [t for t in a[3] if db_of(t) == db]
            if ts:
                parts.append((a, ts))
        out.append((db, parts))
    return out


SLICES = area_slices()


def area_id(code, db):
    """영역 절의 id. 테이블 앵커와 **같은 부류**라 같은 규칙을 쓴다.

    한 영역이 두 DB 에 걸치면 절이 DB 마다 하나씩 생기므로 id 도 하나씩이어야 한다.
    예전엔 그 둘째 자리를 `area_A_2` 로 셌는데, 그러면 DB 가 나온 순서가 바뀌거나
    DB 하나가 늘기만 해도 `area_A` 와 `area_A_2` 가 서로 다른 절로 옮겨 앉는다 —
    테이블 앵커에서 고친 것과 똑같은 결함이다. id 를 (영역코드, DB) 쌍에서만 뽑는다.
    단일 DB(빈 라벨) 면 예전 그대로 `area_A` 이므로 발행된 링크가 그대로 산다.
    """
    return _ident('area_', code if not db else f'{code}\x1f{db}')


AREA_ID = {(a[0], db): area_id(a[0], db) for db, parts in SLICES for a, _ts in parts}
AREA_DBS = {}                   # 영역코드 → 걸쳐 있는 DB 들 (처음 나온 순서)
for _db, _parts in SLICES:
    for _a, _ts in _parts:
        AREA_DBS.setdefault(_a[0], []).append(_db)


# ── 문서 ────────────────────────────────────────────────────────────────────
def build():
    h = [f'<h1>{escape(TITLE)}</h1>']
    # 표지 정보표는 (구분, 내용) 을 두 벌 담는 4칸 표다 — docx 가 처음부터 그렇게 받았다.
    # 여기만 `for k, v in …` 로 2칸을 언팩해서, 4칸으로 적은 배포 예제와 SKILL.md 의
    # 예제가 둘 다 ValueError 로 죽었다. 같은 값을 두 문서가 같은 규칙으로 읽는다.
    meta = ' &nbsp;|&nbsp; '.join(
        f'{escape(str(k))}: {escape(str(v))}' for k, v in meta_pairs(DOC.get('meta')))
    h.append(f'<div class="sub">{meta}</div>' if meta else '')
    if DOC.get('intro'):
        # **여기만 escape() 를 안 한다.** 일부러다 — 함께 배포하는
        # examples/full.spec.json 의 intro 가 `<b>역할</b>` 처럼 마크업을 쓴다.
        # 나머지 doc.* 값(title·meta·area_desc·db_names·mapping*·open*)과 스키마에서
        # 온 모든 문자열은 전부 escape() 를 지난다. 그 경계를 아무 데도 안 적어 두면
        # 다음 사람이 '여기가 escape 를 빼먹었다' 고 읽거나, 반대로 다른 자리에서
        # escape 를 빼도 같은 예외로 보인다 — 그래서 이 한 줄이 예외라고 못박는다.
        # (spec 을 쓰는 사람 = 문서를 내는 사람이라 주입 경로는 아니다.)
        h.append(f'<div class="cmt">{DOC["intro"]}</div>')

    # DB 요약
    h.append('<table><thead><tr><th>DB</th>'
             f'<th>{escape(T("word.areas"))}</th><th>{escape(T("word.tables"))}</th>'
             f'<th>{escape(T("word.columns"))}</th><th>FK</th></tr></thead><tbody>')
    # 세는 것은 **이 문서가 싣는 것** 이다. 예전엔 SCHEMA 를 세고 본문은 영역을 돌아,
    # 영역에 안 든 테이블이 있으면 요약표가 문서에 없는 절까지 세고 있었다.
    for db, parts in SLICES:
        ts = [t for _a, sub in parts for t in sub]
        h.append(f'<tr><td><b>{escape(db_label(db))}</b></td>'
                 f'<td>{len(parts)}</td>'
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
    for db, parts in SLICES:
        n = sum(len(ts) for _a, ts in parts)
        h.append('<div class="g">' + escape(T('html.db_tables', db=db_label(db), n=n))
                 + '</div>')
        for a, ts in parts:
            h.append(f'<div class="g">&nbsp;&nbsp;<a href="#{AREA_ID[(a[0], db)]}">'
                     f'{escape(AREA_NAME[a[0]])}</a></div><ul>')
            for t in ts:
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
    for db, parts in SLICES:
        h.append('<h2>' + escape(T('html.db_tables', db=db_label(db),
                                     n=sum(len(ts) for _a, ts in parts))) + '</h2>')
        for a, tables in parts:
            code, name = a[0], a[1]
            # 영역이 여러 DB 에 걸치면 그 사실을 말한다 — 이 절은 그중 한 DB 의 몫이다.
            span = (f'<span class="badge">{escape(db_label(db))}</span>'
                    if len(AREA_DBS.get(code, [])) > 1 else '')
            h.append(f'<h3 id="{AREA_ID[(code, db)]}">{escape(name)}'
                     f'<span class="badge">{escape(T("word.tables"))} {len(tables)}'
                     f'</span>{span}</h3>')
            if AREA_DESC.get(code):
                h.append(f'<div class="gdesc">{escape(AREA_DESC[code])}</div>')
            # 영역 그림은 영역 전체를 그린다 — 나뉜 절마다 같은 그림을 또 싣지 않는다.
            if AREA_DBS.get(code, [db])[0] == db:
                h.append(figure(f'erd_area_{code}', T('html.area_cap', name=name)))
            for t in tables:
                h.append(table_block(t))

    # ── 6·7장 — spec 이 손으로 적어 넣는 표 ──
    # 예전 판은 `doc.derives`·`doc.mapping`·`doc.open_items` 셋이 HTML 에 없는 것을
    # 하나의 근거("매체 차이")로 함께 넘겼다. 그 근거는 셋 중 하나에만 참이다 —
    # derives 는 HTML 이 인라인 SVG 안에 실제로 그리고 있어 표가 없어도 문서에 있다.
    # 반면 이 둘은 **표로만 실리는 것**이라, 표를 안 그리면 그냥 빠진 것이다. 같은
    # spec 을 준 사람이 docx 에는 있고 HTML 에는 없는 장을 갖게 된다.
    # 말은 docx 와 같은 카탈로그 항목을 쓴다 — 두 문서가 같은 장을 다른 말로 부르면
    # 그것이 또 하나의 '같은 재료를 다르게 읽는 자리' 가 된다.
    for rows, head, intro, note, cols in (
            (MAPPING, 'docx.ch6', doc_text(DOC, 'mapping_intro', T('docx.ch6_intro')),
             DOC.get('mapping_note'),
             ['No', T('word.proposed'), T('word.actual_table'), T('word.applied'),
              T('word.reason')]),
            (OPEN_ITEMS, 'docx.ch7', T('docx.ch7_intro'), DOC.get('open_note'),
             [T('word.priority'), T('word.item'), T('word.target'), T('word.current'),
              T('word.action')])):
        if not rows:
            continue
        h.append(f'<h2>{escape(T(head))}</h2>')
        h.append(f'<div class="gdesc">{escape(str(intro))}</div>')
        h.append('<table><thead><tr>'
                 + ''.join(f'<th>{escape(c)}</th>' for c in cols)
                 + '</tr></thead><tbody>')
        # 칸이 남거나 모자란 행을 맞추는 규칙도 docx 와 한 자리에서 가져온다.
        for cells in meta_cells(rows, width=len(cols)):
            h.append('<tr>' + ''.join(f'<td>{escape(str(c))}</td>' for c in cells)
                     + '</tr>')
        h.append('</tbody></table>')
        if note:
            h.append(f'<div class="small">{escape(str(note))}</div>')

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
    # 박을 그림이 지금 스키마의 것인지 먼저 본다 — 쓰고 나서 알려 줘 봐야 이미
    # 어긋난 문서가 나간 뒤다. SVG 를 쓰더라도 없으면 PNG 로 떨어지므로 둘 다 본다.
    require_fresh(['erd_overview'] + [f'erd_area_{a[0]}' for a in AREAS]
                  + (['erd_full'] if WANT_FULL else []),
                  ('.svg', '.png') if USE_SVG else ('.png',))
    # 빈 값은 '설정하지 않은 것' 으로 친다 — 다른 경로 변수들과 같은 규칙이다.
    # 디렉토리를 가리키면 `IsADirectoryError` 역추적 대신 변수 이름을 대고 멈춘다.
    raw = os.environ.get('ERD_HTML_OUT', '')
    out = Path(raw if raw.strip()
               else config.PROJ / f'{DOCNAME}.html').expanduser()
    out = as_file(out, 'ERD_HTML_OUT')
    out.parent.mkdir(parents=True, exist_ok=True)
    html = build()
    out.write_text(html, encoding='utf-8')
    n_fig = _FIG_N[0]
    # 세는 것은 문서가 싣는 것이다 (len(SCHEMA) 는 문서에 없는 절까지 셌다).
    print(T('log.html_done', tables=len(LISTED), areas=len(AREAS), figs=n_fig,
            mb=f'{len(html) / 1e6:.1f}', name=out.name))
    # 빠진 그림은 영역 것만 세고 있었다 — 개요도나 부록 전체도가 통째로 없어도
    # 조용히 빠진 채로 문서가 나갔다. 박으려던 것 전부를 센다.
    want = ['erd_overview'] + [f'erd_area_{a[0]}' for a in AREAS] \
        + (['erd_full'] if WANT_FULL else [])
    missing = [s for s in want
               if not (config.OUT / f'{s}.svg').exists()
               and not (config.OUT / f'{s}.png').exists()]
    if missing:
        print(T('log.figs_missing', n=len(missing),
                list=', '.join(missing[:6]) + (' …' if len(missing) > 6 else '')))


if __name__ == '__main__':
    main()
