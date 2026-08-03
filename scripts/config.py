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
"""
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

from i18n import t as T


def _p(env, default):
    return Path(os.environ.get(env, default)).expanduser()


PROJ = _p('ERD_PROJ', Path.cwd())
PROJ.mkdir(parents=True, exist_ok=True)     # 없는 경로를 줬다고 마지막 단계에서 죽지 않게
WORK = _p('ERD_WORK', PROJ / 'erd-build')
WORK.mkdir(parents=True, exist_ok=True)
OUT = WORK / 'out'
OUT.mkdir(exist_ok=True)

SCHEMA_JSON = WORK / 'schema.json'
SPEC_JSON = _p('ERD_SPEC', WORK / 'erd.spec.json')
SQL_DIR = _p('ERD_SQL_DIR', PROJ / 'sql')
MODEL_DIR = _p('ERD_MODEL_DIR', PROJ / 'models')

def _docname():
    """파일명으로 쓸 수 있게 다듬는다.

    슬래시가 섞이면 어떤 스크립트는 죽고 어떤 스크립트는 하위 디렉토리를 만들어 엉뚱한
    자리에 쓴다. 빈 값이면 '.html' 같은 숨김 파일이 되어 찾지 못한다.
    """
    raw = os.environ.get('ERD_DOCNAME', '')
    name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', raw).strip('. ')
    return name or 'ERD'


DOCNAME = _docname()
SCHEMAS = [s.strip() for s in os.environ.get('ERD_SCHEMAS', 'public').split(',') if s.strip()]
EXCLUDE = os.environ.get('ERD_EXCLUDE', '')


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


def psql_cmd():
    """psql 실행 명령. ERD_PSQL 이 있으면 그것을, 없으면 docker exec 를 쓴다."""
    if os.environ.get('ERD_PSQL'):
        return shlex.split(os.environ['ERD_PSQL'])
    db = os.environ.get('ERD_DB', '')
    if not db:
        raise SystemExit(
            T('err.no_conn') + '\n'
            "  export ERD_PSQL='psql postgresql://user:pass@host:5432/dbname'\n"
            "  export ERD_DB=" + T('err.no_conn_db'))
    container, user, name = (db.split(':') + ['', '', ''])[:3]
    return ['docker', 'exec', container, 'psql', '-U', user, '-d', name]


SEP = '\x1f'          # 구분자. | 는 기본값·코멘트에 섞여 나와 쓸 수 없다
RS = '\x1e'           # 레코드 구분자. 개행으로 행을 가르면 값 속 개행이 가짜 행이 된다


class QueryFailed(RuntimeError):
    """조회를 끝까지 읽지 못했다.

    부분 결과를 참으로 받아들이면 반쯤 읽은 DB 가 완성된 문서로 나온다. 부르는 쪽이
    '못 읽었다' 와 '읽었더니 0 건이다' 를 구분할 수 있게 예외로 알린다.
    """


def _run(query, rs='\n'):
    """psql 을 한 번 돌린다. 실패는 **부분 출력이 있어도** 반드시 알린다.

    예전엔 `returncode != 0 and not r.stdout` 일 때만 경고했다. 그래서 몇 행 흘리고
    죽은 조회(문 타임아웃·서버 재기동)는 경고 한 줄 없이 지나갔다 — 21개 테이블이
    조용히 4개가 됐다.
    """
    r = subprocess.run(psql_cmd() + ['-tA', '-F', SEP, '-R', rs, '-c', query],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(T('log.query_fail', err=_why(r)))
    return r


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


def excluded(table):
    return bool(EXCLUDE) and re.search(EXCLUDE, table) is not None


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

    반환: [(영역명, [테이블…]), …]
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
        keep.append((T('word.area_other', schema=schema_name), sorted(rest)))
    return keep or [(schema_name, sorted(tables))]


def load_spec(schema):
    """erd.spec.json 을 읽고, 빠진 항목은 스키마·접두어로 자동 추론한다.

    반환: {areas, layers, layer_of, roles, derives}
      areas    [[코드, 영역명, 스키마, [테이블…]], …]   그룹 박스 = 배치 단위
      layers   {코드: (fill, head, border, 라벨)}       색 = 레이어
      layer_of {테이블: 레이어코드}
      roles    {테이블: 한글 역할명}
      derives  [[원천, 대상, 라벨], …]                  ETL 흐름 (FK 아님)
    """
    try:
        spec = json.loads(SPEC_JSON.read_text()) if SPEC_JSON.exists() else {}
    except json.JSONDecodeError as e:
        raise SystemExit(T('err.spec_json', path=SPEC_JSON, err=e))
    tables = [t for t in schema if not excluded(t)]

    # ── 그룹 나누기: 스키마 → (테이블이 많으면) 접두어 ──
    if spec.get('areas'):
        # spec 은 사람이 손으로 쓴다. 오타 하나에 traceback 을 뱉는 대신, 무엇이
        # 이상한지 말해 주고 그릴 수 있는 만큼 그린다.
        areas, seen, missing, dup, empty = [], set(), [], [], []
        for raw in spec['areas']:
            a = (list(raw) + ['', '', '', []])[:4]
            code, name, sch, ts = a[0], a[1], a[2] or 'public', list(a[3] or [])
            ok = []
            for t in ts:
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
            raise SystemExit(T('err.spec_no_area', path=SPEC_JSON))
    else:
        by_schema = {}
        for t in tables:
            by_schema.setdefault(schema[t].get('schema', 'public'), []).append(t)
        areas = []
        raw_max = os.environ.get('ERD_MAX_AREAS', '')
        max_areas = int(raw_max) if raw_max.strip().lstrip('-').isdigit() else 12
        for sch, ts in sorted(by_schema.items()):
            if len(ts) <= 8:                      # 작은 스키마는 통째로 한 영역
                areas.append([_code(len(areas)), sch, sch, sorted(ts)])
                continue
            # 상한은 문서 전체 기준이다 — 스키마마다 따로 세면 스키마가 셋일 때
            # 상한 4 가 12 개가 되어 버린다
            room = max(1, max_areas - len(areas))
            for gname, gts in _split(ts, sch, room):
                areas.append([_code(len(areas)), gname, sch, sorted(gts)])

    # ── 레이어(색): 명시 없으면 영역 단위로 배정 ──
    layer_of = dict(spec.get('layer_of', {}))
    if not layer_of:
        for a in areas:
            for t in a[3]:
                layer_of[t] = a[0]
    keys, layers = [], {}
    for a in areas:
        k = layer_of.get(a[3][0], a[0]) if a[3] else a[0]
        if k not in keys:
            keys.append(k)
    for i, k in enumerate(keys):
        c = PALETTE[i % len(PALETTE)]
        label = next((a[1] for a in areas if layer_of.get(a[3][0] if a[3] else '') == k), k)
        layers[k] = (*c, spec.get('layer_labels', {}).get(k, label))
    for k, v in (spec.get('layers') or {}).items():
        v = list(v)
        # 색이 하나라도 이상하면 PIL 이 알 수 없는 색이라며 죽는다. HTML 쪽은 그대로
        # style 에 박아 버려 더 나쁘다 — 여기서 막는다.
        if len(v) < 4 or not all(_is_color(c) for c in v[:3]):
            raise SystemExit(T('err.spec_layer', key=k, value=v))
        layers[k] = tuple(v[:4])

    # ── 역할명: spec → DB 테이블 코멘트 → 빈값 ──
    roles = dict(spec.get('roles', {}))
    for t in tables:
        roles.setdefault(t, schema[t].get('note', '') or '')

    return {
        'areas': areas,
        'layers': layers,
        'layer_of': layer_of,
        'roles': roles,
        'derives': [list(x) for x in spec.get('derives', [])],
        'doc': spec.get('doc', {}),
    }
