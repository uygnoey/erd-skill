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

import config
from config import SCHEMA_JSON, clean, env_flag, excluded, load_spec
from i18n import LANG, t as T
from svg_canvas import SvgCanvas


def __getattr__(name):
    """`erd.OUT` 은 **물어볼 때** 만든다 (PEP 562 모듈 __getattr__).

    `from config import OUT` 은 그 자리에서 `config` 의 지연 값을 깨워 `mkdir` 을
    돌린다. 이 모듈은 OUT 을 제 코드에서 한 번도 쓰지 않고 **다시 내보내기만**
    하는데(`build_erd.py` 의 `from erd import OUT`), 그 한 줄 때문에 `import erd`
    만으로 부르는 사람의 cwd 에 `erd-build/out` 이 생겼다. 15라운드가 세운
    '**import 는 아무것도 안 만든다**' 를 여기서도 그만큼 지킨다.

    **지키지 못하는 나머지를 여기 적어 둔다.** 이 모듈은 25번째 줄에서 곧바로
    `SCHEMA_JSON.read_text()` 를 한다 — 즉 `import erd` 는 정의상 '이 프로젝트의
    스키마를 읽는다' 는 뜻이고, 그 물음이 `erd-build/`(WORK) 를 만든다. 그것까지
    없애려면 SCHEMA·SPEC·AREAS 를 전부 지연 값으로 돌려야 하는데, 모듈 **안에서의**
    전역 이름 조회는 PEP 562 를 거치지 않으므로 이 파일의 거의 모든 함수를 함께
    고쳐야 한다. 16라운드는 그 크기의 변경을 다른 셋이 같은 워크트리를 고치는 중에
    하지 않기로 했다 — 그래서 `import erd` 는 아직 `erd-build/` 하나를 만든다.
    """
    if name == 'OUT':
        return config.OUT
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


# schema.json 은 쓰는 쪽이 전부 utf-8 로 못 박혀 있다(introspect·parse_ddl·
# merge_schemas·merge_desc). 읽기만 로케일에 맡기면 ascii 로케일(LC_ALL=C)이나
# cp949 에서 한글 코멘트 한 줄에 UnicodeDecodeError 로 죽는다 — 같은 값으로 읽는다.
# 못 읽는 schema.json 은 **이름을 대고** 멈춘다 — config.load_spec 이 spec 에 하는 것과
# 같은 대우다. 예전엔 셋 다 raw 트레이스백이었다: 옛 판이 cp949 로 써 둔 파일은
# UnicodeDecodeError(읽기를 utf-8 로 못 박은 뒤로는 로케일과 무관하게 그렇다), 손으로
# 고치다 만 파일은 JSONDecodeError, 권한이 없으면 OSError. 셋 다 `import erd` 한 줄에서
# 났으므로 사용자는 제 파일 이야기 대신 파이썬의 말을 봤다.
# 손잡이 이름은 ERD_WORK 다 — SCHEMA_JSON 은 WORK/schema.json 이고, 이 파일을 다른
# 자리에서 찾게 만들 수 있는 변수가 그것이다(config 가 OUT 을 'ERD_WORK' 로 부르는 것과
# 같은 방식). 파일 이름 자체는 사용자가 못 고른다.
try:
    _RAW = json.loads(SCHEMA_JSON.read_text(encoding='utf-8'))
except json.JSONDecodeError as e:
    raise SystemExit(T('err.spec_json', path=SCHEMA_JSON, err=e))
except (UnicodeDecodeError, OSError) as e:
    raise SystemExit(T('err.env_bad', env='ERD_WORK', value=SCHEMA_JSON, why=e))
SCHEMA = {k: v for k, v in _RAW.items() if not excluded(k)}
# 그리는 쪽의 제외는 화면에 **한 글자도** 안 나왔다 — 규칙을 밝히는 것은 introspect
# 뿐이라, 이미 뽑아 둔 schema.json 으로 문서만 다시 만드는 실행(그리고 라벨을 붙여
# 합친 schema.json)에서는 테이블이 조용히 줄었다. 실제로 걷어낸 것이 있을 때만 찍는다.
# **규칙만 찍는 것으로는 모자란다.** `excluded()` 는 점으로 앞을 벗겨 가며 묻기 때문에
# (config.excluded 의 설명) 사용자가 적은 정규식 하나가 예상보다 넓게 걸릴 수 있는데,
# 전부 사라져야만 err.no_schema_tables 로 멈추고 **일부만** 사라지면 규칙 한 줄이
# 전부였다 — 어느 테이블이 없어졌는지는 아무도 말하지 않았다. 이름을 댄다.
# 이름은 clean() 을 지나 나간다 — 키에 개행이 들어 있으면(아래에서 씻는 바로 그
# 경우다) 경고 한 줄이 여러 줄로 흩어져 목록이 목록으로 안 보인다.
# **이 줄은 문서 한 벌에 세 번 나온다.** erd 를 import 하는 프로세스마다(build_erd·
# build_html·build_docx) 한 번씩이다 — 놀랄 일이 아니라 그 셋이 저마다 제가 그린
# 것을 말하는 것이다. 한 번만 내려면 세 스크립트가 이 줄을 나눠 갖게 해야 하는데,
# 그 자리(build_erd)는 이 파일 몫이 아니다.
_DROPPED = [k for k in _RAW if k not in SCHEMA]
if _DROPPED:
    print(T('log.exclude_rule', rule=config.EXCLUDE))
    print(T('log.exclude_dropped', n=len(_DROPPED),
            list=', '.join(clean(k) or k for k in _DROPPED[:6])
                 + (' …' if len(_DROPPED) > 6 else '')))
# 제외 규칙은 spec 쪽에서만 걸러지고 있어서, 그리는 쪽은 없는 테이블을 찾다 죽었다.
# 여기서 한 번에 걷어내고, 사라진 테이블을 가리키던 FK 도 같이 떨군다.
if not SCHEMA:
    raise SystemExit(T('err.no_schema_tables', path=SCHEMA_JSON))
# 예전 판이 만든 schema.json 이나 사람이 손댄 파일에는 지금 코드가 기대하는 키가
# 없을 수 있다. 없다고 traceback 을 뱉는 대신 기본값으로 채워 그린다.
for _n, _t in SCHEMA.items():
    _t.setdefault('name', _n)
    for _k, _v in (('pk', []), ('fks', []), ('uniques', []), ('checks', []),
                   ('indexes', []), ('columns', []), ('schema', 'public'),
                   ('origin', 'existing'), ('note', ''), ('db', '')):
        _t.setdefault(_k, _v)
    _t['fks'] = [fk for fk in _t['fks'] if fk.get('ref_table') in SCHEMA]
    for _c in _t['columns']:
        _c.setdefault('added', False)
        _c.setdefault('not_null', False)
        _c.setdefault('default', '')
        _c.setdefault('type', '')
        _c['comment'] = clean(_c.get('comment'))
    _t['note'] = clean(_t.get('note'))
    # ── 이름·타입·기본값도 clean() 을 지난다 ──
    # 설명과 역할명만 씻어 왔다. 그런데 개행이 든 **테이블 이름** 하나면 PIL 이 폭을
    # 재지 못해 그리다 죽어 산출물이 0개가 되고(그림도 문서도 없다), \x1e 가 든
    # 이름은 erd 와 html 은 넘어간 뒤 build_docx 가 lxml 에서 죽어 사용자에게 반 벌만
    # 남긴다. 기본값은 아예 아무도 안 씻어서 raw \x1f 가 HTML 까지 갔다.
    # 값을 있는 그대로 실어 오는 것은 introspect 의 제 일이다 — 그것을 받고도
    # 무너지지 않는 것은 쓰는 쪽 몫이라, 소비자가 다 같이 쓰는 이 자리에서 씻는다.
    _t['name'] = clean(_t.get('name')) or _n
    for _c in _t['columns']:
        _c['name'] = clean(_c.get('name'))
        _c['type'] = clean(_c.get('type'))
        _c['default'] = clean(_c.get('default'))

# 키도 씻는다 — 상자의 제목으로 **그대로 그려지는 것이 키** 라서, 값만 씻어서는
# 개행 하나에 여전히 PIL 이 죽는다. 다만 씻은 뒤 두 키가 같아지면 테이블 하나가
# 소리 없이 사라진다. 조용히 합치느니 손대지 않는 편이 낫다 — 그때는 그대로 둔다.
_clean_key = {_k: (clean(_k) or _k) for _k in SCHEMA}
if len(set(_clean_key.values())) == len(_clean_key):
    SCHEMA = {_clean_key[_k]: _v for _k, _v in SCHEMA.items()}
    for _t in SCHEMA.values():
        for _fk in _t['fks']:
            _fk['ref_table'] = _clean_key.get(_fk['ref_table'], _fk['ref_table'])

# PNG 옆에 같은 그림을 SVG 로도 남긴다. ERD_SVG=0 이면 끈다.
SVG_OUT = env_flag('ERD_SVG', True)
# SVG 는 문서에 박아 쓰는 용도라 그림 안 제목을 뺀다 (캡션이 따로 붙는다).
SVG_TITLE = env_flag('ERD_SVG_TITLE', False)

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


def _usable(path, index=0):
    """실제로 열리는 폰트인지 본다 — 파일이 있다고 폰트인 것은 아니다."""
    try:
        ImageFont.truetype(str(path), 10, index=index)
        return True
    except Exception:
        return False


def _pick_font(env, candidates, kind):
    """(regular, bold) 를 고른다. 볼드 파일이 없으면 regular 로 대신한다."""
    reg, bold = os.environ.get(env), os.environ.get(env + '_BOLD')
    if reg:
        if not Path(reg).exists() or not _usable(reg):
            raise SystemExit(T('err.font_env', env=env, path=reg))
        # 볼드도 **같은 자로 잰다.** 예전엔 exists() 만 봐서 두 갈래로 조용히 샜다:
        # 폰트가 아닌 파일이면 한참 뒤 PIL 안에서 OSError 로 터졌고(사람 말이 아니라
        # 트레이스백이다), 없는 파일이면 아무 말 없이 regular 로 내려가 굵은 글자가
        # 통째로 사라졌다. 사람이 제 손으로 적은 설정이 빗나간 것이므로 regular 과
        # 똑같이 죽는다 — '같은 버그를 반만 고쳤다' 를 여기서 끝낸다.
        if bold and (not Path(bold).exists() or not _usable(bold)):
            raise SystemExit(T('err.font_env', env=env + '_BOLD', path=bold))
        return (reg, 0), ((bold, 0) if bold else (reg, 0))
    for r, b in candidates:
        rp, ri = _face(r)
        if not Path(rp).exists() or not _usable(rp, ri):
            continue
        bp, bi = _face(b)
        # 후보 목록의 볼드는 사람이 적은 설정이 아니라 우리가 짐작한 경로다. 그래서
        # 여기서는 죽지 않고 regular 로 내려간다 — 다만 exists() 만 보면 열리지 않는
        # 파일을 골라 놓고 PIL 이 뒤늦게 터지므로, 재는 자는 위와 같아야 한다.
        # `and _usable(bp, bi)` 를 지우면 빨강인 것을 15라운드가 붙였다:
        # `selftest_r14_render.py` 의 `errors: a bold font from the candidate list
        # is opened before it is picked`. 14라운드는 env 갈래만 시험했다.
        return (rp, ri), ((bp, bi) if Path(bp).exists() and _usable(bp, bi)
                          else (rp, ri))
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
    # ref 스키마에서 끌어온 읽기 전용 원천. readonly 만 보던 탓에 이 배지는 실제로는
    # 한 번도 나오지 않았다 — parse_ddl 은 origin='ref' 로 표시한다.
    if t.get('readonly') or t.get('origin') == 'ref':
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


# 라벨 자리를 잡을 때 글자 좌우로 두는 여백. 이 값은 **자리를 잡는 쪽과 겹침을 세는
# 쪽이 반드시 같이 써야 한다** — 한쪽만 바뀌면 세는 쪽이 글자가 아닌 것을 재게 된다.
LABEL_PAD_X = 3


def boxes_touch(a, b):
    """두 사각형이 실제로 겹치는가. 맞닿기만 한 것은 겹친 것이 아니다.

    라벨 검사 세 곳(라벨↔라벨, 라벨↔테이블, 자리잡기)이 **이 함수 하나**를 쓴다.
    예전엔 라벨↔테이블만 `<` 라 스치기만 해도 세고 라벨↔라벨은 `<=` 라 안 셌다 —
    같은 것을 재면서 반대 규칙을 쓰고 있었다.
    """
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def label_ink_box(box, font, scale):
    """자리 잡기용 사각형 → 글자가 실제로 칠하는 사각형.

    `box` 는 글자보다 사방이 넉넉하다. 좌우는 LABEL_PAD_X 만큼이고, 위아래는 높이가
    글꼴과 무관하게 고정(14·16)이라 11pt 글자의 잉크(10px 남짓)보다 넉넉하다. 겹침을
    그 사각형으로 판정하면 두 줄로 나란히 놓여 멀쩡히 읽히는 라벨이 겹쳤다고 찍힌다.

    라벨을 놓는 두 경로(보통 선의 anchor 'mm', 자기참조 루프의 'rm') 모두 상자를
    anchor y 를 중심으로 대칭으로 잡으므로, 세로 중심이 곧 글자가 놓인 anchor y 다.
    거기서 글꼴이 실제로 칠하는 위·아래 폭을 되짚는다. 표본은 어센더·디센더·밑줄을
    다 담은 'Ag_0y' 라 어떤 라벨보다 넉넉하다 — 이 사각형이 안 닿으면 글자는 확실히
    안 닿는다.

    **테두리(halo) 의 절반을 더한다.** 라벨은 `stroke_width` 만큼 배경색 테두리를
    두르고 그려진다 — 그 테두리도 칠하는 것이라, 남의 글자 위에 얹히면 글자를
    지운다. 글자 상자만 재면 3 떨어진 두 라벨이 0 으로 나오는데 실제로는 한쪽
    테두리가 다른 쪽 글자 가장자리를 파먹는다. 절반씩 더하면 두 상자가 겹치는
    것이 곧 '한쪽 테두리가 다른 쪽 **글자**에 닿는다' 와 같아진다. 온전히 더하지
    않는 이유는 테두리끼리 겹치는 것은 배경색 위 배경색이라 아무것도 안 지우기
    때문이다. 라벨↔테이블도 같은 상자로 잰다 — 두 검사가 다른 자를 쓰면 같은
    버그를 반만 고치게 된다.
    """
    asc, desc = font.getmetrics()
    gb = font.getbbox('Ag_0y')
    mid = (asc + desc) / 2               # anchor 'm' 이 놓이는 자리
    up, down = (mid - gb[1]) / scale, (gb[3] - mid) / scale
    halo = max(2, 2 * scale) / scale / 2         # 그리는 쪽 stroke_width 의 절반
    cy = (box[1] + box[3]) / 2
    return (box[0] + LABEL_PAD_X - halo, cy - up - halo,
            box[2] - LABEL_PAD_X + halo, cy + down + halo)


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
    if not rows:
        # 컬럼을 모르는 테이블 — DDL 이 참조만 하고 정의는 없을 때 이렇게 된다.
        # 제목만 있는 상자로 그린다. 예전엔 여기서 max() 가 죽어 그림이 하나도
        # 안 나왔다. 정작 parse_ddl 은 '이름만 있는 상자로 그린다' 고 안내한다.
        return stub_box(tname)
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
    bd, _ = badge(tname)
    # 제목만 있는 상자에도 배지는 그려진다. measure() 처럼 배지 폭을 더하지 않으면
    # 배지가 테이블명 위에 얹힌다 — 참조만 되고 정의가 없는 테이블에서 실제로 그랬다.
    w = max(tw(tname, f['title']) + tw(bd, f['badge']) + 24,
            tw(T('erd.ref_of', area=AREA_OF.get(tname, T('word.external')),
                  role=ROLE.get(tname, '')), f['role'])) + PAD * 2
    return {'w': int(w), 'h': HEAD_H + 2, 'rows': [], 'cols': (0, 0), 'gap': 0}


# ── 레이아웃 ─────────────────────────────────────────────────────────────────
def layout_area(tnames, with_desc=True, max_cols=None, hgap=210, vgap=95):
    """영역 하나를 배치한다. max_cols 를 주지 않으면 테이블 수에 맞춰 정한다.

    2열로 고정하면 테이블이 많은 영역이 세로로 한없이 길어져(60개면 30행) 문서에
    넣을 수 없는 그림이 된다.
    """
    boxes = {n: measure(n, with_desc) for n in tnames}
    if max_cols is None:
        max_cols = 1 if len(tnames) <= 2 else min(8, max(2, round(len(tnames) ** 0.5)))
    order = sorted(tnames, key=lambda n: -boxes[n]['h'])
    cols = [[] for _ in range(max(1, min(max_cols, len(tnames))))]
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
    # 한 영역을 한 열에 다 쌓으면 테이블이 많을 때 그림이 세로로만 길어진다.
    # 가장 큰 영역을 기준으로 한 열에 담을 행 수를 정하고, 넘치면 옆으로 접는다.
    biggest = max((len(a[3]) for a in AREAS), default=1)
    per_col = max(12, int(biggest ** 0.5 * 1.6)) if biggest > 16 else biggest
    for code, _name, _schema, tables in AREAS:
        w = int(max(max(tw(n, f['title']) for n in tables),
                    max(tw(ROLE.get(n, ''), f['role']) for n in tables)) + PAD * 2 + 50)
        y, col_n, x0 = 0, 0, x
        for n in tables:
            if col_n and col_n % per_col == 0:       # 다음 서브열로 접는다
                x += w + hgap
                y = 0
            boxes[n] = {'w': w, 'h': h, 'rows': [], 'cols': (0, 0), 'gap': 0}
            pos[n] = (x, y)
            y += h + vgap
            col_n += 1
        groups.append((code, tables))
        x += w + hgap
    return pos, boxes, groups


def layout_global(hgap=230, vgap=100, area_gap=150, want_cols=None):
    """전체 상세 레이아웃 — 열 높이가 고르도록 영역을 열에 묶는다.

    영역(=그룹 박스) 단위는 쪼개지 않는다. 작은 영역은 한 열에 세로로 이어 쌓고,
    목표 높이를 넘는 큰 영역만 내부에서 서브열로 나눈다.
    """
    boxes = {n: measure(n, with_desc=True) for a in AREAS for n in a[3]}
    area_h = {a[0]: sum(boxes[n]['h'] + vgap for n in a[3]) for a in AREAS}
    total = sum(area_h.values())
    if want_cols is None:
        # 열 수를 4로 고정해 두면 테이블이 아주 많을 때 다시 세로로 길어진다.
        # 한 열의 높이가 전체 폭의 1.6배쯤 되도록 열 수를 잡는다.
        avg_w = sum(b['w'] for b in boxes.values()) / max(1, len(boxes))
        want_cols = int(max(4, min(8, round((total / (1.6 * (avg_w + hgap))) ** 0.5))))
    # 목표 높이를 가장 큰 영역에 맞추면, 영역이 하나뿐일 때 그 영역이 통째로 한 열이
    # 되어 그림이 세로로 한없이 길어진다(이름 규칙 없는 DB 에서 실제로 그렇게 된다).
    # 큰 영역은 아래에서 서브열로 나누므로 목표는 전체를 열 수로 나눈 값으로 잡는다.
    target = max(total / max(want_cols, 1), 900)

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
        y, col_w = 0, 0
        for code in col:
            ts = tables_of[code]
            # 영역 하나가 목표 높이를 크게 넘으면 그 안에서 서브열로 나눈다.
            # 그룹 박스는 노드 범위를 감싸므로 나뉜 서브열까지 함께 묶인다.
            n_sub = max(1, min(8, round(area_h[code] / target))) if area_h[code] > target * 1.4 else 1
            if n_sub > 1:
                per, subs, cur, cur_h = area_h[code] / n_sub, [], [], 0
                for n in ts:
                    if cur and cur_h + boxes[n]['h'] + vgap > per:
                        subs.append(cur)
                        cur, cur_h = [], 0
                    cur.append(n)
                    cur_h += boxes[n]['h'] + vgap
                if cur:
                    subs.append(cur)
            else:
                subs = [list(ts)]

            sub_x, top_y, tallest = x, y, 0
            for sc in subs:
                yy = top_y
                for n in sc:
                    pos[n] = (sub_x, yy)
                    yy += boxes[n]['h'] + vgap
                tallest = max(tallest, yy - top_y)
                sub_x += max(boxes[n]['w'] for n in sc) + hgap
            col_w = max(col_w, sub_x - x - hgap)
            y = top_y + tallest + area_gap
            groups.append((code, ts))
        x += col_w + hgap
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
    """범례. 폭을 넘으면 줄을 바꾼다. (사용한 높이, 필요한 최소 폭) 을 논리 px 로 반환.

    필요 폭까지 돌려주는 이유: 캔버스 측정이 **레이어 라벨** 만 재던 때, 그 아래
    고정 줄(`extended  existing table · columns…`, `── foreign key (FK) · …`)은 아무도
    재지 않았다. 줄바꿈은 한 줄에 안 들어가는 항목을 다음 줄로 보낼 뿐 항목 자체를
    줄이지 못하므로, 그림이 좁으면 그 줄이 오른쪽으로 잘려 나갔다 — 특별한 입력이
    아니라 테이블 두 개짜리 평범한 스키마에서 en·ko 둘 다 잘렸다.
    """
    LH, GAP = 27, 30
    cx, cy = x, y
    rows = 1
    need = 0

    def nl(w):
        """다음 항목 폭이 남은 폭을 넘으면 줄바꿈"""
        nonlocal cx, cy, rows, need
        # 항목이 홀로 한 줄을 차지해도 들어가야 하는 폭 (줄바꿈 뒤 시작점 x+74 기준).
        # GAP 은 다음 항목과의 간격이라 잉크가 아니다.
        need = max(need, 74 + w - GAP)
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
    return (cy - y) + LH, need


VERIFY_LOG = os.environ.get('ERD_VERIFY_LOG', '')
_LOG_STARTED = False        # 이 판에서 한 줄이라도 썼는가 (첫 줄에서 파일을 비운다)


def verify_log(path, checks, tolerate):
    """검증 결과를 기계가 읽을 자리에 한 벌 더 남긴다 (ERD_VERIFY_LOG=경로, JSONL).

    사람이 읽는 줄은 사람 좋으라고 서식이 바뀐다 — 실제로 (허용)·[경고] 꼬리가
    붙자, 그 줄에서 숫자를 긁던 회귀 시험이 **마지막 항목만** 놓쳤다. 하필 그
    항목이 0 이 아닐 때만 놓치니 시험은 늘 통과했다. 서식이 아니라 값을 보게 한다.

    기본값은 꺼짐이라 사용자 출력은 한 글자도 달라지지 않는다.

    한 판에 그리는 그림이 여럿이라 이어 쓰지만, **판이 바뀌면 처음부터 쓴다** —
    이어 붙이기만 하면 두 번 돌린 뒤 6줄이 남아, 읽는 쪽이 어느 3줄이 이번 것인지
    알 수 없다. 첫 기록에서 한 번만 비운다.

    쓰지 못해도 그림은 이미 저장돼 있다. 계측을 못 남긴 것은 말해 주되, 그것 때문에
    산출물을 없던 일로 만들지는 않는다.
    """
    global _LOG_STARTED
    if not VERIFY_LOG:
        return
    rec = {'file': Path(path).name,
           'counts': dict(checks),                    # 재지 않은 항목은 null
           'tolerated': [k for k, v in checks if v and k in tolerate],
           'warn': [k for k, v in checks if v and k not in tolerate]}
    try:
        with open(VERIFY_LOG, 'w' if not _LOG_STARTED else 'a', encoding='utf-8') as fp:
            fp.write(json.dumps(rec, ensure_ascii=False) + '\n')
        _LOG_STARTED = True
    except OSError as e:
        print(T('log.verify_log_fail', path=VERIFY_LOG, err=e))


def draw_erd(path, tnames, pos, boxes, title, subtitle='', with_desc=True, scale=2,
             stubs=(), legend=False, edge_labels=True, groups=(), derives=False,
             tolerate=()):
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

        INF = float('inf')

        def slot(base, used, pitch, limit=64, lo=None, hi=None, span=None):
            """base 근처에서 이미 쓰인 좌표를 피해 좌우(상하) 번갈아 자리를 잡는다.

            lo·hi 는 넘어서면 안 되는 경계다 — 통로 밖은 테이블 속이다. 예전엔 경계가
            없어서 통로에 들어갈 선이 많으면 남는 선이 테이블을 뚫고 지나갔다. 선은
            노드보다 먼저 그리므로 그 관통은 노드에 덮여 눈에 보이지도 않았다.

            span 은 이 선이 **반대 축으로 차지하는 구간**이다 (세로선이면 y 범위).
            두 세로선은 x 가 가까워도 y 가 안 겹치면 겹쳐 보이지 않는다 — 검증이
            세는 규칙도 그렇다. 그런데 자리를 나눠 주는 쪽은 x 만 보고 통로 한 칸을
            통째로 잡아, 서로 만날 일이 없는 선끼리 자리를 다퉜다. 통로가 그렇게
            꽉 차면 위 fallback 이 남의 선 **위에** 얹는다. span 을 모르는 자리는
            예전대로 (-∞, ∞) 로 두어 보수적으로 잡는다.
            """
            a0, a1 = span or (-INF, INF)

            def far(v):
                return all(abs(v - u) >= pitch - 1 or ub <= a0 or ua >= a1
                           for u, ua, ub in used)

            for k in range(1, 2 * limit + 2):
                off = (k // 2) * pitch * (1 if k % 2 else -1)
                v = base + off
                if lo is not None and not (lo <= v <= hi):
                    continue
                if far(v):
                    used.append((v, a0, a1))
                    return v
            if lo is not None and hi > lo:
                # 통로가 꽉 찼다. 선끼리 붙는 편이 테이블을 뚫는 것보다 낫다 —
                # 경계 안에서 이미 쓴 자리들과 가장 멀리 떨어진 곳을 고른다.
                best, bestd = (lo + hi) / 2, -1.0
                for i in range(1, 128):
                    c = lo + (hi - lo) * i / 128
                    dmin = min((abs(c - u) for u, ua, ub in used
                                if not (ub <= a0 or ua >= a1)), default=1e9)
                    if dmin > bestd:
                        best, bestd = c, dmin
                used.append((best, a0, a1))
                return best
            v = max((u for u, _a, _b in used), default=base) + pitch
            used.append((v, a0, a1))
            return v

        def gutter_bounds(i):
            """세로 통로가 쓸 수 있는 x 범위. 바깥 통로는 넓게 열어 둔다."""
            if i < 0:
                return columns[0]['x1'] - 420, columns[0]['x1'] - 10
            if i >= len(columns) - 1:
                return columns[-1]['x2'] + 10, columns[-1]['x2'] + 420
            return columns[i]['x2'] + 10, columns[i + 1]['x1'] - 10

        def free_y(ci, prefer):
            """열 ci 의 노드 사이 빈 구간 중 prefer 에 가장 가까운 것 → (중심, lo, hi)

            경계까지 돌려주는 이유는, 그 구간에 선이 여럿 지날 때 구간 밖으로 밀려나면
            바로 위아래 테이블을 관통하기 때문이다.
            """
            spans = columns[ci]['spans']
            cands = [(spans[0][0] - 36, spans[0][0] - 420, spans[0][0] - 10),
                     (spans[-1][1] + 36, spans[-1][1] + 10, spans[-1][1] + 420)]
            for a, b in zip(spans, spans[1:]):
                if b[0] - a[1] >= 28:
                    cands.append(((a[1] + b[0]) / 2, a[1] + 7, b[0] - 7))
            return min(cands, key=lambda c: abs(c[0] - prefer))

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
            # 여기서는 **노드별로만** 자리를 나눈다. 이 자리에 `used + exit_all` 로
            # 다른 노드의 진출입 y 까지 피해 보려던 줄이 `if False` 가 붙은 채 남아
            # 있었다 — 조건이 상수라 언제나 `used` 였으니 하는 일이 없었고, 되살릴
            # 수도 없는 모양이었다: `used + exit_all` 은 **새 리스트**라 아래
            # `used.append(v)` 가 그 임시 리스트에 적힌다. 이 노드가 쓴 y 가 기록되지
            # 않아 다음 선이 같은 y 를 도로 고른다 — 분산이 통째로 꺼진다.
            # 되살릴 값어치도 크지 않다. 노드마다 x 가 다르니 y 가 같다고 선이 겹치는
            # 것이 아니고, 선끼리 겹치는 것은 통로 쪽(slot·used_hy)이 맡는다.
            used = exit_used.setdefault(n, [])
            for k in range(1, 14):
                v = cy + (k // 2) * 13 * (1 if k % 2 else -1)
                if y1 + 7 <= v <= y2 - 7 and all(abs(v - u) >= 12 for u in used):
                    used.append(v)
                    return v
            used.append(cy)
            return cy

        def entry_ys(a, b, ca=None, cb=None):
            """이 관계가 드나들 y(컬럼 행)를 미리 잡고 등록한다.

            예전엔 route() 안에서 잡았다. 그러면 먼저 계산된 경로의 통로 lane 은
            **아직 태어나지 않은** 진출입 y 를 피할 수 없다 — 나중 경로의 꼬리가
            앞 경로의 통로선 위에 얹혔고, 그게 평범한 스키마에서 가로선 중첩 1~2 가
            남던 이유다. 그래서 y 부터 전부 잡아 두고 경로는 그 다음에 만든다.
            """
            ya, yb = col_y(a, ca), col_y(b, cb)
            # 진출입 꼬리의 x 범위는 경로를 만들기 전이라 아직 모른다 — 보수적으로 둔다
            used_hy.extend(((ya, -INF, INF), (yb, -INF, INF)))
            return ya, yb

        def route(a, b, ys):
            """노드를 관통하지 않는 직교 경로.

            세로 이동은 열 사이 통로에서만, 열을 건너뛸 때는 그 열의 노드 사이
            빈 구간을 따라 수평으로 지난다. ys 는 entry_ys() 가 미리 잡아 둔 진출입 y.
            """
            ia, ib = col_of[a], col_of[b]
            ya, yb = ys
            ax1, _t1, ax2, _t2 = rect(a)
            bx1, _t3, bx2, _t4 = rect(b)
            if ia == ib:                                  # 같은 열 — 왼쪽 통로로 우회
                lo, hi = gutter_bounds(ia - 1)
                gx = slot(gutter_x(ia - 1), used_vx, 14, lo=lo, hi=hi,
                          span=(min(ya, yb), max(ya, yb)))
                pts = [(ax1, ya), (gx, ya), (gx, yb), (bx1, yb)]
            else:
                right = ib > ia
                step = 1 if right else -1
                gidx = [(i if right else i - 1) for i in range(ia, ib, step)]
                mids = list(range(ia + step, ib, step))
                pts = [(ax2 if right else ax1, ya)]
                y = ya
                for k, gi in enumerate(gidx):
                    lo, hi = gutter_bounds(gi)
                    # 이 통로에서 세로로 얼마나 내려가는지 **먼저** 알아야 자리를
                    # 나눌 때 y 를 볼 수 있다. 중간 열로 건널 때는 그 열의 빈 구간
                    # 안에서 정해지므로 구간째로 잡아 둔다 (아직 어디일지는 모른다).
                    if k < len(mids):
                        yc, ylo, yhi = free_y(mids[k], yb)
                        span = (min(y, ylo), max(y, yhi))
                    else:
                        span = (min(y, yb), max(y, yb))
                    gx = slot(gutter_x(gi), used_vx, 14, lo=lo, hi=hi, span=span)
                    pts.append((gx, y))
                    if k < len(mids):                     # 중간 열은 노드 사이로 건넌다
                        # 이 가로 구간은 지금 통로에서 **다음** 통로까지만 간다.
                        # 다음 통로의 x 는 아직 안 정했지만 그 통로가 쓸 수 있는
                        # 범위는 안다 — 넉넉하게 그 범위까지로 잡는다. 넓게 잡는
                        # 쪽이 안전하다: 좁게 잡으면 안 겹친다고 잘못 볼 수 있다.
                        nlo, nhi = gutter_bounds(gidx[k + 1])
                        yp = slot(yc, used_hy, 13, lo=ylo, hi=yhi,
                                  span=(min(gx, nlo), max(gx, nhi)))
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
            placed_ink = []          # placed 와 나란히 — 겹침 판정은 잉크로 한다

            def on_a_table(cand):
                """이 자리가 테이블을 건드리는가 — **검증이 세는 것과 같은 자로.**

                예전엔 자리 잡기용 여백 상자로 봤다. 그런데 그 상자는 높이가 14 로
                고정이라 글꼴 잉크(위 4.25·아래 6.25)에 테두리를 더한 것보다 아래쪽이
                **좁다**. 그래서 여백 상자로는 노드에 안 닿는데 실제로 칠하는 것은
                닿는 자리가 생겼고, 자리잡기가 통과시킨 것을 검증이 `라벨↔테이블 1`
                로 잡았다 — 둘이 다른 상자를 보고 있었던 것이다.
                """
                a = label_ink_box(cand, f['edge'], S)
                return any(boxes_touch(a, o) for o in node_rects)

            def clashes(cand):
                """다른 라벨과 겹치는가 — **검증이 세는 것과 같은 자로** 잰다.

                자리를 잡는 쪽이 여백 상자로 보고 검증이 잉크로 보면, 검증이 통과시킬
                자리를 자리잡기가 거부한다. 그러면 멀쩡한 후보를 버리고 여백으로
                밀려나는 라벨이 생긴다 — 둘이 같은 자를 써야 한다.
                """
                a = label_ink_box(cand, f['edge'], S)
                return any(boxes_touch(a, b) for b in placed_ink)

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
                            yield (cx - bw / 2 - LABEL_PAD_X, p[1] + dy - 7,
                                   cx + bw / 2 + LABEL_PAD_X, p[1] + dy + 7)

                def v_cands(p, q):
                    """수직 구간 — 통로 안, 선 좌우로."""
                    y0, y1_ = min(p[1], q[1]), max(p[1], q[1])
                    for frac in (0.3, 0.5, 0.7, 0.15, 0.85):
                        cy = y0 + (y1_ - y0) * frac
                        if cy - 7 < y0 or cy + 7 > y1_:
                            continue
                        for dx in (-8 - bw / 2, 8 + bw / 2):
                            yield (p[0] + dx - bw / 2 - LABEL_PAD_X, cy - 7,
                                   p[0] + dx + bw / 2 + LABEL_PAD_X, cy + 7)

                v_segs_own = [(p, q) for p, q in zip(pts, pts[1:]) if abs(p[0] - q[0]) < 0.5]

                # 테이블과 겹치는 자리는 후보에서 제외한다 (강제 조건).
                box = None
                fallback = None
                for gen, args in ([(h_cands, s) for s in segs]
                                  + [(v_cands, s) for s in v_segs_own]):
                    for cand in gen(*args):
                        if on_a_table(cand):
                            continue
                        if not clashes(cand):
                            box = cand
                            break
                        if fallback is None:
                            fallback = cand
                    if box:
                        break
                if box is None:
                    # 전부 막히면 노드 위쪽 여백으로. **한 줄에 몰아 놓지 않는다** —
                    # 예전엔 자리가 하나뿐이라 밀려난 라벨들이 같은 높이에 나란히
                    # 쌓였고, 긴 컬럼명이 여럿이면 그대로 서로를 덮었다(`라벨↔라벨`
                    # 이 남던 자리다). 여백은 노드 위라 얼마든지 넓힐 수 있으니
                    # 줄을 늘리고 좌우로도 비켜 가며 빈자리를 찾는다.
                    #
                    # **이 두 갈래도 `on_a_table()` 을 지난다.** 예전엔 `clashes()`
                    # 만 보았고, 그러고도 `라벨↔테이블` 이 0 이었던 것은 검사 덕이
                    # 아니라 `ymax` 가 **모든** 테이블 top 의 최소라는 암묵 기하
                    # 때문이었다 — 여백은 늘 그 위였다. 그러면 이 자리의 y 를 한 줄
                    # 고치는 사람은 아무 경고 없이 라벨을 테이블 속에 넣게 된다.
                    # 근거를 기하에 두지 않고 **검사에 둔다.** (오늘 이 검사가
                    # 거르는 자리는 없다. 그래서 이 줄들은 그림을 바꾸지 않는다 —
                    # 바뀌는 것은 다음 사람이 y 를 옮겼을 때다.)
                    p, q = segs[0]
                    cx = (p[0] + q[0]) / 2
                    ymax = min((r[1] for r in node_rects), default=top)
                    for row in range(40):
                        for sx in (0, bw + 14, -(bw + 14), 2 * bw + 28, -2 * bw - 28):
                            cand = (cx + sx - bw / 2 - LABEL_PAD_X, ymax - 22 - row * 19,
                                    cx + sx + bw / 2 + LABEL_PAD_X, ymax - 8 - row * 19)
                            if not on_a_table(cand) and not clashes(cand):
                                box = cand
                                break
                        if box:
                            break
                    # 그래도 없으면 겹치더라도 제 선 곁에 둔다 (여백 끝까지 찼다는 뜻).
                    # `fallback` 은 위 후보 반복문이 `on_a_table()` 을 통과시킨 뒤에만
                    # 담아 둔 자리라 테이블을 안 건드린다. 마지막 리터럴 상자에는 그
                    # 보장이 없으므로 여기서 직접 확인하고, 닿으면 닿지 않을 때까지
                    # 위로 올린다. **끝난다**: 한 번에 19 씩 올라가고 잉크 상자 높이는
                    # 유한하며 어떤 테이블 top 도 ymax 아래로 내려가지 않으므로,
                    # 잉크 아래끝이 ymax 위로 올라오는 순간 반복이 멎는다.
                    if box is None and fallback is None:
                        box = (cx - bw / 2 - LABEL_PAD_X, ymax - 22,
                               cx + bw / 2 + LABEL_PAD_X, ymax - 8)
                        while on_a_table(box):
                            box = (box[0], box[1] - 19, box[2], box[3] - 19)
                    box = box or fallback
                placed.append(box)
                placed_ink.append(label_ink_box(box, f['edge'], S))
                # 배경 사각형으로 덮으면 그 아래를 지나던 다른 선이 끊겨 보인다.
                # 글자 둘레만 배경색으로 두르면 선은 이어진 채로 글자도 읽힌다.
                d.text(((box[0] + box[2]) / 2 * S, (box[1] + box[3]) / 2 * S), text,
                       font=f['edge'], fill=LABEL_TXT, anchor='mm',
                       stroke_width=max(2, 2 * S), stroke_fill=BG)

        # ── 경로를 먼저 모두 계산한다 (교차 hop 을 그리기 위해) ──
        # 마지막 칸(pinned)은 '이 경로의 첫·끝 가로 구간의 y 를 라우터가 고른 것이
        # 아니다' 는 표시다. route() 의 양 끝은 col_y() 가 준 **컬럼 행**에 못박혀
        # 있다 — 문서가 못박은 불변식이라 라우터가 옮길 수 없다. 검증에서 이 둘을
        # 구분하지 않으면, 라우터가 어쩔 수 없는 겹침까지 회귀로 몰린다.
        edges = []          # (pts, color, label, dashed, pinned)
        inside = set(tnames)
        self_loops = []
        pending = []        # (a, b, color, label, dashed, 진출입 y) — 경로는 나중에

        if derives:
            for src, dst, label in DERIVES:
                if src in inside and dst in inside:
                    pending.append((src, dst, '#B0885A', label, True,
                                    entry_ys(src, dst)))

        for tname in tnames:
            if tname in stubs:
                continue
            for fk in SCHEMA[tname]['fks']:
                ref = fk['ref_table']
                color = EDGE          # 선은 FK(실선)·ETL(점선) 두 종류만 쓴다
                lbl = f"{fk['column']}: {fk['ref_column']}"
                if ref == tname:
                    continue                              # 자기참조는 아래에서 처리한다
                if ref not in inside:
                    continue
                pending.append((tname, ref, color, lbl, False,
                                entry_ys(tname, ref, fk['column'], fk['ref_column'])))

        # ── 자기참조 루프 ──
        # 진출입 y 가 다 모인 **뒤에**, 통로 lane 을 고르기 **전에** 자리잡는다.
        #
        # 예전엔 이 블록이 entry_ys() 보다 먼저 돌았다. 두 단계로 나눈 것(y 를 다 잡고
        # 나서 경로를 만든다)을 통로 lane 에만 적용하고 루프에는 적용하지 않은 자리다.
        # 그래서 팔 높이 cy±dy 는 **아직 태어나지 않은** 진출입 y 를 피할 수 없었고,
        # 팔은 used_vx 에만 등록되고 used_hy 에는 안 들어가 뒤에 잡히는 통로 lane 도
        # 팔을 피하지 못했다. 자기참조가 든 평범한 스키마에서 가로선 중첩 [경고] 가
        # 났고, 그것은 세는 실수가 아니라 실제로 겹쳐 그린 선이었다 (팔과 다른 선의
        # 꼬리가 1px 차이로 50px 넘게 나란히 달렸다). [경고] 가 흔해지면 회귀 신호가
        # 아니라 소음이 되므로 그림보다 이쪽이 더 아프다.
        all_rects = [(m, rect(m)) for m in tnames]   # 루프 자리 재기용 — 한 번만 만든다

        def loop_room(self_n, ylo, yhi):
            """루프가 테이블을 건드리지 않고 쓸 수 있는 x 구간 — (왼쪽 끝, 오른쪽 끝).

            루프는 세 구간(가로 둘·세로 하나)이 전부 ylo..yhi 띠 안에 있다. 그러니
            그 띠와 세로로 겹치는 다른 테이블의 가장자리를 넘어가면 안 된다 —
            넘어가면 팔이 그 테이블을 관통한다. slot() 은 **다른 선**만 피하지
            테이블은 안 피하고, 테이블을 피하는 장치(gutter_bounds)는 통로 전용이라
            루프에는 쓰이지 않았다. 그래서 여기서 루프 몫으로 한 번 더 잰다.
            """
            sx1, _sy1, sx2, _sy2 = rect(self_n)
            left, right = sx1 - 600, sx2 + 600     # 바깥은 넉넉히, 그래도 유한하게
            for m, (ox1, oy1, ox2, oy2) in all_rects:
                if m == self_n:
                    continue
                if oy2 <= ylo or oy1 >= yhi:       # 세로로 안 겹치면 팔이 지날 일 없다
                    continue
                # 갈래는 셋이다. 예전엔 앞의 둘만 보고 **x 구간이 원본과 걸치는**
                # 셋째를 통째로 지나쳤다 — 같은 열의 더 넓은 테이블이 딱 그 모양이라
                # (ox1 == sx1, ox2 > sx2), 오른쪽 방이 끝까지 열린 것으로 계산됐고
                # 팔이 그 테이블 한가운데 심겼다. 걸치는 테이블은 그쪽 방을
                # **없앤다** — 팔은 sx1 에서 왼쪽으로 / sx2 에서 오른쪽으로만 뻗으므로,
                # 그 방향으로 삐져나온 테이블은 어디에 놓아도 지난다. 원본의 x 구간
                # 안에 온전히 들어앉은 테이블은 어느 쪽도 막지 않는다 — 팔이 그
                # 구간 안으로는 들어가지 않는다.
                if ox2 <= sx1:                     # 완전히 왼쪽
                    left = max(left, ox2 + 10)
                elif ox1 < sx1:                    # 왼쪽 가장자리를 물고 있다
                    left = max(left, sx1)
                if ox1 >= sx2:                     # 완전히 오른쪽
                    right = min(right, ox1 - 10)
                elif ox2 > sx2:                    # 오른쪽 가장자리를 물고 있다
                    right = min(right, sx2)
            return left, right

        for tname in tnames:
            if tname in stubs:
                continue
            for fk in SCHEMA[tname]['fks']:
                if fk['ref_table'] != tname:
                    continue
                k = sum(1 for lp in self_loops if lp[3] == tname)
                x1, y1, x2, y2 = rect(tname)
                cy = (y1 + y2) / 2
                dy0 = 16 + k * 24
                # 팔은 제 라벨을 담을 만큼 길어야 한다. 짧으면 라벨이 놓일 자리가
                # 노드 위밖에 안 남아 flush_labels() 가 그림 밖 여백으로 밀어낸다.
                need = tw(fk['column'], f['edge']) / S + 16 if edge_labels else 40
                want = max(30 + k * 22, min(need, 320))

                # 높이와 좌우를 **함께** 고른다. 높이를 먼저 못박으면 그 띠에서
                # 남는 폭이 얼마든 그대로 써야 한다.
                #
                # 방(room)은 dy 가 자랄수록 **줄기만 한다.** loop_room 의 경계는 띠와
                # 세로로 겹치는 테이블에서만 나오고, 띠는 dy 를 키울수록 넓어지기만
                # 하므로 걸리는 테이블이 늘 뿐 줄지 않는다. 그러니 위로 올라가다
                # 방이 없어지면 더 올라가 봐야 소용이 없고, 좁히는 수밖에 없다.
                # 예전엔 방이 음수여도 그대로 채택하고 아래 lo/hi 에서 억지로 벌려
                # 팔을 남의 테이블 속에 심었다.
                def room_at(cand):
                    lft, rgt = loop_room(tname, cy - cand, cy + cand)
                    room_l, room_r = x1 - 12 - lft, rgt - (x2 + 12)
                    side, room = (('L', room_l) if room_l >= min(want, room_r)
                                  else ('R', room_r))
                    return (cand, side, room, lft, rgt)

                def clear_at(cand):
                    return min((min(abs(cy - cand - u), abs(cy + cand - u))
                                for u, _ua, _ub in used_hy), default=1e9)

                best, spare = None, None
                for step in range(40):
                    entry = room_at(dy0 + step * 13)
                    if entry[2] < 1:
                        break        # 여기서 방이 없으면 더 넓은 띠에도 없다
                    clear = clear_at(entry[0])
                    if clear < 12:
                        # 이 높이는 다른 가로선과 겹친다. 그래도 **가장 덜 겹치는**
                        # 것을 하나 챙겨 둔다 — 예전엔 전부 버리고 처음 높이로
                        # 돌아갔고, 자기참조가 셋 넘게 붙으면 그 처음 높이가 남의
                        # 선 위였다.
                        if spare is None or clear > spare[0]:
                            spare = (clear, entry)
                        continue
                    if best is None or entry[2] > best[2]:
                        best = entry
                    if entry[2] >= want:
                        break
                if best is None and spare is None:
                    # dy0 에서 이미 방이 없다 = 위로는 전부 없다. 띠를 **좁혀** 본다.
                    #
                    # 이 반복문은 **살아 있다.** dy0 = 16 + k·24 이므로 k>=1 이면
                    # range(27, 11, -13) = [27, 14] 이고, 시험 한 벌에서 본문이 44번
                    # 돈다. 14라운드는 "dy0=16 이면 빈 range 라 한 번도 안 돈다" 고
                    # 적었는데 그것은 k=0 일 때만 참이다. 그러면서도 통째로
                    # `for cand in []:` 로 죽여도 시험은 전부 초록이었다 — 지키는
                    # 케이스가 없었다는 뜻이다. 지금은 있다:
                    # `selftest_r14_render.py` 의 `render: a self-reference arm with
                    # no room in its own band narrows the band`.
                    for cand in range(int(dy0) - 13, 11, -13):
                        entry = room_at(cand)
                        if entry[2] < 1:
                            continue
                        clear = clear_at(cand)
                        # 좁히기는 **가장 덜 겹치는 후보**를 고른다. 예전엔 그 위에
                        # `if clear >= 12: best = entry; break` 한 갈래가 더 있었다.
                        # 그 갈래는 **도달할 수 없었다** — 15라운드가 실코드 계측으로
                        # (자기참조 2~20개 × gap 12~60, 이 자리 진입 5322회, 방 있는
                        # 후보 8181개, 최대 clear = 11.000, 발동 0회) 확인했고, 16라운드가
                        # 같은 판을 다시 돌렸다(247판, 진입 **13,299회**, 최대 clear
                        # **11.000**, 발동 **0회**). 산수도 같은 말을 한다: 첫 팔은 dy=16 에
                        # 앉고 후보는 dy0-13m 이며 dy0 은 24 씩 뛰므로 후보와 앞 팔의
                        # 거리는 12 를 못 넘고, `used_hy` 에는 가로선도 들어 있어 실제
                        # 최소는 늘 더 작다. 반증할 수 없는 갈래를 '언젠가 되살아날지
                        # 모른다' 는 이유로 남겨 두면 다음 라운드가 또 같은 자리를
                        # 붙들게 되므로 지웠다 [없앰]. 지워도 뜻은 그대로다 — 후보가
                        # 셋뿐인 반복문에서 '문턱을 넘으면 즉시 채택' 과 '전부 보고
                        # 최선을 채택' 은 문턱을 넘는 후보가 없으면 같은 답이고,
                        # 넘는 후보가 생기면 뒤엣것이 더 나은 답을 준다.
                        if spare is None or clear > spare[0]:
                            spare = (clear, entry)
                if best is None:
                    # 어느 높이에도 방이 없다. 그때만 테이블에 바짝 붙인다(12px).
                    # 옛 코드는 이 자리에 600px 창을 열어 두어, 방이 없을 때마다
                    # 팔이 남의 테이블 한가운데 앉았다.
                    best = spare[1] if spare else (dy0, room_at(dy0)[1], 0,
                                                   x1 - 13, x2 + 13)
                dy, side, room, lft, rgt = best

                # 어느 쪽으로 나갈지는 넓이만으로 못 고른다. 넓어도 그 통로가 이미
                # 꽉 찼으면 slot() 이 남의 선 위에 얹는다(그쪽이 테이블을 뚫는 것보다
                # 낫다는 판단이라 그렇게 만들어져 있다). 테이블 하나에 통로가 둘
                # 있는데 한쪽만 보고 포기할 이유가 없으므로, **비어 있는 차선이
                # 있는 쪽**을 먼저 고른다.
                def clean_lane(base, lo, hi):
                    """slot() 이 깨끗이 잡을 자리가 있는가 — 등록하지 않고 본다."""
                    if hi <= lo:
                        return None
                    for step in range(1, 130):
                        off = (step // 2) * 14 * (1 if step % 2 else -1)
                        v = base + off
                        if lo <= v <= hi and all(
                                abs(v - u) >= 13 or ub <= cy - dy or ua >= cy + dy
                                for u, ua, ub in used_vx):
                            return v
                    return None

                # 경계는 loop_room 이 준 그대로 쓴다. 예전엔 min(…, x1-13) ·
                # max(…, x2+13) 로 **한 칸을 억지로 만들어**, 방이 없는 쪽에도 차선이
                # 있는 것처럼 보이게 했다 — 그 한 칸이 곧 남의 테이블 속이다.
                lo_l, hi_l = max(lft, x1 - 600), x1 - 12
                lo_r, hi_r = x2 + 12, min(rgt, x2 + 600)
                free_l = clean_lane(x1 - max(min(want, hi_l - lo_l), 12), lo_l, hi_l)
                free_r = clean_lane(x2 + max(min(want, hi_r - lo_r), 12), lo_r, hi_r)
                if side == 'L' and free_l is None and free_r is not None:
                    side, room = 'R', hi_r - lo_r
                elif side == 'R' and free_r is None and free_l is not None:
                    side, room = 'L', hi_l - lo_l
                arm = max(min(want, room), 12)
                # 세로 팔도 자리를 **잡아서** 쓴다. 예전엔 x1-dx 를 그냥 등록만 해
                # 뒤에 오는 통로만 피하게 했는데, 그러면 이미 그 자리를 쓰고 있는
                # 선과는 겹친다 — 팔이 길어질수록 더 그렇다.
                #
                # `hi > lo` 를 반드시 지킨다. 같거나 뒤집히면 slot() 이 경계를 통째로
                # 버리고(`max(used) + pitch`) 아무 데나 자리를 잡는데, 그 '아무 데나'
                # 가 남의 테이블 속이다. 벌리는 방향이 중요하다: 예전엔 방이 없는
                # 쪽으로 **바깥으로** 600px 벌려 팔을 이웃 테이블에 심었고, 여기서는
                # 제 테이블에 바짝 붙는 쪽으로만 벌린다 — 12px 는 어느 이웃도 들어올
                # 수 없는 자기 몫이다.
                #
                # 15라운드까지 이 자리는 `if hi - lo < 1:` 한 갈래였다. 그 갈래는
                # selftest 184 프로세스 + 퍼저 120 프로세스에서 **한 번도 실행되지
                # 않았고**, 16라운드가 15라운드 코드에 계수기를 박아 다시 쟀을 때도
                # 그랬다 — 퍼저(mix·big 4씨앗 × 60판) + 자기참조 판 247개에서 이 줄에
                # **106,317번** 닿는 동안 발동 **0회**, 본 `hi - lo` 의 최솟값은
                # **1.000**(테이블에 바짝 붙는 갈래의 값이다). 결과에 아무 흔적을 남기지
                # 않는 조용한 수선이라 결과를 보는 어떤 시험으로도 반증할 수 없었다.
                # 그래서 16라운드가 **갈래를 없앴다** [없앰]. 대신 같은 보장을 갈래
                # 없이 편다 — 고른 쪽 경계에 12px 자기 몫을 `min`/`max` 로 보태면
                # `hi - lo >= 1` 이 계산 자체의 결론이 된다:
                #   · L: hi 는 정확히 x1-12 이고 lo <= x1-13 이므로 >= 1
                #   · R: lo 는 정확히 x2+12 이고 hi >= x2+13 이므로 >= 1
                # 보태는 자리가 **side 를 고른 뒤**인 것이 중요하다. 위 lo_l/hi_r 을
                # 미리 벌리면 방이 없는 쪽에도 차선이 있는 것처럼 보여(clean_lane 이
                # 그 한 칸을 찾아낸다) 팔이 그쪽 테이블로 갈아탄다 — 14라운드가 지운
                # 바로 그 버그다. 여기서는 clean_lane 이 다 본 뒤라 차선 판단이 바뀌지
                # 않는다. 보통 판에서는 lo_l 이 이미 x1-13 보다 작아 min/max 가 아무
                # 것도 안 바꾼다.
                #
                # 남는 것은 '보태기 없이도 정말 안전한가' 인데, 그것은 코드가 아니라
                # 불변식이라 시험이 직접 계측한다 — `selftest_r14_render.py` 의
                # `render: the bounds handed to slot() for a self-reference arm are
                # never empty` 가 아래 `near = …` 줄에서 lo·hi 를 그 자리의 지역
                # 변수로 읽어 `hi - lo >= 1` 을 못박는다.
                lo, hi = ((min(lo_l, x1 - 13), hi_l) if side == 'L'
                          else (lo_r, max(hi_r, x2 + 13)))
                near = x1 if side == 'L' else x2
                ax = slot(near - arm if side == 'L' else near + arm, used_vx, 14,
                          lo=lo, hi=hi, span=(cy - dy, cy + dy))
                # 팔도 가로선이다 — 통로가 피하게. x 범위는 팔이 실제로 덮는 만큼만.
                _ax0, _ax1 = min(ax, near), max(ax, near)
                used_hy.extend(((cy - dy, _ax0, _ax1), (cy + dy, _ax0, _ax1)))
                self_loops.append(([(near, cy - dy), (ax, cy - dy),
                                    (ax, cy + dy), (near, cy + dy)],
                                   EDGE, fk['column'], tname))

        # 진출입 y 가 다 모인 뒤에야 통로 lane 을 고른다 — 위 entry_ys() 참고.
        for a, b, color, lbl, dash, ys in pending:
            edges.append((route(a, b, ys), color, lbl, dash, True))

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

        for ei, (pts, color, label, dash, _pinned) in enumerate(edges):
            draw_edge(pts, color, ei, dash)
            if dash:
                arrow_head(pts, color)
            else:
                crow_foot(pts, color)
                one_bar(pts, color)
            if edge_labels:
                path_label(pts, label, color)

        for pts, color, label, _owner in self_loops:
            draw_edge(pts, color, -1)
            crow_foot(pts, color)
            one_bar(pts, color)
        for pts, color, label, _owner in self_loops:
            if edge_labels:
                # **다른 라벨과 정말로 같은 대우.** 예전엔 여기서 바로 그렸다 —
                # 노드보다 먼저 그리는 자리라, 라벨이 테이블에 걸치면 그대로 지워졌다
                # (겹친 자리의 글자 픽셀이 한 점도 안 남는 것을 재서 확인했다).
                # 자리도 pts[1][0]-6 에 못박혀 있어 후보 탐색이 아예 없었다. 그래서
                # 문서가 말하는 '라벨은 노드 다음에' 도, SKILL.md 가 말하는
                # flush_labels() 의 후보 넓히기도 이 라벨에는 해당이 없었다.
                # 이제 다른 라벨과 같은 큐에 넣는다 — 노드를 피하는 것이 강제 조건이고,
                # 그리는 것은 노드 다음이다.
                path_label(pts, label, color)

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

        # 자기참조 루프도 검증 대상이다. 그리기만 하고 재지 않아서, 루프가 옆 테이블을
        # 지나가도 선↔테이블 0 이 찍혔다.
        # 자기참조 루프의 팔 높이(cy±dy)는 라우터가 고른 값이라 pinned 가 아니다 —
        # 루프끼리 포개지면 그건 진짜 회귀다.
        return edges + [(pts, color, label, False, False)
                        for pts, color, label, _o in self_loops], placed

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
    # 더미 측정은 본체만 잰다. 제목·부제·범례는 그 바깥이라 길면 잘려 나갔다 —
    # 영역명이 곧 범례 라벨이라 자동 분류된 긴 이름에서 실제로 잘렸다.
    W = int(lx1 - lx0) + MARGIN * 2
    W = max(W, int(tw(title, f['head']) / S) + MARGIN * 2)
    if subtitle:
        W = max(W, int(tw(subtitle, f['legend']) / S) + MARGIN * 2)
    legend_h = 0
    if legend:                       # 범례도 실제로 그려보고 재다 (줄바꿈 반영)
        # 두 번 잰다. 먼저 폭 제한 없이 그려 **가장 넓은 항목**이 요구하는 폭을 받고,
        # 캔버스를 거기까지 넓힌 뒤, 그 폭으로 다시 그려 줄바꿈이 반영된 높이를 받는다.
        # 순서를 바꾸면 안 된다 — 높이는 폭에 딸린 값이다.
        def _leg_probe(mw):
            return draw_legend(Tracker(ImageDraw.Draw(Image.new('RGB', (1, 1)))),
                               f, MARGIN, 0, S, mw)
        W = max(W, int(_leg_probe(10 ** 6)[1]) + MARGIN * 2)
        legend_h = _leg_probe(W - MARGIN * 2)[0] + 20
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
    # 라벨 상자는 **한 벌만** 만든다. 예전엔 라벨↔라벨만 잉크(label_ink_box)로 재고
    # 라벨↔테이블은 자리 잡기용 여백 상자를 그대로 썼다. 게다가 맞닿음 규칙이 서로
    # 반대였다 — 이쪽은 `<` 라 스치기만 해도 겹쳤다고 세고, 저쪽은 `<=` 라 안 셌다.
    # 같은 버그를 반만 고친 자리라, 자를 하나로 합친다.
    lab_boxes = [label_ink_box(b, f['edge'], S) for b in placed]
    lab_hit = sum(1 for b in lab_boxes for o in node_rects if boxes_touch(b, o))
    # 세그먼트마다 그 선의 양 끝(출발·도착 지점)을 달아 둔다 — 같은 지점으로 모여드는
    # 합류와, 아무 상관 없이 같은 자리에 겹쳐 그려진 것을 구분하기 위해서다.
    # 그리고 그 구간의 y 를 라우터가 골랐는지(pin=False) 컬럼 행에 못박혀 있는지
    # (pin=True) 도 같이 달아 둔다 — 아래 overlaps() 가 쓴다.
    segs_v, segs_h = [], []
    for pts, _color, _label, _dash, pinned in edges:
        ends = ((round(pts[0][0]), round(pts[0][1])),
                (round(pts[-1][0]), round(pts[-1][1])))
        last = len(pts) - 2
        for j, (p, q) in enumerate(zip(pts, pts[1:])):
            # 경로의 첫·끝 구간은 노드에 붙는 진출입 꼬리다. route() 가 만든 경로에서
            # 그 y 는 col_y() 가 준 컬럼 행이라 라우터의 선택이 아니다.
            pin = pinned and (j == 0 or j == last)
            if abs(p[0] - q[0]) < 0.5:
                segs_v.append((p[0], min(p[1], q[1]), max(p[1], q[1]), ends, False))
            else:
                segs_h.append((p[1], min(p[0], q[0]), max(p[0], q[0]), ends, pin))

    def overlaps(segs):
        """같은 자리에 겹쳐 그려진 구간을, **라우터가 고칠 수 있는 것만** 센다.

        같은 지점으로 모여드는 선(한 컬럼 행으로 들어가는 여러 FK)은 겹쳐 보이는 것이
        정상이라 세지 않는다. 판별은 세그먼트에 달아 둔 그 선의 양 끝으로 한다 —
        예전엔 좌표가 우연히 같기만 해도 합류로 넘어갔다.

        다만 이 예외는 길이를 따지지 않는다. 같은 행으로 모여드는 두 선이 아주 길게
        나란히 달려도 '합류' 로 넘어간다. 다발로 보이는 것이 자연스러워서 그렇게 두었다.

        진출입 꼬리끼리 스치는 것도 세지 않는다. 그 y 는 '선은 노드 가운데가 아니라
        실제 컬럼 행에서 드나든다' 는 불변식이 정한 값이라 라우터에 선택권이 없다 —
        서로 다른 두 테이블의 어떤 행 높이가 우연히 3px 안에 들면 그 짧은 꼬리는
        반드시 겹친다. 예전엔 이것까지 세는 바람에 평범한 21테이블 스키마가 첫 판부터
        [경고] 를 달고 나왔고, 그러면 [경고] 는 회귀 신호가 아니라 소음이 된다.
        꼬리 하나와 통로를 달리는 긴 구간이 겹치는 것은 통로 배정(slot) 이 진 것이라
        그대로 센다.
        """
        n = 0
        for i, (a, s0, s1, ea, pa) in enumerate(segs):
            for (b, t0, t1, eb, pb) in segs[i + 1:]:
                lap = min(s1, t1) - max(s0, t0)
                if abs(a - b) >= 3 or lap <= 6:
                    continue
                if set(ea) & set(eb) and ea != eb:
                    continue         # 같은 컬럼 행으로 모여드는 합류 — 겹쳐도 정상이다
                # 양 끝이 **둘 다** 같으면 합류가 아니라 같은 선을 두 번 그린 것이다.
                # 예전엔 이것까지 합류로 넘어갔다 — 모든 구간을 복제해 보면 원래 있던
                # 겹침 수만 네 배가 될 뿐, 복제 자체는 한 건도 잡히지 않았다.
                if pa and pb:
                    continue         # 컬럼 행에 못박힌 진출입 꼬리끼리 — 옮길 수 없다
                n += 1
                if DEBUG_OVERLAP:
                    print(T('log.overlap_at', a=f'{a:.0f}', s0=f'{s0:.0f}',
                             s1=f'{s1:.0f}', t0=f'{t0:.0f}', t1=f'{t1:.0f}'))
        return n

    def thru_nodes():
        """테이블 속을 지나는 선을 센다.

        문서가 '선이 테이블을 관통하지 않는다' 고 못박아 두고선 정작 이걸 재지 않았다.
        선을 노드보다 먼저 그리므로 관통은 노드에 덮여 **보이지도 않는다** — 선이
        테이블 뒤로 사라졌다 반대편에서 나온다. 눈으로는 못 잡는다.
        """
        n = 0
        for x, y0, y1, _e, _p in segs_v:
            for (ox0, oy0, ox1, oy1) in node_rects:
                if ox0 + 2 < x < ox1 - 2 and min(y1, oy1) - max(y0, oy0) > 4:
                    n += 1
        for y, x0, x1, _e, _p in segs_h:
            for (ox0, oy0, ox1, oy1) in node_rects:
                if oy0 + 2 < y < oy1 - 2 and min(x1, ox1) - max(x0, ox0) > 4:
                    n += 1
        return n

    def lab_hits():
        """라벨끼리 포개진 수.

        라벨↔테이블만 재고 있어서 라벨 둘이 겹쳐도 0 이 찍혔다 — 자기참조가 둘인
        테이블에서 실제로 두 라벨이 포개졌다.

        라벨이 관계선 위에 얹히는 것은 세지 않는다. 라벨은 그 선을 설명하는 것이라
        선 곁에 있는 게 맞고, 글자 둘레를 배경색으로 둘러 읽는 데 지장이 없다.

        `placed` 에 든 것은 **자리 잡기용** 사각형이라 글자보다 사방이 넉넉하다
        (좌우 LABEL_PAD_X, 위아래로는 글꼴 잉크 바깥까지). 그걸 그대로 판정에 쓰면,
        두 줄로 나란히 놓여 멀쩡히 읽히는 라벨이 겹쳤다고 찍힌다 — 자기참조가 절반쯤
        든 무작위 스키마 120개에서 열한 번 그랬고, 열한 번 다 글자 픽셀은 한 점도
        닿지 않았다(bbox 로 1~4px, 그중 한 번은 0px 맞닿음). 따로 쓴 퍼저 80개에서도
        같은 자리가 셋 나왔고 잘라서 눈으로 본 셋 다 두 줄로 멀쩡히 읽혔다. [경고] 가
        그런 식으로 나면 회귀 신호가 아니라 소음이 된다. 그래서 잰다고 말한 것 —
        사람 눈에 보이는 **글자** — 을 재도록 여백을 걷어 내고(label_ink_box),
        맞닿은 것은 겹친 것으로 세지 않는다.
        """
        n = 0
        for i, a in enumerate(lab_boxes):        # 라벨↔테이블과 **같은 상자·같은 규칙**
            for b in lab_boxes[i + 1:]:
                if boxes_touch(a, b):
                    n += 1
        return n

    # 개요도·전체도는 노드 진출 y 가 고정이라 가로선 중첩이 소수 남는 것이 정상인데,
    # 숫자만 찍으면 그 '아는 겹침' 과 회귀를 구분할 수 없다. 그래서 허용된 항목은
    # 값에 (허용) 을 달고, 0 이어야 하는 항목이 0 이 아니면 같은 줄에 [경고] 를 단다.
    #
    # 라벨을 아예 그리지 않는 그림(개요도)에서는 라벨 항목이 잴 것이 없다. 그런데도
    # 0 을 찍으면 '재 보니 깨끗하다' 로 읽힌다 — 안 한 검사를 했다고 말하는 짓이다.
    # 그런 항목은 값 대신 '해당 없음' 을 찍고, 경고 판정에서도 뺀다.
    checks = [('label_table', lab_hit if edge_labels else None),
              ('label_x', lab_hits() if edge_labels else None),
              ('thru', thru_nodes()),
              ('v_overlap', overlaps(segs_v)), ('h_overlap', overlaps(segs_h))]
    parts = [f"{T('verify.' + k)} "
             + (T('verify.na') if v is None
                else T('verify.tolerated', n=v) if v and k in tolerate else str(v))
             for k, v in checks]
    bad = [T('verify.' + k) for k, v in checks if v and k not in tolerate]
    print(T('log.verify', name=Path(path).name, report=' · '.join(parts))
          + (T('verify.warn', list=', '.join(bad)) if bad else ''))
    # 그림을 먼저 저장하고 계측을 뒤에 남긴다. 순서가 반대였을 때, 로그 경로가
    # 쓸 수 없는 자리이면 '검증했다' 는 줄만 찍힌 채 PNG 한 장 없이 죽었다 —
    # 재는 도구가 재려는 것을 부수면 안 된다.
    img.save(path)
    verify_log(path, checks, tolerate)

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
    # 컬럼을 모르는 테이블(참조만 되고 정의가 없는 것)은 rows 가 비어 있다
    w_role = max([len(r[0]) for r in box['rows']] + [0])
    w_name = max([len(r[1]) for r in box['rows']] + [0])
    w_type = max([len(r[2]) for r in box['rows']] + [0])
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


def graphml_edge(eid, src, tgt, fk, derive=False):
    # ETL 흐름은 그림과 같은 갈색 점선으로 — FK 와 구분되어야 한다
    color = '#B0885A' if derive else EDGE
    label = escape(fk['column'] if derive
                   else f"{fk['column']} : {fk['ref_column']}")
    return f'''    <edge id="{eid}" source="{src}" target="{tgt}">
      <data key="d3">{label}</data>
      <data key="d2">
        <y:PolyLineEdge>
          <y:Path sx="0.0" sy="0.0" tx="0.0" ty="0.0"/>
          <y:LineStyle color="{color}" type="{'dashed' if derive else 'line'}" width="1.0"/>
          <y:Arrows source="{'none' if derive else 'crows_foot_many'}" target="{'standard' if derive else 'crows_foot_one'}"/>
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
    # ETL 흐름도 넣는다. FK 만 내보내고 있어서, yEd 로 열어 재배치하고 다시 뽑으면
    # 그림에 있던 흐름이 소리 없이 사라졌다 — 문서는 yEd 재출력을 권한다.
    for src, dst, label in DERIVES:
        if src in ids and dst in ids:
            parts.append(graphml_edge(f'e{e}', ids[src], ids[dst],
                                      {'column': label, 'ref_column': '',
                                       'on_delete': 'ETL'}, derive=True))
            e += 1
    parts.append('  </graph>\n</graphml>\n')
    # 첫 줄이 스스로를 `encoding="UTF-8"` 이라고 **선언한다**(GRAPHML_HEAD). 인코딩을
    # 안 주면 실제로 쓰이는 것은 로케일이 정하므로 선언과 알맹이가 어긋난다 — cp949
    # 로케일이면 yEd 가 한글을 깨서 열고, ascii 로케일이면 그 전에 UnicodeEncodeError
    # 로 죽어 그림은 다 그려 놓고 GraphML 만 0바이트로 남았다. 선언한 대로 쓴다.
    Path(path).write_text(''.join(parts), encoding='utf-8')
    return len(ids), e
