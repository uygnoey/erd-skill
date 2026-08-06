#!/usr/bin/env python3
"""출력 언어 — 콘솔 메시지와 산출 문서(HTML·docx·ERD 범례)의 말을 고른다.

  ERD_LANG=en|ko|ja|es    직접 지정
  없으면 로케일(LC_ALL·LC_MESSAGES·LANG), 그것도 없으면 en.

문구는 `lang/<코드>.py` 의 `M` 딕셔너리에 있다. 언어를 하나 더 늘리려면 그 폴더에
파일을 하나 더 놓으면 된다 — 코드는 건드리지 않는다. 빠진 키는 영어로 떨어진다.
"""
import locale
import os
import sys
from importlib import import_module
from pathlib import Path

# ── 화면으로 나가는 글자 ─────────────────────────────────────────────────────
# 파일에 무엇으로 쓰는지는 로케일에서 떼어 놨는데(열 때마다 encoding='utf-8'), 화면에
# 무엇으로 쓰는지는 여전히 로케일이 정한다. 그 고리가 실측으로 이렇게 끊어졌다:
#
#   $ PYTHONUTF8=0 PYTHONCOERCECLOCALE=0 LC_ALL=C python3 build_erd.py
#   … GraphML 을 끝까지 다 쓴 뒤 ↓
#   print(T('log.graphml', …))
#   UnicodeEncodeError: 'ascii' codec can't encode character '\xb7' …
#
# 카탈로그의 문구 상당수가 가운뎃점 `·`·곱셈표 `×`·화살표 `→` 를 쓰고, 표에 실리는
# 테이블 이름·컬럼 설명은 애초에 사용자의 말이다. 그래서 로케일이 C 이면 **그림은
# 다 그려 놓고 그 사실을 말하다가** 죽는다 — 산출물이 반만 나오고 rc≠0 이 된다.
# 말 한 줄 때문에 물건을 잃는 것이 이 저장소가 `_load`·`t()` 에서 두 번 물리친 바로
# 그 모양이라, 같은 답을 여기에도 댄다: **그림은 계속 그리되 알려 준다.**
#
# 무엇을 바꾸는가 — `errors` 하나뿐이다. `encoding` 은 손대지 않는다.
#   · `encoding='utf-8'` 로 덮지 않는 이유가 둘 있다. (1) 사용자가 준
#     `PYTHONIOENCODING` 의 뜻을 말없이 뒤집는다. (2) 선언한 것과 다른 바이트를
#     파이프에 흘린다 — 회귀 시험은 `subprocess.run(text=True)` 로 이 출력을 잡고,
#     그 디코딩은 **부모의** 로케일로 한다. 실측: 자식이 utf-8 로 쓰면 C 로케일
#     부모가 `UnicodeDecodeError: 'ascii' codec can't decode byte 0xc2` 로 죽는다.
#     자식의 죽음을 부모의 죽음으로 옮기는 것은 고친 것이 아니다.
#   · `errors='replace'` 도 아니다. `?` 는 진짜 `?` 와 구별되지 않아 **조용히
#     잘못된 것**이 된다. `backslashreplace` 는 `\xb7` 처럼 되돌릴 수 있게 남기고,
#     무엇보다 CPython 이 **똑같은 상황의 stderr 에 이미 고른 처리기**다(아래 참고).
#     한 줄에 두 규칙을 두지 않으려면 stdout 도 같은 것을 써야 한다.
#
# 언제 바꾸는가 — 지금 처리기가 '터질 수 있는' 것일 때만이다. C 로케일의 stdout 은
# `strict` 가 아니라 `surrogateescape` 인데(실측), 이것도 서로게이트가 아닌 글자에는
# 그대로 터진다. 그래서 세 이름을 다 센다. 이미 무른 처리기(`backslashreplace` 등)는
# 건드리지 않는다 — stderr 가 실제로 그렇다.
#
# 왜 라이브러리인 여기서 프로세스 전역을 건드리는가. 이 저장소의 실행기는 여덟인데
# 모두 `i18n` 을 거치고, `lang/` 도 `selftest*` 도 이 갈래의 소유가 아니라 실행기마다
# 한 줄씩 심는 길이 막혀 있다. 대신 손대는 폭을 최소로 묶는다: **`errors` 만**,
# **터질 수 있는 처리기일 때만**, **`PYTHONIOENCODING` 이 처리기를 직접 고르지
# 않았을 때만**. 그래서 보통의 UTF-8 터미널에서는 나가는 바이트가 한 글자도 달라지지
# 않고(UTF-8 은 무엇이든 적을 수 있다), 옛 동작을 그대로 원하는 사람에게는
# `PYTHONIOENCODING=utf-8:strict` 라는 표준 손잡이가 그대로 남는다.
#
# 알리는 줄은 두지 않는다. 이 자리의 하드코딩 영어는 아래 `_load`·`t()` 의 둘뿐이고,
# 그 둘의 근거는 '카탈로그가 깨져 카탈로그로 낼 수 없다' 다. 여기는 카탈로그가
# 멀쩡하다 — 새 문구가 필요한 것이지 카탈로그를 못 쓰는 것이 아니고, `lang/` 은 이
# 갈래의 소유가 아니다. 대신 표식(`\xb7`)이 화면에 그대로 보이므로 무슨 일이
# 일어났는지는 눈에 남는다.
_RAISING = ('strict', 'surrogateescape', 'surrogatepass')


def _errors_pinned():
    """`PYTHONIOENCODING` 이 오류 처리기를 **직접** 골랐는가.

    형식은 `인코딩[:처리기]` 다. `ascii` 와 `ascii:strict` 는 스트림에서는 똑같이
    `strict` 로 보여서 구별할 수 없으므로, 사용자가 정말로 그렇게 적었는지는 환경변수
    원문으로만 알 수 있다. 직접 골랐으면 그 뜻대로 둔다 — 터지길 원했으면 터진다.
    """
    return bool((os.environ.get('PYTHONIOENCODING') or '').partition(':')[2].strip())


def _keep_console_alive(stream):
    """터질 수 있는 처리기를 `backslashreplace` 로 무르게 한다. 바꿨으면 True.

    파이프로 리디렉트돼도(TextIOWrapper 다) 그대로 먹고, `io.StringIO` 로 갈아 끼운
    스트림은 `errors` 도 `reconfigure` 도 없어 저절로 빠진다. `sys.stdout` 이 None 인
    경우(윈도우 pythonw)도 같은 길로 빠진다. 여기서 터지면 본전도 못 찾으므로
    마지막 한 겹은 통째로 감싼다.
    """
    if _errors_pinned():
        return False
    if getattr(stream, 'errors', None) not in _RAISING:
        return False
    reconfigure = getattr(stream, 'reconfigure', None)
    if reconfigure is None:
        return False
    try:
        reconfigure(errors='backslashreplace')
    except Exception:                                            # noqa: BLE001
        return False
    return True


# stderr 도 함께 넘긴다. CPython 은 stderr 에 늘 `backslashreplace` 를 물려서
# (실측: `PYTHONIOENCODING=ascii:strict` 로도 stderr 는 backslashreplace 였다)
# 오늘은 이 부름이 아무것도 안 바꾼다. 그래도 적어 두는 이유는, 규칙이 '어느
# 스트림' 이 아니라 '터질 수 있는 처리기' 이기 때문이다 — 누가 stderr 를 갈아
# 끼우면 그때 이 줄이 답한다.
_keep_console_alive(sys.stdout)
_keep_console_alive(sys.stderr)


def _supported():
    """lang/ 에 놓인 파일이 곧 지원 언어다 — 목록을 따로 적어 두면 어긋난다."""
    try:
        codes = sorted(p.stem for p in (Path(__file__).parent / 'lang').glob('*.py')
                       if not p.stem.startswith('_'))
    except Exception:
        codes = []
    return tuple(codes) or ('en',)


SUPPORTED = _supported()


def _pick():
    v = (os.environ.get('ERD_LANG') or os.environ.get('LC_ALL')
         or os.environ.get('LC_MESSAGES') or os.environ.get('LANG') or '')
    if not v:
        try:
            v = locale.getdefaultlocale()[0] or ''
        except Exception:
            v = ''
    v = v.lower().replace('-', '_')
    for code in SUPPORTED:
        if v == code or v.startswith(code + '_') or v.startswith(code + '.'):
            return code
    return 'en'


LANG = _pick()


def _load(code):
    try:
        return dict(import_module(f'lang.{code}').M)
    except Exception as e:
        # 조용히 영어로 떨어지면 카탈로그가 깨진 걸 아무도 모른다. 그림은 계속 그리되
        # 왜 말이 바뀌었는지는 알려 준다.
        print(f'  [warn] lang/{code}.py could not be loaded ({e}) — falling back to English')
        return {}


_EN = _load('en')
_M = _EN if LANG == 'en' else {**_EN, **_load(LANG)}

_WARNED = set()      # 같은 키로 두 번 울지 않는다 — t() 는 표의 칸마다 불린다


def t(key, /, **kw):
    """문구를 가져온다. 자리표시자는 이름으로 넣는다 — 어순이 언어마다 다르기 때문이다.

    key 는 위치 전용이다. 그러지 않으면 `{key}` 라는 자리표시자를 쓰는 순간
    t() 의 첫 인자와 부딪혀 TypeError 가 난다.
    """
    s = _M.get(key)
    if s is None:                       # 카탈로그에 없는 키는 눈에 띄게 남긴다
        return f'⟨{key}⟩'
    if not kw:
        return s
    try:
        return s.format(**kw)
    except (KeyError, IndexError, ValueError):
        # 번역판의 자리표시자가 영어판과 어긋나면(`{n}` 을 `{count}` 로 적는 등) 여기서
        # 터진다. 그런데 이 예외는 문구를 **쓰는 자리** 에서 터지므로, 문구 하나의
        # 오타가 산출물을 통째로 못 나오게 한다 — 그림도 문서도 없이 역추적만 남는다.
        # 위(`_load`)에서 이미 정한 것과 같은 판단을 여기에도 댄다: **그림은 계속
        # 그리되 왜 말이 바뀌었는지는 알려 준다.** 영어판 문구로 한 번 더 해 보고,
        # 그것도 안 되면(영어판 자체가 깨진 것이다) 키를 눈에 띄게 남긴다.
        # 조용히 넘어가지는 않는다 — 깨진 카탈로그를 아무도 모르는 것이 더 나쁘다.
        if key not in _WARNED:
            _WARNED.add(key)
            print(f'  [warn] lang/{LANG}.py: the placeholders of {key!r} do not match '
                  f'the English catalog — falling back to English for this line')
        en = _EN.get(key)
        if en is not None and en is not s:   # LANG=en 이면 같은 문자열이라 또 터진다
            try:
                return en.format(**kw)
            except (KeyError, IndexError, ValueError):
                pass
        return f'⟨{key}⟩'
