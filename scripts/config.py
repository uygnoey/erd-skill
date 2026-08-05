#!/usr/bin/env python3
"""ERD 생성 공통 설정 — 어떤 DB에도 붙을 수 있게 전부 외부화했다.

경로·접속은 환경변수, 그림의 뼈대(영역·레이어색·역할명·ETL흐름)는 `erd.spec.json`.
spec 이 없으면 스키마와 테이블명 접두어로 자동 추론한다.

  ERD_PROJ      최종 문서를 저장할 디렉토리        (기본: 현재 디렉토리)
  ERD_WORK      중간 산출물(schema.json)·PNG      (기본: $ERD_PROJ/erd-build)
  ERD_SPEC      그림 뼈대 정의 JSON               (기본: $ERD_WORK/erd.spec.json)
  ERD_DOCNAME   산출 문서 파일명 (확장자 제외)

  # DB 접속 — 둘 중 하나
  ERD_DB        docker 컨테이너 경유  형식: container:user:dbname
  ERD_PSQL      psql 명령을 직접 지정  예: 'psql postgresql://u:p@host:5432/db'

  ERD_SCHEMAS   인트로스펙션 대상 스키마 (콤마 구분, 기본: public)
  ERD_EXCLUDE   제외할 테이블 정규식

  # DDL 파싱을 쓸 때만 (introspect.py 대신 parse_ddl.py 사용 시)
  ERD_SQL_DIR   파싱할 DDL 디렉토리
  ERD_MODEL_DIR 컬럼 설명을 뽑을 ORM 모델 디렉토리

빈 값(`ERD_X=`)의 뜻은 **자리마다 다르다.** 세 규칙이고, 셋 다 여기 적는다 — 15라운드
전에는 세 자리에 흩어져 있고 어디에도 함께 적혀 있지 않아, 하나를 보고 나머지를
짐작하면 틀렸다.

  경로 (ERD_PROJ·ERD_WORK·ERD_SPEC·ERD_SQL_DIR·ERD_MODEL_DIR·ERD_DOC_HTML …)
      빈 값·공백뿐인 값 = **설정하지 않은 것** → 위에 적힌 기본값 (`_p`)
      Path('') 이 Path('.') 이 되어 산출물이 부르는 사람의 cwd 에 흩어지는 것을 막는다.

  켜짐/꺼짐 (ERD_SVG·ERD_HTML_SVG·ERD_HTML_FULL·ERD_HTML_STATS·ERD_SVG_TITLE·ERD_STALE)
      빈 값 = **꺼짐** (`env_flag`)
      셸에서 `ERD_SVG= cmd` 로 한 번만 끄는 것이 흔한 손버릇이다. 기본값으로 되돌리는
      길은 따로 있다 — `unset`.

  목록 (ERD_SCHEMAS)
      빈 값 = **여기서 멈춘다** (`_schemas`)
      경로처럼 '없는 셈' 치면 기본값 public 으로 슬며시 돌아가는데, 그러면 사용자가
      물은 적 없는 스키마의 문서가 완성된 얼굴로 나온다. 잘못 적었다고 말하는 편이 낫다.
"""
import json
import os
import re
import shlex
import subprocess
import unicodedata
from pathlib import Path

from i18n import t as T


def env_flag(env, default=False):
    """켜짐/꺼짐 환경변수 하나 — 규칙은 **이것 하나뿐이다.**

    예전엔 다섯 자리가 저마다 `os.environ.get(...) not in ('0','false','no')` 를 적고
    있었다. 소문자 세 낱말만 끄므로 `ERD_HTML_SVG=False`·`NO`·`off` 는 **껐는데
    켜졌고**, `'0 '` 은 공백 하나로 도로 켜졌다. 같은 저장소의 ERD_STALE 은
    `.strip().lower()` 를 하고 있었으니 코드가 제 안에서 두 규칙을 쓴 셈이다.

    모르는 값은 참으로 치지 않는다 — 그러면 `flase` 같은 오타가 조용히 켜짐이 된다.
    이름을 대어 알리고 그 변수의 기본값으로 간다.

    **이 규칙을 지나야 하는 변수 목록은 모듈 첫머리에 있다.** 낱말을 더 받아야 하는
    변수는 그 낱말만 제 자리에서 먼저 걸러 내고 **나머지는 여기로 넘긴다** — 규칙을
    복사해 가면 곧 두 규칙이 된다. `ERD_STALE` 이 그 모양이다: 'warn'·'ok' 는
    build_erd.py 가 제 뜻으로 받고, 그 밖의 값은 `env_flag('ERD_STALE', False)` 가
    답한다. 켜짐/꺼짐을 새로 다는 자리는 그냥 이것만 부르면 된다.
    """
    raw = os.environ.get(env)
    if raw is None:
        return default
    v = raw.strip().lower()
    if v in ('', '0', 'false', 'no', 'off', 'n', 'f'):
        return False
    if v in ('1', 'true', 'yes', 'on', 'y', 't'):
        return True
    print(T('log.env_not_flag', env=env, value=raw, used='1' if default else '0'))
    return default


def _p(env, default):
    """경로 환경변수 하나. **빈 값은 설정하지 않은 것으로 친다.**

    `os.environ.get(env, default)` 는 빈 문자열도 값으로 받아 `Path('')` → `Path('.')`
    이 됐다. `ERD_WORK=''` 하나로 중간 산출물과 out/ 이 부르는 사람의 cwd 에 흩어졌다 —
    지우려 해도 어디에 생겼는지 모른다. 공백만 있는 값도 같다.
    """
    raw = os.environ.get(env, '')
    return Path(raw if raw.strip() else str(default)).expanduser()


def as_dir(path, env):
    """디렉토리로 쓸 자리. 다른 종류의 노드가 있으면 **변수 이름을 대고** 멈춘다.

    mkdir 이 던지는 `FileExistsError: [Errno 17]` 은 어느 환경변수가 그랬는지도,
    무엇이 이미 거기 있는지도 말해 주지 않는다.
    """
    if path.exists() and not path.is_dir():
        raise SystemExit(T('err.env_not_dir', env=env, path=path))
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise SystemExit(T('err.env_bad', env=env, value=path, why=e))
    return path


def as_file(path, env):
    """읽을 파일 자리. 디렉토리를 가리키면 `IsADirectoryError` 대신 이름을 댄다.

    없는 파일은 여기서 막지 않는다 — 부르는 쪽이 '없으면 기본값' 을 쓸 수 있어야 한다.
    """
    if path.exists() and not path.is_file():
        raise SystemExit(T('err.env_not_file', env=env, path=path))
    return path


_BAD_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def safe_name(raw):
    """파일명 조각으로 쓸 수 있게 다듬는다.

    슬래시가 섞이면 어떤 스크립트는 죽고 어떤 스크립트는 하위 디렉토리를 만들어 엉뚱한
    자리에 쓴다. 앞뒤의 점·공백은 '.html' 같은 숨김 파일을 만든다.
    """
    return _BAD_NAME.sub('_', str(raw)).strip('. ')


def _docname():
    return safe_name(os.environ.get('ERD_DOCNAME', '')) or 'ERD'


DOCNAME = _docname()


def _schemas():
    """ERD_SCHEMAS — 설정했는데 빈 값이면 기본값으로 슬며시 돌아가지 않는다.

    `ERD_SCHEMAS=''` 는 `where table_schema in ()` 라는 문법 오류 SQL 이 되어,
    사용자는 제 변수 대신 psql 의 파서 오류를 봤다. 빈 값의 뜻이 경로 변수와 왜
    다른지는 모듈 첫머리에 적혀 있다.
    """
    raw = os.environ.get('ERD_SCHEMAS', 'public')
    out = [s.strip() for s in raw.split(',') if s.strip()]
    if not out:
        raise SystemExit(T('err.env_empty', env='ERD_SCHEMAS'))
    return out


# 정규식은 **쓰기 전에** 한 번 컴파일해 본다. 예전엔 excluded() 안에서 처음 컴파일돼,
# `re.error: unterminated character set` 이 어느 변수 탓인지 말도 없이 튀어나왔다.
EXCLUDE = os.environ.get('ERD_EXCLUDE', '')
try:
    _EXCLUDE_RE = re.compile(EXCLUDE) if EXCLUDE else None
except re.error as e:
    raise SystemExit(T('err.env_bad', env='ERD_EXCLUDE', value=EXCLUDE, why=e))


_CTRL = {c: ' ' for c in range(32)}
_CTRL[0x7f] = ' '


def clean(s):
    """사람이 읽을 한 줄로 만든다. 설명·역할명은 전부 여기를 지난다.

    개행이 든 문자열은 PIL 이 폭을 재지 못해 그리다 죽고(다이어그램이 통째로 안 나온다),
    제어문자는 GraphML·SVG 를 XML 로서 깨뜨려 yEd 가 파일 열기를 거부한다. DB 코멘트는
    조회 단계에서 걸러도, 수기 사전(MANUAL)과 손으로 고친 schema.json 은 안 걸린다.
    """
    if not s:
        return ''
    return ' '.join(str(s).translate(_CTRL).split())


def _psql_words():
    """ERD_PSQL 을 **시작 자리에서 한 번** 분해해 본다.

    따옴표가 안 맞으면 shlex 가 `ValueError: No closing quotation` 을 던지는데, 그
    자리는 첫 조회 직전이라 사용자는 제 변수 이름 대신 shlex 의 말을 봤다.
    """
    raw = os.environ.get('ERD_PSQL', '')
    if not raw.strip():
        return []
    try:
        words = shlex.split(raw)
    except ValueError as e:
        raise SystemExit(T('err.env_bad', env='ERD_PSQL', value=raw, why=e))
    if not words:
        raise SystemExit(T('err.env_empty', env='ERD_PSQL'))
    return words


# ── 늦춰 두는 값 ────────────────────────────────────────────────────────────
# 14라운드까지 아래 아홉은 모듈 최상단의 **대입**이었다. 그래서 `import config` 한 번에
# 경로가 만들어지고 ERD_PSQL·ERD_SCHEMAS 가 판정됐다. 두 가지가 딸려 왔다.
#
# ① cwd 오염.  `import config` → `PROJ = as_dir(_p('ERD_PROJ', Path.cwd()), …)` →
#    `path.mkdir(parents=True, exist_ok=True)`. DB 도 안 보고 그림도 안 그리는 import
#    하나가 부르는 사람의 cwd 에 `erd-build/out` 을 만들었다 — 빈 디렉터리에서 회귀
#    시험을 돌리면 `./erd-build` 가 남았고(시험이 parse_ddl 을 inspect 하려고 import
#    한 것이 전부다), README·SKILL 이 안내하는 직접 실행 경로도 같았다. 14라운드는
#    `install.sh --check` 쪽만 임시 디렉터리로 피했다 — 그 자리의 증상만 가린 셈이다.
#
# ② 사망 범위.  `ERD_PSQL='psql "unclosed'` 하나로 **DB 를 한 번도 안 쓰는**
#    build_html.py·build_docx.py·merge_desc.py 가 전부 rc 1 이었다. 이미 있는
#    schema.json 으로 문서만 다시 뽑는 실행이 통째로 막혔다. 같은 이유로
#    `ERD_SCHEMAS=''` 도 그림·문서 쪽 스크립트를 함께 죽였다.
#
# 값은 **처음 물어볼 때** 만든다 (PEP 562 모듈 __getattr__). 계산은 한 번뿐이고,
# 실제로 쓰는 쪽(`from config import OUT`)에서는 예전과 똑같이 그 자리에서 만들어지고
# 예전과 똑같이 이름을 대고 멈춘다 — 옮긴 것은 **누가 그 값을 묻는가** 뿐이다.
# 모듈 안에서는 전역 이름 조회가 __getattr__ 을 거치지 않으므로 _get() 으로 부른다.
_LAZY = {
    'PROJ': lambda: as_dir(_p('ERD_PROJ', Path.cwd()), 'ERD_PROJ'),
    'WORK': lambda: as_dir(_p('ERD_WORK', _get('PROJ') / 'erd-build'), 'ERD_WORK'),
    'OUT': lambda: as_dir(_get('WORK') / 'out', 'ERD_WORK'),
    'SCHEMA_JSON': lambda: _get('WORK') / 'schema.json',
    'SPEC_JSON': lambda: as_file(_p('ERD_SPEC', _get('WORK') / 'erd.spec.json'),
                                 'ERD_SPEC'),
    'SQL_DIR': lambda: _p('ERD_SQL_DIR', _get('PROJ') / 'sql'),
    'MODEL_DIR': lambda: _p('ERD_MODEL_DIR', _get('PROJ') / 'models'),
    'SCHEMAS': _schemas,
    'PSQL_WORDS': _psql_words,
}
_LAZY_DONE = {}


def _get(name):
    """늦춰 둔 값 하나 — 계산은 이름마다 한 번뿐이다.

    16R. 15라운드가 여기 적어 둔 근거는 "mkdir 도 **경고도** 두 번 나지 않는다"
    였는데, `_LAZY` 에 든 아홉 중 경고를 찍는 것은 하나도 없다 — `as_dir`·`as_file`
    은 실패하면 경고가 아니라 SystemExit 이고, `_schemas`·`_psql_words` 도 멈추거나
    조용하다. 있지도 않은 피해를 근거로 세운 셈이라 문장을 코드가 하는 일에 맞춘다.

    그래서 **이 캐시를 지워도 지금은 밖에서 아무것도 달라지지 않는다.** mkdir 은
    `exist_ok=True` 라 멱등이고 `shlex.split` 은 순수하다 — 검증자가 캐시를 지우고
    161개를 돌려 전부 초록이었다(16R 뮤턴트 `M6`). 그것을 무는 케이스는 **일부러
    만들지 않았다**: 관측할 수 없는 것을 재는 시험은 동작이 아니라 구현을 베껴
    적는 것이고, 그러면 다음 사람이 이 자리를 못 고친다.

    캐시가 지키는 것은 **다음** 지연 값이다. 여기에 경고를 찍는 것이나 부를 때마다
    답이 달라질 수 있는 것(`Path.cwd()` 를 그때그때 읽는 따위)을 넣는 순간 캐시가
    곧 동작이 되고, 그때는 그것을 무는 케이스를 함께 넣어야 한다.
    """
    if name not in _LAZY_DONE:
        _LAZY_DONE[name] = _LAZY[name]()
    return _LAZY_DONE[name]


def __getattr__(name):
    if name in _LAZY:
        return _get(name)
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def has_db():
    """DB 에 붙을 수 있는가 — 빈 값·공백뿐인 값은 설정 안 한 것으로 친다."""
    return bool(_get('PSQL_WORDS') or os.environ.get('ERD_DB', '').strip())


PGENC = 'UTF8'        # psql 파이프의 인코딩. PostgreSQL 이 부르는 이름 (파이썬은 utf-8)


def psql_cmd():
    """psql 실행 명령. ERD_PSQL 이 있으면 그것을, 없으면 docker exec 를 쓴다."""
    if _get('PSQL_WORDS'):
        return list(_get('PSQL_WORDS'))
    db = os.environ.get('ERD_DB', '')
    if not db:
        raise SystemExit(
            T('err.no_conn') + '\n'
            "  export ERD_PSQL='psql postgresql://user:pass@host:5432/dbname'\n"
            "  export ERD_DB=" + T('err.no_conn_db'))
    container, user, name = (db.split(':') + ['', '', ''])[:3]
    # `-e` 로 컨테이너 **안**의 psql 에도 클라이언트 인코딩을 넘긴다. 우리 프로세스의
    # 환경변수(_psql_env)는 docker exec 가 컨테이너로 실어 주지 않으므로, 이 경로만
    # 빼먹으면 안쪽 psql 은 컨테이너 로케일(보통 C)이 정한 인코딩으로 답한다.
    return ['docker', 'exec', '-e', f'PGCLIENTENCODING={PGENC}',
            container, 'psql', '-U', user, '-d', name]


SEP = '\x1f'          # 구분자. | 는 기본값·코멘트에 섞여 나와 쓸 수 없다
RS = '\x1e'           # 레코드 구분자. 개행으로 행을 가르면 값 속 개행이 가짜 행이 된다


class QueryFailed(RuntimeError):
    """조회를 끝까지 읽지 못했다.

    부분 결과를 참으로 받아들이면 반쯤 읽은 DB 가 완성된 문서로 나온다. 부르는 쪽이
    '못 읽었다' 와 '읽었더니 0 건이다' 를 구분할 수 있게 예외로 알린다.
    """


def _psql_env():
    """psql 에게 줄 환경 — 클라이언트 인코딩을 **보내는 쪽에** 못 박는다.

    읽는 쪽만 utf-8 로 못 박으면 반쪽이다. psql 은 client_encoding 을 제 로케일에서
    정하므로, 우리가 utf-8 로 읽겠다고 정해도 상대는 cp949 로 보낼 수 있다. 양쪽을
    같은 값으로 맞춰야 왕복이 로케일과 무관해진다.

    **사용자가 이미 준 PGCLIENTENCODING 도 덮어쓴다.** 이 파이프는 사람이 보는
    화면이 아니라 우리가 규격을 통째로 정하는 기계용 통로다 — 이미 `-tA`, 구분자
    `\\x1f`, `row_to_json` 까지 우리가 지정한다. 게다가 UTF8 은 서버가 무엇으로
    저장하든 그 글자를 전부 담을 수 있는 유일한 선택이다: 다른 값을 주면 옮길 수
    없는 글자에서 psql 이 'character with byte sequence … has no equivalent in
    encoding …' 로 조회를 통째로 실패시킨다. 사용자의 다른 psql 세션에는 영향이
    없다 — 자식 프로세스의 환경만 바꾼다.
    """
    env = dict(os.environ)
    env['PGCLIENTENCODING'] = PGENC
    return env


def _run(query, rs='\n'):
    """psql 을 한 번 돌린다. 실패는 **부분 출력이 있어도** 반드시 알린다.

    예전엔 `returncode != 0 and not r.stdout` 일 때만 경고했다. 그래서 몇 행 흘리고
    죽은 조회(문 타임아웃·서버 재기동)는 경고 한 줄 없이 지나갔다 — 21개 테이블이
    조용히 4개가 됐다.

    **파이프도 파일과 같은 자리다.** `text=True` 만 주면 파이썬은 psql 의 출력을
    **로케일 인코딩**으로 읽는다 — ascii 로케일(LC_ALL=C)에서는 한글 코멘트가 든 DB
    가 여기서 `UnicodeDecodeError` 로 죽어, utf-8 로 못 박아 둔 schema.json 쓰기에
    닿지도 못했다. 읽는 값과 보내는 값(_psql_env)을 같은 것으로 못 박는다.

    `errors='replace'` 는 마지막 그물이다. 서버가 SQL_ASCII 면 psql 은 아무 변환도
    하지 않고 저장된 바이트를 그대로 보내므로 무엇으로 읽어도 어긋날 수 있는데,
    그때 예외가 나면 이 자리는 raw 트레이스백이 된다(psql_rows 밖의 부르는 이도
    있었다). 글자가 U+FFFD 로 보이는 편이 낫다 — 적어도 문서에서 눈에 띈다.

    다만 '눈에 띈다' 는 **문서를 끝까지 읽는 사람에게만** 참이었다. rc 는 0 이고
    화면에는 한 글자도 안 나왔다 — 실측된 모양이 이렇다:
        customers | note = '���� ���̺�'
    그래서 값을 손에 쥐는 이 자리에서 한 번 알린다. _run 이 psql·psql_rows 두 갈래가
    함께 지나는 유일한 목이라 여기 두면 어느 쪽으로 읽어도 걸린다.
    """
    r = subprocess.run(psql_cmd() + ['-tA', '-F', SEP, '-R', rs, '-c', query],
                       capture_output=True, text=True,
                       encoding='utf-8', errors='replace', env=_psql_env())
    if r.returncode != 0:
        print(T('log.query_fail', err=_why(r)))
    _warn_undecodable(r.stdout)
    return r


_ENC_WARNED = False      # 옮기지 못한 글자는 한 번만 알린다 — 조회마다 울면 소음이 된다


def _warn_undecodable(text):
    """읽은 값에 U+FFFD 가 섞였으면 **한 번** 알린다.

    되풀이를 막는 방식은 i18n 의 `_WARNED` 와 같다: 한 번 운 것은 기억해 두고 다시
    울지 않는다. 그쪽은 키마다, 여기는 프로세스마다다 — 원인이 하나(클라이언트
    인코딩)라 두 번째 조회가 같은 말을 해도 알려 주는 것이 없다. introspect 는 조회를
    열 번 넘게 돌리고 그 대부분이 컬럼 코멘트를 실어 오므로, 행마다 울면 진짜 진행
    출력이 경고에 묻힌다.

    `errors='replace'` 가 만든 U+FFFD 와 DB 에 원래 그 글자가 들어 있던 경우를 여기서
    구별하지는 못한다. 후자는 사실상 없고(그 자체가 이미 깨진 값이다), 있더라도 이
    문구가 가리키는 손잡이를 확인해 보라는 말이라 사용자가 잃는 것이 없다.
    """
    global _ENC_WARNED
    if _ENC_WARNED or '�' not in (text or ''):
        return
    _ENC_WARNED = True
    print(T('log.psql_undecodable', enc=PGENC))


def _why(r):
    """psql 이 남긴 실패 사유 한 줄."""
    return r.stderr.strip()[:200] or f'exit {r.returncode}'


def psql(query, rs='\n'):
    """DB 조회 — 결과를 SEP 구분 문자열로 돌려준다.

    행 구분은 rs 로 한다. 기본값에 개행이 든 컬럼(DEFAULT E'a\\nb')이 행 하나를
    둘로 쪼개 유령 테이블을 만들었다 — 개행이 들어올 수 있는 조회는 rs=RS 로 부른다.
    """
    return _run(query, rs).stdout


def psql_rows(query, n):
    """조회 결과를 필드 n개짜리 행 목록으로 돌려준다. 못 읽으면 QueryFailed.

    값을 구분자로 이어 붙여 받지 않고 **행마다 JSON 한 줄**로 받는다. 구분자를 무엇으로
    고르든 값이 그 바이트를 품을 수 있기 때문이다 — `|` 다음엔 개행이, 개행 다음엔
    \\x1e 가 똑같은 유령 행을 만들었다(값 하나에 \\x1e 가 들어 있으면 테이블 하나짜리
    DB 가 테이블 4개로 읽혔다). JSON 은 제어문자를 \\uXXXX 로 적으므로 한 행이 결코
    한 줄을 넘지 않고, 값이 담을 수 있는 어떤 바이트도 구분자로 오해되지 않는다.

    ORDER BY 는 서브쿼리 안으로 들어가지만 바깥은 행을 재배열하지 않는 단순 투영이라
    컬럼 순서(ordinal_position)는 그대로 지켜진다.
    """
    cols = ', '.join(f'c{i}' for i in range(n))
    r = _run(f'select row_to_json(_r) from ({query}\n) _r({cols})')
    out = []
    for line in r.stdout.splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            # 흘리다 끊기면 마지막 줄이 잘린 JSON 으로 남는다 — 지어내지 않고 실패로 센다
            raise QueryFailed(T('err.query_truncated')) from None
        out.append(['' if row.get(f'c{i}') is None else str(row[f'c{i}'])
                    for i in range(n)])
    if r.returncode != 0:
        raise QueryFailed(_why(r))
    return out


def excluded(name):
    """ERD_EXCLUDE 판정 — **이 규칙은 이것 하나뿐이다.**

    부르는 세 자리가 손에 든 것이 서로 다르다. introspect 는 조회에서 막 나온
    **테이블 이름**(라벨도 스키마도 아직 안 붙었다), erd.py 와 load_spec 은 schema.json
    의 **키**(`<라벨>.<스키마>.<이름>` 이 될 수 있다)다. 예전엔 각자 제가 든 것에
    정규식을 그대로 걸어서, 같은 규칙이 자리마다 다르게 걸렸다 — `ERD_EXCLUDE='^tmp_'`
    는 introspect 에서 `tmp_x` 를 잡지만 `ERD_LABEL=shop` 을 쓰면 키가 `shop.tmp_x` 라
    `^` 가 라벨에 막혀 그리는 쪽에서는 안 잡혔다. DDL 경로(parse_ddl)는 아예 거르지
    않으므로 그쪽은 키 판정만 남는다. 한 실행 안에서 걸린 것과 안 걸린 것이 갈렸다.

    그래서 **점으로 앞을 벗겨 가며** 물어본다: `shop.public.orders` 는 그 자신과
    `public.orders`·`orders` 로 한 번씩. 문서(SKILL.md·SKILL.ko.md)가 약속하는 것은
    '제외할 테이블 정규식' 이므로 사용자가 적은 `^tmp_` 는 **테이블 이름**에 걸려야
    하고, 라벨·스키마까지 적은 `^shop\\.` 같은 것도 예전처럼 그대로 걸린다.

    **넘치게 잡는 쪽을 골랐다.** 이 규칙은 키 판정보다 더 잡을 수는 있어도 덜 잡지는
    않는다. 근거는 '어느 쪽이 시끄러운가' 가 **아니다** — 둘 다 조용하다. 일부만 더
    빠지면 아무 줄도 안 나가고(빠진 테이블 이름을 댈 카탈로그 키가 없다), 일부가 덜
    빠지면 원치 않는 테이블이 문서에 실릴 뿐 역시 아무 말이 없다. 시끄러움으로는
    고를 수 없으니 **약속한 것**으로 고른다. 근거 둘이다.

    ① 문서가 약속한 것이 테이블 이름이다(위). 키 판정만 하던 예전 쪽이 약속과
       어긋나 있었지, 이름까지 보는 것이 덤으로 얹는 제외가 아니다.
    ② DB 경로에서는 이미 introspect 가 **테이블 이름**으로 걸러 schema.json 을 쓴다 —
       이름에 걸리는 것은 뒤 단계가 보기도 전에 없다. 그래서 이 규칙이 실제로 더
       잡게 되는 자리는 introspect 의 그물을 안 지난 경우뿐이다: 라벨을 붙여 합친
       schema.json(merge_schemas), 그리고 아예 거르지 않는 DDL 경로(parse_ddl).
       바로 거기가 사용자가 적은 `^tmp_` 가 안 듣던 자리다.

    반대로 키 쪽으로 통일하면(introspect 도 키로 판정) `ERD_LABEL` 을 쓰는 사람의
    `^tmp_` 는 **지금 되던 것까지 안 되게** 된다. 그것도 조용하다. 고를 값어치가 없다.

    빠진 테이블을 이름 대어 알리는 것이 옳지만 그 말을 할 키가 카탈로그에 없다
    (`log.exclude_rule` 은 규칙만 찍는다). 지금은 **규칙이 실제로 걷어낸 것이 있으면
    규칙이라도 밝히는 것**까지 한다 — erd.py 가 SCHEMA 를 만드는 자리. 이름까지 대려면
    카탈로그에 키가 하나 필요하다.

    이름 안에 점이 든 테이블(따옴표로 만든 `"a.b"`)은 `b` 로도 한 번 물어보게 된다.
    그 이름은 애초에 키에서도 스키마 구분과 섞이는 자리라, 넘치는 쪽으로 둔다.
    """
    if _EXCLUDE_RE is None:
        return False
    parts = str(name).split('.')
    return any(_EXCLUDE_RE.search('.'.join(parts[i:])) is not None
               for i in range(len(parts)))


# ── 그림 뼈대 (spec) ────────────────────────────────────────────────────────
# 레이어 색 팔레트 — (fill, header, border). 스키마·그룹 수만큼 순환 배정한다.
PALETTE = [
    ('#25324D', '#35507D', '#4A80C0'),   # 남색
    ('#3E3226', '#5E4732', '#B0885A'),   # 갈색
    ('#33294A', '#4A3A6B', '#8A6BB0'),   # 보라
    ('#1E3A3D', '#2B5A5E', '#4FA3A3'),   # 청록
    ('#333333', '#4A4A4A', '#8A8A8A'),   # 회색
    ('#2C3A28', '#415A3B', '#7DA86E'),   # 녹색
    ('#3D2A2E', '#5C3F45', '#A9707C'),   # 자주
]


def _code(i):
    """영역 코드 A…Z, 그 다음은 AA·AB…

    26 개를 넘기면 chr() 가 '[' 나 '\\' 를 내놓아 erd_area_\\.png 같은 파일명이 됐다.
    macOS 에서는 넘어가도 Windows 에서는 만들 수 없는 이름이다.
    """
    out, i = '', i + 1
    while i:
        i, r = divmod(i - 1, 26)
        out = chr(ord('A') + r) + out
    return out


def _code_key(code):
    """**같은 파일이 될 코드**끼리 묶는 열쇠.

    영역 코드는 `erd_area_<코드>.png` 라는 파일 이름이 된다. 그 이름이 서로 다른지를
    파이썬의 `==` 로 물으면 틀린다 — macOS(APFS·HFS+ 기본)와 Windows 는 대소문자를
    가리지 않고, macOS 는 유니코드 결합 형태도 가리지 않는다. `'A' != 'a'` 인데
    `erd_area_A.png` 와 `erd_area_a.png` 는 **같은 파일**이라, 뒤에 그린 영역이 앞의
    영역 그림을 조용히 덮어썼다(문서의 'Orders' 절에 남의 영역 그림이 실린다).
    경고 한 줄 없이 HTML 은 `figures 5` 라고 적었다.

    NFC 로 모으고 casefold 로 접는다 — 리눅스(대소문자를 가리는 FS)에서는 필요 이상으로
    엄한 셈이지만, 넘치게 잡으면 이름을 하나 바꾸면 되고 모자라면 그림이 사라진다.
    """
    return unicodedata.normalize('NFC', str(code)).casefold()


def _is_color(c):
    return isinstance(c, str) and re.fullmatch(r'#[0-9A-Fa-f]{6}', c.strip()) is not None


def _prefix(name, depth=2):
    """테이블명 접두어. depth=2 면 order_item_options → order_item, 1 이면 order."""
    parts = name.split('_')
    return '_'.join(parts[:depth]) if len(parts) > depth else parts[0]


def _split(tables, schema_name, max_areas, min_size=3):
    """테이블을 이름 접두어로 묶어 영역 후보를 만든다.

    좁은 접두어(2토큰)로 먼저 묶고, 거기서 남은 것들을 넓은 접두어(1토큰)로 한 번 더
    묶는다. 두 번 묶는 이유는 한 번만 하면 '기타' 가 비대해지기 때문이다 — 80개
    테이블에서 39개가 기타로 몰리면 그 영역은 세로로 한없이 길어져 못 쓴다.

    max_areas 는 **이 스키마가 쓸 수 있는 영역 수 전부** 다 — '기타' 도 그 안에 든다.
    예전엔 '기타' 를 상한 밖에 두어, 상한 4 를 적으면 스키마 하나에서도 5개가 나왔다.

    반환: [(영역명, [테이블…]), …]  — 길이는 언제나 1 이상 max_areas 이하
    """
    keep, rest = [], list(tables)
    for depth in (2, 1):
        groups = {}
        for t in rest:
            groups.setdefault(_prefix(t, depth), []).append(t)
        rest = []
        for gname, gts in sorted(groups.items(), key=lambda kv: -len(kv[1])):
            same = next((k for k in keep if k[0] == gname), None)
            if same:                     # 넓은 접두어가 앞 라운드와 같은 이름이 되면 합친다
                same[1].extend(gts)      # (feature_standard + feature → feature 하나로)
            elif len(gts) >= min_size and len(keep) < max_areas:
                keep.append((gname, list(gts)))
            else:
                rest += gts
        if not rest:
            break

    if rest:
        # '기타' 가 자리를 차지하려면 가장 작은 묶음을 도로 내놓는다. 그러지 않으면
        # 상한을 한 칸 넘긴다 — 영역 수가 곧 문서의 목차라 4를 적은 사람에게 5장이 간다.
        while keep and len(keep) >= max_areas:
            rest += keep.pop()[1]
        keep.append((T('word.area_other', schema=schema_name), sorted(rest)))
    return keep or [(schema_name, sorted(tables))]


# spec 에서 아는 최상위 키와, 그 키가 어떤 모양이어야 하는지.
# 이 목록이 곧 '아는 키' 다 — 여기 없는 키는 오타로 보고 이름을 대어 알린다.
_SPEC_SHAPE = {
    'areas':        (list, '[[code, name, schema, [table, …]], …]'),
    'layers':       (dict, '{code: [fill, header, border, label]}'),
    'layer_labels': (dict, '{code: label}'),
    'layer_of':     (dict, '{table: layer code}'),
    'roles':        (dict, '{table: role name}'),
    'derives':      (list, '[[from, to, label], …]'),
    'doc':          (dict, '{"title": …, "subtitle": …, …}'),
}


def _jtype(v):
    """JSON 이 부르는 이름으로 무엇이 왔는지 말한다."""
    if isinstance(v, bool):
        return 'a boolean'
    return {dict: 'an object', list: 'an array', str: 'a string', int: 'a number',
            float: 'a number', type(None): 'null'}.get(type(v), type(v).__name__)


def _spec_bad(key, got):
    raise SystemExit(T('err.spec_type', path=_get('SPEC_JSON'), key=key,
                       want=_SPEC_SHAPE[key][1], got=_jtype(got)))


def _spec_val(spec, key):
    """spec 의 키 하나 — 모양이 다르면 **키 이름과 기대 모양을 대고** 멈춘다.

    4라운드가 이 자리를 고치면서 areas 에만 손댔다. 그래서 `"roles": "users"` 는
    `ValueError: dictionary update sequence element #0 has length 1` 로,
    `"layer_of": ["orders"]` 는 같은 부류로, `"doc": [1,2]` 는 저 멀리 build_erd 의
    `AttributeError` 로 나왔다. 아는 키는 전부 같은 자리에서 같은 말로 답한다.
    """
    want, _shape = _SPEC_SHAPE[key]
    v = spec.get(key)
    if v is None:
        return want()
    if not isinstance(v, want):
        _spec_bad(key, v)
    return v


def _clean_deep(v):
    """spec 이 실어 오는 문자열을 전부 clean() 에 통과시킨다.

    clean() 이 있는 이유를 적은 주석이 "수기 사전과 손으로 고친 schema.json 은 안
    걸린다" 였는데, 정작 **가장 손으로 쓰는 파일인 spec** 이 그 그물 밖이었다.
    `roles` 의 개행 하나로 PIL 이 폭을 못 재 그림이 0장이 됐고, `doc.subtitle` 의
    \\x0b 하나로 docx 가 lxml 에서 죽었다 — 같은 입력에 HTML 만 살아남아, 한 바이트로
    무엇이 나오고 무엇이 안 나오는지가 갈렸다.
    """
    if isinstance(v, str):
        return clean(v)
    if isinstance(v, dict):
        return {(clean(k) if isinstance(k, str) else k): _clean_deep(x)
                for k, x in v.items()}
    if isinstance(v, list):
        return [_clean_deep(x) for x in v]
    return v


MAX_AREAS_DEFAULT = 12


def _max_areas():
    """ERD_MAX_AREAS — 못 읽으면 **말하고** 기본값으로 간다.

    예전 판은 `int(raw) if raw.strip().lstrip('-').isdigit() else 12` 였다. 셋이
    한꺼번에 걸린다: `abc`·`3.5`·`1e3` 은 아무 말 없이 12 가 되고(사용자는 제가 적은
    값이 쓰인 줄 안다), `lstrip('-')` 때문에 `--5` 와 `²` 는 검사를 통과해 바로 다음
    `int()` 에서 raw ValueError 로 죽고, `0`·`-3` 은 max(1,…) 에 눌려 1 이 되는데
    그것도 말이 없었다.
    """
    raw = os.environ.get('ERD_MAX_AREAS', '')
    if not raw.strip():
        return MAX_AREAS_DEFAULT
    try:
        n = int(raw.strip())
    except ValueError:
        print(T('log.env_not_number', env='ERD_MAX_AREAS', value=raw,
                default=MAX_AREAS_DEFAULT))
        return MAX_AREAS_DEFAULT
    if n < 1:
        print(T('log.env_clamped', env='ERD_MAX_AREAS', value=n, used=1))
        return 1
    return n


def _free_code(used):
    """아직 안 쓴 영역 코드 하나. spec 이 A·B 를 이미 썼으면 그 뒤부터 고른다.

    '안 썼다' 는 `_code_key` 로 판정한다. 예전엔 `_code(i) in used` 였는데, `_code` 는
    언제나 대문자를 내놓고 spec 은 소문자를 적을 수 있다 — `'A' in {'a'}` 가 거짓이라
    '기타' 영역이 `A` 를 받아 갔고, macOS·Windows 에서 `erd_area_a.png` 와
    `erd_area_A.png` 는 같은 파일이라 **Orders 영역 그림이 mart-other 그림으로 조용히
    덮였다.** 두 장을 그렸다고 찍고 한 장만 남는데 경고는 없었다.
    """
    keys = {_code_key(u) for u in used}
    i = 0
    while _code_key(_code(i)) in keys:
        i += 1
    used.add(_code(i))
    return _code(i)


def load_spec(schema):
    """erd.spec.json 을 읽고, 빠진 항목은 스키마·접두어로 자동 추론한다.

    반환: {areas, layers, layer_of, roles, derives}
      areas    [[코드, 영역명, 스키마, [테이블…]], …]   그룹 박스 = 배치 단위
      layers   {코드: (fill, head, border, 라벨)}       색 = 레이어
      layer_of {테이블: 레이어코드}
      roles    {테이블: 한글 역할명}
      derives  [[원천, 대상, 라벨], …]                  ETL 흐름 (FK 아님)
    """
    spec_json = _get('SPEC_JSON')
    # 인코딩을 안 주면 로케일이 정한다 — ascii 로케일(LC_ALL=C)이나 cp949 에서는
    # 한글이 든 spec 이 읽는 자리에서 죽었다. 이 파일들은 언제나 utf-8 로 쓰므로
    # (merge_schemas·introspect·parse_ddl) 읽기도 utf-8 로 못 박는다.
    #
    # 그리고 여기서 날 수 있는 실패는 JSONDecodeError 만이 아니다. utf-8 이 아닌
    # 파일이면 UnicodeDecodeError 가, 권한이 없거나 읽는 도중 사라지면 OSError 가
    # **raw 트레이스백**으로 나갔다 — 사용자는 제 변수 이름 대신 파이썬의 말을 봤다.
    # as_dir·as_file·_psql_words·_max_areas 가 줄곧 없애 온 그 모양이다. 같은 대우를
    # 한다: 변수 이름을 대고 멈춘다. (spec 경로는 기본값일 수도 있지만, 그때도 이
    # 자리를 옮길 수 있는 손잡이는 ERD_SPEC 하나뿐이다 — as_file 이 쓰는 방식과 같다.)
    try:
        spec = json.loads(spec_json.read_text(encoding='utf-8')) if spec_json.exists() else {}
    except json.JSONDecodeError as e:
        raise SystemExit(T('err.spec_json', path=spec_json, err=e))
    except (UnicodeDecodeError, OSError) as e:
        raise SystemExit(T('err.env_bad', env='ERD_SPEC', value=spec_json, why=e))
    if not isinstance(spec, dict):
        raise SystemExit(T('err.spec_root', path=spec_json, got=_jtype(spec)))
    # 아는 키 목록에 없는 최상위 키는 오타로 본다. 예전엔 `areas` 를 `area` 로 적으면
    # spec 이 통째로 없는 것과 같아져 자동 추론이 대신 나왔는데, 화면에는 한 글자도
    # 안 알렸다. `_` 로 시작하는 키는 주석이다 (examples/*.spec.json 이 쓴다).
    unknown = [str(k) for k in spec if not str(k).startswith('_') and k not in _SPEC_SHAPE]
    if unknown:
        print(T('log.spec_unknown', n=len(unknown), list=', '.join(sorted(unknown)[:6]),
                known=', '.join(sorted(_SPEC_SHAPE))))
    tables = [t for t in schema if not excluded(t)]

    # ── 그룹 나누기: 스키마 → (테이블이 많으면) 접두어 ──
    if _spec_val(spec, 'areas'):
        # spec 은 사람이 손으로 쓴다. 오타 하나에 traceback 을 뱉는 대신, 무엇이
        # 이상한지 말해 주고 그릴 수 있는 만큼 그린다.
        areas, seen, missing, dup, empty = [], set(), [], [], []
        codes = {}                 # _code_key → 그 이름을 먼저 가져간 코드 원문
        for raw in spec['areas']:
            if not isinstance(raw, (list, tuple)):
                _spec_bad('areas', raw)
            a = (list(raw) + ['', '', '', []])[:4]
            if a[3] and not isinstance(a[3], (list, tuple)):
                _spec_bad('areas', raw)
            code, name = clean(a[0]), clean(a[1])
            # 영역 코드는 erd_area_<코드>.png 라는 **파일 이름**이 된다. `x/y` 를 적으면
            # 없는 디렉토리에 쓰려다 PIL 이 `FileNotFoundError` 로 죽어 그 뒤 산출물이
            # 통째로 사라진다 — 자동 생성 코드(_code)가 '[' 를 피하는 것과 같은 이유다.
            # 손으로 적는 쪽만 그 검사 밖에 있었다.
            if _BAD_NAME.search(code):
                raise SystemExit(T('err.env_name', env=f'{spec_json}: area code',
                                   value=code, safe=safe_name(code) or 'A'))
            # 두 영역이 **같은 파일 이름이 될** 코드를 적으면 여기서 멈춘다. 예전엔
            # 그대로 지나가서 erd_area_<코드>.png 두 장이 서로 덮어썼고 — 뒤에 그린 것만
            # 남는데 화면에는 두 장을 그렸다고 찍혔다. 'A' 와 'a' 처럼 파이썬으로는
            # 다르지만 macOS·Windows 에서는 같은 이름인 짝이 특히 조용했다.
            # 그리는 도중에 알아서는 늦다 — 앞의 산출물이 이미 지워진 뒤다.
            key = _code_key(code)
            if key in codes:
                raise SystemExit(T('err.spec_dup_code', path=spec_json,
                                   code=code, other=codes[key],
                                   file=f'erd_area_{code}.png'))
            codes[key] = code
            sch, ts = clean(a[2]) or 'public', list(a[3] or [])
            ok = []
            for t in ts:
                if not isinstance(t, str):   # 테이블 이름이 아니면 (dict·list 는 곧
                    _spec_bad('areas', raw)  # unhashable 이라 `in` 에서 죽는다)
                if t not in schema:
                    missing.append(t)
                elif t in seen:
                    dup.append(t)          # 한 테이블을 두 영역에 두면 문서에 두 번 나온다
                else:
                    seen.add(t)
                    ok.append(t)
            if ok:
                areas.append([code, name, sch, ok])
            else:
                empty.append(str(code))
        if missing:
            print(T('log.spec_missing', n=len(missing), list=', '.join(missing[:6])))
        if dup:
            print(T('log.spec_dup', n=len(dup), list=', '.join(dup[:6])))
        if empty:
            print(T('log.spec_empty', list=', '.join(empty[:6])))
        if not areas:
            raise SystemExit(T('err.spec_no_area', path=spec_json))
        # ── 어느 영역에도 없는 테이블 ──
        # spec 쪽 오류 셋(missing·dup·empty)은 세어 말해 주면서 **네 번째 방향** 만
        # 빠져 있었다. 자리가 없는 테이블은 좌표가 안 생겨 erd.py 가 `pos[n]` 에서
        # KeyError 로 죽었고 — 경고 한 줄 없이 GraphML·PNG·SVG·HTML·docx 가 통째로
        # 0개가 됐다. SKILL.md 에 실린 예제(영역 하나짜리)가 바로 그 모양이다.
        # 이름을 대어 알리고, 남은 것을 '기타' 영역으로 받아 그림은 낸다.
        left = [t for t in tables if t not in seen]
        if left:
            print(T('log.spec_orphan', n=len(left), list=', '.join(left[:6])))
            # 테이블이 하나도 안 남아 버려진 영역의 코드도 이미 쓴 것으로 친다 —
            # 그 코드를 '기타' 에게 다시 내주면 사용자가 적은 이름과 그림이 어긋난다.
            used = set(codes.values())
            by_sch = {}
            for t in left:
                by_sch.setdefault(clean(schema[t].get('schema', 'public')) or 'public',
                                  []).append(t)
            for sch, ts in sorted(by_sch.items()):
                areas.append([_free_code(used), T('word.area_other', schema=sch),
                              sch, sorted(ts)])
        # ERD_MAX_AREAS 는 **자동 분류에만** 거는 상한이다 (아래 else 가지). spec 이
        # 손으로 적은 영역은 그 상한과 무관하게 전부 그린다 — 사용자가 이름까지 적어
        # 둔 절을 말없이 버리는 것이 더 나쁘다. 다만 상한을 적어 둔 사람에게는
        # **그 수가 안 지켜진다는 사실**을 말한다. 예전엔 한 글자도 안 나왔고,
        # 거기에 '기타' 영역까지 얹혀 상한 1 에 영역 3개가 나왔다.
        if os.environ.get('ERD_MAX_AREAS', '').strip():
            cap = _max_areas()      # 한 번만 부른다 — 못 읽은 값의 경고가 두 번 찍힌다
            if len(areas) > cap:
                print(T('log.max_areas_spec', env='ERD_MAX_AREAS', value=cap,
                        n=len(areas), path=spec_json))
    else:
        by_schema = {}
        for t in tables:
            by_schema.setdefault(schema[t].get('schema', 'public'), []).append(t)
        areas = []
        max_areas = _max_areas()
        # 상한은 문서 전체 기준이다 — 스키마마다 따로 세면 스키마가 셋일 때
        # 상한 4 가 12 개가 되어 버린다. 단 스키마를 통째로 버릴 수는 없으므로
        # 스키마마다 한 영역은 반드시 남긴다. 그래서 실제 하한은 스키마 개수다.
        todo = sorted(by_schema.items())
        for i, (sch, ts) in enumerate(todo):
            later = len(todo) - i - 1             # 뒤에 올 스키마도 한 자리씩은 가져간다
            if len(ts) <= 8:                      # 작은 스키마는 통째로 한 영역
                areas.append([_code(len(areas)), sch, sch, sorted(ts)])
                continue
            room = max(1, max_areas - len(areas) - later)
            for gname, gts in _split(ts, sch, room):
                areas.append([_code(len(areas)), gname, sch, sorted(gts)])

    # ── 레이어(색): 명시 없으면 영역 단위로 배정 ──
    # 레이어 코드는 그림 안(GraphML 설명)에도 그대로 실린다 — 양쪽을 같은 규칙으로
    # 씻어야 spec 이 적은 코드와 여기서 만든 코드가 계속 맞는다.
    layer_of = {k: clean(v) for k, v in _spec_val(spec, 'layer_of').items()}
    if not layer_of:
        for a in areas:
            for t in a[3]:
                layer_of[t] = a[0]
    labels = {clean(k): clean(v) for k, v in _spec_val(spec, 'layer_labels').items()}
    keys, layers = [], {}
    for a in areas:
        k = layer_of.get(a[3][0], a[0]) if a[3] else a[0]
        if k not in keys:
            keys.append(k)
    for i, k in enumerate(keys):
        c = PALETTE[i % len(PALETTE)]
        label = next((a[1] for a in areas if layer_of.get(a[3][0] if a[3] else '') == k), k)
        layers[k] = (*c, labels.get(k, label))
    for k, v in _spec_val(spec, 'layers').items():
        # 색이 하나라도 이상하면 PIL 이 알 수 없는 색이라며 죽는다. HTML 쪽은 그대로
        # style 에 박아 버려 더 나쁘다 — 여기서 막는다.
        if not isinstance(v, (list, tuple)):
            raise SystemExit(T('err.spec_layer', key=k, value=v))
        v = [clean(x) if isinstance(x, str) else x for x in v]
        if len(v) < 4 or not all(_is_color(c) for c in v[:3]):
            raise SystemExit(T('err.spec_layer', key=k, value=v))
        layers[clean(k)] = tuple(v[:4])

    # ── 역할명: spec → DB 테이블 코멘트 → 빈값 ──
    roles = {k: clean(v) for k, v in _spec_val(spec, 'roles').items()}
    for t in tables:
        roles.setdefault(t, clean(schema[t].get('note', '')))

    derives = []
    for x in _spec_val(spec, 'derives'):
        # `"derives": "ab"` 는 죽지도 않고 [["a"],["b"]] 라는 쓰레기를 만든 뒤,
        # 한참 뒤에 엉뚱한 KeyError 로 나왔다.
        if not isinstance(x, (list, tuple)):
            _spec_bad('derives', x)
        derives.append([clean(v) if isinstance(v, str) else v for v in x])

    return {
        'areas': areas,
        'layers': layers,
        'layer_of': layer_of,
        'roles': roles,
        'derives': derives,
        'doc': _clean_deep(_spec_val(spec, 'doc')),
    }
