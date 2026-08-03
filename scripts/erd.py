#!/usr/bin/env python3
"""schema.json → ERD 산출물 (DataGrip 다크 스타일)

  1) GraphML (yEd entityRelationship 노드 · 컬럼 설명 포함)
  2) PNG    (전체 개요도 + 영역별 상세도 · 문서 삽입용)
  3) SVG    (PNG 와 같은 그림을 벡터로 — HTML 문서 삽입용)

색은 **레이어**로 구분하고 배치는 **영역**으로 묶는다. 둘 다 erd.spec.json 이
정하며, spec 이 없으면 스키마와 테이블명 접두어로 자동 분류한다.
"""
import json
import os
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image, ImageDraw, ImageFont

Image.MAX_IMAGE_PIXELS = None      # 우리가 만드는 그림이라 폭탄 검사 불필요
MAX_PIXELS = 160_000_000           # 이보다 커지면 배율을 낮춘다

from config import OUT, SCHEMA_JSON, load_spec
from i18n import LANG, t as T
from svg_canvas import SvgCanvas

SCHEMA = json.loads(SCHEMA_JSON.read_text())

# PNG 옆에 같은 그림을 SVG 로도 남긴다. ERD_SVG=0 이면 끈다.
SVG_OUT = os.environ.get('ERD_SVG', '1') not in ('0', 'false', 'no')
# SVG 는 문서에 박아 쓰는 용도라 그림 안 제목을 뺀다 (캡션이 따로 붙는다).
SVG_TITLE = os.environ.get('ERD_SVG_TITLE', '0') not in ('0', 'false', 'no')

# ── 폰트 선택 ────────────────────────────────────────────────────────────────
# 본문은 Pretendard 를 쓴다. 없으면 OS 기본 한글 폰트로 내려간다.
# 각 후보는 (regular, bold) 쌍이고, 각 항목은 (경로, ttc face index).
# .ttc 는 한 파일에 여러 face 가 들어 있어 index 로 볼드를 고르고,
# .otf/.ttf 는 굵기마다 파일이 따로다 — 그래서 쌍으로 관리한다.
# 환경변수 ERD_FONT / ERD_FONT_BOLD / ERD_MONO / ERD_MONO_BOLD 가 항상 이긴다.
_H = str(Path.home())
_SANS_CANDIDATES = [
    (f'{_H}/Library/Fonts/Pretendard-Regular.otf',  f'{_H}/Library/Fonts/Pretendard-Bold.otf'),
    ('/Library/Fonts/Pretendard-Regular.otf',       '/Library/Fonts/Pretendard-Bold.otf'),
    (f'{_H}/.local/share/fonts/Pretendard-Regular.otf',
     f'{_H}/.local/share/fonts/Pretendard-Bold.otf'),
    ('/usr/share/fonts/opentype/pretendard/Pretendard-Regular.otf',
     '/usr/share/fonts/opentype/pretendard/Pretendard-Bold.otf'),
    ('/usr/share/fonts/truetype/pretendard/Pretendard-Regular.ttf',
     '/usr/share/fonts/truetype/pretendard/Pretendard-Bold.ttf'),
    # ── 폴백: OS 기본 폰트 (한글 · 일본어 · 라틴 순으로 훑는다) ──
    ('/System/Library/Fonts/AppleSDGothicNeo.ttc',                     # macOS
     ('/System/Library/Fonts/AppleSDGothicNeo.ttc', 1)),
    ('/System/Library/Fonts/Hiragino Sans GB.ttc',                     # macOS · 일본어
     ('/System/Library/Fonts/Hiragino Sans GB.ttc', 1)),
    ('/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf',
     '/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf'),
    ('/usr/share/fonts/truetype/nanum/NanumGothic.ttf',                # Debian/Ubuntu
     '/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf'),
    ('/usr/share/fonts/nanum/NanumGothic.ttf',                         # Fedora/RHEL
     '/usr/share/fonts/nanum/NanumGothicBold.ttf'),
    ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
     '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'),
    ('C:/Windows/Fonts/malgun.ttf', 'C:/Windows/Fonts/malgunbd.ttf'),  # Windows
    ('C:/Windows/Fonts/YuGothM.ttc', 'C:/Windows/Fonts/YuGothB.ttc'),  # Windows · 일본어
]

# 라틴만 덮는 폰트. 한글·한자를 쓰는 말에는 붙이지 않는다 — 이걸로 그리면 글자가 전부
# □ 로 나오는데, 그림은 '성공' 으로 끝나 버려 두부 문서를 그대로 배포하게 된다.
# 못 찾고 죽는 편이 낫다.
_LATIN_CANDIDATES = [
    ('/System/Library/Fonts/Helvetica.ttc',                            # macOS
     ('/System/Library/Fonts/Helvetica.ttc', 1)),
    ('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
     '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
    ('/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf',
     '/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf'),
    ('C:/Windows/Fonts/arial.ttf', 'C:/Windows/Fonts/arialbd.ttf'),
]
if LANG not in ('ko', 'ja'):
    _SANS_CANDIDATES = _SANS_CANDIDATES + _LATIN_CANDIDATES

# Pretendard 는 한글·라틴은 덮지만 한자는 덮지 못한다 — 일본어로 뽑을 땐 한자가
# □ 로 나오므로, 그 언어의 폰트를 앞에 세운다.
_JA_CANDIDATES = [
    ('/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc',                  # macOS (일본어)
     '/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc'),
    ('/Library/Fonts/ヒラギノ角ゴ ProN W3.otf',
     '/Library/Fonts/ヒラギノ角ゴ ProN W6.otf'),
    ('/System/Library/Fonts/NotoSansJP-Regular.otf',
     '/System/Library/Fonts/NotoSansJP-Bold.otf'),
    ('/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
     '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc'),
    ('/usr/share/fonts/opentype/noto/NotoSansJP-Regular.otf',
     '/usr/share/fonts/opentype/noto/NotoSansJP-Bold.otf'),
    ('C:/Windows/Fonts/YuGothM.ttc', 'C:/Windows/Fonts/YuGothB.ttc'),  # Windows
    ('C:/Windows/Fonts/meiryo.ttc', 'C:/Windows/Fonts/meiryob.ttc'),
    ('/System/Library/Fonts/Osaka.ttf', '/System/Library/Fonts/Osaka.ttf'),
    # 마지막 수단. GB 는 간체 중국어용이라 한자 자형이 중국식이다(骨·直 등이 다르게
    # 보인다). 그래도 일본어 폰트가 하나도 없을 때 □ 보다는 읽을 수 있다.
    (('/System/Library/Fonts/Hiragino Sans GB.ttc', 0),
     ('/System/Library/Fonts/Hiragino Sans GB.ttc', 2)),
]
if LANG == 'ja':
    _SANS_CANDIDATES = _JA_CANDIDATES + _SANS_CANDIDATES
_MONO_CANDIDATES = [
    ('/System/Library/Fonts/Menlo.ttc', ('/System/Library/Fonts/Menlo.ttc', 1)),
    ('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf',
     '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'),
    ('/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono.ttf',
     '/usr/share/fonts/dejavu-sans-mono-fonts/DejaVuSansMono-Bold.ttf'),
    ('/usr/share/fonts/truetype/liberation/LiberationMono-Regular.ttf',
     '/usr/share/fonts/truetype/liberation/LiberationMono-Bold.ttf'),
    ('C:/Windows/Fonts/consola.ttf', 'C:/Windows/Fonts/consolab.ttf'),
]


def _face(entry):
    """후보 항목 → (경로, index). 문자열이면 index 0."""
    return entry if isinstance(entry, tuple) else (entry, 0)


def _pick_font(env, candidates, kind):
    """(regular, bold) 를 고른다. 볼드 파일이 없으면 regular 로 대신한다."""
    reg, bold = os.environ.get(env), os.environ.get(env + '_BOLD')
    if reg:
        if not Path(reg).exists():
            raise SystemExit(T('err.font_env', env=env, path=reg))
        return (reg, 0), ((bold, 0) if bold and Path(bold).exists() else (reg, 0))
    for r, b in candidates:
        rp, ri = _face(r)
        if not Path(rp).exists():
            continue
        bp, bi = _face(b)
        return (rp, ri), ((bp, bi) if Path(bp).exists() else (rp, ri))
    raise SystemExit(T('err.font_none', kind=kind, env=env,
                       looked=', '.join(_face(r)[0] for r, _ in candidates)))


FONT, FONT_B = _pick_font('ERD_FONT', _SANS_CANDIDATES, T('word.font_body'))
MONO, MONO_B = _pick_font('ERD_MONO', _MONO_CANDIDATES, T('word.font_mono'))
FONT_PATH, MONO_PATH = FONT[0], MONO[0]          # 하위 호환 — 경로만 쓰던 곳

# ── 다크 테마 ────────────────────────────────────────────────────────────────
BG = '#222222'
DEBUG_OVERLAP = False
TXT = '#F7F1FF'
TYPE_TXT = '#8B8B8B'
DESC_TXT = '#A8B8CC'
EDGE = '#7A8290'
EDGE_CASCADE = '#C4736B'
LABEL_TXT = '#9BA3AE'   # 관계 라벨은 중립 회색 — 색 구분은 선이 담당한다

# ── 그림의 뼈대 — erd.spec.json 에서 읽고, 없으면 스키마·접두어로 자동 추론 ──────
# 레이어 색(LAYERS)과 테이블→레이어(LAYER_OF)는 전적으로 spec 이 정한다.
# spec 이 없으면 config.load_spec 이 영역 단위로 팔레트를 돌려 배정한다.
SPEC = load_spec(SCHEMA)
AREAS = SPEC['areas']                    # [코드, 영역명, 스키마, [테이블…]]
LAYERS = SPEC['layers']                  # {코드: (fill, head, border, 라벨)}
LAYER_OF = SPEC['layer_of']              # {테이블: 레이어코드}
ROLE = SPEC['roles']                     # {테이블: 한글 역할명}
DERIVES = SPEC['derives']                # [[원천, 대상, 라벨], …] ETL 흐름 (FK 아님)

AREA_OF = {t: a[0] for a in AREAS for t in a[3]}
AREA_NAME = {a[0]: a[1] for a in AREAS}
AREA_SCHEMA = {a[0]: a[2] for a in AREAS}


def layer(t):
    code = LAYER_OF.get(t) or AREA_OF.get(t)
    return code if code in LAYERS else next(iter(LAYERS))


def badge(tname):
    t = SCHEMA[tname]
    if t.get('readonly'):
        return T('word.source'), '#D9A566'
    if t.get('origin') == 'new':
        return 'NEW', '#7ED07E'
    if any(c['added'] for c in t['columns']):
        return T('word.extended'), '#E2C275'
    return T('word.existing'), '#9AA0A6'


def col_role(t, c):
    if c['name'] in t['pk']:
        return 'PK'
    if any(fk['column'] == c['name'] for fk in t['fks']):
        return 'FK'
    return ''


_ADDED = T('word.added')          # 붙이는 쪽과 알아보는 쪽이 같은 문자열을 봐야 한다


def col_line(t, c, with_desc=True, desc_max=62):
    typ = c['type'] + (' NN' if c['not_null'] else '')
    desc = c['comment'] if with_desc else ''
    if len(desc) > desc_max:
        desc = desc[:desc_max - 1] + '…'
    if c['added']:
        desc = _ADDED + ' ' + desc
    return (col_role(t, c), c['name'] + ':', typ, desc)


# ── 폰트 ─────────────────────────────────────────────────────────────────────
def _tt(face, size):
    """(경로, index) → 폰트. index 를 못 쓰는 파일이면 조용히 0 번 face 로."""
    path, index = face
    try:
        return ImageFont.truetype(path, size, index=index)
    except (OSError, ValueError):
        return ImageFont.truetype(path, size)


def load_fonts(scale=1):
    return {
        'title': _tt(FONT_B, 16 * scale),
        'role': _tt(FONT, 12 * scale),
        'badge': _tt(FONT_B, 11 * scale),
        'mono': _tt(MONO, 12 * scale),
        'monob': _tt(MONO_B, 12 * scale),
        'desc': _tt(FONT, 12 * scale),
        'legend': _tt(FONT, 14 * scale),
        'head': _tt(FONT_B, 22 * scale),
        'edge': _tt(FONT, 11 * scale),
    }


_probe = ImageDraw.Draw(Image.new('RGB', (10, 10)))


def tw(text, font):
    return _probe.textlength(text, font=font)


class Tracker:
    """ImageDraw 래퍼 — 그리기 호출의 좌표를 모아 실제 사용 범위를 잰다.

    1×1 더미 캔버스에 씌우면 캔버스 밖 좌표도 그대로 수집되므로,
    무엇이 어디까지 그려지는지 미리 알 수 있다.
    """

    def __init__(self, d):
        self._d = d
        self.bbox = [float('inf'), float('inf'), float('-inf'), float('-inf')]

    def empty(self):
        return self.bbox[0] == float('inf')

    def _add(self, xs, ys):
        self.bbox[0] = min(self.bbox[0], *xs)
        self.bbox[1] = min(self.bbox[1], *ys)
        self.bbox[2] = max(self.bbox[2], *xs)
        self.bbox[3] = max(self.bbox[3], *ys)

    def _xy(self, xy):
        if xy and isinstance(xy[0], (list, tuple)):
            self._add([p[0] for p in xy], [p[1] for p in xy])
        else:
            self._add(xy[0::2], xy[1::2])

    def line(self, xy, **kw):
        self._xy(xy)
        self._d.line(xy, **kw)

    def rectangle(self, xy, **kw):
        self._xy(xy)
        self._d.rectangle(xy, **kw)

    def rounded_rectangle(self, xy, **kw):
        self._xy(xy)
        self._d.rounded_rectangle(xy, **kw)

    def arc(self, xy, *a, **kw):
        self._xy(xy)
        self._d.arc(xy, *a, **kw)

    def ellipse(self, xy, **kw):
        self._xy(xy)
        self._d.ellipse(xy, **kw)

    def text(self, xy, text, font=None, anchor=None, **kw):
        w = _probe.textlength(text, font=font)
        h = (font.size if font is not None else 12) * 1.4
        x, y = xy
        x0 = x - w if (anchor or '')[:1] == 'r' else (x - w / 2 if (anchor or '')[:1] == 'm' else x)
        y0 = y - h / 2 if (anchor or '')[1:2] == 'm' else y
        self._add([x0, x0 + w], [y0, y0 + h])
        self._d.text(xy, text, font=font, anchor=anchor, **kw)


# ── 노드 크기 ────────────────────────────────────────────────────────────────
PAD = 12
ROW_H = 18
HEAD_H = 46
KEY_W = 22          # 키 아이콘 열


def measure(tname, with_desc=True):
    t = SCHEMA[tname]
    f = load_fonts()
    rows = [col_line(t, c, with_desc) for c in t['columns']]
    w_name = max(tw(r[1], f['monob']) for r in rows)
    w_type = max(tw(r[2], f['mono']) for r in rows)
    w_desc = max([tw(r[3], f['desc']) for r in rows] + [0]) if with_desc else 0
    bd, _ = badge(tname)
    w_title = max(tw(tname, f['title']) + tw(bd, f['badge']) + 24,
                  tw(ROLE.get(tname, ''), f['role']) + 60)
    gap = 8
    inner = KEY_W + w_name + gap + w_type + (gap + w_desc if with_desc else 0)
    return {
        'w': int(max(inner, w_title) + PAD * 2),
        'h': int(HEAD_H + len(rows) * ROW_H + PAD),
        'rows': rows, 'cols': (w_name, w_type), 'gap': gap,
    }


def stub_box(tname):
    f = load_fonts()
    w = max(tw(tname, f['title']),
            tw(T('erd.ref_of', area=AREA_OF.get(tname, T('word.external')),
                  role=ROLE.get(tname, '')), f['role'])) + PAD * 2
    return {'w': int(w), 'h': HEAD_H + 2, 'rows': [], 'cols': (0, 0), 'gap': 0}


# ── 레이아웃 ─────────────────────────────────────────────────────────────────
def layout_area(tnames, with_desc=True, max_cols=2, hgap=210, vgap=95):
    boxes = {n: measure(n, with_desc) for n in tnames}
    order = sorted(tnames, key=lambda n: -boxes[n]['h'])
    cols = [[] for _ in range(min(max_cols, len(tnames)))]
    heights = [0] * len(cols)
    for n in order:
        i = heights.index(min(heights))
        cols[i].append(n)
        heights[i] += boxes[n]['h'] + vgap

    inside = set(tnames)
    ext = []
    for n in tnames:
        for fk in SCHEMA[n]['fks']:
            r = fk['ref_table']
            if r not in inside and r not in ext:
                ext.append(r)
    for n in ext:
        boxes[n] = stub_box(n)

    pos, x = {}, 0
    for col in cols:
        w = max(boxes[n]['w'] for n in col)
        y = 0
        for n in col:
            pos[n] = (x, y)
            y += boxes[n]['h'] + vgap
        x += w + hgap
    if ext:
        y = 0
        for n in ext:
            pos[n] = (x, y)
            y += boxes[n]['h'] + 30
    return pos, boxes, ext


def layout_overview(hgap=230, vgap=76):
    """전체 개요도 — 영역(=스키마 그룹)별 세로 열. 컬럼 미표시."""
    pos, boxes, groups = {}, {}, []
    f = load_fonts()
    x, h = 0, HEAD_H + 2
    for code, _name, _schema, tables in AREAS:
        w = int(max(max(tw(n, f['title']) for n in tables),
                    max(tw(ROLE.get(n, ''), f['role']) for n in tables)) + PAD * 2 + 50)
        y = 0
        for n in tables:
            boxes[n] = {'w': w, 'h': h, 'rows': [], 'cols': (0, 0), 'gap': 0}
            pos[n] = (x, y)
            y += h + vgap
        groups.append((code, tables))
        x += w + hgap
    return pos, boxes, groups


def layout_global(hgap=230, vgap=100, area_gap=150, want_cols=4):
    """전체 상세 레이아웃 — 열 높이가 고르도록 영역을 열에 묶는다.

    영역(=그룹 박스) 단위는 쪼개지 않는다. 작은 영역은 한 열에 세로로 이어 쌓고,
    목표 높이를 넘는 큰 영역만 내부에서 서브열로 나눈다.
    """
    boxes = {n: measure(n, with_desc=True) for a in AREAS for n in a[3]}
    area_h = {a[0]: sum(boxes[n]['h'] + vgap for n in a[3]) for a in AREAS}
    total = sum(area_h.values())
    target = max(max(area_h.values()), total / want_cols)

    # 영역을 순서대로 열에 배정 (누적이 목표를 넘으면 새 열)
    cols, cur, cur_h = [], [], 0
    for code, _n, _s, _t in AREAS:
        h = area_h[code]
        if cur and cur_h + h > target:
            cols.append(cur)
            cur, cur_h = [], 0
        cur.append(code)
        cur_h += h + area_gap
    if cur:
        cols.append(cur)

    tables_of = {a[0]: a[3] for a in AREAS}
    pos, groups, x = {}, [], 0
    for col in cols:
        w = max(boxes[n]['w'] for code in col for n in tables_of[code])
        y = 0
        for code in col:
            for n in tables_of[code]:
                pos[n] = (x, y)
                y += boxes[n]['h'] + vgap
            y += area_gap
            groups.append((code, tables_of[code]))
        x += w + hgap
    return pos, boxes, groups


# ── 렌더 ─────────────────────────────────────────────────────────────────────
def draw_key_icon(d, x, y, kind, S):
    """PK/FK 표시 — 참고 스타일의 컬럼 좌측 아이콘"""
    if kind == 'PK':
        c = '#E8C05A'
        d.rounded_rectangle([x * S, (y + 3) * S, (x + 9) * S, (y + 11) * S],
                            radius=2 * S, outline=c, width=max(1, S))
        d.line([((x + 9) * S, (y + 7) * S), ((x + 14) * S, (y + 7) * S)], fill=c, width=max(1, S))
    elif kind == 'FK':
        c = '#5AC8D8'
        d.rounded_rectangle([x * S, (y + 3) * S, (x + 9) * S, (y + 11) * S],
                            radius=2 * S, outline=c, width=max(1, S))
        d.ellipse([(x + 10) * S, (y + 9) * S, (x + 14) * S, (y + 13) * S],
                  outline=c, width=max(1, S))
    else:
        d.rounded_rectangle([x * S, (y + 3) * S, (x + 9) * S, (y + 11) * S],
                            radius=2 * S, outline='#6A7280', width=max(1, S))


def draw_legend(d, f, x, y, S, max_w=10 ** 6):
    """범례. 폭을 넘으면 줄을 바꾼다. 사용한 높이(논리 px)를 반환."""
    LH, GAP = 27, 30
    cx, cy = x, y
    rows = 1

    def nl(w):
        """다음 항목 폭이 남은 폭을 넘으면 줄바꿈"""
        nonlocal cx, cy, rows
        if cx + w > x + max_w:
            cx, cy, rows = x + 74, cy + LH, rows + 1

    def label(text, dx=0, dy=1):
        d.text(((cx + dx) * S, (cy + dy) * S), text, font=f['legend'], fill='#C8C8C8')

    d.text((cx * S, cy * S), T('word.layer'), font=f['legend'], fill='#8E96A0')
    cx += 74
    for _code, (fill, head, border, txt) in LAYERS.items():
        w = 40 + tw(txt, f['legend']) / S + GAP
        nl(w)
        d.rectangle([cx * S, cy * S, (cx + 26) * S, (cy + 16) * S], fill=fill,
                    outline=border, width=max(1, S))
        d.rectangle([cx * S, cy * S, (cx + 26) * S, (cy + 5) * S], fill=head,
                    outline=border, width=max(1, S))
        label(txt, 33)
        cx += w

    cx, cy, rows = x, cy + LH, rows + 1
    d.text((cx * S, cy * S), T('word.notation'), font=f['legend'], fill='#8E96A0')
    cx += 74
    for kind, txt in (('PK', T('word.pk')), ('FK', T('word.fk'))):
        w = 24 + tw(txt, f['legend']) / S + GAP
        nl(w)
        draw_key_icon(d, cx, cy, kind, S)
        label(txt, 21, 0)
        cx += w
    for txt, color, desc in (('NEW', '#7ED07E', T('erd.lg_new')),
                             (T('word.extended'), '#E2C275', T('erd.lg_ext')),
                             (T('word.source'), '#D9A566', T('erd.lg_src'))):
        bwid = tw(txt, f['badge']) / S
        w = bwid + 10 + tw(desc, f['legend']) / S + GAP
        nl(w)
        d.text((cx * S, cy * S), txt, font=f['badge'], fill=color)
        label(desc, bwid + 9, 0)
        cx += w

    cx, cy, rows = x, cy + LH, rows + 1
    d.text((cx * S, cy * S), T('word.lines'), font=f['legend'], fill='#8E96A0')
    cx += 74
    for kind, txt in (('fk', T('erd.lg_fk')),
                      ('etl', T('erd.lg_etl')),
                      ('hop', T('erd.lg_hop'))):
        w = 40 + tw(txt, f['legend']) / S + GAP
        nl(w)
        my = cy + 8
        if kind == 'fk':
            d.line([(cx * S, my * S), ((cx + 30) * S, my * S)], fill=EDGE, width=max(1, S))
        elif kind == 'etl':
            for i in range(3):
                bx = cx + i * 11
                d.line([(bx * S, my * S), ((bx + 6) * S, my * S)],
                       fill='#B0885A', width=max(1, S))
        else:
            d.line([(cx * S, my * S), ((cx + 10) * S, my * S)], fill=EDGE, width=max(1, S))
            d.arc([(cx + 10) * S, (my - 5) * S, (cx + 20) * S, (my + 5) * S], 180, 360,
                  fill=EDGE, width=max(1, S))
            d.line([((cx + 20) * S, my * S), ((cx + 30) * S, my * S)],
                   fill=EDGE, width=max(1, S))
        label(txt, 38, 0)
        cx += w
    return (cy - y) + LH


def draw_erd(path, tnames, pos, boxes, title, subtitle='', with_desc=True, scale=2,
             stubs=(), legend=False, edge_labels=True, groups=(), derives=False):
    """2단계 렌더 — ① 실제로 그려지는 모든 요소의 범위를 재고 ② 거기에 여백을 붙여 그린다.

    선·라벨·그룹 박스는 노드 바깥으로 나가므로, 노드 위치만으로 캔버스를 잡으면 잘린다.
    """
    f = load_fonts(scale)
    S = scale
    MARGIN = 64                      # 본체 사방 여백
    title_h = 104 + (30 if groups else 0)
    legend_h = 0            # 실제 범례 높이는 아래에서 측정한다

    def render(d, ML, top):
        """다이어그램 본체(그룹 박스·관계선·노드·라벨)를 그린다."""
        def rect(n):
            x, y = pos[n]
            return x + ML, y + top, x + ML + boxes[n]['w'], y + top + boxes[n]['h']

        # ── 스키마 그룹 박스 (노드 아래) ──
        GP = 22
        for code, tables in groups:
            rs = [rect(n) for n in tables if n in pos]
            if not rs:
                continue
            gx1 = min(r[0] for r in rs) - GP
            gy1 = min(r[1] for r in rs) - GP
            gx2 = max(r[2] for r in rs) + GP
            gy2 = max(r[3] for r in rs) + GP
            schema = AREA_SCHEMA[code]
            gcol = '#B0885A' if schema == 'ref' else '#5A6472'
            d.rounded_rectangle([gx1 * S, gy1 * S, gx2 * S, gy2 * S], radius=10 * S,
                                outline=gcol, width=max(1, S))
            label = T('erd.group_label', schema=schema, code=code,
                       name=AREA_NAME[code])
            lw = tw(label, f['legend']) / S
            d.rectangle([(gx1 + 14) * S, (gy1 - 10) * S, (gx1 + 26 + lw) * S, (gy1 + 10) * S],
                        fill=BG)
            d.text(((gx1 + 20) * S, (gy1 - 8) * S), label, font=f['legend'], fill=gcol)

        # ── 열 구조 · 통로 (노드를 관통하지 않는 직교 라우팅용) ──
        xs = sorted({pos[n][0] for n in tnames})
        columns = []
        for cx in xs:
            ns = [n for n in tnames if pos[n][0] == cx]
            columns.append({
                'nodes': ns,
                'x1': min(rect(n)[0] for n in ns),
                'x2': max(rect(n)[2] for n in ns),
                'spans': sorted((rect(n)[1], rect(n)[3]) for n in ns),
            })
        col_of = {n: i for i, c in enumerate(columns) for n in c['nodes']}

        def gutter_x(i):
            """열 i 와 i+1 사이 세로 통로의 중심. i<0 은 맨 왼쪽 바깥."""
            if i < 0:
                return columns[0]['x1'] - 54
            if i >= len(columns) - 1:
                return columns[-1]['x2'] + 54
            return (columns[i]['x2'] + columns[i + 1]['x1']) / 2

        used_vx, used_hy = [], []

        def slot(base, used, pitch, limit=64):
            """base 근처에서 이미 쓰인 좌표를 피해 좌우(상하) 번갈아 자리를 잡는다.

            자리를 찾을 때까지 계속 벌린다 — 선끼리는 절대 겹치지 않아야 한다.
            """
            for k in range(1, 2 * limit + 2):
                off = (k // 2) * pitch * (1 if k % 2 else -1)
                v = base + off
                if all(abs(v - u) >= pitch - 1 for u in used):
                    used.append(v)
                    return v
            v = max(used, default=base) + pitch
            used.append(v)
            return v

        def free_y(ci, prefer):
            """열 ci 의 노드 사이 빈 구간 중 prefer 에 가장 가까운 통과 y"""
            spans = columns[ci]['spans']
            cands = [spans[0][0] - 36, spans[-1][1] + 36]
            for a, b in zip(spans, spans[1:]):
                if b[0] - a[1] >= 28:
                    cands.append((a[1] + b[0]) / 2)
            return min(cands, key=lambda y: abs(y - prefer))

        exit_used = {}                   # 노드별로 이미 쓴 진출입 y (컬럼이 없을 때 분산)
        exit_all = []                    # 전체 진출입 y (같은 행에 몰리는 것 방지)

        def col_y(n, colname):
            """해당 컬럼 행의 세로 중심. 컬럼을 못 찾으면 노드 안에서 자리를 나눠 쓴다."""
            _x1, y1, _x2, y2 = rect(n)
            box = boxes[n]
            if box['rows']:
                for i, r in enumerate(box['rows']):
                    if r[1].rstrip(':') == colname:
                        base = y1 + HEAD_H + 5 + i * ROW_H + ROW_H / 2
                        # 같은 컬럼으로 여러 선이 모이면 행 안에서 미세하게 어긋내
                        # 어느 선이 어디로 가는지 구분되게 한다 (행은 그대로 가리킴)
                        for off in (0, -4.5, 4.5, -7, 7):
                            v = base + off
                            if all(abs(v - u) >= 4 for u in exit_all):
                                exit_all.append(v)
                                return v
                        return base
            cy = (y1 + y2) / 2           # 개요도·축약 박스 — 한 점에 몰리지 않게 분산
            used = exit_used.setdefault(n, [])
            used = used + exit_all if False else used
            for k in range(1, 14):
                v = cy + (k // 2) * 13 * (1 if k % 2 else -1)
                if y1 + 7 <= v <= y2 - 7 and all(abs(v - u) >= 12 for u in used):
                    used.append(v)
                    return v
            used.append(cy)
            return cy

        def route(a, b, ca=None, cb=None):
            """노드를 관통하지 않는 직교 경로.

            세로 이동은 열 사이 통로에서만, 열을 건너뛸 때는 그 열의 노드 사이
            빈 구간을 따라 수평으로 지난다.
            """
            ia, ib = col_of[a], col_of[b]
            ya, yb = col_y(a, ca), col_y(b, cb)
            used_hy.extend((ya, yb))     # 통과선이 진출입선의 y 를 피하도록 등록
            ax1, _t1, ax2, _t2 = rect(a)
            bx1, _t3, bx2, _t4 = rect(b)
            if ia == ib:                                  # 같은 열 — 왼쪽 통로로 우회
                gx = slot(gutter_x(ia - 1), used_vx, 14)
                pts = [(ax1, ya), (gx, ya), (gx, yb), (bx1, yb)]
            else:
                right = ib > ia
                step = 1 if right else -1
                gseq = [gutter_x(i if right else i - 1) for i in range(ia, ib, step)]
                mids = list(range(ia + step, ib, step))
                pts = [(ax2 if right else ax1, ya)]
                y = ya
                for k, g in enumerate(gseq):
                    gx = slot(g, used_vx, 14)
                    pts.append((gx, y))
                    if k < len(mids):                     # 중간 열은 노드 사이로 건넌다
                        yp = slot(free_y(mids[k], yb), used_hy, 13)
                        pts.append((gx, yp))
                        y = yp
                pts.append((pts[-1][0], yb))
                pts.append((bx1 if right else bx2, yb))
            out = [pts[0]]
            for p in pts[1:]:
                if abs(p[0] - out[-1][0]) > 0.5 or abs(p[1] - out[-1][1]) > 0.5:
                    out.append(p)
            return out

        # ── 선 · 화살표 · 라벨 헬퍼 ──
        def dashed(p1, p2, color, dash=9, gap=6):
            (x1, y1), (x2, y2) = p1, p2
            ln = max(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5, 1)
            ux, uy, t = (x2 - x1) / ln, (y2 - y1) / ln, 0
            while t < ln:
                e = min(t + dash, ln)
                d.line([((x1 + ux * t) * S, (y1 + uy * t) * S),
                        ((x1 + ux * e) * S, (y1 + uy * e) * S)], fill=color, width=max(1, S))
                t = e + gap

        def unit(p, q):
            dx, dy = q[0] - p[0], q[1] - p[1]
            ln = max((dx * dx + dy * dy) ** 0.5, 1)
            return dx / ln, dy / ln

        def crow_foot(pts, color):
            """자식(N) 쪽 — 경로 시작점에 까치발"""
            x1, y1 = pts[0]
            ux, uy = unit(pts[0], pts[1])
            fx, fy = x1 + ux * 13, y1 + uy * 13
            for sgn in (-1, 1):
                d.line([(x1 * S, y1 * S),
                        ((fx - uy * 6 * sgn) * S, (fy + ux * 6 * sgn) * S)],
                       fill=color, width=max(1, S))

        def one_bar(pts, color):
            """부모(1) 쪽 — 경로 끝점에 직교 짧은 선"""
            x2, y2 = pts[-1]
            ux, uy = unit(pts[-2], pts[-1])
            px, py = x2 - ux * 11, y2 - uy * 11
            d.line([((px - uy * 6) * S, (py + ux * 6) * S),
                    ((px + uy * 6) * S, (py - ux * 6) * S)], fill=color, width=max(1, S))

        def arrow_head(pts, color):
            x2, y2 = pts[-1]
            ux, uy = unit(pts[-2], pts[-1])
            for sgn in (-1, 1):
                d.line([(x2 * S, y2 * S),
                        ((x2 - ux * 11 - uy * 5 * sgn) * S,
                         (y2 - uy * 11 + ux * 5 * sgn) * S)], fill=color, width=max(1, S))

        placed = []                      # 이미 배치된 라벨 bbox (겹침 방지)
        label_queue = []                 # 라벨은 노드보다 나중에 그린다 (가려짐 방지)

        def path_label(pts, text, color):
            label_queue.append((pts, text, color))

        def flush_labels():
            """노드·다른 라벨을 피해 라벨을 배치한다. 노드 렌더 이후에 호출."""
            node_rects = [rect(n) for n in tnames]

            def hits(box, others):
                return any(not (box[2] < o[0] or box[0] > o[2]
                                or box[3] < o[1] or box[1] > o[3]) for o in others)

            # 긴 경로부터 자리를 잡는다 (짧은 쪽이 밀려날 여지가 크다)
            for pts, text, color in sorted(
                    label_queue,
                    key=lambda e: -max((abs(q[0] - p[0]) for p, q in zip(e[0], e[0][1:])
                                        if abs(p[1] - q[1]) < 0.5), default=0)):
                bw = tw(text, f['edge']) / S
                segs = sorted(((p, q) for p, q in zip(pts, pts[1:])
                               if abs(p[1] - q[1]) < 0.5),
                              key=lambda s: -abs(s[1][0] - s[0][0]))
                if not segs:
                    segs = [(pts[len(pts) // 2 - 1], pts[len(pts) // 2])]

                def h_cands(p, q):
                    """수평 구간 — 선 바로 위(-)를 우선하고 막히면 아래(+)로."""
                    x0, x1_ = min(p[0], q[0]), max(p[0], q[0])
                    for frac in (0.5, 0.34, 0.66, 0.2, 0.8, 0.42, 0.58):
                        cx = min(max(x0 + (x1_ - x0) * frac, x0 + bw / 2), x1_ - bw / 2) \
                            if x1_ - x0 > bw else (x0 + x1_) / 2
                        for dy in (-12, 12, -27, 27, -42, 42, -57, 57):
                            yield (cx - bw / 2 - 3, p[1] + dy - 7,
                                   cx + bw / 2 + 3, p[1] + dy + 7)

                def v_cands(p, q):
                    """수직 구간 — 통로 안, 선 좌우로."""
                    y0, y1_ = min(p[1], q[1]), max(p[1], q[1])
                    for frac in (0.3, 0.5, 0.7, 0.15, 0.85):
                        cy = y0 + (y1_ - y0) * frac
                        if cy - 7 < y0 or cy + 7 > y1_:
                            continue
                        for dx in (-8 - bw / 2, 8 + bw / 2):
                            yield (p[0] + dx - bw / 2 - 3, cy - 7,
                                   p[0] + dx + bw / 2 + 3, cy + 7)

                v_segs_own = [(p, q) for p, q in zip(pts, pts[1:]) if abs(p[0] - q[0]) < 0.5]

                # 테이블과 겹치는 자리는 후보에서 제외한다 (강제 조건).
                box = None
                fallback = None
                for gen, args in ([(h_cands, s) for s in segs]
                                  + [(v_cands, s) for s in v_segs_own]):
                    for cand in gen(*args):
                        if hits(cand, node_rects):
                            continue
                        if not hits(cand, placed):
                            box = cand
                            break
                        if fallback is None:
                            fallback = cand
                    if box:
                        break
                box = box or fallback
                if box is None:                      # 전부 막히면 노드 위쪽 여백으로
                    p, q = segs[0]
                    box = ((p[0] + q[0]) / 2 - bw / 2 - 3, top - 22,
                           (p[0] + q[0]) / 2 + bw / 2 + 3, top - 8)
                placed.append(box)
                d.rectangle([box[0] * S, box[1] * S, box[2] * S, box[3] * S], fill=BG)
                d.text(((box[0] + box[2]) / 2 * S, (box[1] + box[3]) / 2 * S), text,
                       font=f['edge'], fill=LABEL_TXT, anchor='mm')

        # ── 경로를 먼저 모두 계산한다 (교차 hop 을 그리기 위해) ──
        edges = []          # (pts, color, label, dashed)
        inside = set(tnames)
        self_loops = []

        if derives:
            for src, dst, label in DERIVES:
                if src in inside and dst in inside:
                    edges.append((route(src, dst), '#B0885A', label, True))

        for tname in tnames:
            if tname in stubs:
                continue
            for fk in SCHEMA[tname]['fks']:
                ref = fk['ref_table']
                color = EDGE          # 선은 FK(실선)·ETL(점선) 두 종류만 쓴다
                lbl = f"{fk['column']}: {fk['ref_column']}"
                if ref == tname:                          # 자기참조 — 좌측 ㄷ자 루프
                    x1, y1, _x2, y2 = rect(tname)
                    cy = (y1 + y2) / 2
                    self_loops.append(([(x1, cy - 16), (x1 - 30, cy - 16),
                                        (x1 - 30, cy + 16), (x1, cy + 16)],
                                       color, fk['column']))
                    continue
                if ref not in inside:
                    continue
                edges.append((route(tname, ref, fk['column'], fk['ref_column']),
                              color, lbl, False))

        # ── 교차점 수집 : 수평선이 수직선을 넘을 때 반원으로 점프 ──
        v_segs = []
        for ei, (pts, *_r) in enumerate(edges):
            for p, q in zip(pts, pts[1:]):
                if abs(p[0] - q[0]) < 0.5:
                    v_segs.append((ei, p[0], min(p[1], q[1]), max(p[1], q[1])))

        HOP = 5

        def draw_h(x0, x1, y, color, ei, dash=False):
            cuts = sorted(vx for (vei, vx, vy0, vy1) in v_segs
                          if vei != ei and vy0 + 2 < y < vy1 - 2
                          and min(x0, x1) + HOP + 2 < vx < max(x0, x1) - HOP - 2)
            sgn = 1 if x1 > x0 else -1
            if sgn < 0:
                cuts = list(reversed(cuts))
            cur = x0
            for cx in cuts:
                seg_end = cx - sgn * HOP
                if dash:
                    dashed((cur, y), (seg_end, y), color)
                else:
                    d.line([(cur * S, y * S), (seg_end * S, y * S)], fill=color, width=max(1, S))
                d.arc([(cx - HOP) * S, (y - HOP) * S, (cx + HOP) * S, (y + HOP) * S],
                      180, 360, fill=color, width=max(1, S))
                cur = cx + sgn * HOP
            if dash:
                dashed((cur, y), (x1, y), color)
            else:
                d.line([(cur * S, y * S), (x1 * S, y * S)], fill=color, width=max(1, S))

        def draw_edge(pts, color, ei, dash=False):
            for p, q in zip(pts, pts[1:]):
                if abs(p[1] - q[1]) < 0.5:
                    draw_h(p[0], q[0], p[1], color, ei, dash)
                elif dash:
                    dashed(p, q, color)
                else:
                    d.line([(p[0] * S, p[1] * S), (q[0] * S, q[1] * S)],
                           fill=color, width=max(1, S))

        for ei, (pts, color, label, dash) in enumerate(edges):
            draw_edge(pts, color, ei, dash)
            if dash:
                arrow_head(pts, color)
            else:
                crow_foot(pts, color)
                one_bar(pts, color)
            if edge_labels:
                path_label(pts, label, color)

        for pts, color, label in self_loops:
            draw_edge(pts, color, -1)
            crow_foot(pts, color)
            one_bar(pts, color)
            if edge_labels:
                d.text(((pts[0][0] - 34) * S, ((pts[0][1] + pts[-1][1]) / 2) * S), label,
                       font=f['edge'], fill=color, anchor='rm')

        # ── 노드 ──
        for n in tnames:
            x1, y1, x2, y2 = rect(n)
            fill, head, border, _ = LAYERS[layer(n)]
            box = boxes[n]
            is_stub = n in stubs
            d.rectangle([x1 * S, y1 * S, x2 * S, y2 * S], fill=fill, outline=border, width=max(1, S))
            d.rectangle([x1 * S, y1 * S, x2 * S, (y1 + HEAD_H) * S], fill=head,
                        outline=border, width=max(1, S))
            d.text(((x1 + PAD) * S, (y1 + 5) * S), n, font=f['title'], fill=TXT)
            bd, bc = badge(n)
            if not is_stub:
                d.text(((x2 - PAD) * S, (y1 + 9) * S), bd, font=f['badge'], fill=bc, anchor='ra')
            sub = ROLE.get(n, '')
            if is_stub:
                sub = T('erd.ref_of', area=AREA_OF.get(n, T('word.external')), role=sub)
            d.text(((x1 + PAD) * S, (y1 + 27) * S), sub, font=f['role'], fill='#B9C2CC')
            if not box['rows']:
                continue
            w_name, w_type = box['cols']
            gap = box['gap']
            cy = y1 + HEAD_H + 5
            for role, cname, ctype, cdesc in box['rows']:
                draw_key_icon(d, x1 + PAD, cy, role, S)
                cx = x1 + PAD + KEY_W
                d.text((cx * S, cy * S), cname, font=f['monob'], fill=TXT)
                cx += w_name + gap
                d.text((cx * S, cy * S), ctype, font=f['mono'], fill=TYPE_TXT)
                cx += w_type + gap
                if cdesc:
                    d.text((cx * S, cy * S), cdesc, font=f['desc'],
                           fill=('#D3A6E8' if cdesc.startswith(_ADDED) else DESC_TXT))
                cy += ROW_H

        if edge_labels:
            flush_labels()               # 라벨은 노드 위에 — 가려지지 않도록 마지막에

        return edges, placed

    # ① 측정 — 1×1 더미 캔버스에 그려 좌표만 수집한다 (캔버스 밖도 정확히 추적)
    probe = Tracker(ImageDraw.Draw(Image.new('RGB', (1, 1))))
    edges, placed = render(probe, 0, 0)
    if probe.empty():
        lx0 = ly0 = 0
        lx1 = max(pos[n][0] + boxes[n]['w'] for n in tnames)
        ly1 = max(pos[n][1] + boxes[n]['h'] for n in tnames)
    else:
        lx0, ly0, lx1, ly1 = (v / S for v in probe.bbox)

    # ② 실제 렌더 — 측정 범위 + 여백
    W = int(lx1 - lx0) + MARGIN * 2
    legend_h = 0
    if legend:                       # 범례도 실제로 그려보고 높이를 잰다 (줄바꿈 반영)
        probe_leg = Tracker(ImageDraw.Draw(Image.new('RGB', (1, 1))))
        legend_h = draw_legend(probe_leg, f, MARGIN, 0, S, W - MARGIN * 2) + 20
    H = int(ly1 - ly0) + title_h + legend_h + MARGIN
    while S > 1 and W * H * S * S > MAX_PIXELS:      # 너무 크면 배율을 낮춘다
        S -= 1
        f = load_fonts(S)
        print(T('log.scale_down', name=Path(path).name, s=S))
    img = Image.new('RGB', (W * S, H * S), BG)
    d = ImageDraw.Draw(img)

    d.text((MARGIN * S, 30 * S), title, font=f['head'], fill=TXT)
    if subtitle:
        d.text((MARGIN * S, 62 * S), subtitle, font=f['legend'], fill='#9AA0A6')
    if legend:
        draw_legend(d, f, MARGIN, H - legend_h + 4, S, W - MARGIN * 2)

    off_x, off_y = MARGIN - lx0, title_h - ly0
    edges, placed = render(d, off_x, off_y)

    # ── 자체 검증: 라벨-테이블 겹침 / 선-선 중첩 ──
    node_rects = [(pos[n][0] + off_x, pos[n][1] + off_y,
                   pos[n][0] + off_x + boxes[n]['w'], pos[n][1] + off_y + boxes[n]['h'])
                  for n in tnames]
    lab_hit = sum(1 for b in placed for o in node_rects
                  if not (b[2] < o[0] or b[0] > o[2] or b[3] < o[1] or b[1] > o[3]))
    segs_v, segs_h = [], []
    for pts, *_r in edges:
        for p, q in zip(pts, pts[1:]):
            (segs_v if abs(p[0] - q[0]) < 0.5 else segs_h).append(
                (p[0], min(p[1], q[1]), max(p[1], q[1])) if abs(p[0] - q[0]) < 0.5
                else (p[1], min(p[0], q[0]), max(p[0], q[0])))

    def overlaps(segs):
        """겹친 길이를 센다. 단 한쪽 끝을 공유하는 것은 '같은 지점으로 합류' 이므로 제외."""
        n = 0
        for i, (a, s0, s1) in enumerate(segs):
            for (b, t0, t1) in segs[i + 1:]:
                if abs(a - b) >= 3 or min(s1, t1) - max(s0, t0) <= 6:
                    continue
                if abs(s0 - t0) < 3 or abs(s1 - t1) < 3:
                    continue         # 같은 컬럼으로 모이는 합류 구간
                n += 1
                if DEBUG_OVERLAP:
                    print(T('log.overlap_at', a=f'{a:.0f}', s0=f'{s0:.0f}',
                             s1=f'{s1:.0f}', t0=f'{t0:.0f}', t1=f'{t1:.0f}'))
        return n

    report = {T('verify.label_table'): lab_hit,
              T('verify.v_overlap'): overlaps(segs_v),
              T('verify.h_overlap'): overlaps(segs_h)}
    print(T('log.verify', name=Path(path).name,
             report=' · '.join(f'{k} {v}' for k, v in report.items())))
    img.save(path)

    # ── 같은 그림을 벡터로 한 벌 더 (문서 삽입용 — 확대해도 안 뭉갠다) ──
    # 문서에는 제목·번호가 캡션으로 따로 붙으므로 그림 안 제목은 뺀다(중복·번호 충돌).
    # 단독으로 볼 SVG 가 필요하면 ERD_SVG_TITLE=1.
    if SVG_OUT:
        S, f = 1, load_fonts(1)          # 벡터라 배율이 필요 없다
        head_h = title_h if SVG_TITLE else 0
        H_svg = H - (title_h - head_h)
        c = SvgCanvas(W, H_svg, BG)
        if SVG_TITLE:
            c.text((MARGIN, 30), title, font=f['head'], fill=TXT)
            if subtitle:
                c.text((MARGIN, 62), subtitle, font=f['legend'], fill='#9AA0A6')
        if legend:
            draw_legend(c, f, MARGIN, H_svg - legend_h + 4, S, W - MARGIN * 2)
        render(c, off_x, head_h - ly0)
        svg_path = Path(path).with_suffix('.svg')
        c.save(svg_path, title=title)
        print(f'    SVG  {svg_path.name}  {svg_path.stat().st_size / 1024:.0f}KB')
    return path


# ── GraphML ──────────────────────────────────────────────────────────────────
GRAPHML_HEAD = '''<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns"
         xmlns:java="http://www.yworks.com/xml/yfiles-common/1.0/java"
         xmlns:sys="http://www.yworks.com/xml/yfiles-common/markup/primitives/2.0"
         xmlns:x="http://www.yworks.com/xml/yfiles-common/markup/2.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xmlns:y="http://www.yworks.com/xml/graphml"
         xmlns:yed="http://www.yworks.com/xml/yed/3"
         xsi:schemaLocation="http://graphml.graphdrawing.org/xmlns \
http://www.yworks.com/xml/schema/graphml/1.1/ygraphml.xsd">
  <key for="node" id="d0" yfiles.type="nodegraphics"/>
  <key for="node" id="d1" attr.name="description" attr.type="string"/>
  <key for="edge" id="d2" yfiles.type="edgegraphics"/>
  <key for="edge" id="d3" attr.name="description" attr.type="string"/>
  <graph edgedefault="directed" id="G">
'''


def graphml_node(nid, tname, pos, box):
    t = SCHEMA[tname]
    fill, head, border, layer_label = LAYERS[layer(tname)]
    x, y = pos
    w_role = max(len(r[0]) for r in box['rows'])
    w_name = max(len(r[1]) for r in box['rows'])
    w_type = max(len(r[2]) for r in box['rows'])
    lines = [f'{r[0]:<{w_role}}  {r[1]:<{w_name}}  {r[2]:<{w_type}}' + (f'  {r[3]}' if r[3] else '')
             for r in box['rows']]
    attrs = escape('\n'.join(lines))
    bd, _ = badge(tname)
    title = escape(f'{tname}  ·  {ROLE.get(tname, "")}  [{bd}]')
    height = 34 + len(box['rows']) * 16 + 8
    desc = escape(T('erd.node_desc', layer=layer_label, code=AREA_OF[tname],
                     area=AREA_NAME[AREA_OF[tname]], note=t.get('note', '')))
    return f'''    <node id="{nid}">
      <data key="d1">{desc}</data>
      <data key="d0">
        <y:GenericNode configuration="com.yworks.entityRelationship.big_entity">
          <y:Geometry height="{height}.0" width="{box['w']}.0" x="{x}.0" y="{y}.0"/>
          <y:Fill color="{fill}" transparent="false"/>
          <y:BorderStyle color="{border}" type="line" width="1.0"/>
          <y:NodeLabel alignment="center" autoSizePolicy="content" backgroundColor="{head}"\
 configuration="com.yworks.entityRelationship.label.name" fontFamily="Dialog" fontSize="13"\
 fontStyle="bold" hasLineColor="false" horizontalTextPosition="center" iconTextGap="4"\
 modelName="internal" modelPosition="t" textColor="#FFFFFF" verticalTextPosition="bottom"\
 visible="true">{title}</y:NodeLabel>
          <y:NodeLabel alignment="left" autoSizePolicy="content"\
 configuration="com.yworks.entityRelationship.label.attributes" fontFamily="Monospaced"\
 fontSize="12" fontStyle="plain" hasBackgroundColor="false" hasLineColor="false"\
 horizontalTextPosition="center" iconTextGap="4" modelName="custom" textColor="#F0F0F0"\
 verticalTextPosition="bottom" visible="true">{attrs}<y:LabelModel>\
<y:ErdAttributesNodeLabelModel/></y:LabelModel><y:ModelParameter>\
<y:ErdAttributesNodeLabelModelParameter/></y:ModelParameter></y:NodeLabel>
          <y:StyleProperties>
            <y:Property class="java.lang.Boolean" name="y.view.ShadowNodePainter.SHADOW_PAINTING"\
 value="true"/>
          </y:StyleProperties>
        </y:GenericNode>
      </data>
    </node>
'''


def graphml_edge(eid, src, tgt, fk):
    color = EDGE
    label = escape(f"{fk['column']} : {fk['ref_column']}")
    return f'''    <edge id="{eid}" source="{src}" target="{tgt}">
      <data key="d3">{label}</data>
      <data key="d2">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="{color}" type="line" width="1.0"/>
          <y:Arrows source="crows_foot_many" target="crows_foot_one"/>
          <y:EdgeLabel alignment="center" configuration="AutoFlippingLabel" distance="2.0"\
 fontFamily="Dialog" fontSize="10" fontStyle="plain" hasLineColor="false"\
 horizontalTextPosition="center" modelName="centered" preferredPlacement="anywhere"\
 ratio="0.5" textColor="{color}" verticalTextPosition="bottom" visible="true">{label}\
</y:EdgeLabel>
          <y:BendStyle smoothed="false"/>
        </y:PolyLineEdge>
      </data>
    </edge>
'''


def build_graphml(path, pos, boxes):
    ids = {n: f'n{i}' for i, n in enumerate(SCHEMA)}
    parts = [GRAPHML_HEAD]
    for n in SCHEMA:
        parts.append(graphml_node(ids[n], n, pos[n], boxes[n]))
    e = 0
    for n, t in SCHEMA.items():
        for fk in t['fks']:
            if fk['ref_table'] not in ids:
                continue
            parts.append(graphml_edge(f'e{e}', ids[n], ids[fk['ref_table']], fk))
            e += 1
    parts.append('  </graph>\n</graphml>\n')
    Path(path).write_text(''.join(parts))
    return len(ids), e
