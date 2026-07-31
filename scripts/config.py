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


def _p(env, default):
    return Path(os.environ.get(env, default)).expanduser()


PROJ = _p('ERD_PROJ', Path.cwd())
WORK = _p('ERD_WORK', PROJ / 'erd-build')
WORK.mkdir(parents=True, exist_ok=True)
OUT = WORK / 'out'
OUT.mkdir(exist_ok=True)

SCHEMA_JSON = WORK / 'schema.json'
SPEC_JSON = _p('ERD_SPEC', WORK / 'erd.spec.json')
SQL_DIR = _p('ERD_SQL_DIR', PROJ / 'sql')
MODEL_DIR = _p('ERD_MODEL_DIR', PROJ / 'models')

DOCNAME = os.environ.get('ERD_DOCNAME', 'ERD')
SCHEMAS = [s.strip() for s in os.environ.get('ERD_SCHEMAS', 'public').split(',') if s.strip()]
EXCLUDE = os.environ.get('ERD_EXCLUDE', '')


def psql_cmd():
    """psql 실행 명령. ERD_PSQL 이 있으면 그것을, 없으면 docker exec 를 쓴다."""
    if os.environ.get('ERD_PSQL'):
        return shlex.split(os.environ['ERD_PSQL'])
    db = os.environ.get('ERD_DB', '')
    if not db:
        raise SystemExit(
            'DB 접속 정보가 없다. 둘 중 하나를 지정할 것.\n'
            "  export ERD_PSQL='psql postgresql://user:pass@host:5432/dbname'\n"
            "  export ERD_DB='컨테이너:계정:DB'        # docker 경유")
    container, user, name = (db.split(':') + ['', '', ''])[:3]
    return ['docker', 'exec', container, 'psql', '-U', user, '-d', name]


SEP = '\x1f'          # 구분자. | 는 기본값·코멘트에 섞여 나와 쓸 수 없다


def psql(query):
    """DB 조회 — 결과를 SEP 구분 문자열로 돌려준다. 실패하면 빈 문자열."""
    r = subprocess.run(psql_cmd() + ['-tA', '-F', SEP, '-c', query],
                       capture_output=True, text=True)
    if r.returncode != 0 and not r.stdout:
        print(f'  [경고] DB 조회 실패: {r.stderr.strip()[:200]}')
    return r.stdout


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


def _prefix(name):
    """테이블명 접두어 — 첫 두 토큰까지 본다 (order_item_options → order_item)."""
    parts = name.split('_')
    return '_'.join(parts[:2]) if len(parts) > 2 else parts[0]


def load_spec(schema):
    """erd.spec.json 을 읽고, 빠진 항목은 스키마·접두어로 자동 추론한다.

    반환: {areas, layers, layer_of, roles, derives}
      areas    [[코드, 영역명, 스키마, [테이블…]], …]   그룹 박스 = 배치 단위
      layers   {코드: (fill, head, border, 라벨)}       색 = 레이어
      layer_of {테이블: 레이어코드}
      roles    {테이블: 한글 역할명}
      derives  [[원천, 대상, 라벨], …]                  ETL 흐름 (FK 아님)
    """
    spec = json.loads(SPEC_JSON.read_text()) if SPEC_JSON.exists() else {}
    tables = [t for t in schema if not excluded(t)]

    # ── 그룹 나누기: 스키마 → (테이블이 많으면) 접두어 ──
    if spec.get('areas'):
        areas = [list(a) for a in spec['areas']]
    else:
        by_schema = {}
        for t in tables:
            by_schema.setdefault(schema[t].get('schema', 'public'), []).append(t)
        areas, code = [], ord('A')
        max_areas = int(os.environ.get('ERD_MAX_AREAS', 7))
        for sch, ts in sorted(by_schema.items()):
            if len(ts) <= 8:                      # 작은 스키마는 통째로 한 영역
                areas.append([chr(code), sch, sch, sorted(ts)])
                code += 1
                continue
            groups = {}
            for t in ts:
                groups.setdefault(_prefix(t), []).append(t)
            # 큰 그룹부터 살리고, 작은 것들(2개 이하)과 상한 초과분은 '기타' 로 합친다
            ordered = sorted(groups.items(), key=lambda kv: -len(kv[1]))
            keep, rest = [], []
            for gname, gts in ordered:
                if len(gts) >= 3 and len(keep) < max_areas:
                    keep.append((gname, gts))
                else:
                    rest += gts
            if rest:
                keep.append((f'{sch} 기타', sorted(rest)))
            if not keep:
                keep = [(sch, sorted(ts))]
            for gname, gts in keep:
                areas.append([chr(code), gname, sch, sorted(gts)])
                code += 1

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
        layers[k] = tuple(v)

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
