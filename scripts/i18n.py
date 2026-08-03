#!/usr/bin/env python3
"""출력 언어 — 콘솔 메시지와 산출 문서(HTML·docx·ERD 범례)의 말을 고른다.

  ERD_LANG=en|ko|ja|es    직접 지정
  없으면 로케일(LC_ALL·LC_MESSAGES·LANG), 그것도 없으면 en.

문구는 `lang/<코드>.py` 의 `M` 딕셔너리에 있다. 언어를 하나 더 늘리려면 그 폴더에
파일을 하나 더 놓으면 된다 — 코드는 건드리지 않는다. 빠진 키는 영어로 떨어진다.
"""
import locale
import os
from importlib import import_module
from pathlib import Path


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


def t(key, **kw):
    """문구를 가져온다. 자리표시자는 이름으로 넣는다 — 어순이 언어마다 다르기 때문이다."""
    s = _M.get(key)
    if s is None:                       # 카탈로그에 없는 키는 눈에 띄게 남긴다
        return f'⟨{key}⟩'
    return s.format(**kw) if kw else s
