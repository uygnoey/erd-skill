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
        # 보는 PC 에 그 폰트가 없을 때를 대비한 폴백 체인.
        # 한자를 쓰는 말이면 그 글리프를 가진 폰트를 앞에 세운다.
        self.fallback = font_fallback or (
            "'Hiragino Sans','Yu Gothic','Noto Sans JP','Meiryo',"
            "'Pretendard','Apple SD Gothic Neo','Malgun Gothic',sans-serif"
            if LANG == 'ja' else
            "'Pretendard','Apple SD Gothic Neo','Malgun Gothic','Noto Sans KR',"
            "'Helvetica Neue',sans-serif")
        self.mono_fallback = "'Menlo','D2Coding','DejaVu Sans Mono','Consolas',monospace"

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
    def text(self, xy, text, font=None, anchor=None, fill=None, **_kw):
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
        from pathlib import Path
        Path(path).write_text(self.tostring(title), encoding='utf-8')
        return path
