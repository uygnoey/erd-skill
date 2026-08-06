#!/usr/bin/env python3
"""ImageDraw 흉내를 내는 SVG 캔버스.

`erd.py` 의 `render(d, ...)` 는 PIL ImageDraw 에만 의존한다 — 그리기 원시명령이
text·line·rectangle·rounded_rectangle·arc·ellipse 여섯 뿐이다. 그래서 같은
인터페이스를 가진 이 객체를 대신 넘기면 **레이아웃 계산은 그대로 두고** 결과만
벡터로 뽑을 수 있다.

좌표·폰트 폭은 PIL 이 잰 값을 그대로 쓴다. 그래야 PNG 와 SVG 가 한 픽셀도
어긋나지 않는다. 다만 SVG 는 보는 PC 의 폰트로 글자를 그리므로, 폰트가 없으면
폭이 달라져 글자가 표를 넘어간다 — 그래서 모든 <text> 에 PIL 이 잰 폭을
`textLength` 로 못 박는다. 폰트가 없어도 칸을 벗어나지 않는다.
"""
from xml.sax.saxutils import escape
from i18n import LANG

_ANCHOR = {'l': 'start', 'm': 'middle', 'r': 'end'}

# ── 폰트 폴백 체인 ──────────────────────────────────────────────────────────
# 보는 PC 에 그 폰트가 없을 때를 대비한 목록이다. SVG 도판(이 파일)과 HTML 본문
# (`build_html.py` 의 CSS)이 **같은 규칙을 한 벌로** 쓴다 — 두 벌이면 한쪽만 고쳐서
# 같은 문서의 그림과 본문이 다른 폰트로 나온다.
#
# 예전엔 `ja` 냐 아니냐 둘로만 갈려서, 영어·스페인어 문서도 한글 폰트를 첫 후보로
# 삼았다. 브라우저·뷰어는 이 목록을 **글자마다** 훑으므로(앞엣것에 그 글리프가
# 없으면 다음으로 넘어간다) 문서의 말에 맞는 폰트를 앞에 세우면 된다. 다만 다른
# 문자 체계를 **빼지는** 않는다 — 문서의 말이 영어여도 컬럼 설명은 그 DB 를 쓰는
# 사람의 말로 적혀 있다. 앞뒤 순서만 바꾼다.
#
# (`erd.py` 의 `_SANS_CANDIDATES` 는 같은 것을 반대로 정한다: PIL 은 그림 하나를
#  **폰트 하나**로 그리므로 라틴 전용 폰트가 앞서면 한글·한자가 통째로 □ 가 된다.
#  그래서 거기서는 라틴 후보를 맨 뒤에만 붙이고, ko·ja 에는 아예 안 붙인다. 고르는
#  방식이 다르니 순서도 다르다 — 두 판단이 지키는 것은 같다. '그 문서의 글자가 다
#  보이게'.)
_JA_FONTS = "'Hiragino Sans','Yu Gothic','Noto Sans JP','Meiryo'"
_KO_FONTS = "'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR'"
_LATIN_FONTS = "'Helvetica Neue','Segoe UI',Arial"

# 한자를 쓰는 말이면 그 글리프를 가진 폰트를 앞에 세운다. 한국어 문서에서 일본어
# 폰트가 **앞서면** 한자가 일본식 자형으로 나오므로(骨·直 등이 다르게 보인다) ko 는
# 그것을 맨 뒤에 둔다.
#
# 빼지 않고 맨 뒤에라도 두는 것은 **동작 변경**이다 — 예전 ko 체인에는 일본어 폰트가
# 하나도 없었다. 근거는 `erd.py` 의 `_JA_CANDIDATES` 마지막 줄이 이미 내린 판단과 같다:
# 자형이 남의 나라 것이어도 **□ 보다는 읽을 수 있다.** 이 자리가 실제로 쓰이는 때는 앞의
# 넷(Pretendard·Apple SD Gothic Neo·Malgun Gothic·Noto Sans KR)이 하나도 없거나 그 넷이
# 다 그 한자를 못 덮을 때뿐이고, 그때 예전 판이 하던 일은 generic sans-serif 로 떨어지는
# 것 — 곧 두부다. '제 말 먼저, 나머지 문자 체계는 뒤에 남긴다' 는 **한 규칙**을 세 갈래에
# 똑같이 대는 것이기도 하다 (en·es 가 KO·JA 를 뒤에 남기는 것과 같은 이유).
_STACKS = {
    'ja': (_JA_FONTS, _KO_FONTS, _LATIN_FONTS),
    'ko': (_KO_FONTS, _LATIN_FONTS, _JA_FONTS),
}
_LATIN_STACK = (_LATIN_FONTS, _KO_FONTS, _JA_FONTS)


def font_stack(lang=None):
    """그 언어 문서가 쓸 폰트 폴백 체인. 모르는 말은 라틴 우선으로 친다."""
    code = LANG if lang is None else lang
    return ','.join(_STACKS.get(code, _LATIN_STACK)) + ',sans-serif'


FONT_STACK = font_stack()
MONO_STACK = "'Menlo','D2Coding','DejaVu Sans Mono','Consolas',monospace"


def _pairs(xy):
    """[(x,y),(x,y)] · [x0,y0,x1,y1] 둘 다 받는다 — PIL 이 둘 다 허용한다."""
    if xy and isinstance(xy[0], (tuple, list)):
        return [(float(p[0]), float(p[1])) for p in xy]
    return [(float(xy[i]), float(xy[i + 1])) for i in range(0, len(xy), 2)]


def _box(xy):
    p = _pairs(xy)
    xs = [q[0] for q in p]
    ys = [q[1] for q in p]
    return min(xs), min(ys), max(xs), max(ys)


def _n(v):
    """숫자를 짧게 — 소수 둘째 자리면 충분하고, 파일이 눈에 띄게 작아진다."""
    return f'{v:.2f}'.rstrip('0').rstrip('.')


class SvgCanvas:
    """PIL ImageDraw 호환 캔버스. 그린 것을 SVG 문자열로 돌려준다."""

    def __init__(self, width, height, bg='#222222', font_fallback=None):
        self.w, self.h = int(width), int(height)
        self.bg = bg
        self.parts = []
        self.fallback = font_fallback or FONT_STACK
        self.mono_fallback = MONO_STACK

    # ── 도형 ────────────────────────────────────────────────────────────────
    def _shape(self, tag, attrs, fill=None, outline=None, width=1):
        a = dict(attrs)
        a['fill'] = fill or 'none'
        if outline:
            a['stroke'] = outline
            a['stroke-width'] = _n(width or 1)
        self.parts.append(
            f'<{tag} ' + ' '.join(f'{k}="{v}"' for k, v in a.items()) + '/>')

    def rectangle(self, xy, fill=None, outline=None, width=1, **_kw):
        x0, y0, x1, y1 = _box(xy)
        self._shape('rect', {'x': _n(x0), 'y': _n(y0),
                             'width': _n(x1 - x0), 'height': _n(y1 - y0)},
                    fill, outline, width)

    def rounded_rectangle(self, xy, radius=0, fill=None, outline=None, width=1, **_kw):
        x0, y0, x1, y1 = _box(xy)
        self._shape('rect', {'x': _n(x0), 'y': _n(y0),
                             'width': _n(x1 - x0), 'height': _n(y1 - y0),
                             'rx': _n(radius), 'ry': _n(radius)},
                    fill, outline, width)

    def ellipse(self, xy, fill=None, outline=None, width=1, **_kw):
        x0, y0, x1, y1 = _box(xy)
        self._shape('ellipse', {'cx': _n((x0 + x1) / 2), 'cy': _n((y0 + y1) / 2),
                                'rx': _n((x1 - x0) / 2), 'ry': _n((y1 - y0) / 2)},
                    fill, outline, width)

    def line(self, xy, fill=None, width=1, **_kw):
        pts = _pairs(xy)
        if len(pts) < 2:
            return
        d = ' '.join(f'{_n(x)},{_n(y)}' for x, y in pts)
        self.parts.append(
            f'<polyline points="{d}" fill="none" stroke="{fill or "#000"}" '
            f'stroke-width="{_n(width or 1)}" stroke-linecap="butt"/>')

    def arc(self, xy, start, end, fill=None, width=1, **_kw):
        """PIL arc — 각도는 3시 방향 0도, 시계방향, y 축이 아래로 향한다."""
        import math
        x0, y0, x1, y1 = _box(xy)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = (x1 - x0) / 2, (y1 - y0) / 2
        if rx <= 0 or ry <= 0:
            return
        sweep = (end - start) % 360 or 360
        sx = cx + rx * math.cos(math.radians(start))
        sy = cy + ry * math.sin(math.radians(start))
        ex = cx + rx * math.cos(math.radians(end))
        ey = cy + ry * math.sin(math.radians(end))
        large = 1 if sweep > 180 else 0
        self.parts.append(
            f'<path d="M {_n(sx)},{_n(sy)} A {_n(rx)},{_n(ry)} 0 {large} 1 {_n(ex)},{_n(ey)}" '
            f'fill="none" stroke="{fill or "#000"}" stroke-width="{_n(width or 1)}"/>')

    # ── 글자 ────────────────────────────────────────────────────────────────
    def text(self, xy, text, font=None, anchor=None, fill=None,
             stroke_width=0, stroke_fill=None, **_kw):
        if text is None or text == '':
            return
        x, y = float(xy[0]), float(xy[1])
        size = getattr(font, 'size', 12)
        try:
            ascent, descent = font.getmetrics()
        except Exception:
            ascent, descent = size * 0.8, size * 0.2
        try:
            fam, style = font.getname()
        except Exception:
            fam, style = '', ''
        mono = 'mono' in (fam or '').lower() or (fam or '') in ('Menlo', 'D2Coding')
        family = (f"'{fam}',{self.mono_fallback}" if mono
                  else (f"'{fam}',{self.fallback}" if fam else self.fallback))
        bold = 'bold' in (style or '').lower()

        a = (anchor or 'la')
        ah, av = a[0], (a[1] if len(a) > 1 else 'a')
        # SVG 의 y 는 baseline — PIL 의 기준선(a=위, m=가운데, s=baseline)에서 옮긴다
        if av == 'a':
            y += ascent
        elif av == 'm':
            y += (ascent - descent) / 2
        elif av == 'd':
            y -= descent

        w = self._width(text, font)
        attrs = [f'x="{_n(x)}"', f'y="{_n(y)}"',
                 f'font-family="{family}"', f'font-size="{_n(size)}"']
        if stroke_width and stroke_fill:
            # paint-order=stroke 라야 테두리가 글자 **뒤** 로 간다 (PIL 과 같은 순서)
            attrs += [f'stroke="{stroke_fill}"', f'stroke-width="{_n(stroke_width)}"',
                      'paint-order="stroke"', 'stroke-linejoin="round"']
        if bold:
            attrs.append('font-weight="700"')
        if _ANCHOR.get(ah, 'start') != 'start':
            attrs.append(f'text-anchor="{_ANCHOR[ah]}"')
        if fill:
            attrs.append(f'fill="{fill}"')
        if w > 0:
            # 폰트가 없는 PC 에서도 칸을 넘지 않게 폭을 못 박는다
            attrs.append(f'textLength="{_n(w)}"')
            attrs.append('lengthAdjust="spacing"')
        self.parts.append(f'<text {" ".join(attrs)}>{escape(str(text))}</text>')

    @staticmethod
    def _width(text, font):
        if font is None:
            return 0
        try:
            return font.getlength(str(text))
        except Exception:
            return 0

    # ── 출력 ────────────────────────────────────────────────────────────────
    def tostring(self, title=None):
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" '
                f'height="{self.h}" viewBox="0 0 {self.w} {self.h}" '
                f'shape-rendering="crispEdges" text-rendering="optimizeLegibility">')
        t = f'<title>{escape(title)}</title>' if title else ''
        bg = f'<rect width="{self.w}" height="{self.h}" fill="{self.bg}"/>'
        return head + t + bg + ''.join(self.parts) + '</svg>'

    def save(self, path, title=None):
        from config import atomic_write_text
        atomic_write_text(path, self.tostring(title))
        return path
