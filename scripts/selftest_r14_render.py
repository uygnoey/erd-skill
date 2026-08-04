#!/usr/bin/env python3
"""그림을 그리는 쪽(erd.py)이 지키는 것 — 자기참조 팔의 자리, 라벨의 자리, 재는 자.

`selftest.py` 가 옆에 있는 `selftest_*.py` 를 글로브로 찾아 불러오므로 여기 항목은
등록 줄 없이 함께 돈다 (selftest_kit.load_extras 참고).

파일 끝에는 **회귀 시험이 아닌 도구**도 함께 있다(퍼저·판 만들기). `__main__` 이라
시험 중에는 한 줄도 돌지 않는다 — 쓰는 법은 그 자리 주석에.

열 자리를 지킨다 — R1~R6 은 14·15라운드, R7~R10 은 16라운드다.

  R1  자기참조 팔이 **x 구간이 겹치는** 테이블을 뚫는다. loop_room() 이 '완전히 왼쪽'
      과 '완전히 오른쪽' 만 보고, 원본의 가장자리를 물고 있는 테이블(같은 열의 더 넓은
      테이블이 딱 그 모양이다)은 한 번도 보지 않았다. 게다가 방이 없을 때 lo/hi 를
      바깥으로 억지로 벌려 팔을 그 테이블 한가운데 심었다.
  R2  그 관통을 재는 쪽이 **자기참조 루프를 검증 세그먼트에 넣는가.** 넣는 줄은
      draw_erd() 의 return 한 줄뿐인데, 그 줄을 `self_loops` → `[]` 로 바꿔도 101개가
      전부 통과했다. 카운터가 루프를 못 보면 루프가 테이블을 지나도 `thru 0` 이다.
  R3  방이 없을 때 팔이 제 테이블에 **바짝 붙는가**(12px). 옛 코드는 그 자리에서
      경계를 600px 바깥으로 벌려, 방이 없다는 바로 그 이유로 팔을 남의 테이블
      한가운데 넣었다.
  R4  `ERD_FONT_BOLD`·`ERD_MONO_BOLD` 를 regular 과 같은 자로 재는가. regular 은
      exists() 와 _usable() 을 둘 다 보는데 볼드는 exists() 만 봤다 — 폰트가 아닌
      파일이면 한참 뒤 PIL 안에서 트레이스백이 났고, 없는 파일이면 아무 말 없이
      regular 로 내려가 굵은 글자가 통째로 사라졌다.
  R5  **후보 목록의 볼드도 같은 자로 재는가.** R4 는 사람이 env 로 준 갈래만 지켰다.
      `_pick_font` 는 갈래가 둘인데(env / 후보 목록) 시험이 하나만 봤으므로,
      후보 목록 쪽의 `and _usable(bp, bi)` 를 지워도 전부 초록이었다 — 이 저장소가
      다섯 번 되풀이한 '같은 버그를 반만 고쳤다' 가 이번엔 **시험 쪽에서** 났다.
  R6  방이 제 띠에 없을 때 **띠를 좁혀** 자리를 찾는가. 그 반복문은 시험 한 벌에서
      본문이 44번이나 도는데도 통째로 `for cand in []:` 로 죽여도 전부 초록이었다 —
      죽은 코드가 아니라 **지켜지지 않는 살아 있는 코드**였다. 그리고 그 좁히기가
      끝내 실패했을 때 `slot()` 에 건네는 경계가 **빈 창이 아닌가**(hi > lo).
  R7  라벨이 갈 곳을 잃었을 때 가는 **여백 폴백**이 테이블을 피하는가. 15라운드까지
      그 두 갈래는 `clashes()` 만 보고 `on_a_table()` 을 부르지 않았고, 그런데도
      `라벨↔테이블` 이 0 이었던 것은 검사 덕이 아니라 그 y 가 모든 테이블 위라는
      **암묵 기하** 때문이었다. 여기서는 칠한 글자를 erd.py 밖에서 다시 재
      (label_ink) 테이블과 맞대 본다.
  R8  다섯 카운터가 **실제 도판 규모에서도** 세는가. 검증자 뮤턴트 n21(`thru_nodes()`
      첫 줄에 `if len(node_rects) > 12: return 0`)이 161개를 전부 통과했다 — 시험의
      판이 죄다 작았기 때문이다. 같은 판에 상관없는 테이블 15개를 깔아 열여덟으로
      만든다.
  R9  `import erd` 가 부르는 사람의 cwd 에 무엇을 만드는가. `erd-build/out` 은 이제
      안 만든다(`from config import OUT` 이 그 자리에서 mkdir 을 돌렸다). 스키마를
      읽는 `erd-build/` 는 아직 만든다 — 그 경계까지 케이스가 못박는다.
  R10 (도구) 퍼저와 판 만들기를 이 파일 안에 둔다. 14라운드는 퍼저를 안 남겨 그
      라운드의 수치가 전부 판정불가가 됐고, 15라운드는 scratchpad 에만 두었다.

R1·R2·R3·R6·R7·R8 은 **카운터를 믿지 않는다.** `d.line()`·`d.text()` 호출 자체를
받아 적어 다시 세고, '그린 것' 과 '잰 것' 을 나란히 놓는다 — 그림이 실제로 테이블을
지나는데 카운터가 0 이면 그것이 실패다. 카운터만 읽었으면 R2·R8 의 뮤턴트가 그대로
지나갔다.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from selftest_kit import Fail, case, col, has, run, table, write_schema

HERE = Path(__file__).resolve().parent

EXPECT_CASES = 10        # 등록 개수를 파일이 스스로 못박는다 (selftest_kit.load_extras)


# ── 실제로 칠한 선을 받아 적는 자리 ──────────────────────────────────────────
# 다섯 카운터는 전부 **계획한 좌표**를 읽는다. 계획을 읽는 쪽이 자기참조를 빼먹으면
# (그것이 R2 다) 카운터는 늘 0 이다. 그래서 ImageDraw 를 감싸 d.line() 과 노드 상자를
# 그대로 받아 적고, 여기서 다시 센다. 자를 erd.py 안에 두지 않는다 — 재는 코드가
# 재는 대상 안에 있으면 같이 죽는다.
#
# 두 번째 자도 있다(argv[2] == 'trace'). `sys.settrace` 로 draw_erd 의 render() 프레임
# 만 훑어, 팔의 경계가 정해진 바로 다음 줄에서 lo·hi 를 **그 자리의 지역 변수 그대로**
# 읽는다. 경계가 빈 창인지는 결과에 흔적을 남기지 않으므로(slot() 이 조용히 아무 데나
# 잡는다) 결과만 보는 시험으로는 그 전제를 영영 반증할 수 없다. 줄 번호는 소스에서
# 글자로 찾는다(찾지 못하면 죽는다) — 번호를 손으로 적으면 서식이 바뀌는 순간
# 조용히 0 을 재게 된다.
#
# 세 번째 자는 라벨이다(label_ink). `d.text()` 로 실제로 찍힌 글자에서 잉크 상자를
# erd.py 밖에서 다시 만든다 — 배치와 검증이 **같은** 실수를 하면 카운터로는 볼 수
# 없기 때문이다(13라운드에 실제로 그랬다: 둘이 다른 상자를 봤다).
_PROBE = '''\
import json
import os
import sys
from pathlib import Path

from PIL import ImageDraw as RID

import erd

MODE = sys.argv[1]
TRACE = len(sys.argv) > 2 and sys.argv[2] == 'trace'
EV = []
NODE_FILL = ({v[0] for v in erd.LAYERS.values()}
             | {v[1] for v in erd.LAYERS.values()})
LINE_COL = {erd.EDGE, erd.EDGE_CASCADE}
GUARD_SRC = "near = x1 if side == 'L' else x2"
OBS = []


class Rec:
    def __init__(self, img):
        self._d = RID.Draw(img)
        self._on = img.size != (1, 1)   # 1×1 은 자리를 재는 판이지 칠하는 판이 아니다

    def __getattr__(self, name):
        fn = getattr(self._d, name)
        if not self._on:
            return fn
        if name == 'rectangle':
            def rect(xy, **kw):
                if kw.get('fill') in NODE_FILL:
                    b = ([xy[0][0], xy[0][1], xy[1][0], xy[1][1]]
                         if isinstance(xy[0], (list, tuple)) else list(xy))
                    EV.append(['node', [float(v) for v in b]])
                return fn(xy, **kw)
            return rect
        if name == 'line':
            def ln(xy, **kw):
                if kw.get('fill') in LINE_COL:
                    EV.append(['line', [float(xy[0][0]), float(xy[0][1]),
                                        float(xy[1][0]), float(xy[1][1])]])
                return fn(xy, **kw)
            return ln
        if name == 'text':
            def txt(xy, text, **kw):
                if kw.get('fill') == erd.LABEL_TXT:
                    EV.append(['label', [float(xy[0]), float(xy[1])], text,
                               kw.get('font')])
                return fn(xy, text, **kw)
            return txt
        return fn


def label_ink(ev, scale):
    """**칠한** 라벨의 잉크 상자 — `erd.label_ink_box` 를 부르지 않고 다시 만든다.

    라벨 카운터 둘(label_table · label_x)은 배치가 남긴 `placed` 를 읽는다. 그러니
    배치와 검증이 같은 실수를 하면(예전에 그랬다 — 서로 다른 상자를 봤다) 카운터는
    그것을 볼 수 없다. 여기서는 `d.text()` 호출로 실제로 찍힌 글자 한가운데와 글꼴을
    받아 적고, 그 자리에서 잉크 상자를 **다시 계산한다.** 식은 그리는 쪽과 같아야
    하지만(같은 글자를 재는 것이므로) 코드는 erd.py 밖에 있다 — 재는 코드가 재는
    대상 안에 있으면 같이 죽는다.
    """
    out = []
    for e in ev:
        if e[0] != 'label':
            continue
        (cx, cy), text, font = e[1], e[2], e[3]
        asc, desc = font.getmetrics()
        gb = font.getbbox('Ag_0y')
        mid = (asc + desc) / 2
        up, down = (mid - gb[1]) / scale, (gb[3] - mid) / scale
        halo = max(2, 2 * scale) / scale / 2
        w = font.getlength(text) / scale
        cx, cy = cx / scale, cy / scale
        out.append([cx - w / 2 - halo, cy - up - halo,
                    cx + w / 2 + halo, cy + down + halo])
    return out


def _touch(a, b):
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def node_boxes(ev, scale):
    """받아 적은 사각형을 **테이블 하나에 상자 하나**로 되돌린다.

    상자 하나는 머리와 몸통 두 번에 나눠 칠해진다. 그대로 두면 라벨 하나가 테이블
    하나를 건드려도 둘로 세어, erd 쪽 카운터(테이블마다 상자 하나)와 견줄 수가 없다.
    x 구간이 똑같고 위아래로 맞닿은 것만 합친다 — 같은 열에 나란히 선 **다른** 테이블
    둘을 하나로 붙이지 않으려고 맞닿음까지 본다.
    """
    out = []
    for e in ev:
        if e[0] != 'node':
            continue
        b = [v / scale for v in e[1]]
        for o in out:
            if (abs(o[0] - b[0]) < 0.51 and abs(o[2] - b[2]) < 0.51
                    and b[1] <= o[3] + 1 and o[1] <= b[3] + 1):
                o[1], o[3] = min(o[1], b[1]), max(o[3], b[3])
                break
        else:
            out.append(b)
    return out


def label_report(ev, scale):
    """라벨을 erd 밖에서 잰 결과. 좌표는 전부 scale 로 나눈 도면 좌표다."""
    nodes = node_boxes(ev, scale)
    labs = label_ink(ev, scale)
    ymax = min((n[1] for n in nodes), default=0.0)
    on_table = [[i, [round(v, 1) for v in labs[i]], [round(v, 1) for v in o]]
                for i, a in enumerate(labs) for o in nodes if _touch(a, o)]
    pairs = [[i, j] for i in range(len(labs)) for j in range(i + 1, len(labs))
             if _touch(labs[i], labs[j])]
    return {'n_labels': len(labs), 'n_nodes': len(nodes), 'ymax': round(ymax, 1),
            'on_table': len(on_table), 'on_table_first': on_table[:2],
            'lab_pairs': len(pairs), 'pairs_first': pairs[:3],
            # 노드 위 여백으로 밀려난 라벨 — 폴백 두 갈래가 놓는 자리다.
            'margin': sum(1 for a in labs if a[3] <= ymax)}


def thru_of(ev):
    """칠한 선 가운데 노드 상자 **속**을 지나는 것. 가장자리 2px 는 봐준다."""
    nodes = [e[1] for e in ev if e[0] == 'node']
    out = []
    for e in ev:
        if e[0] != 'line':
            continue
        x0, y0, x1, y1 = e[1]
        for n in nodes:
            ix0, ix1 = max(min(x0, x1), n[0] + 2), min(max(x0, x1), n[2] - 2)
            iy0, iy1 = max(min(y0, y1), n[1] + 2), min(max(y0, y1), n[3] - 2)
            if abs(x1 - x0) < 1 and n[0] + 2 < x0 < n[2] - 2 and iy1 - iy0 > 8:
                out.append(['V', round(x0, 1), round(iy0, 1), round(iy1, 1),
                            [round(v, 1) for v in n]])
            elif abs(y1 - y0) < 1 and n[1] + 2 < y0 < n[3] - 2 and ix1 - ix0 > 8:
                out.append(['H', round(y0, 1), round(ix0, 1), round(ix1, 1),
                            [round(v, 1) for v in n]])
    return out


def guard_line():
    """팔의 경계 lo·hi 를 읽을 줄이 erd.py 몇째 줄인가 — 글자로 찾는다.

    15라운드에는 `if hi - lo < 1:` 을 봤다. 16라운드가 그 갈래를 없애고(도달 불가능한
    조용한 수선이라 반증할 수 없었다) 보장을 갈래 없는 min/max 로 폈으므로, 이제는
    lo·hi 가 확정된 **바로 다음 줄**에서 같은 지역 변수를 읽는다. 'line' 이벤트는 그
    줄을 실행하기 **전에** 오므로, 읽는 자리는 대입 다음 줄이라야 한다.
    """
    src = Path(erd.__file__).read_text(encoding='utf-8').splitlines()
    hit = [i + 1 for i, ln in enumerate(src) if ln.strip() == GUARD_SRC]
    if len(hit) != 1:
        raise SystemExit('the probe looks for the line %r in erd.py and found %d '
                         'of them — the guard was renamed or reformatted, so this '
                         'probe would silently observe nothing'
                         % (GUARD_SRC, len(hit)))
    return hit[0]


def traced(fn):
    """fn() 을 돌리며 그 줄에서 hi - lo 를 받아 적는다 (TRACE 일 때만)."""
    if not TRACE:
        return fn()
    tgt, path = guard_line(), erd.__file__

    def tr(frame, event, arg):
        if event == 'call':
            ok = (frame.f_code.co_name == 'render'
                  and frame.f_code.co_filename == path)
            return tr if ok else None
        if event == 'line' and frame.f_lineno == tgt:
            lv = frame.f_locals
            OBS.append(round(float(lv['hi']) - float(lv['lo']), 3))
        return tr

    sys.settrace(tr)
    try:
        return fn()
    finally:
        sys.settrace(None)


def guard_report():
    return {'n': len(OBS), 'min': min(OBS) if OBS else None,
            'worst': sorted(OBS)[:5], 'traced': TRACE}


def arms_of(ev, box, scale):
    """자기참조 팔의 **세로 구간**만 골라 낸다.

    같은 색으로 칠하는 짧은 표식(까마귀발·한 줄 막대)이 섞여 들어오면 '팔이 12px 로
    붙었다' 와 구별이 안 된다. 팔의 세로 구간은 길이가 2·dy 이고 dy 는 12 아래로
    내려가지 않으므로(띠 좁히기 range 의 끝이 11 이다), 길이 20·scale 로 가른다.
    """
    out = []
    for e in ev:
        if e[0] != 'line':
            continue
        x0, y0, x1, y1 = e[1]
        if abs(x1 - x0) >= 1 or abs(y1 - y0) <= 20 * scale:
            continue
        if box[0] - 3 <= x0 <= box[2] + 3:
            continue                      # 제 상자 안/가장자리 — 팔이 아니다
        out.append({'x': round(x0, 1), 'dy': round(abs(y1 - y0) / 2, 1),
                    'reach': round(box[0] - x0 if x0 < box[0] else x0 - box[2], 1)})
    return out


def self_box(ev, boxes):
    """'s' 의 상자 — 이 그림에서 제일 좁은 것 (다른 둘은 넓히려고 만든 것이다)."""
    want_w = boxes['s']['w'] * 2                  # 기록된 좌표는 scale=2 배다
    return min((e[1] for e in ev if e[0] == 'node'),
               key=lambda b: abs((b[2] - b[0]) - want_w))


erd.ImageDraw = type('m', (), {'Draw': Rec})
erd.OUT.mkdir(parents=True, exist_ok=True)

if MODE == 'every':
    # 전체도와 영역도 전부. build_erd.py 가 그리는 것과 같은 배치를 쓴다.
    jobs = []
    pos, boxes, groups = erd.layout_global()
    jobs.append(('full', list(erd.SCHEMA), pos, boxes, set()))
    for code, _n, _s, tables in erd.AREAS:
        apos, aboxes, ext = erd.layout_area(tables, with_desc=True)
        jobs.append(('area_' + code, tables + ext, apos, aboxes, set(ext)))
    out = {'diagrams': [], 'thru_total': 0, 'n_lines': 0}
    for name, tn, p_, b_, stubs in jobs:
        EV.clear()
        traced(lambda: erd.draw_erd(
            erd.OUT / ('probe_' + name + '.png'), tn, p_, b_, 'probe',
            with_desc=True, scale=2, stubs=stubs, legend=True))
        thru = thru_of(EV)
        n = sum(1 for e in EV if e[0] == 'line')
        out['diagrams'].append({'name': name, 'n_lines': n, 'thru': thru[:4],
                                'n_thru': len(thru)})
        out['thru_total'] += len(thru)
        out['n_lines'] += n
    out['guard'] = guard_report()
    print(json.dumps(out))

elif MODE == 'boxed' or MODE.startswith('boxed:'):
    # 자기참조 하나짜리 테이블을, 그 **왼쪽 가장자리와 오른쪽 가장자리를 각각 물고
    # 있는** 넓은 테이블 둘 사이에 끼운다. 팔은 sx1 에서 왼쪽으로 / sx2 에서
    # 오른쪽으로만 뻗으므로 어느 쪽으로도 빠져나갈 수 없다 — 이 그림은 **반드시**
    # 테이블을 지나는 자기참조 루프를 담는다. 자리는 draw_erd() 에 그대로 넘기는
    # pos 로 못박는다(라우터가 아니라 시험이 정한다). 요점은 그림이 아니라, 그
    # 관통을 재는 쪽이 보느냐다.
    #
    # `boxed:<n>` 이면 상관없는 테이블 n 개를 아래쪽에 더 깐다 — **판을 키우려고**
    # 그런다. 세 테이블짜리 판에서만 무는 케이스는 "테이블이 12개를 넘으면 0 을
    # 돌려준다" 같은 크기 조건부 거짓말을 통과시킨다(검증자 뮤턴트 n21).
    fill = int(MODE.split(':')[1]) if ':' in MODE else 0
    pos, boxes, _g = erd.layout_global()
    names = ['s', 'wl', 'wr'] + [f'f{i:02d}' for i in range(fill)]
    sw = boxes['s']['w']
    pos['s'] = (1000.0, 1000.0)
    pos['wl'] = (1040.0 - boxes['wl']['w'], 1000.0)     # 오른쪽 끝이 sx1 + 40
    pos['wr'] = (1000.0 + sw - 40, 1000.0)              # 왼쪽 끝이 sx2 - 40
    for i in range(fill):
        # 루프에서 멀찍이 아래로. 이 테이블들은 관계가 없으므로 선을 만들지 않고,
        # 자리도 못박으므로 위 세 개의 배치를 바꾸지 않는다 — 바뀌는 것은 **판의
        # 크기**뿐이다.
        pos[f'f{i:02d}'] = (600.0 + (i % 5) * 320.0, 1500.0 + (i // 5) * 320.0)
    traced(lambda: erd.draw_erd(erd.OUT / 'probe_boxed.png', names, pos, boxes,
                                'probe', with_desc=True, scale=2, legend=False))
    thru = thru_of(EV)
    recs = [json.loads(x) for x
            in Path(os.environ['ERD_VERIFY_LOG']).read_text().splitlines() if x.strip()]
    # 's' 는 이 그림에서 제일 좁은 상자다. 팔이 제 테이블 곁을 얼마나 벗어났는지
    # 재려면 그 상자가 어디인지 알아야 한다.
    box = self_box(EV, boxes)
    xs = [v for e in EV if e[0] == 'line' for v in (e[1][0], e[1][2])]
    # draw_erd 는 그림이 너무 크면 **말없이 배율을 낮춘다.** 그러면 받아 적은 좌표를
    # 2 로 나누는 이 자를 통째로 어긋나게 만드므로, 실제로 쓰인 배율을 상자 폭에서
    # 되짚어 함께 넘긴다 — 부르는 쪽이 2 인지 확인한다.
    ws = [e[1][2] - e[1][0] for e in EV if e[0] == 'node']
    seen = round(max(ws) / max(boxes[n]['w'] for n in names), 3) if ws else 0
    print(json.dumps({'n_lines': sum(1 for e in EV if e[0] == 'line'),
                      'n_thru': len(thru), 'thru': thru[:4],
                      'counts': recs[-1]['counts'], 'labels': label_report(EV, 2),
                      'n_tables': len(names), 'scale_seen': seen,
                      'self_box': box, 'line_x': [min(xs), max(xs)] if xs else None,
                      'guard': guard_report(), 'scale': 2}))

elif MODE.startswith('narrow:'):
    # 자기참조 **둘**짜리 테이블 하나와, 그 좌우를 막는 넓은 테이블 둘. 막는 둘은
    # **아래로 gap 만큼 내려** 둔다 — 그러면 팔의 띠(cy ± dy)가 gap 보다 넓어질 때만
    # 걸린다. 둘째 팔은 dy0 = 16 + 1·24 = 40 에서 출발하므로 gap 을 40 아래로 두면
    # **제 띠에는 방이 없고 더 넓은 띠에도 없다**(방은 dy 가 자랄수록 줄기만 한다).
    # 남은 길은 하나뿐이다 — 띠를 좁히는 것. 좁히기가 없으면 팔은 12px 로 붙는다.
    gap = float(MODE.split(':')[1])
    pos, boxes, _g = erd.layout_global()
    names = ['s', 'wl', 'wr']
    sw, sh = boxes['s']['w'], boxes['s']['h']
    pos['s'] = (1000.0, 1000.0)
    cy = 1000.0 + sh / 2
    pos['wl'] = (1000.0 - boxes['wl']['w'] - 2.0, cy + gap)   # 오른쪽 끝이 sx1 - 2
    pos['wr'] = (1000.0 + sw + 2.0, cy + gap)                 # 왼쪽 끝이 sx2 + 2
    traced(lambda: erd.draw_erd(erd.OUT / 'probe_narrow.png', names, pos, boxes,
                                'probe', with_desc=True, scale=2, legend=False))
    box = self_box(EV, boxes)
    print(json.dumps({'n_lines': sum(1 for e in EV if e[0] == 'line'),
                      'n_thru': len(thru_of(EV)), 'thru': thru_of(EV)[:4],
                      'self_box': box, 'arms': arms_of(EV, box, 2),
                      'guard': guard_report(), 'gap': gap, 'scale': 2}))

else:
    raise SystemExit('unknown probe mode: ' + MODE)
'''


# 폰트 고르기는 그림이 아니라 **함수 하나**로 잰다. `_pick_font` 의 갈래는 둘인데
# (env / 후보 목록) 후보 목록은 모듈이 import 되는 순간 이 기계에 있는 경로로 이미
# 결정돼 버려, 바깥에서는 그 갈래에 무엇도 밀어 넣을 수 없다. 그래서 그 함수를
# 직접 부른다 — 이 기계에서 실제로 열리는 폰트를 regular 로 주고, 볼드 자리에만
# 셋을 번갈아 넣는다.
_FONT_PROBE = '''\
import json
import sys

import erd

reg, other = erd.FONT_PATH, erd.MONO_PATH
out = {'reg': reg, 'other': other, 'picked': {}}
for tag, bold in (('not_a_font', sys.argv[1]), ('missing', sys.argv[2]),
                  ('usable', other)):
    # env 이름은 일부러 세팅되지 않은 것을 준다 (부르는 쪽이 ERD_* 를 전부 지운다).
    r, b = erd._pick_font('ERD_FONT_CANDIDATE_PROBE', [(reg, bold)], 'probe')
    out['picked'][tag] = [r[0], b[0]]
print(json.dumps(out))
'''


def _clean_env(work, **extra):
    """부르는 사람의 ERD_*·cwd·$HOME 을 하나도 물려받지 않은 환경."""
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e.update({'ERD_WORK': str(work), 'ERD_PROJ': str(work), 'ERD_LANG': 'en',
              'ERD_DOCNAME': 'T', 'ERD_SVG': '0'})
    e.update({k: str(v) for k, v in extra.items()})
    return e


def _probe(work, mode, verify_log=None, trace=False):
    """probe 를 별도 프로세스로 돌린다. 부르는 사람의 ERD_* 는 하나도 물려받지 않는다.

    selftest_kit.run() 을 쓰지 않는 이유가 있다. 'boxed' 판은 **일부러 더러운 그림**을
    그리므로(그것이 요점이다) 훑기(sweep_verify)에 걸리면 안 된다. 훑기는 run() 이
    등록한 기록만 보므로, 여기서 제 손으로 돌리고 제 손으로 읽는다.
    """
    e = _clean_env(work)
    if verify_log:
        e['ERD_VERIFY_LOG'] = str(verify_log)
    argv = [sys.executable, '-c', _PROBE, mode] + (['trace'] if trace else [])
    r = subprocess.run(argv, capture_output=True, text=True, env=e, cwd=str(HERE))
    if r.returncode != 0:
        raise Fail(f'the line probe died ({mode}):\n{r.stdout[-2000:]}\n{r.stderr[-2000:]}')
    return json.loads(r.stdout.strip().splitlines()[-1])


# ── R1 의 픽스처 ─────────────────────────────────────────────────────────────
# 14라운드 검토자가 무작위 60판(씨앗 991, 자기참조 최대 8)에서 줄여 낸 6테이블
# 37컬럼짜리 최소 재현본이다. **이 모양이 핵심이다**: 같은 열에 놓이면서 원본보다
# 넓은 테이블이 있어야, x 구간이 걸치는데도 loop_room 이 한 번도 보지 않는 그 갈래로
# 들어간다. 기존 자기참조 케이스 둘(`_self_ref_fixture` 는 이름이 짧아 폭이 고르고,
# `_long_name_fixture` 는 모든 테이블이 같은 컬럼 집합이라 폭이 같다)은 이 모양을
# 만들지 않는다 — 그래서 둘 다 초록인 채로 관통이 남아 있었다.
#
# 이 스키마를 낸 퍼저는 저장소에 없다 — 그러니 **이 리스트가 그 판의 유일한 사본**
# 이고, 지우면 다시 못 만든다. 같은 종류를 새로 만들려면 아래 '다섯 카운터를 무엇이
# 움직이는가' 에 적어 둔 모양(스키마 여럿 · 20~45 테이블 · 허브 · 긴 이름 · 테이블당
# 자기참조 0~3)으로 무작위 판을 찍고 `ERD_VERIFY_LOG` 의 counts 를 모으면 된다.
_MIN_THRU = [
    ('code_registry_identifier_00', ['id'], []),
    ('code_identifier_audit_01',
     ['id', 'identifier_owner_node_0_id',
      'root_organization_registry_unit_extremely_long_qualifier_identifier_1_id',
      'registry_ledger_account_2_id', 'ledger_identifier_node_3_id',
      'payload_0', 'payload_1', 'payload_2'],
     ['identifier_owner_node_0_id',
      'root_organization_registry_unit_extremely_long_qualifier_identifier_1_id',
      'registry_ledger_account_2_id', 'ledger_identifier_node_3_id']),
    ('registry_organization_registry_unit_extremely_long_qualifier_parent_03',
     ['id', 'registry_group_root_0_id', 'code_identifier_audit_3_id',
      'owner_code_audit_4_id', 'identifier_registry_audit_5_id',
      'audit_parent_group_6_id'],
     ['registry_group_root_0_id', 'code_identifier_audit_3_id',
      'owner_code_audit_4_id', 'identifier_registry_audit_5_id',
      'audit_parent_group_6_id']),
    ('owner_audit_identifier_06',
     ['id', 'ledger_account_audit_3_id'], ['ledger_account_audit_3_id']),
    ('registry_group_account_07',
     ['id', 'unit_code_parent_0_id', 'account_identifier_ref_1_id',
      'registry_node_account_2_id', 'ledger_owner_code_3_id',
      'identifier_parent_registry_4_id', 'parent_group_account_5_id',
      'root_code_parent_6_id', 'payload_0'],
     ['unit_code_parent_0_id', 'account_identifier_ref_1_id',
      'registry_node_account_2_id', 'ledger_owner_code_3_id',
      'identifier_parent_registry_4_id', 'parent_group_account_5_id',
      'root_code_parent_6_id']),
    ('ledger_ref_identifier_08',
     ['id', 'registry_group_unit_0_id',
      'group_registry_organization_registry_unit_extremely_long_qualifier_1_id',
      'parent_ledger_unit_2_id', 'parent_audit_account_3_id',
      'owner_node_identifier_4_id', 'registry_code_parent_5_id',
      'registry_organization_registry_unit_extremely_long_qualifier_parent_03_ref_187',
      'payload_0', 'payload_1', 'payload_2'],
     ['registry_group_unit_0_id',
      'group_registry_organization_registry_unit_extremely_long_qualifier_1_id',
      'parent_ledger_unit_2_id', 'parent_audit_account_3_id',
      'owner_node_identifier_4_id', 'registry_code_parent_5_id']),
]
# 마지막 하나는 자기참조가 아니라 남을 가리키는 FK 다 (원본 그대로 남긴다).
_MIN_THRU_XREF = ('ledger_ref_identifier_08',
                  'registry_organization_registry_unit_extremely_long_qualifier'
                  '_parent_03_ref_187',
                  'registry_organization_registry_unit_extremely_long_qualifier'
                  '_parent_03')


def _min_thru_fixture(work):
    def fk(c, r):
        return {'column': c, 'ref_table': r, 'ref_column': 'id',
                'on_delete': 'CASCADE'}

    t = {}
    for name, cols, selfs in _MIN_THRU:
        t[name] = table(
            name, [col(c, 'text' if c.startswith('payload_') else 'bigint')
                   for c in cols],
            pk=['id'], fks=[fk(c, name) for c in selfs])
    src, cname, dst = _MIN_THRU_XREF
    t[src]['fks'].append(fk(cname, dst))
    write_schema(work, t)
    return t


@case('render: a self-reference arm clears a table whose x range overlaps its own')
def _(work):
    # 14라운드. `loop_room()` 은 팔이 쓸 수 있는 x 구간을 재는데, 원본 테이블의
    # **완전히 왼쪽**(ox2 <= sx1)과 **완전히 오른쪽**(ox1 >= sx2)만 보고 있었다.
    # 같은 열에 놓인 더 넓은 테이블은 ox1 == sx1, ox2 > sx2 라 어느 쪽도 아니고,
    # 그래서 `continue` 도 clamp 도 없이 **그냥 무시**됐다. 팔이 그 안에 앉았다.
    #
    # 직전 커밋이 "팔이 테이블을 뚫지 않게 한다" 고 적었지만 이 갈래가 남아 있었다.
    # 여기서 세는 것은 `thru` 카운터가 아니라 **실제 d.line() 호출**이다 — 카운터가
    # 루프를 아예 안 보는 문제는 아래 케이스가 따로 지킨다.
    _min_thru_fixture(work)
    got = _probe(work, 'every')
    if got['n_lines'] < 100:
        raise Fail(f'nothing to measure — only {got["n_lines"]} relationship line '
                   'segments were painted across all the diagrams')
    if got['thru_total']:
        bad = [d for d in got['diagrams'] if d['n_thru']][0]
        first = bad['thru'][0]
        raise Fail(
            f'{got["thru_total"]} painted line segment(s) run inside a table box; '
            f'first in {bad["name"]}: {first[0]} at {first[1:4]} through node '
            f'{first[4]} — a self-reference arm was planted in a table whose x '
            'range overlaps its own')


def _boxed_fixture(work, wide, k=4, fill=0):
    """자기참조 k 개짜리 좁은 테이블과, 그 양쪽 가장자리를 각각 물고 있는 넓은 둘.

    자리는 probe 가 pos 로 못박는다 — 라우터가 아니라 시험이 정하는 배치다.

    자기참조를 **여럿** 둔다. 하나면 slot() 이 늘 base(x1-12) 를 그대로 내주므로
    경계가 얼마나 넓은지가 드러나지 않는다 — 옛 600px 창을 되살려도 팔은 같은 자리에
    앉는다(그렇게 확인했다). 팔이 여럿이라야 자리다툼이 생기고, 그때 경계가 어디까지
    열려 있는지가 그림에 나타난다.

    `fill` 은 **판을 키우는** 상관없는 테이블 수다. 관계가 없으므로 선을 한 줄도
    만들지 않고 자리도 probe 가 못박는다 — 바뀌는 것은 `node_rects` 의 길이뿐이다.
    세 테이블짜리 판에서만 무는 케이스는 "테이블이 12개 넘으면 0" 같은 크기 조건부
    거짓말을 통과시킨다.
    """
    tabs = {
        's': table('s', [col('id')] + [col(f'parent_{j}_id') for j in range(k)],
                   pk=['id'],
                   fks=[{'column': f'parent_{j}_id', 'ref_table': 's',
                         'ref_column': 'id', 'on_delete': 'CASCADE'}
                        for j in range(k)]),
        'wl': table('wl', list(wide), pk=['id']),
        'wr': table('wr', list(wide), pk=['id'])}
    for i in range(fill):
        tabs[f'f{i:02d}'] = table(f'f{i:02d}',
                                  [col('id'), col(f'filler_note_{i:02d}', 'text')],
                                  pk=['id'])
    write_schema(work, tabs)


_WIDE = ([col('id')]
         + [col(f'padding_column_that_makes_this_table_wide_{i:02d}',
                'character varying(255)') for i in range(3)])


@case('render: a self-reference loop is measured, not only drawn')
def _(work):
    # 14라운드. 자기참조 루프를 검증 세그먼트에 넣는 것은 draw_erd() 의 return
    # **한 줄**이고, 그 줄 바로 위 주석이 '그리기만 하고 재지 않아서 루프가 옆
    # 테이블을 지나가도 선↔테이블 0 이 찍혔다' 고 적어 두었다. 그런데 그 줄에서
    # `self_loops` 를 `[]` 로 바꿔도 101개가 전부 통과했다 — 지키는 케이스가 없었다.
    #
    # 그래서 **관통이 불가피한 그림**을 하나 만든다: 자기참조 하나짜리 테이블의
    # 왼쪽 가장자리와 오른쪽 가장자리를 각각 물고 있는 넓은 테이블 둘. 팔은 어느
    # 쪽으로도 못 빠져나가므로 루프는 반드시 테이블을 지난다. 이 그림에 그려지는
    # 관계선은 그 루프뿐이므로(다른 두 테이블에는 FK 가 없다) `thru` 가 0 이면
    # 재는 쪽이 루프를 통째로 못 보고 있다는 뜻이다.
    #
    # 카운터를 믿지 않는다. 먼저 **칠한 선**으로 관통을 확인하고(없으면 잴 것이
    # 없는 것이므로 그 자체가 실패다), 그다음에 카운터가 같은 말을 하는지 본다.
    _boxed_fixture(work, _WIDE)
    log = work.parent / 'boxed.jsonl'
    got = _probe(work, 'boxed', verify_log=log)
    if not got['n_lines']:
        raise Fail('no relationship line was painted at all — the fixture stopped '
                   'drawing the self-reference, so nothing is being measured')
    if not got['n_thru']:
        raise Fail('this fixture is meant to box the loop in on both sides so that '
                   'it cannot help but cross a table, and nothing crossed one — '
                   're-tighten the fixture, or the check below proves nothing')
    got_thru = got['counts'].get('thru')
    if got_thru is None:
        raise Fail('line↔table was not measured at all on a diagram that routes a line')
    if not got_thru:
        first = got['thru'][0]
        raise Fail(
            f'{got["n_thru"]} painted segment(s) of the self-reference loop run '
            f'through a table (first: {first[0]} at {first[1:4]} through node '
            f'{first[4]}) and the line↔table counter still says 0 — the self-loops '
            'never reached the segments the verification reads')


@case('render: a self-reference arm with no room hugs its own table')
def _(work):
    # 14라운드. 팔이 놓일 방이 없을 때 옛 코드는 경계를 **바깥으로** 벌렸다:
    # `(dy0, 'L', 0, x1 - 600, x2 + 600)` 로 떨어지거나, lo/hi 를
    # `min(max(lft, x1-600), hi-1)` · `max(min(rgt, x2+600), lo+1)` 로 억지로 만들어
    # slot() 에 600px 짜리 창을 줬다. 방이 없다는 것은 그 창이 통째로 남의 테이블
    # 속이라는 뜻이므로, 벌리는 것이 정확히 최악의 수다 — 같은 라운드가 앞선
    # 커밋에서 이 자리의 '아무 데나' 를 한 번 잡아냈고(`selftest_history.py` 의
    # `render: a self-reference loop is not painted through a table`), 이 갈래는
    # 그때도 남아 있었다.
    #
    # 방이 없으면 갈 곳은 하나뿐이다: 제 테이블에 바짝 붙는 것(12px). 그 12px 는
    # 어떤 이웃도 들어올 수 없는 제 몫이라 최소 피해다. 여기서는 이 그림에 그려진
    # **모든 관계선의 x** 가 자기 상자에서 한 뼘 밖을 못 나가는지 본다.
    _boxed_fixture(work, _WIDE)
    got = _probe(work, 'boxed', verify_log=work.parent / 'hug.jsonl')
    if not got['line_x']:
        raise Fail('no relationship line was painted — nothing to measure')
    bx0, _by0, bx1, _by1 = got['self_box']
    reach = 14 * got['scale']       # 12px 팔 + 선 굵기, 기록된 좌표는 scale 배다
    lo, hi = got['line_x']
    if lo < bx0 - reach or hi > bx1 + reach:
        raise Fail(
            f'the loop has no room on either side, and its arm still reached '
            f'x {lo:.0f}..{hi:.0f} while its own box is {bx0:.0f}..{bx1:.0f} '
            f'(at most {reach:.0f} outside is its own margin) — with no room the '
            'bounds must close onto the table, not open to a 600px window')


# 둘째 팔이 출발하는 띠. `dy0 = 16 + k * 24` (erd.py) 에서 k = 1 이다.
_DY0_SECOND = 16 + 24


@case('render: a self-reference arm with no room in its own band narrows the band')
def _(work):
    # 15라운드. `for cand in range(int(dy0) - 13, 11, -13)` — 제 띠에 방이 없을 때
    # 띠를 **좁혀** 보는 반복문이다. 14라운드는 이것을 "dy0=16 이면 빈 range 라 본문이
    # 한 번도 안 돈다" 고 적었는데 거짓이었다: dy0 = 16 + k·24 이므로 k>=1 이면
    # `range(27, 11, -13)` = [27, 14] 다. 계측해 보면 시험 한 벌에서 본문이 44번 돈다.
    # 그런데도 반복문을 통째로 `for cand in []:` 로 죽이면 전부 초록이었다 —
    # **죽은 코드가 아니라 지켜지지 않는 살아 있는 코드**이고, 다음 라운드가 여기를
    # 건드리면 조용히 회귀한다.
    #
    # 그래서 좁히기 말고는 길이 없는 그림을 만든다. 막는 테이블 둘을 자기참조
    # 테이블의 좌우에 두되 **아래로 gap 만큼 내린다.** 띠는 dy 가 자랄수록 넓어지기만
    # 하므로 걸리는 테이블은 늘 뿐 줄지 않는다 — 즉 제 띠(dy0=40)에서 막히면 더 넓은
    # 띠에도 막힌다. 좁히면 gap 아래로 내려가 방이 열린다.
    #
    # 판을 둘 건다. gap=33 은 첫 후보(27)가 바로 열리고, gap=20 은 첫 후보가 막혀
    # 반복문 안의 `continue` 를 지나 둘째 후보(14)에서 열린다.
    _boxed_fixture(work, _WIDE, k=2)
    for gap in (33.0, 20.0):
        got = _probe(work, f'narrow:{gap:.0f}',
                     verify_log=work.parent / f'narrow{gap:.0f}.jsonl')
        S = got['scale']
        arms = got['arms']
        if len(arms) != 2:
            raise Fail(
                f'nothing to measure (gap {gap:.0f}) — this fixture must paint two '
                f'self-reference arms and {len(arms)} vertical arm segment(s) were '
                f'found among {got["n_lines"]} painted segments')
        if got['n_thru']:
            raise Fail(f'gap {gap:.0f}: the narrowed arm runs through a table — '
                       f'{got["thru"][0]}')
        hug = min(a['reach'] for a in arms)
        band = max(a['dy'] for a in arms)
        if band >= _DY0_SECOND * S:
            raise Fail(
                f'gap {gap:.0f}: an arm still spans its starting band '
                f'(dy {band / S:.0f} >= {_DY0_SECOND}) although that band is walled '
                'in on both sides — the band was never narrowed')
        if hug <= 24 * S:
            raise Fail(
                f'gap {gap:.0f}: an arm gave up and hugged its own table (reach '
                f'{hug / S:.0f}px) although narrowing the band opens room for a '
                'full-length arm — the narrowing loop is not doing anything')


@case('render: the bounds handed to slot() for a self-reference arm are never empty')
def _(work):
    # 15라운드가 세우고 16라운드가 다시 겨눈 자리. 방이 없어 lo/hi 가 뒤집히면
    # slot() 이 경계를 통째로 버리고 '아무 데나' 자리를 잡는데, 그 아무 데나가 남의
    # 테이블 속이다. 15라운드까지는 `if hi - lo < 1:` 한 갈래가 그것을 조용히 고쳤다.
    # 그 갈래는 selftest 184 프로세스 + 퍼저 120 프로세스에서 한 번도 실행되지 않았고
    # (16라운드가 15라운드 코드에 계수기를 박아 다시 쟀다: 퍼저 mix·big 4씨앗 × 60판
    # + 자기참조 판 247개에서 이 자리 도달 106,317회, 발동 0회, 본 hi-lo 의 최솟값
    # 1.000), 조용히 고치는 줄이라
    # 결과에도 흔적이 없다 — 결과만 보는 시험으로는 영영 반증할 수 없었다. 16라운드가
    # 그 갈래를 없애고, 같은 보장을 갈래 없는 min/max 하나로 폈다.
    #
    # 그래서 결과가 아니라 **그 자리의 지역 변수**를 본다(sys.settrace). 지키는 것은
    # 수선이 아니라 불변식이다: 팔의 경계는 어느 갈래로 와도 1px 이상 열려 있다.
    # 갈래는 셋뿐이고 셋 다 그것을 보장한다 —
    #   · 넓히기/좁히기가 고른 띠: 그 쪽 room >= 1 이라 hi - lo = min(room, 588) >= 1
    #   · spare 로 떨어진 띠: spare 에 들어가기 전에 room >= 1 을 이미 봤다
    #   · 어느 띠에도 방이 없어 12px 로 붙는 갈래: lft/rgt 가 x1-13 · x2+13 이라 정확히 1
    # 그리고 고른 쪽 경계에 12px 자기 몫을 보태는 min/max 가 그 셋과 무관하게 1px 을
    # 보장한다. 이 케이스가 빨강이면 그 넷이 함께 깨진 것이다.
    #
    # 세 판을 함께 건다 — 붙는 갈래(boxed), 좁히는 갈래(narrow), 실제 배치(every).
    seen, worst = 0, None
    _boxed_fixture(work, _WIDE)
    for mode in ('boxed', 'narrow:33'):
        got = _probe(work, mode, verify_log=work.parent / 'guard.jsonl', trace=True)
        g = got['guard']
        if not g['traced']:
            raise Fail(f'{mode}: the probe did not trace at all')
        seen += g['n']
        if g['min'] is not None and (worst is None or g['min'] < worst[1]):
            worst = (mode, g['min'], g['worst'])
    _min_thru_fixture(work)
    got = _probe(work, 'every', verify_log=work.parent / 'guard2.jsonl', trace=True)
    g = got['guard']
    seen += g['n']
    if g['min'] is not None and (worst is None or g['min'] < worst[1]):
        worst = ('every', g['min'], g['worst'])
    if seen < 20:
        raise Fail(f'nothing to measure — the three boards reached the bounds of a '
                   f'self-reference arm only {seen} time(s); this case proves '
                   'nothing unless the arms are actually placed')
    if worst and worst[1] < 1:
        raise Fail(
            f'the bounds handed to slot() closed to {worst[1]} on the {worst[0]} '
            f'board (the five tightest: {worst[2]}) — slot() drops lo/hi it cannot '
            'satisfy (hi <= lo) and then plants the arm anywhere, which is inside a '
            'table. 16R removed the silent repair that used to hide this: the width '
            'now comes from one branchless min/max on the line above, so a red here '
            'means that expression, or one of the three branches feeding it, broke')


@case('render: a label with nowhere to sit lands above every table, not on one')
def _(work):
    # 16라운드. 라벨 자리잡기의 후보가 전멸했을 때 가는 폴백은 두 갈래다 — 노드 위
    # 여백을 40줄 × 5칸 뒤지는 반복문과, 그것마저 실패했을 때의 마지막 상자. 15라운드
    # 까지 **둘 다 `clashes()` 만 보고 `on_a_table()` 을 부르지 않았다.** 그런데도
    # `label_table` 이 0 이었던 것은 검사 덕이 아니라 그 자리의 y 가 `ymax`(모든
    # 테이블 top 의 최소) 위라는 **암묵 기하** 때문이었다. 검증자가 811 도판에서
    # 움직여 보려다 실패한 것이 그 증거이고, 동시에 문제이기도 하다: 지켜지는 근거가
    # 검사가 아니면, 그 y 를 한 줄 옮기는 사람은 아무 경고 없이 라벨을 테이블 속에
    # 넣는다.
    #
    # 여기서 재는 것은 카운터가 아니라 **칠한 글자**다. `d.text()` 호출을 받아 적고
    # 잉크 상자를 erd.py 밖에서 다시 만들어(label_ink) 테이블과 맞대 본다. 그리고
    # 카운터가 같은 말을 하는지 나란히 본다.
    #
    # 'boxed' 판은 자기참조 넷이 좌우로 막힌 그림이라 네 라벨이 **전부** 여백 폴백으로
    # 밀린다(그래서 이 판이 폴백을 재는 자리다). 그 사실 자체를 먼저 못박는다 —
    # 폴백을 안 지나면 이 케이스는 아무것도 증명하지 않는다.
    _boxed_fixture(work, _WIDE)
    got = _probe(work, 'boxed', verify_log=work.parent / 'fallback.jsonl')
    lab = got['labels']
    if got['scale_seen'] != got['scale']:
        raise Fail(f'nothing to measure — draw_erd lowered the scale to '
                   f'{got["scale_seen"]}x, so the ruler in this probe (which divides '
                   f'by {got["scale"]}) is reading the wrong coordinates')
    if lab['n_labels'] != 4:
        raise Fail(f'nothing to measure — this fixture must paint the four '
                   f'self-reference labels and {lab["n_labels"]} were painted')
    if lab['margin'] != lab['n_labels']:
        raise Fail(
            f'nothing to measure — only {lab["margin"]} of {lab["n_labels"]} labels '
            'were pushed into the margin above the tables, so the fallback branch '
            'this case exists for was not taken; re-tighten the fixture (or the y of '
            'the fallback moved, which is exactly what this case is here to catch)')
    if lab['on_table']:
        first = lab['on_table_first'][0]
        raise Fail(
            f'{lab["on_table"]} painted label(s) sit on a table box — label #{first[0]} '
            f'inked {first[1]} overlaps the node {first[2]}. The fallback must ask '
            'on_a_table() like every other candidate does; do not lean on "the margin '
            'happens to be above ymax"')
    if got['counts'].get('label_table') != 0:
        raise Fail(
            f'the painted labels clear every table but label↔table reports '
            f'{got["counts"].get("label_table")!r} — the counter and the picture '
            'disagree')


@case('render: line↔table is still counted when the board is full size')
def _(work):
    # 16라운드. 검증자 뮤턴트 n21 — `thru_nodes()` 첫 줄에 `if len(node_rects) > 12:
    # return 0` 을 넣으면 161개가 **전부 초록**이었다. 퍼저로 대조하면 같은 뮤턴트가
    # 진짜 회귀의 thru 49 를 4 로 줄인다. 즉 큰 판이 통째로 0 으로 보고되는데도
    # 회귀 시험이 아무 말을 안 했다 — 시험의 판이 전부 작았기 때문이다.
    #
    # 그래서 같은 'boxed' 판에 **상관없는 테이블 15개**를 더 깔아 열여덟 테이블로
    # 만든다. 선은 그대로 자기참조 루프뿐이고 자리도 못박혀 있으므로 그림은 바뀌지
    # 않는다 — 바뀌는 것은 판의 크기뿐이다. 여기서도 먼저 **칠한 선**으로 관통을
    # 확인하고(없으면 잴 것이 없는 것이므로 그 자체가 실패다), 그다음에 카운터가
    # 같은 말을 하는지 본다.
    _boxed_fixture(work, _WIDE, fill=15)
    got = _probe(work, 'boxed:15', verify_log=work.parent / 'big.jsonl')
    if got['n_tables'] < 16:
        raise Fail(f'nothing to measure — this board must be big enough that a '
                   f'size-conditional counter would give up on it, and it has only '
                   f'{got["n_tables"]} tables')
    if not got['n_thru']:
        raise Fail('this fixture boxes the loop in on both sides so that it cannot '
                   'help but cross a table, and nothing crossed one — re-tighten the '
                   'fixture, or the check below proves nothing')
    if not got['counts'].get('thru'):
        first = got['thru'][0]
        raise Fail(
            f'{got["n_thru"]} painted segment(s) run through a table on an '
            f'{got["n_tables"]}-table board (first: {first[0]} at {first[1:4]} '
            f'through node {first[4]}) and line↔table reports '
            f'{got["counts"].get("thru")!r} — the counter stops counting once the '
            'board is a real size, so every full-size diagram reports a clean 0')
    # 라벨 자도 같이 읽는다. 이 판에서 둘 다 0 이지만, 0 을 **재고 있다**는 것과
    # '재는 척한다' 는 다르다 — 칠한 글자로 다시 세어 카운터와 맞춰 본다.
    lab = got['labels']
    if lab['on_table'] != got['counts'].get('label_table'):
        raise Fail(
            f'the painted labels touch a table {lab["on_table"]} time(s) but '
            f'label↔table says {got["counts"].get("label_table")!r} on an '
            f'{got["n_tables"]}-table board')
    if lab['lab_pairs'] != got['counts'].get('label_x'):
        raise Fail(
            f'the painted labels overlap each other {lab["lab_pairs"]} time(s) but '
            f'label↔label says {got["counts"].get("label_x")!r} with '
            f'{lab["n_labels"]} labels on the board')


@case('erd: importing erd creates nothing but the directory it reads the schema from')
def _(work):
    # 16라운드. 검증자가 빈 디렉터리에서 재니 `import erd` 하나가 `./erd-build` 와
    # `./erd-build/out` 을 만들었다. 15라운드가 세운 '**import 는 아무것도 안
    # 만든다**' 는 `config`·`parse_ddl`·`introspect`·`merge_desc` 넷에만 성립했고,
    # 그 회귀 케이스도 그 넷만 본다. 원인은 `from config import OUT` — 그 이름들은
    # PEP 562 로 늦춰져 있어서 **가져오는 그 순간** mkdir 이 돈다.
    #
    # 이 파일은 그 규칙을 **erd.py 가 지킬 수 있는 만큼**만 못박는다. erd.py 는
    # 25번째 줄에서 곧바로 schema.json 을 읽는 모듈이라 `import erd` 는 정의상 '이
    # 프로젝트의 스키마를 읽는다' 는 뜻이고, 그 물음이 WORK(`erd-build/`) 를 만든다.
    # 그것까지 없애려면 SCHEMA·SPEC·AREAS 를 전부 지연 값으로 돌려야 하는데 모듈
    # 안에서의 전역 조회는 PEP 562 를 거치지 않아 파일 전체를 고쳐야 한다 — 16라운드는
    # 하지 않았다. 그러니 여기서 재는 것은 **정확히 그 경계**다: 스키마를 읽는 자리는
    # 만들고, 산출물 자리는 물어볼 때까지 안 만든다. 다음 라운드가 나머지 절반을
    # 없애면 이 케이스의 기대값을 함께 좁히면 된다(빈 목록으로).
    cwd = work.parent / 'erd_cwd'
    (cwd / 'erd-build').mkdir(parents=True, exist_ok=True)
    write_schema(cwd / 'erd-build', {'t': table('t', [col('id')], pk=['id'])})
    env = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    r = subprocess.run(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0, sys.argv[1]); import erd; print("ok")',
         str(HERE)],
        capture_output=True, text=True, cwd=str(cwd), env=env)
    if r.returncode != 0:
        raise Fail(f'erd must still import when the schema is there:\n'
                   f'{r.stdout[-300:]}\n{r.stderr[-500:]}')
    left = sorted(p.name for p in cwd.iterdir())
    if left != ['erd-build']:
        raise Fail(f"importing erd left {left} in the caller's directory — it may "
                   'only touch the directory it reads schema.json from')
    inside = sorted(p.name for p in (cwd / 'erd-build').iterdir())
    if 'out' in inside:
        raise Fail(
            "importing erd created the output directory (erd-build/out) — nothing "
            'was drawn yet. `from config import OUT` wakes the deferred value at '
            'import time; ask for it where it is used (erd.OUT / config.OUT) '
            f'instead. The working directory now holds {inside}')

    # 안 만드는 것과 못 만드는 것은 다르다 — 물어보면 그 자리에서 만들어야 한다.
    r = subprocess.run(
        [sys.executable, '-c',
         'import sys; sys.path.insert(0, sys.argv[1]); import erd; print(erd.OUT)',
         str(HERE)],
        capture_output=True, text=True, cwd=str(cwd), env=env)
    if r.returncode != 0:
        raise Fail(f'asking erd.OUT must still answer:\n{r.stderr[-500:]}')
    # macOS 의 /tmp 는 /private/tmp 의 심볼릭 링크라 글자로 견주면 어긋난다.
    said = Path(r.stdout.strip().splitlines()[-1]).resolve()
    want = (cwd / 'erd-build' / 'out').resolve()
    if said != want:
        raise Fail(f'erd.OUT answered {said} instead of {want} — deferring must not '
                   'move the path')
    if not (cwd / 'erd-build' / 'out').is_dir():
        raise Fail('asking for erd.OUT must create it — deferring is not refusing')


# ── 다섯 카운터를 무엇이 움직이는가 (15·16라운드 조사 기록) ───────────────────
# 12라운드가 "그물은 있는데 걸리는 물고기가 없다" 고 부른 자리다. 14라운드 검토자의
# 퍼저는 1138장을 재고 `thru` 하나만 움직였고, 나머지 넷은 **수정 전에도** 0 이었다 —
# 그러면 '다른 카운터가 안 올랐다' 는 아무것도 뜻하지 않는다. 15라운드가 넷을 각각
# 겨냥해 다시 쟀다. 결과를 여기 적어 둔다. 숫자만 옮기지 말고 **왜 그런지**를 남긴다.
#
#   thru        움직인다. 이 파일의 'boxed' 판이 매번 낸다(양쪽이 막힌 자기참조).
#               무작위로도 난다 — loop_room 의 '걸치는' 두 갈래를 되돌리면 mix 판
#               4씨앗 × 60판에서 42·57·69·45.
#   v_overlap   움직인다. 스키마 여럿 · 40~70 테이블 · 허브 여럿짜리 판에서 난다.
#   h_overlap   움직인다. 위와 같은 판, 그리고 이 파일의 narrow gap=20 판에서 2.
#   label_x     움직인다. **아주 몰아넣어야** 난다 — 허브 하나에 자식 40, 자식마다
#               길이 60 넘는 이름의 FK 12개(라벨 480개). 라벨 자리잡기는 막히면 노드
#               위 여백을 40줄 × 5칸 = 200자리 뒤지는데, 그 200을 넘겨야 겹친다.
#               16라운드가 다시 쟀다(값은 15라운드가 적은 245 가 아니었다):
#                 자식 40 · FK 12 (라벨 480) → 영역도 label_x **124**,
#                     erd 밖에서 다시 잰 잉크 상자도 **124** — 두 자가 정확히 같다.
#                     전체도+영역도 62초, 영역도만 30초.
#                 자식 32 · FK 12 (라벨 384) → 0.  자식 26 (312) → 0.  자식 20 → 0.
#                 자기참조만 몰아넣은 판(테이블 하나에 자기참조 250·400)도 0 —
#                     팔마다 라벨의 x 중심이 갈라져 한 무리가 200자리를 못 채운다.
#               그래서 **회귀 시험에는 아직 넣지 못했다.** 30초짜리 케이스 하나를
#               161개짜리 벌(52초)에 넣는 것이 옳은지 판단이 서지 않아서다. 대신
#               `label_x` 를 크기 조건부로 거짓말시키는 뮤턴트(`lab_hits()` 첫 줄에
#               `if len(lab_boxes) > 3: return 0`)는 `selftest.py` 의 단위 케이스가
#               잡는다 — 이 파일은 못 잡는다. 다음 라운드가 여기를 열려면 위 40×12
#               판을 쓰면 된다(`python3 selftest_r14_render.py board --mode …` 가
#               아니라 손으로 만든 허브 판이다. 만드는 법은 위 두 줄이 전부다).
#   label_table **입력으로는 못 움직인다 — 그리고 그것이 옳다.** 자리잡기의
#               `on_a_table()` 과 검증의 `lab_hit` 이 같은 함수 둘(label_ink_box ·
#               boxes_touch)을 쓰고, 노드를 피하는 것이 자리잡기의 강제 조건이며,
#               막혔을 때 가는 여백 폴백도 **이제는** on_a_table() 을 지난다
#               (16라운드. 그 전에는 안 지났고, 0 인 근거가 검사가 아니라 '여백은
#               모든 노드 위' 라는 암묵 기하였다). 살아 있다는 것은 뮤턴트로만
#               보인다: `on_a_table` 이 잉크 상자 대신 여백 상자를 보게 되돌리면
#               (둘이 어긋나던 옛 모양) 같은 퍼저 20판에서 label_table 2 가 나온다.
#
# 그래서 이 파일의 케이스들은 `label_table`·`label_x` 의 **값**을 회귀 신호로 쓰지
# 않는다. 대신 `R7`·`R8` 은 그 0 을 erd.py 밖의 자로 **다시 재서** 카운터와 맞춰
# 본다 — '0 이라 깨끗하다' 와 '0 밖에 안 나오는 자라서 모른다' 는 다르고, 두 자가
# 함께 0 이라야 앞엣것이다.


# ── 폰트 설정 ────────────────────────────────────────────────────────────────
def _resolved_font(work, env):
    """이 기계에서 실제로 열리는 폰트 경로를 **코드에게 물어** 받는다.

    시험이 제 손으로 경로를 적으면 그 경로가 없는 기계에서 조용히 딴 것을 재게 된다.
    """
    e = _clean_env(work)
    var = {'ERD_FONT': 'FONT_PATH', 'ERD_MONO': 'MONO_PATH'}[env]
    r = subprocess.run([sys.executable, '-c', f'import erd; print(erd.{var})'],
                       capture_output=True, text=True, env=e, cwd=str(HERE))
    if r.returncode != 0:
        raise Fail(f'could not ask erd.py which font it uses:\n{r.stderr[-800:]}')
    return r.stdout.strip().splitlines()[-1]


@case('errors: an unusable ERD_FONT_BOLD is explained the same way ERD_FONT is')
def _(work):
    # 14라운드. regular 은 `exists()` 와 `_usable()` 을 둘 다 보고 사람 말로 죽는데
    # 볼드는 `exists()` 만 봤다. 갈래가 둘로 새고 있었다 —
    #   · 폰트가 아닌 파일: exists() 를 지나가고 한참 뒤 PIL 안에서
    #     `OSError: unknown file format` 으로 터진다 (사람 말이 아니라 트레이스백)
    #   · 없는 파일: 아무 말 없이 regular 로 내려간다 (굵은 글자가 통째로 사라져도
    #     아무도 모른다)
    # `errors: an unusable font is explained` 는 `ERD_FONT` 만 본다. 이 저장소가
    # 다섯 번 되풀이한 '같은 버그를 반만 고쳤다' 의 모양 그대로다.
    write_schema(work, {'t': table('t', [col('id')])})
    for env in ('ERD_FONT', 'ERD_MONO'):
        good = _resolved_font(work, env)
        # 먼저 대조군. regular 만 세워도 그림이 나와야, 아래 실패가 볼드 탓임이
        # 성립한다 — 안 그러면 '아무거나 주면 죽는다' 를 재는 것이 된다.
        run('build_erd.py', work, env={env: good})
        for bad, why in ((str(HERE / 'erd.py'), 'a file that is not a font'),
                         (str(work / 'no-such-font.ttf'), 'a file that is not there')):
            r = run('build_erd.py', work, env={env: good, env + '_BOLD': bad},
                    expect_ok=False)
            out = r.stdout + r.stderr
            if 'Traceback' in r.stderr:
                raise Fail(f'{env}_BOLD set to {why} should be a message, not a '
                           f'traceback:\n{r.stderr[-600:]}')
            has(out, env + '_BOLD',
                f'{env}_BOLD set to {why} must name the variable that is wrong')


@case('errors: a bold font from the candidate list is opened before it is picked')
def _(work):
    # 15라운드. 위 케이스는 `_pick_font` 의 **env 갈래**만 본다. 같은 함수에는 갈래가
    # 하나 더 있다 — 사람이 아무것도 주지 않았을 때 도는 후보 목록 쪽이고, 거기서도
    # 볼드는 `Path(bp).exists() and _usable(bp, bi)` 로 둘 다 재야 한다. 14라운드가
    # 그렇게 고쳤는데 지키는 케이스가 없어서, `and _usable(bp, bi)` 를 지워도 전부
    # 초록이었다. **고친 것의 절반이 반증 불가능했다** — 이 저장소가 다섯 번 되풀이한
    # '같은 버그를 반만 고쳤다' 가 이번엔 시험 쪽에서 났다.
    #
    # 후보 목록은 모듈이 import 되는 순간 이 기계의 경로로 굳으므로 바깥에서 밀어
    # 넣을 수가 없다. 그래서 함수를 직접 부른다 — 세팅되지 않은 env 이름을 주어
    # env 갈래를 지나치게 하고, 후보 하나를 손으로 만들어 준다.
    #
    # **양쪽을 다 본다.** 열리지 않는 볼드는 regular 로 내려가야 하고(죽지는 않는다 —
    # 우리가 짐작한 경로지 사람이 적은 설정이 아니다), 열리는 볼드는 그대로 쓰여야
    # 한다. 뒤엣것이 없으면 '늘 regular 로 내려간다' 는 뮤턴트가 통과한다.
    write_schema(work, {'t': table('t', [col('id')])})
    not_a_font = str(HERE / 'erd.py')
    missing = str(work / 'no-such-font.ttf')
    r = subprocess.run([sys.executable, '-c', _FONT_PROBE, not_a_font, missing],
                       capture_output=True, text=True, env=_clean_env(work),
                       cwd=str(HERE))
    if r.returncode != 0:
        raise Fail(f'the font probe died:\n{r.stdout[-800:]}\n{r.stderr[-1500:]}')
    got = json.loads(r.stdout.strip().splitlines()[-1])
    reg, other = got['reg'], got['other']
    if reg == other:
        raise Fail('nothing to measure — this machine resolves ERD_FONT and ERD_MONO '
                   f'to the same file ({reg}), so the "a usable bold is kept" half '
                   'of this case cannot be told apart from the fallback')
    for tag, why in (('not_a_font', 'a file that exists but will not open as a font'),
                     ('missing', 'a file that is not there')):
        picked = got['picked'][tag][1]
        if picked != reg:
            raise Fail(
                f'a candidate whose bold is {why} was picked anyway ({picked!r}) '
                f'instead of falling back to its own regular ({reg!r}) — the '
                'candidate list measures the bold with exists() only, so PIL blows '
                'up much later, inside the drawing code, with a traceback')
    kept = got['picked']['usable'][1]
    if kept != other:
        raise Fail(
            f'a candidate whose bold opens fine was dropped anyway (picked {kept!r}, '
            f'the bold on offer was {other!r}) — the fallback is unconditional, so '
            'the check above proves nothing and bold text is gone everywhere')


# ══════════════════════════════════════════════════════════════════════════════
# 도구 — 회귀 시험이 아니라 **다음 라운드가 쓸 자**다.
# ══════════════════════════════════════════════════════════════════════════════
# 14라운드는 퍼저를 남기지 않아 그 라운드의 수치가 전부 판정불가가 됐고, 15라운드는
# scratchpad 에만 두어 검증자가 제 것을 새로 써야 했다. scratchpad 는 사라진다.
# 그래서 이 파일 안에 둔다. `selftest.py` 는 이 파일을 **import** 하므로 아래
# `__main__` 은 시험 중에는 한 줄도 돌지 않는다.
#
#   python3 selftest_r14_render.py fuzz --seed 7 --boards 60 --mode mix
#   python3 selftest_r14_render.py fuzz --scripts /other/scripts --seed 7 …
#   python3 selftest_r14_render.py board --mode big --seed 3 --out /tmp/w
#
# `--scripts` 로 **다른 트리**를 가리킬 수 있다 — 수정 전/후를 나란히 재는 방법이
# 그것이다(사본을 만들고 erd.py 만 옛것으로 바꿔 두 번 돌린다).
#
# 판 모양은 15라운드 퍼저(scratchpad/r15-render/fuzz_counters.py)의 것을 그대로
# 옮겼다. 모양이 같아야 라운드 사이 수치를 견줄 수 있다.
# ── 뮤턴트 목록 (16라운드가 실제로 돌린 것) ───────────────────────────────────
# 뮤턴트를 넣는 하네스 자체는 여기 못 넣는다 — 그것은 시험 벌 **바깥**에서 사본
# 트리를 만들어 돌려야 하고, 시험이 제 사본을 만들어 제 뮤턴트를 채점하면 15라운드가
# 지적한 '재는 쪽이 제 답안을 제가 채점한다' 로 되돌아간다. 대신 **레시피**를 둔다:
# 트리를 통째로 복사하고(`.git` 제외) 아래 원문을 그대로 찾아 바꾼 뒤
# `python3 selftest.py` 를 돌린다. 못 찾으면 죽여야 한다 — 안 그러면 '뮤턴트 없이
# 초록' 을 뮤턴트가 잡힌 것으로 착각한다.
#
#   이름                erd.py 의 원문 → 바꾼 것                       16R 후 빨강
#   fb_y_down          `ymax - 22 - row * 19` / `ymax - 8 - row * 19`
#                        → `ymax + 22 + row * 19` / `ymax + 36 + row * 19`   R7
#   fb_row_nocheck     `if not on_a_table(cand) and not clashes(cand):`
#                        → `if not clashes(cand):`                           (없음)
#   fb_last_nolift     마지막 상자의 `while on_a_table(box): …` 두 줄 삭제    (없음)
#   n21                `thru_nodes()` 첫 줄에 `if len(node_rects) > 12: return 0`
#                                                                            R8 + selftest.py 둘
#   n3                 `lab_hits()` 첫 줄에 `if len(lab_boxes) > 3: return 0` selftest.py 둘
#   lab_hit_sliced     `for b in lab_boxes` → `for b in lab_boxes[:3]`        selftest.py 하나
#   bounds_no_min      `min(lo_l, x1 - 13)`·`max(hi_r, x2 + 13)` 되돌리기     (없음)
#   bounds_outward     같은 자리를 600 으로                                   R1·R3 + history
#   narrow_dead        `for cand in range(int(dy0) - 13, 11, -13):` → `for cand in []:`  R6
#   narrow_spare_gone  좁히기의 `if spare is None or clear > spare[0]:` → `if False:`    R6
#   hug_600            `x1 - 13, x2 + 13` → `x1 - 600, x2 + 600`             R3
#   loop_room_straddle `elif ox1 < sx1: left = max(left, sx1)` 삭제           R3·R7
#   loops_unmeasured   `for pts, color, label, _o in self_loops]` → `… in []]`  R2·R8
#   out_eager          `from config import SCHEMA_JSON` → `… import OUT, SCHEMA_JSON`  R9
#
# `(없음)` 은 **오늘 어떤 판으로도 반증할 수 없다**는 뜻이다. 셋 다 '일어나지 않는
# 상태'를 막는 검사라 그렇다 — 지우면 뜻이 달라지지만 그 차이가 어떤 입력에도
# 드러나지 않는다. 그 자리를 없애는 대신 남겨 둔 이유는 각 자리 주석에 적어 두었다.
COUNTERS = ['label_table', 'label_x', 'thru', 'v_overlap', 'h_overlap']
_WORDS = ['registry', 'ledger', 'account', 'identifier', 'node', 'parent', 'owner',
          'code', 'unit', 'group', 'audit', 'root', 'ref', 'organization']
_LONG_Q = 'extremely_long_qualifier_that_widens_the_label'

# 판 하나를 그리는 자리. build_erd.py 를 부르지 않는다 — 그 파일은 이 라운드에
# 다른 사람이 고치는 중이고, 여기서 재려는 것은 erd.py 가 그리는 그림이다.
_DRIVE = '''\
import erd

erd.OUT.mkdir(parents=True, exist_ok=True)
pos, boxes, groups = erd.layout_global()
# build_erd.py 가 그리는 것과 같은 세 갈래: 개요도(라벨 없음) · 전체도 · 영역도.
opos, oboxes, ogroups = erd.layout_overview()
erd.draw_erd(erd.OUT / 'fz_overview.png', list(erd.SCHEMA), opos, oboxes, 'fuzz',
             with_desc=False, scale=2, legend=True, edge_labels=False,
             groups=ogroups, derives=True)
erd.draw_erd(erd.OUT / 'fz_full.png', list(erd.SCHEMA), pos, boxes, 'fuzz',
             with_desc=True, scale=2, legend=True, groups=groups, derives=True)
for code, _n, _s, tables in erd.AREAS:
    apos, aboxes, ext = erd.layout_area(tables, with_desc=True)
    erd.draw_erd(erd.OUT / ('fz_area_' + code + '.png'), tables + ext, apos, aboxes,
                 'fuzz', with_desc=True, scale=2, stubs=set(ext), legend=True)
print('ok')
'''


def _fz_col(name, typ='bigint'):
    return {'name': name, 'type': typ, 'not_null': False, 'default': None,
            'comment': '', 'added': False, 'identity': False}


def _fz_table(name, cols, pk=(), fks=(), schema='public'):
    return {'name': name, 'schema': schema, 'db': '', 'origin': 'existing',
            'columns': cols, 'pk': list(pk), 'fks': list(fks), 'uniques': [],
            'checks': [], 'indexes': [], 'note': '', 'rows': 1, 'size': ''}


def _fz_fk(c, r):
    return {'column': c, 'ref_table': r, 'ref_column': 'id', 'on_delete': 'CASCADE'}


def board(rnd, mode):
    """무작위 스키마 한 판. mode: self · hub · long · chain · mix · big · dense"""
    if mode in ('big', 'dense'):
        return _board_big(rnd, dense=(mode == 'dense'))
    n = rnd.randint(4, 14)
    names = []
    for i in range(n):
        base = '_'.join(rnd.sample(_WORDS, 3))
        if mode in ('long', 'mix') and rnd.random() < 0.4:
            base += '_' + _LONG_Q
        names.append(f'{base}_{i:02d}')
    tabs = {}
    for i, nm in enumerate(names):
        cols, fks = [_fz_col('id')], []
        if mode in ('self', 'mix') or (mode in ('long', 'hub', 'chain')
                                       and rnd.random() < 0.3):
            for j in range(rnd.randint(0, 4)):
                c = f'{rnd.choice(_WORDS)}_{rnd.choice(_WORDS)}_{j}_id'
                if mode in ('long', 'mix') and rnd.random() < 0.5:
                    c = f'{_LONG_Q}_{j}_id'
                cols.append(_fz_col(c))
                fks.append(_fz_fk(c, nm))
        if mode in ('hub', 'mix') and i > 0 and rnd.random() < 0.7:
            c = f'hub_{i}_id'
            cols.append(_fz_col(c))
            fks.append(_fz_fk(c, names[0]))
        if mode in ('chain', 'mix') and i > 0:
            c = f'prev_{i}_id'
            cols.append(_fz_col(c))
            fks.append(_fz_fk(c, names[i - 1]))
        if mode != 'self' and i > 1 and rnd.random() < 0.5:
            tgt = names[rnd.randrange(i)]
            c = f'{tgt[:24]}_x{i}_id'
            cols.append(_fz_col(c))
            fks.append(_fz_fk(c, tgt))
        for j in range(rnd.randint(0, 3)):
            cols.append(_fz_col(f'payload_{j}', 'text'))
        tabs[nm] = _fz_table(nm, cols, pk=['id'], fks=fks)
    return tabs


def _board_big(rnd, dense=False):
    """스키마 여럿 · 20~45 테이블 · 허브 · 사슬 · 자기참조 · 긴 이름을 한 판에.

    작은 판에서는 다섯 카운터 중 `thru` 밖에 안 움직인다 — 영역도가 하나뿐이고 선이
    붐비지 않아 라벨도 통로도 다툴 일이 없다. 실제 DB 는 스키마가 여럿이고 테이블이
    수십 개다.
    """
    n = rnd.randint(40, 70) if dense else rnd.randint(20, 45)
    schemas = ['public', 'mart', 'ref', 'ops'][:rnd.randint(1, 4)]
    names, sch = [], {}
    for i in range(n):
        base = '_'.join(rnd.sample(_WORDS, rnd.randint(2, 3)))
        if rnd.random() < 0.35:
            base += '_' + _LONG_Q
        nm = f'{base}_{i:02d}'
        names.append(nm)
        sch[nm] = rnd.choice(schemas)
    hubs = names[:max(1, n // (4 if dense else 8))]
    tabs = {}
    for i, nm in enumerate(names):
        cols, fks = [_fz_col('id')], []
        for j in range(rnd.randint(0, 4 if dense else 3)):
            c = (f'{_LONG_Q}_{j}_id' if rnd.random() < 0.4
                 else f'{rnd.choice(_WORDS)}_parent_{j}_id')
            cols.append(_fz_col(c))
            fks.append(_fz_fk(c, nm))
        for h in hubs:
            if h != nm and rnd.random() < (0.7 if dense else 0.45):
                c = f'{h[:28]}_hub_{i}_id'
                cols.append(_fz_col(c))
                fks.append(_fz_fk(c, h))
        if i > 0 and rnd.random() < 0.6:
            c = f'prev_{i}_id'
            cols.append(_fz_col(c))
            fks.append(_fz_fk(c, names[i - 1]))
        for j in range(rnd.randint(0, 4)):
            cols.append(_fz_col(f'payload_{j}', 'text'))
        tabs[nm] = _fz_table(nm, cols, pk=['id'], fks=fks, schema=sch[nm])
    return tabs


def _fuzz_one(scripts, work, tabs):
    """판 하나를 그리고 `ERD_VERIFY_LOG` 의 기록을 돌려준다."""
    work.mkdir(parents=True, exist_ok=True)
    (work / 'schema.json').write_text(json.dumps(tabs, ensure_ascii=False))
    log = work.parent / 'verify.jsonl'
    if log.exists():
        log.unlink()
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e.update({'ERD_WORK': str(work), 'ERD_PROJ': str(work), 'ERD_LANG': 'en',
              'ERD_DOCNAME': 'T', 'ERD_SVG': '0', 'ERD_VERIFY_LOG': str(log)})
    r = subprocess.run([sys.executable, '-c', _DRIVE], capture_output=True,
                       text=True, env=e, cwd=str(scripts))
    if r.returncode != 0:
        return None, (r.stdout + r.stderr)[-1500:]
    if not log.exists():
        return None, 'no verify log'
    return [json.loads(x) for x in log.read_text().splitlines() if x.strip()], None


def _fuzz(argv):
    import random
    import shutil
    import tempfile

    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    scripts = Path(opt('--scripts', str(HERE))).resolve()
    seed = int(opt('--seed', '1'))
    boards = int(opt('--boards', '20'))
    mode = opt('--mode', 'mix')
    rnd = random.Random(seed)
    tot = {k: 0 for k in COUNTERS}
    na = {k: 0 for k in COUNTERS}
    worst = {k: None for k in COUNTERS}
    hits = {k: 0 for k in COUNTERS}
    n_diag = n_board = n_die = 0
    root = Path(tempfile.mkdtemp(prefix='fuzz16-'))
    try:
        for b in range(boards):
            tabs = board(rnd, mode)
            work = root / f'b{b:03d}' / 'work'
            recs, err = _fuzz_one(scripts, work, tabs)
            n_board += 1
            if recs is None:
                n_die += 1
                print(f'  board {b} died: {err[:300]}', file=sys.stderr)
                continue
            for rec in recs:
                n_diag += 1
                for k in COUNTERS:
                    v = rec['counts'].get(k)
                    if v is None:
                        na[k] += 1
                        continue
                    tot[k] += v
                    if v:
                        hits[k] += 1
                        if worst[k] is None or v > worst[k][1]:
                            worst[k] = (rec['file'], v, b)
            shutil.rmtree(work.parent, ignore_errors=True)
    finally:
        shutil.rmtree(root, ignore_errors=True)
    print(json.dumps({'scripts': str(scripts), 'seed': seed, 'mode': mode,
                      'boards': n_board, 'diagrams': n_diag, 'died': n_die,
                      'total': tot, 'diagrams_hit': hits, 'na': na,
                      'worst': worst}))


def _board_file(argv):
    """무작위 판 하나를 schema.json 으로 떨궈 눈으로 볼 수 있게 한다."""
    import random

    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    out = Path(opt('--out', './fuzz-board')).resolve()
    out.mkdir(parents=True, exist_ok=True)
    tabs = board(random.Random(int(opt('--seed', '1'))), opt('--mode', 'mix'))
    (out / 'schema.json').write_text(json.dumps(tabs, ensure_ascii=False, indent=1))
    print(out / 'schema.json', f'({len(tabs)} tables)')


if __name__ == '__main__':
    _cmd = sys.argv[1] if len(sys.argv) > 1 else ''
    if _cmd == 'fuzz':
        _fuzz(sys.argv[2:])
    elif _cmd == 'board':
        _board_file(sys.argv[2:])
    else:
        raise SystemExit(__doc__.splitlines()[0] + '\n'
                         'usage: selftest_r14_render.py fuzz '
                         '[--scripts DIR] [--seed N] [--boards N] [--mode NAME]\n'
                         '       selftest_r14_render.py board '
                         '[--out DIR] [--seed N] [--mode NAME]\n'
                         'modes: self hub long chain mix big dense\n'
                         '(the regression cases run from selftest.py, not from here)')
