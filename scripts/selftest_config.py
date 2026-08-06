#!/usr/bin/env python3
"""config·spec·i18n·환경변수 회귀 시험.

    python3 selftest_config.py           여기 있는 것 전부
    python3 selftest_config.py spec:      이름에 'spec:' 이 든 것만

`selftest_kit.CASES` 에 등록된다 — `selftest.py` 를 돌리면 `load_extras()` 가 옆에
놓인 `selftest_*.py` 를 글로브로 찾아 오므로 세 파일이 한 벌로 돈다.

여기 담는 기준은 저쪽 둘과 같다 — **한 번이라도 조용히 깨졌던 것**. 이번 라운드의
것은 모양이 하나로 모인다: *사람이 손으로 적는 값*(환경변수 · erd.spec.json)이
틀렸을 때 코드가 무엇을 했는가. 셋 중 하나였다.

  · raw traceback 을 뱉었다        (사용자는 제 변수 이름 대신 파이썬 내부를 본다)
  · 조용히 다른 값으로 갔다        (껐는데 켜지고, 적은 숫자 대신 기본값이 쓰인다)
  · 아무 말 없이 아무것도 안 했다  (오타 난 spec 키, 접속 없는 ERD_DEFAULT_PK)

앞의 것은 눈에 띄기라도 하지만 뒤의 둘은 **틀린 문서가 완성된 얼굴로** 나온다.
"""
import json
import os
import re
import shlex
import subprocess
import sys
import unicodedata

from selftest_kit import (Fail, HERE, case, col, eq, has, main, run, table,
                          write_schema)


EXPECT_CASES = 31       # 등록 개수를 파일이 스스로 못박는다 (selftest_kit.load_extras)


def env_without_erd(**extra):
    """부르는 사람의 ERD_* 를 하나도 물려받지 않은 환경 (selftest_kit.run 과 같은 규칙)."""
    e = {k: v for k, v in os.environ.items() if not k.startswith('ERD_')}
    e['ERD_LANG'] = 'en'
    e.update({k: str(v) for k, v in extra.items()})
    return e


def py(code, args=(), env=None, cwd=None):
    """파이썬 조각 하나를 별도 프로세스로 돌린다 (cwd 를 내가 정해야 하는 케이스용)."""
    return subprocess.run([sys.executable, '-c', code, *[str(a) for a in args]],
                          capture_output=True, text=True, encoding='utf-8',
                          env=env or env_without_erd(), cwd=str(cwd or HERE))


def no_traceback(r, what):
    if 'Traceback' in r.stderr:
        raise Fail(f'{what}\n      {r.stderr[-500:]}')


def three(work):
    """SKILL.md 의 예제와 같은 모양 — 테이블 셋, 그중 둘만 spec 의 영역에 있다."""
    t = {n: table(n, [col('id')], pk=['id'])
         for n in ('users', 'orders', 'order_items')}
    t['order_items']['fks'] = [{'column': 'id', 'ref_table': 'orders',
                                'ref_column': 'id', 'on_delete': 'CASCADE'}]
    write_schema(work, t)
    return t


def spec(work, obj):
    (work / 'erd.spec.json').write_text(json.dumps(obj), encoding='utf-8')


def run_argv(script, work, args, env=None, expect_ok=True):
    """argv 를 받는 스크립트 하나 (`merge_schemas.py <라벨>…`).

    `selftest_kit.run` 은 인자를 붙일 자리가 없다 — 다른 것은 전부 그것과 같은 규칙으로
    맞춘다 (ERD_* 를 하나도 안 물려받고, ERD_WORK·ERD_PROJ 를 이 케이스의 자리로 준다).
    """
    e = env_without_erd(ERD_WORK=work, ERD_PROJ=work, ERD_DOCNAME='T')
    if env:
        e.update({k: str(v) for k, v in env.items()})
    r = subprocess.run([sys.executable, str(HERE / script), *[str(a) for a in args]],
                       capture_output=True, text=True, encoding='utf-8', env=e, cwd=str(HERE))
    if expect_ok and r.returncode != 0:
        raise Fail(f'{script} {args} exited {r.returncode}\n{r.stdout}\n{r.stderr}')
    return r


# ── spec ────────────────────────────────────────────────────────────────────

@case('spec: a table named in no area is placed, not a KeyError')
def _(work):
    # 14라운드. load_spec 은 spec 쪽 오류 셋(missing·dup·empty)을 세어 말해 주면서
    # **네 번째 방향** 만 빠뜨렸다 — 스키마에 있는데 어느 영역에도 없는 테이블.
    # 그 테이블은 좌표가 안 생겨 erd.py 의 `pos[n]` 이 KeyError 로 죽었고, 경고 한 줄
    # 없이 GraphML·PNG·SVG·HTML·docx 가 **통째로 0개**가 됐다. SKILL.md 에 실린
    # 예제(영역 하나짜리 spec)가 바로 그 모양이라, 문서대로 따라 한 사람이 걸렸다.
    three(work)
    spec(work, {'areas': [['A', 'Orders', 'public', ['orders', 'order_items']]]})
    r = run('build_erd.py', work)
    has(r.stdout, 'users', 'the table that no area names is named on screen')

    import xml.etree.ElementTree as ET
    NS = {'g': 'http://graphml.graphdrawing.org/xmlns'}
    nodes = ET.parse(work / 'T.graphml').getroot().findall('.//g:node', NS)
    eq(len(nodes), 3, 'all three tables reach the GraphML — the odd one is placed, not dropped')
    if not (work / 'out' / 'erd_full.png').exists():
        raise Fail('the drawing must still come out — 0 artifacts was the bug')
    # 받아 준 자리가 이미 쓰인 코드를 덮어써서도 안 된다 (spec 이 A 를 썼다)
    pngs = sorted(p.name for p in (work / 'out').glob('erd_area_*.png'))
    eq(len(pngs), 2, f'the leftovers get their own area, next to the spec ones: {pngs}')
    if 'erd_area_A.png' not in pngs:
        raise Fail(f"the area the spec named must keep its own code: {pngs}")


@case('spec: a key of the wrong type is explained for every key, not just areas')
def _(work):
    # 4라운드가 이 자리를 고치면서 `areas` 에만 손댔다. 같은 파일의 나머지 키는 그대로라
    # 사람 말 대신 파이썬 내부가 나왔다:
    #   "roles": "users"      → ValueError: dictionary update sequence element #0 …
    #   "layer_of": ["orders"] → 같은 부류
    #   "doc": [1,2]          → 저 멀리 build_erd.py 의 AttributeError
    #   "derives": "ab"       → 죽지도 않고 [["a"],["b"]] 를 만든 뒤 엉뚱한 KeyError
    # **반만 고친 수정**의 표본이라 네 키를 한 케이스에서 함께 못박는다.
    three(work)
    for key, bad in (('roles', 'users'), ('layer_of', ['orders']),
                     ('doc', [1, 2]), ('derives', 'ab'),
                     ('areas', 'orders'), ('layers', 'TX'),
                     ('roles', {'users': ['not', 'a role']}),
                     ('layer_of', {'users': ['not', 'a code']}),
                     ('layer_labels', {'TX': 42})):
        spec(work, {key: bad})
        r = run('build_erd.py', work, expect_ok=False)
        no_traceback(r, f'a {key} of the wrong type must be a message, not a traceback')
        has(r.stdout + r.stderr, key, f'the message names the key ({key})')
        if (work / 'out' / 'erd_full.png').exists():
            raise Fail(f'a spec that cannot be read must not leave a drawing ({key})')
    # 뿌리도 같은 자리에서 답한다 — spec 이 통째로 배열이면 첫 .get() 에서 죽었다
    (work / 'erd.spec.json').write_text('[1, 2]', encoding='utf-8')
    r = run('build_erd.py', work, expect_ok=False)
    no_traceback(r, 'a spec that is not an object must be a message too')
    has(r.stdout + r.stderr, 'areas', 'and it says what the file should have looked like')


@case('spec: a misspelled top-level key is named, not silently dropped')
def _(work):
    # 아는 키 일곱만 .get() 으로 집고 나머지는 존재조차 안 봤다. `areas` 를 `area` 로
    # 적으면 **spec 이 통째로 없는 것과 같아지고** 자동 추론이 대신 나오는데, 화면에는
    # 한 글자도 안 알렸다 — 사람은 제가 적은 영역이 쓰인 줄 안다.
    three(work)
    spec(work, {'_comment': 'examples/*.spec.json 이 쓰는 주석',
                'area': [['A', 'Orders', 'public', ['orders']]],
                'role': {'orders': 'x'}, 'derive': []})
    r = run('build_erd.py', work)
    for typo in ('area', 'role', 'derive'):
        has(r.stdout, typo, f'the misspelled key is named ({typo})')
    if '_comment' in r.stdout:
        raise Fail('a key starting with _ is a comment — warning about it makes noise')
    # 아는 키만 적은 spec 은 조용해야 한다. 안 그러면 경고가 소음이 되어 죽는다.
    spec(work, {'areas': [['A', 'Orders', 'public', ['users', 'orders', 'order_items']]],
                'layer_of': {}, 'layers': {}, 'layer_labels': {}, 'roles': {},
                'derives': [], 'doc': {}})
    r = run('build_erd.py', work)
    if 'not known' in r.stdout:
        raise Fail(f'a spec that uses only known keys must not warn:\n{r.stdout}')


@case('spec: an area code that cannot be a file name is refused, not written into a '
      'directory that is not there')
def _(work):
    # C1·C7 과 같은 부류를 훑다 나온 것이다. 영역 코드는 그림 파일 이름
    # (erd_area_<코드>.png) 이 되는데, 자동 생성 코드(_code)는 26개를 넘길 때 '[' 나
    # '\\' 가 나오지 않게 이미 조심하고 있었다 — **손으로 적는 spec 쪽만** 그 검사
    # 밖이었다. `"areas": [["x/y", …]]` 하나면 PIL 이 없는 디렉토리에 쓰려다
    # FileNotFoundError 로 죽고, 그 뒤 도판·문서가 통째로 사라진다.
    three(work)
    spec(work, {'areas': [['x/y', 'All', 'public', ['users', 'orders', 'order_items']]]})
    r = run('build_erd.py', work, expect_ok=False)
    no_traceback(r, 'an area code with a separator must be a message, not a PIL traceback')
    has(r.stdout + r.stderr, 'x/y', 'the offending code is shown')
    for stray in work.rglob('erd_area_*'):
        raise Fail(f'nothing may be half-written under a made-up path: {stray}')
    # 쓸 수 있는 코드는 그대로 지나간다
    spec(work, {'areas': [['A.1', 'All', 'public', ['users', 'orders', 'order_items']]]})
    run('build_erd.py', work)
    if not (work / 'out' / 'erd_area_A.1.png').exists():
        raise Fail('a code that is merely unusual must still draw — this check only '
                   'refuses what cannot be a file name')


@case('spec: a newline or control character in a spec string does not kill any builder')
def _(work):
    # 4라운드가 schema.json 쪽에서 고친 것과 **정확히 같은 결함**이 spec 경로에 남아
    # 있었다. clean() 이 있는 이유를 적은 주석은 "수기 사전과 손으로 고친 schema.json
    # 은 안 걸린다" 였는데, 정작 **가장 손으로 쓰는 파일인 spec** 이 그 그물 밖이었다.
    #   roles 에 개행 하나   → build_erd.py exit 1 (PIL: can't measure multiline text)
    #   doc.subtitle 에 \x0b → build_docx.py exit 1 (All strings must be XML compatible)
    # 같은 입력에서 build_html.py 만 살아남았다 — 한 바이트로 무엇이 나오고 무엇이
    # 안 나오는지가 갈렸다. 그래서 **네 산출물을 한 번에** 지나가게 한다.
    #
    # 15R. 14라운드 판은 `roles`·`layer_labels`·`doc` 만 물었다. 같은 파일의 나머지
    # 세 자리 — **영역 이름**, **layers 의 키**, **derives 의 문자열** — 는 그물 밖이라,
    # 그 셋의 clean() 을 하나씩 되돌려도 141개가 전부 초록이었다. 셋 다 산출물에
    # 그대로 실리는 값이다:
    #   영역 이름  → docx 4장 절 제목 · html 절 제목   (되돌리면 docx rc 1)
    #   layers 키  → docx 레이어 범례 표의 첫 칸        (되돌리면 docx rc 1)
    #   derives 라벨 → graphml 엣지 라벨 · docx 5장 표  (되돌리면 VT 가 그대로 실린다)
    three(work)
    spec(work, {'areas': [['A', 'All\x0bof it', 'public', ['orders', 'order_items']],
                          ['B', 'Sec\x0bond', 'public', ['users']]],
                'roles': {'users': 'member\naccount', 'orders': 'role\x0bvt'},
                'layers': {'B\x0b': ['#3E3226', '#5E4732', '#B0885A', 'sec\x0bcolor']},
                'layer_labels': {'A': 'lay\x0ber'},
                'derives': [['orders', 'users', 'der\x0bives']],
                'doc': {'title': 'ti\ntle', 'subtitle': 'sub\x0bvt',
                        'area_desc': {'A': 'desc\x0bhere'}}})
    run('merge_desc.py', work)
    run('build_erd.py', work)
    run('build_html.py', work)
    run('build_docx.py', work)
    import zipfile
    html = (work / 'T.html').read_text(encoding='utf-8')
    graphml = (work / 'T.graphml').read_text(encoding='utf-8')
    with zipfile.ZipFile(work / 'T.docx') as z:
        docx = z.read('word/document.xml').decode('utf-8')
    for name, text in (('html', html), ('graphml', graphml), ('docx', docx)):
        if '\x0b' in text:
            raise Fail(f'a control character reached the {name} — yEd and lxml refuse it')
    has(html, 'member account', 'the newline in a role became one space, not a lost table')
    has(html, 'desc here', 'and doc strings pass through the same sieve')
    has(docx, 'sub vt', 'the subtitle only docx prints is cleaned too')
    has(graphml, 'lay er', 'so is a layer label')
    has(docx, 'All of it', 'an area name is cleaned before it becomes a chapter heading')
    has(docx, 'sec color', 'and so is a layer the spec spells out by hand')
    has(graphml, 'der ives', 'and the label on an ETL arrow')
    has(docx, 'der ives', 'which docx lists in its own chapter')


@case('spec: a table name that is not a string is a message, not an unhashable TypeError')
def _(work):
    # 15R. 4라운드가 '오타 하나에 raw traceback' 을 고쳤고, 14라운드가 areas 안
    # **테이블 자리**에도 그 검사를 달았다. 그런데 그 검사를 지워도 141개가 전부
    # 초록이었다 — 지키는 항목이 하나도 없었다. 지우면 이렇게 된다:
    #   {"areas":[["A","x","public",[{"a":1}]]]} → TypeError: unhashable type: 'dict'
    # `t not in schema` 가 dict·list 를 해시하려다 죽는 자리다. 사용자는 제가 잘못
    # 적은 줄 대신 파이썬 내부를 본다.
    for i, bad in enumerate(([{'a': 1}], [['orders']], [{'a': 1}, 'orders'], [None])):
        w = work / f'bad{i}'
        three(w)
        spec(w, {'areas': [['A', 'x', 'public', bad]]})
        r = run('build_erd.py', w, expect_ok=False)
        no_traceback(r, f'a table entry of {bad!r} must be a message, not a traceback')
        has(r.stdout + r.stderr, 'areas', f'the message names the key ({bad!r})')
        if (w / 'out' / 'erd_full.png').exists():
            raise Fail(f'a spec that cannot be read must not leave a drawing ({bad!r})')
    # 제대로 적은 것은 그대로 지나간다 — 막기만 하는 검사는 고친 것이 아니다
    w = work / 'ok'
    three(w)
    spec(w, {'areas': [['A', 'x', 'public', ['users', 'orders', 'order_items']]]})
    run('build_erd.py', w)


@case('spec: two area codes that would write the same file name are refused')
def _(work):
    # 15R. 수정자 3이 14라운드에 "AREA_ID 가 하나로 합쳐지고 erd_area_<code>.png 도
    # 서로 덮어쓴다 — 뿌리가 spec 로더 쪽" 이라고 보고만 하고 넘어간 자리다.
    # 영역 코드는 **파일 이름**이 되므로 같은 이름이 될 코드 둘은 그림 한 장을
    # 지운다. 그리는 도중에 알아서는 늦다 — 앞의 산출물이 이미 지워진 뒤다.
    #   'A' 와 'A'   같은 글자
    #   'A' 와 'a'   macOS(APFS·HFS+)·Windows 에서 같은 파일
    #   'Ä' 와 'Ä'  macOS 에서 같은 파일 (유니코드 결합 형태)
    for i, (x, y) in enumerate((('A', 'A'), ('A', 'a'), ('Ä', 'Ä'))):
        w = work / f'dup{i}'
        three(w)
        spec(w, {'areas': [[x, 'One', 'public', ['orders', 'order_items']],
                           [y, 'Two', 'public', ['users']]]})
        r = run('build_erd.py', w, expect_ok=False)
        no_traceback(r, f'two areas coded {x!r}/{y!r} must be a message, not a traceback')
        has(r.stdout + r.stderr, x, f'the offending code is shown ({x!r})')
        stray = sorted(p.name for p in w.rglob('erd_area_*'))
        eq(stray, [], f'nothing may be half-drawn before the clash is told: {stray}')
    # 서로 다른 코드는 그대로 두 장을 낸다
    w = work / 'ok'
    three(w)
    spec(w, {'areas': [['A', 'One', 'public', ['orders', 'order_items']],
                       ['B', 'Two', 'public', ['users']]]})
    run('build_erd.py', w)
    eq(areas_drawn(w), 2, 'two areas with different codes still draw two diagrams')


@case('spec: an area code written in lower case keeps a diagram of its own')
def _(work):
    # 15R — **14라운드가 만든 것.** `_free_code` 가 `_code(i)`(언제나 대문자)만 `used`
    # 와 비교했다. spec 이 코드를 'a' 로 적으면 `'A' in {'a'}` 가 거짓이라 '기타'
    # 영역이 A 를 받아 갔고, macOS·Windows 에서 erd_area_a.png 와 erd_area_A.png 는
    # **같은 파일**이다:
    #   PNG  area a Orders (2 + 3 refs)     → erd_area_a.png  1806×1464
    #   PNG  area A mart other (2 + 1 refs) → erd_area_A.png  1534×1284
    #   PIL: erd_area_a.png → (1534, 1284)   ← Orders 그림이 남의 그림으로 덮였다
    # 문서의 'Orders' 절이 조용히 남의 영역 그림을 싣는다. HTML 은 `figures 5` 라고
    # 적었고 경고는 한 줄도 없었다. 이전 판에는 spec 분기에서 자동 코드가 아예 안
    # 생겨서 이 자리가 없었다.
    three(work)
    spec(work, {'areas': [['a', 'Orders', 'public', ['orders', 'order_items']]]})
    r = run('build_erd.py', work)
    announced = sorted(set(re.findall(r'erd_area_[^\s]+\.png', r.stdout)))
    eq(len(announced), 2, f'the leftovers get an area next to the spec one: {announced}')
    # ① 이름이 대소문자·유니코드 형태만 다르면 안 된다 (플랫폼과 무관한 규칙)
    folded = [unicodedata.normalize('NFC', n).casefold() for n in announced]
    eq(sorted(set(folded)), sorted(folded),
       f'two area diagrams may not differ only in case — on macOS and Windows that is '
       f'one file: {announced}')
    # ② 그리고 이 파일시스템에서 실제로 announced 만큼 남아야 한다
    on_disk = sorted(p.name for p in (work / 'out').glob('erd_area_*.png'))
    eq(on_disk, announced, 'every area diagram the run announced is a file of its own')
    # ③ spec 이 적은 코드는 spec 것으로 남는다
    if 'erd_area_a.png' not in on_disk:
        raise Fail(f'the code the spec wrote must stay that area\'s: {on_disk}')


@case('spec: an area whose tables all vanished still keeps its code away from the '
      'leftovers')
def _(work):
    # 16R. 15라운드가 `load_spec` 의 고아 처리에서 `used = {a[0] for a in areas}` 를
    # `used = set(codes.values())` 로 바꿨다 — **보고 어디에도 없던 동작 변경**이고,
    # 지키는 항목도 없었다. 되돌리면 이렇게 된다: spec 이 A 라고 이름 붙인 영역의
    # 테이블이 하나도 실재하지 않아 그 영역이 버려지면, `areas` 에는 A 가 없으므로
    # '기타' 영역이 **A 를 다시 받아 간다.** 화면과 문서는 그때부터 사용자가
    # 'Orders' 라고 적어 둔 코드로 남의 영역을 부른다 — 경고는 영역이 비었다는 줄
    # 하나뿐이고, 그 줄은 코드가 재활용됐다는 말을 하지 않는다.
    three(work)
    spec(work, {'areas': [['A', 'Orders', 'public', ['no_such_table']],
                          ['B', 'Users', 'public', ['users']]]})
    r = run('build_erd.py', work)
    has(r.stdout, 'no usable table', 'the area whose tables are all missing is reported')
    on_disk = sorted(p.name for p in (work / 'out').glob('erd_area_*.png'))
    eq(len(on_disk), 2, f'the spec area that survived, plus one for the leftovers: {on_disk}')
    if 'erd_area_A.png' in on_disk:
        raise Fail(f"the code the spec spent on 'Orders' must not come back as the "
                   f'leftovers area: {on_disk}')
    # 그리고 announced 와 실제 파일이 어긋나서도 안 된다 (`erd_area_a.png` 케이스와 같은 규칙)
    announced = sorted(set(re.findall(r'erd_area_[^\s]+\.png', r.stdout)))
    eq(on_disk, announced, 'every area diagram the run announced is a file of its own')
    # 버려진 영역이 없으면 예전 그대로 — 남는 코드부터 순서대로 받는다
    w = work / 'nodrop'
    three(w)
    spec(w, {'areas': [['A', 'Orders', 'public', ['orders', 'order_items']]]})
    run('build_erd.py', w)
    eq(sorted(p.name for p in (w / 'out').glob('erd_area_*.png')),
       ['erd_area_A.png', 'erd_area_B.png'],
       'a spec that wastes no code still hands the leftovers the next one')


# ── 환경변수 ────────────────────────────────────────────────────────────────

_FLAG_PROBE = '''\
import os, sys
sys.path.insert(0, os.environ['PROBE_SCRIPTS'])
import config
for raw in sys.argv[1:]:
    os.environ['ERD_PROBE'] = raw
    print(repr(raw), config.env_flag('ERD_PROBE', True),
          config.env_flag('ERD_PROBE', False))
'''


@case('config: every ERD_* boolean reads FALSE / No / off / "0 " the same as 0')
def _(work):
    # 다섯 자리가 저마다 `os.environ.get(...) not in ('0','false','no')` 를 적고 있었다.
    # 소문자 세 낱말만 끄므로 **껐는데 켜졌다**: ERD_HTML_SVG=False 로도, NO 로도,
    # off 로도 SVG 가 4개 박혔고, ERD_HTML_STATS='0 ' 은 공백 하나로 도로 켜졌다.
    # 같은 저장소의 ERD_STALE 은 .strip().lower() 를 하고 있었으니 코드가 제 안에서
    # 두 규칙을 썼다. 규칙을 config.env_flag 하나로 모으고 다섯이 그것을 쓴다.
    # 15R. **모르는 값**을 재는 자리가 없었다 — `return default` 를 `return True` 로
    # 바꾸면 `ERD_HTML_STATS=maybe` 가 기준 False 에서 True 로 넘어가는데 141개가
    # 전부 초록이었다. 오타 하나가 조용히 '켬' 이 되는 것이 이 함수가 막으려던 바로
    # 그것이라, 세 갈래(끔·켬·모름)를 한자리에서 못박는다.
    off = ('0', 'false', 'False', 'FALSE', 'no', 'No', 'NO', 'off', 'OFF', 'n',
           '0 ', ' 0', '  false  ', '')
    on = ('1', 'true', 'True', 'TRUE', 'yes', 'YES', 'on', 'ON', 'y', ' 1 ')
    unknown = ('maybe', 'flase', '2', '-1', 'null', 'None', 'ok')
    r = py(_FLAG_PROBE, off + on + unknown,
           env=env_without_erd(PROBE_SCRIPTS=str(HERE)))
    if r.returncode != 0:
        raise Fail(f'the probe did not run: {r.stderr[-400:]}')
    got = {}
    for line in r.stdout.splitlines():
        if line.startswith("'") or line.startswith('"'):
            raw, a, b = line.rsplit(' ', 2)
            got[raw] = (a == 'True', b == 'True')
    eq(len(got), len(off) + len(on) + len(unknown), 'the probe answered for every spelling')
    for raw in off:
        eq(got[repr(raw)], (False, False), f'{raw!r} is off whatever the default is')
    for raw in on:
        eq(got[repr(raw)], (True, True), f'{raw!r} is on whatever the default is')
    for raw in unknown:
        eq(got[repr(raw)], (True, False),
           f"{raw!r} is not a yes — a value nobody can read falls back to that variable's "
           f'own default, and says so')

    # 다섯 변수가 **그 규칙을 실제로 지나는지**. 모르는 값은 이름을 대어 알리므로,
    # 그 한 줄이 곧 '이 변수는 env_flag 를 지난다' 는 증거가 된다.
    t = {'a': table('a', [col('id')], pk=['id']),
         'b': table('b', [col('id'), col('a_id')], pk=['id'],
                    fks=[{'column': 'a_id', 'ref_table': 'a', 'ref_column': 'id',
                          'on_delete': 'CASCADE'}])}
    write_schema(work, t)
    r = run('build_erd.py', work, env={'ERD_SVG': 'maybe', 'ERD_SVG_TITLE': 'maybe'})
    for name in ('ERD_SVG', 'ERD_SVG_TITLE'):
        has(r.stdout, name, f'{name} goes through the one rule')
    r = run('build_html.py', work, env={'ERD_HTML_SVG': 'maybe', 'ERD_HTML_FULL': 'maybe',
                                        'ERD_HTML_STATS': 'maybe'})
    for name in ('ERD_HTML_SVG', 'ERD_HTML_FULL', 'ERD_HTML_STATS'):
        has(r.stdout, name, f'{name} goes through the one rule')
    # 말만 하고 값은 켜 버리면 고친 것이 아니다. ERD_HTML_STATS 의 문서상 기본값은
    # 꺼짐이고, 배지 `rows ≈ n` 이 그 스위치의 눈에 보이는 자국이다.
    if 'rows ≈' in (work / 'T.html').read_text(encoding='utf-8'):
        raise Fail("ERD_HTML_STATS=maybe must land on the documented default (off) — "
                   'a value nobody can read must not become a yes')

    # 그리고 실제로 꺼지는지. 예전 판이 켜 버리던 철자로만 재 본다.
    for i, spelling in enumerate(('False', 'NO', 'off', '0 ')):
        w = work / f'svg{i}'
        write_schema(w, t)
        run('build_erd.py', w, env={'ERD_SVG': spelling})
        svgs = sorted(p.name for p in (w / 'out').glob('*.svg'))
        eq(svgs, [], f'ERD_SVG={spelling!r} means off, and off means no SVG file')
    r = run('build_html.py', work, env={'ERD_HTML_SVG': 'False'})
    html = (work / 'T.html').read_text(encoding='utf-8')
    eq(html.count('<svg'), 0, "ERD_HTML_SVG=False embeds PNG, not the SVG it was told to drop")
    run('build_html.py', work, env={'ERD_HTML_SVG': '1'})
    if (work / 'T.html').read_text(encoding='utf-8').count('<svg') == 0:
        raise Fail('and the switch still turns on — an always-off flag is not a fix')


def many(work, groups=5, per=3):
    """접두어가 다른 묶음 여러 개 — 자동 영역 나누기가 실제로 도는 모양."""
    t = {}
    for g in range(groups):
        for i in range(per):
            n = f'g{g}_t{i}'
            t[n] = table(n, [col('id')], pk=['id'])
    write_schema(work, t)
    return t


def areas_drawn(work):
    return len(list((work / 'out').glob('erd_area_*.png')))


@case('spec: a doc value of the wrong shape names its field')
def _(work):
    write_schema(work, {'t': table('t', [col('id')])})
    for value, key in (({'scope': 'one line'}, 'doc.scope'),
                       ({'sources': 'information_schema'}, 'doc.sources'),
                       ({'scope': [['a']]}, 'doc.scope'),
                       ({'meta': ['label']}, 'doc.meta'),
                       ({'mapping': [['1', 2]]}, 'doc.mapping'),
                       ({'open_items': [['high'], {'bad': 'row'}]}, 'doc.open_items'),
                       ({'title': 123}, 'doc.title'),
                       ({'area_desc': ['x']}, 'doc.area_desc'),
                       ({'area_desc': {'A': 1}}, 'doc.area_desc'),
                       ({'db_names': {'shop': 1}}, 'doc.db_names')):
        (work / 'erd.spec.json').write_text(json.dumps({'doc': value}), encoding='utf-8')
        r = run('build_erd.py', work, expect_ok=False)
        no_traceback(r, f'malformed {key}')
        has(r.stdout + r.stderr, key, f'the error names {key}')

    (work / 'erd.spec.json').write_text(
        json.dumps({'doc': {'scpoe': ['misspelled scope']}}), encoding='utf-8')
    r = run('build_erd.py', work)
    has(r.stdout + r.stderr, 'doc.scpoe',
        'an unknown nested doc key is named instead of silently using the default')


@case('config: ERD_QUERY_TIMEOUT rejects non-finite numbers')
def _(work):
    code = 'import config; print(config.query_timeout())'
    for raw in ('nan', 'inf', '1e309'):
        r = py(code, env=env_without_erd(ERD_QUERY_TIMEOUT=raw))
        if r.returncode == 0:
            raise Fail(f'ERD_QUERY_TIMEOUT={raw} was accepted as {r.stdout.strip()!r}')
        has(r.stdout + r.stderr, 'ERD_QUERY_TIMEOUT', 'the invalid variable is named')


@case('config: an ERD_MAX_AREAS that is not a number says so instead of silently meaning 12')
def _(work):
    # `int(raw) if raw.strip().lstrip('-').isdigit() else 12` 하나에 셋이 걸려 있었다.
    #   abc·3.5·1e3 → 아무 말 없이 12 (사용자는 제가 적은 값이 쓰인 줄 안다)
    #   --5·²       → lstrip('-')·isdigit() 를 통과해 바로 다음 int() 에서 raw ValueError
    #   0·-3        → max(1,…) 에 눌려 1 이 되는데 그것도 말이 없었다
    many(work / 'base')
    run('build_erd.py', work / 'base')
    default_areas = areas_drawn(work / 'base')
    if default_areas < 3:
        raise Fail(f'the fixture must actually split into areas (got {default_areas})')

    for i, raw in enumerate(('abc', '3.5', '1e3', '²')):
        w = work / f'bad{i}'
        many(w)
        r = run('build_erd.py', w, env={'ERD_MAX_AREAS': raw})
        has(r.stdout, 'ERD_MAX_AREAS', f'{raw!r} is reported by name')
        has(r.stdout, raw, f'{raw!r} is shown as it was written')
        eq(areas_drawn(w), default_areas, f'{raw!r} falls back to the documented default')

    w = work / 'dashes'
    many(w)
    r = run('build_erd.py', w, env={'ERD_MAX_AREAS': '--5'})
    no_traceback(r, '--5 passed the old check and died in the int() right after it')
    has(r.stdout, '--5', 'the value that could not be read is shown')

    w = work / 'zero'
    many(w)
    r = run('build_erd.py', w, env={'ERD_MAX_AREAS': '0'})
    has(r.stdout, 'ERD_MAX_AREAS', 'a value below 1 is raised, and says so')
    eq(areas_drawn(w), 1, 'and one area is what comes out')

    w = work / 'three'
    many(w)
    r = run('build_erd.py', w, env={'ERD_MAX_AREAS': '3'})
    eq(areas_drawn(w), 3, 'a number that reads is obeyed — the warning path must not eat it')
    if 'ERD_MAX_AREAS' in r.stdout:
        raise Fail('a value that reads fine must not warn')


@case('config: an empty or blank ERD_WORK falls back to $ERD_PROJ/erd-build, not the cwd')
def _(work):
    # `os.environ.get(env, default)` 는 **빈 문자열도 값**이라 Path('') → Path('.') 이
    # 됐다. ERD_WORK='' 하나로 schema.json 과 out/ 이 부르는 사람의 cwd 에 흩어졌다 —
    # 지우려 해도 어디에 생겼는지 모른다. ERD_SPEC·ERD_SQL_DIR·ERD_MODEL_DIR 도 같다.
    #
    # 15R. 14라운드 판은 **빈 문자열만** 재고 `_p` 의 `raw.strip()` 은 안 쟀다 —
    # 전형적인 '같은 버그를 반만 고쳤다'. `.strip()` 을 지우면 `ERD_WORK='  '` 가
    # 값으로 통해 cwd 에 이름이 공백 두 칸인 디렉터리가 생기고(지우려면 따옴표를 쳐야
    # 한다) 산출물이 거기로 간다. 되돌려도 141개가 전부 초록이었다. 셸 붙여넣기에서
    # 꼬리 공백은 눈에 안 보이므로 흔한 입력이다.
    #
    # 이 케이스만 제 손으로 프로세스를 띄운다 — 재려는 것이 **cwd 에 무엇이 생기는가**
    # 라서, 부르는 쪽이 cwd 를 정해야 한다 (selftest_kit.run 은 scripts/ 에서 돈다).
    proj = work / 'proj'
    write_schema(proj / 'erd-build', {'a': table('a', [col('id')], pk=['id'])})
    for i, blank in enumerate(('', '  ', '\t', ' \n ')):
        cwd = work / f'cwd{i}'
        cwd.mkdir(parents=True, exist_ok=True)
        r = py('import runpy, sys; sys.path.insert(0, sys.argv[1]); '
               'runpy.run_path(sys.argv[1] + "/build_erd.py", run_name="__main__")',
               [str(HERE)],
               env=env_without_erd(ERD_PROJ=proj, ERD_WORK=blank, ERD_SPEC=blank,
                                   ERD_DOCNAME='T'),
               cwd=cwd)
        if r.returncode != 0:
            raise Fail(f'ERD_WORK={blank!r} must simply mean "not set":\n'
                       f'{r.stdout[-400:]}\n{r.stderr[-400:]}')
        if not (proj / 'erd-build' / 'out' / 'erd_full.png').exists():
            raise Fail('the drawing belongs under $ERD_PROJ/erd-build, as the default says')
        left = sorted(p.name for p in cwd.iterdir())
        eq(left, [], f"ERD_WORK={blank!r} scattered something into the caller's "
                     f'directory: {left}')


@case('config: ERD_MAX_AREAS says so when a spec asks for more areas than the cap')
def _(work):
    # 15R. 상한은 **자동 분류 가지**에만 걸려 있고 spec 가지는 그 값을 아예 안 봤다.
    # 거기에 '어느 영역에도 없는 테이블' 을 받는 '기타' 영역까지 얹혀서,
    # ERD_MAX_AREAS=1 + 영역 하나짜리 spec 이 영역 3개가 됐다. 회귀는 아니지만
    # 상한을 적은 사람에게는 새 초과 요인이고, 화면에는 한 글자도 안 나왔다.
    # 고르는 것은 둘이다 — 사람이 이름까지 적은 절을 말없이 버리거나, 다 그리고
    # 말하거나. 뒤엣것을 골랐고, **말한다는 것**을 여기서 못박는다.
    three(work)
    spec(work, {'areas': [['A', 'Orders', 'public', ['orders', 'order_items']]]})
    r = run('build_erd.py', work, env={'ERD_MAX_AREAS': '1'})
    has(r.stdout, 'ERD_MAX_AREAS', 'the cap that will not hold is named')
    eq(areas_drawn(work), 2,
       'and the areas a person wrote by hand are all drawn — the spec wins, out loud')

    # 상한 안에 드는 실행은 조용해야 한다. 안 그러면 경고가 소음이 되어 죽는다.
    w = work / 'roomy'
    three(w)
    spec(w, {'areas': [['A', 'Orders', 'public', ['orders', 'order_items']]]})
    r = run('build_erd.py', w, env={'ERD_MAX_AREAS': '5'})
    if 'ERD_MAX_AREAS' in r.stdout:
        raise Fail(f'a cap the drawing stays under must not warn:\n{r.stdout}')
    # 적지도 않은 사람에게 말을 걸어서도 안 된다
    w = work / 'unset'
    three(w)
    spec(w, {'areas': [['A', 'Orders', 'public', ['orders', 'order_items']]]})
    r = run('build_erd.py', w)
    if 'ERD_MAX_AREAS' in r.stdout:
        raise Fail(f'a variable nobody set must not be mentioned:\n{r.stdout}')


@case("config: an import alone creates nothing in the caller's directory")
def _(work):
    # 15R — 14라운드부터 있던 것을 검증자가 os.mkdir 후킹으로 잡았다:
    #   selftest_kit.py:445  main → fn(tmp/'work')
    #   selftest_schema.py:858 → import parse_ddl
    #   parse_ddl.py:24      → from config import RS, SCHEMA_JSON, …
    #   config.py:92         → PROJ = as_dir(_p('ERD_PROJ', Path.cwd()), 'ERD_PROJ')
    #   config.py:76         → path.mkdir(parents=True, exist_ok=True)
    # **import 하나로** 부르는 사람의 cwd 에 erd-build/out 이 생겼다. 빈 디렉터리에서
    # selftest.py 를 돌리기만 해도 ./erd-build 가 남았고(.gitignore 라 git status 에도
    # 안 보인다), README·SKILL 이 안내하는 직접 실행 경로도 그대로였다 — 14라운드는
    # `install.sh --check` 쪽만 임시 디렉터리로 피했다.
    cwd = work / 'clean'
    cwd.mkdir(parents=True, exist_ok=True)
    r = py('import sys; sys.path.insert(0, sys.argv[1]); '
           'import config, parse_ddl, introspect, merge_desc; print("ok")',
           [str(HERE)], env=env_without_erd(), cwd=cwd)
    if r.returncode != 0:
        raise Fail(f'the modules must still import: {r.stdout[-300:]}\n{r.stderr[-400:]}')
    left = sorted(p.name for p in cwd.iterdir())
    eq(left, [], f"an import must not touch the caller's directory: {left}")

    # 그렇다고 값을 없앤 것이 아니다 — 물어보면 그 자리에서 만들고, 예전과 같은
    # 곳을 가리킨다. 안 만드는 것과 못 만드는 것은 다르다.
    proj = work / 'proj'
    r = py('import sys; sys.path.insert(0, sys.argv[1]); '
           'import config; print(config.WORK); print(config.OUT); '
           'print(config.SCHEMA_JSON)',
           [str(HERE)], env=env_without_erd(ERD_PROJ=proj), cwd=cwd)
    if r.returncode != 0:
        raise Fail(f'asking for the path must still answer: {r.stderr[-400:]}')
    said = [x for x in r.stdout.splitlines() if x.strip()]
    eq(said, [str(proj / 'erd-build'), str(proj / 'erd-build' / 'out'),
              str(proj / 'erd-build' / 'schema.json')],
       'the paths are what they always were')
    if not (proj / 'erd-build' / 'out').is_dir():
        raise Fail('asking for OUT must create it — deferring is not the same as refusing')
    eq(sorted(p.name for p in cwd.iterdir()), [],
       "and still nothing lands in the caller's directory")


@case('config: an unusable ERD_PSQL stops the scripts that ask the database, not the '
      'ones that never do')
def _(work):
    # 15R — 14라운드 수정자 자신이 신고하고 검증자가 확정했다. ERD_PSQL 은 config 를
    # import 하는 **시작 자리**에서 분해됐으므로, `ERD_PSQL='psql "unclosed'` 하나로
    # DB 를 한 번도 안 쓰는 build_erd.py·build_html.py·build_docx.py·merge_desc.py 가
    # 전부 rc 1 이었다 — 이미 있는 schema.json 으로 **문서만 다시 뽑는 실행**이 통째로
    # 막힌다. 접속이 깨진 것과 문서를 못 만드는 것은 다른 일이다.
    three(work)
    bad = {'ERD_PSQL': 'psql "unclosed'}
    run('merge_desc.py', work, env=bad)
    run('build_erd.py', work, env=bad)
    run('build_html.py', work, env=bad)
    run('build_docx.py', work, env=bad)
    for name in ('T.html', 'T.docx', 'T.graphml'):
        if not (work / name).exists():
            raise Fail(f'{name} never asks the database — a broken ERD_PSQL must not '
                       f'stop it')

    # 검사를 없앤 것이 아니라 **묻는 쪽으로 옮겼다.** 묻는 둘은 예전처럼 시작 자리에서
    # 이름을 대고 멈춘다 — 첫 조회를 던지기 전이다.
    d = work / 'sql'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text(
        'CREATE TABLE orders (id bigint PRIMARY KEY, m bigint REFERENCES merchants(id));\n',
        encoding='utf-8')
    for script, kw in (('introspect.py', {}), ('parse_ddl.py', {'sql_dir': d})):
        r = run(script, work, env=bad, expect_ok=False, **kw)
        no_traceback(r, f'{script} must still name the variable, not quote shlex')
        has(r.stdout + r.stderr, 'ERD_PSQL', f'{script} names ERD_PSQL')


@case('config: an empty ERD_SCHEMAS stops the scripts that read the database, not the '
      'ones that never do')
def _(work):
    # 16R. 위 케이스(`an unusable ERD_PSQL …`)와 **같은 결함의 나머지 절반**이다.
    # config.py 의 '늦춰 두는 값' 주석 ② 는 `ERD_PSQL` 과 `ERD_SCHEMAS` 를 나란히
    # 적어 두었는데 — "같은 이유로 `ERD_SCHEMAS=''` 도 그림·문서 쪽 스크립트를 함께
    # 죽였다" — 재는 항목은 ERD_PSQL 쪽만 있었다. `_LAZY_DONE = {}` 뒤에
    # `SCHEMAS = _schemas()` 한 줄을 도로 놓아 14라운드 모양으로 되돌려도 161개가
    # 전부 초록이었다. 되돌리면 이렇게 된다:
    #   ERD_SCHEMAS= python3 merge_desc.py   → rc 1  ERD_SCHEMAS is set to an empty value
    #   ERD_SCHEMAS= python3 build_erd.py    → rc 1  (같은 말)
    #   ERD_SCHEMAS= python3 build_html.py   → rc 1
    #   ERD_SCHEMAS= python3 build_docx.py   → rc 1
    # 넷 다 스키마 목록을 한 번도 안 본다. 이미 있는 schema.json 으로 **문서만 다시
    # 뽑는 실행**이 통째로 막히는 것이 ERD_PSQL 때와 똑같다. 게다가 `ERD_SCHEMAS=` 는
    # 셸에서 한 번만 비워 보려는 흔한 손버릇이다.
    three(work)
    blank = {'ERD_SCHEMAS': ''}
    run('merge_desc.py', work, env=blank)
    run('build_erd.py', work, env=blank)
    run('build_html.py', work, env=blank)
    run('build_docx.py', work, env=blank)
    for name in ('T.html', 'T.docx', 'T.graphml'):
        if not (work / name).exists():
            raise Fail(f'{name} never reads ERD_SCHEMAS — an empty one must not stop it')

    # DDL 경로도 스키마 목록을 안 본다
    w = work / 'ddl'
    d = w / 'sql'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text('CREATE TABLE t (id bigint PRIMARY KEY);\n', encoding='utf-8')
    run('parse_ddl.py', w, sql_dir=d, env=blank)
    if not (w / 'schema.json').exists():
        raise Fail('parse_ddl.py never reads ERD_SCHEMAS either')

    # 검사를 없앤 것이 아니라 **읽는 쪽으로 옮겼다.** 실제로 그 목록으로 조회를 던지는
    # introspect 는 예전처럼 시작 자리에서 이름을 대고 멈춘다 — 서버에 묻기 전이다.
    r = run('introspect.py', work, env=blank, expect_ok=False)
    no_traceback(r, 'an empty ERD_SCHEMAS must still be a message, not a traceback')
    has(r.stdout + r.stderr, 'ERD_SCHEMAS',
        'the one script that asks with that list still names the variable')


@case('errors: every ERD_* path variable pointed at the wrong kind of node is a message,'
      ' not a traceback')
def _(work):
    # 다섯 자리가 전부 같은 모양이었다 — 경로 환경변수가 잘못된 종류의 노드를 받으면
    # errno 를 그대로 뱉었고, 그 줄에는 어느 변수 탓인지가 없다.
    #   ERD_PROJ=파일      → FileExistsError [Errno 17]   (mkdir)
    #   ERD_SPEC=디렉터리   → IsADirectoryError [Errno 21] (read_text)
    #   ERD_DOC_HTML=디렉터리 → 같은 것
    #   ERD_SQL_FILES=없는 파일 → FileNotFoundError [Errno 2]
    #   ERD_LABEL=a/b      → ValueError: Invalid name 'schema.a/b.json'
    # 마지막 것이 특히 나빴다: **DB 조회를 전부 끝낸 뒤** 마지막 쓰기에서 죽어 왕복이
    # 통째로 버려졌다. 그래서 여기서는 접속을 아예 주지 않는다 — 시작 자리에서 걸러야만
    # 통과한다 (접속을 먼저 봤다면 메시지는 ERD_PSQL 을 말했을 것이다).
    write_schema(work, {'a': table('a', [col('id')], pk=['id'])})
    afile, adir = work / 'a.file', work / 'a.dir'
    afile.write_text('not a directory', encoding='utf-8')
    adir.mkdir(parents=True, exist_ok=True)

    checks = [('build_erd.py', {'ERD_PROJ': str(afile)}, 'ERD_PROJ'),
              ('build_erd.py', {'ERD_SPEC': str(adir)}, 'ERD_SPEC'),
              ('merge_desc.py', {'ERD_DOC_HTML': str(adir)}, 'ERD_DOC_HTML'),
              ('parse_ddl.py', {'ERD_SQL_FILES': 'nope.sql'}, 'ERD_SQL_FILES'),
              ('introspect.py', {'ERD_LABEL': 'a/b'}, 'ERD_LABEL')]
    for script, env, name in checks:
        r = run(script, work, env=env, expect_ok=False)
        no_traceback(r, f'{name} pointed at the wrong kind of node tracebacked')
        has(r.stdout + r.stderr, name, f'the message names {name}')

    sql_dir = work / 'sql'
    sql_dir.mkdir(exist_ok=True)
    (work / 'outside.sql').write_text('CREATE TABLE escaped (id bigint);', encoding='utf-8')
    r = run('parse_ddl.py', work, env={'ERD_SQL_FILES': '../outside.sql'},
            expect_ok=False)
    no_traceback(r, 'ERD_SQL_FILES outside ERD_SQL_DIR must be rejected at the boundary')
    has(r.stdout + r.stderr, '../outside.sql', 'the path that escaped the SQL directory is named')

    (sql_dir / 'once.sql').write_text(
        'CREATE TABLE once (id bigint PRIMARY KEY);', encoding='utf-8')
    run('parse_ddl.py', work, env={'ERD_SQL_FILES': 'once.sql, ./once.sql, once.sql'})
    parsed = json.loads((work / 'schema.json').read_text(encoding='utf-8'))
    eq([c['name'] for c in parsed['once']['columns']], ['id'],
       'the same named DDL file is parsed once, not once per list occurrence')
    # ERD_LABEL 은 쓸 수 있는 값이면 그대로 지나가야 한다 — 막기만 하는 검사는 기능을
    # 없앤 것이지 고친 것이 아니다.
    r = run('introspect.py', work, env={'ERD_LABEL': 'shop'}, expect_ok=False)
    has(r.stdout + r.stderr, 'ERD_PSQL',
        'a usable label gets as far as the connection check, as it always did')


@case('errors: a bad ERD_EXCLUDE regex and an unbalanced ERD_PSQL quote are messages')
def _(work):
    # config.py 안에서 처음 쓰이는 자리까지 검사가 미뤄져 있었다 — excluded() 의
    # re.search 가 `re.error: unterminated character set` 을, psql_cmd() 의 shlex 가
    # `ValueError: No closing quotation` 을 던졌다. 둘 다 변수 이름을 말하지 않는다.
    write_schema(work, {'a': table('a', [col('id')], pk=['id'])})
    r = run('build_erd.py', work, env={'ERD_EXCLUDE': '[a'}, expect_ok=False)
    no_traceback(r, 'a broken ERD_EXCLUDE must be a message')
    has(r.stdout + r.stderr, 'ERD_EXCLUDE', 'the message names the variable')
    r = run('introspect.py', work, env={'ERD_PSQL': 'psql "unclosed'}, expect_ok=False)
    no_traceback(r, 'an unbalanced quote in ERD_PSQL must be a message')
    has(r.stdout + r.stderr, 'ERD_PSQL', 'the message names the variable')
    # 멀쩡한 정규식은 그대로 걸러야 한다
    write_schema(work / 'ok', {'a': table('a', [col('id')], pk=['id']),
                               'skipme': table('skipme', [col('id')], pk=['id'])})
    r = run('build_erd.py', work / 'ok', env={'ERD_EXCLUDE': '^skip'})
    graphml = (work / 'ok' / 'T.graphml').read_text(encoding='utf-8')
    if 'skipme' in graphml:
        raise Fail('a valid ERD_EXCLUDE must still exclude — the check must not disarm it')


# 조회문을 받아 적기만 하는 가짜 psql. 버전 물음에만 답한다 — 그래야 introspect 가
# 정작 재려는 조회(스키마 목록이 든 where 절)까지 간다.
_QUERY_LOG = '''\
import json, os, sys
a = sys.argv
q = a[a.index('-c') + 1]
open(os.environ['QLOG'], 'a').write(q + chr(10))
if 'server_version' in q:
    sys.stdout.write(json.dumps({'c0': '16.0', 'c1': '160000'}) + chr(10))
'''


@case('introspect: an empty ERD_SCHEMAS is refused by name, not as a SQL syntax error')
def _(work):
    # config 가 빈 조각을 걸러 SCHEMAS=[] 가 되면 `where table_schema in ()` 라는
    # 문법 오류 SQL 이 나갔고, 사용자가 보는 것은 제 변수가 아니라 psql 의 파서 오류였다.
    # 그리고 이름 속 따옴표를 막지 않아 ERD_SCHEMAS="s1','s2" 가 `in ('s1'', ''s2')` 라는
    # 남의 문법이 됐다.
    work.mkdir(parents=True, exist_ok=True)
    qlog = work / 'queries.txt'
    fake = work / 'fake_psql.py'
    fake.write_text(_QUERY_LOG, encoding='utf-8')
    psql = f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}'
    for raw in ('', ' , '):
        r = run('introspect.py', work, expect_ok=False,
                env={'ERD_SCHEMAS': raw, 'ERD_PSQL': psql, 'QLOG': str(qlog)})
        no_traceback(r, 'an empty ERD_SCHEMAS must be a message')
        has(r.stdout + r.stderr, 'ERD_SCHEMAS', f'the message names the variable ({raw!r})')
        if qlog.exists():
            raise Fail(f'nothing may be asked of the server first: {qlog.read_text(encoding='utf-8')[:200]}')

    run('introspect.py', work, expect_ok=False,
        env={'ERD_SCHEMAS': "s1','s2", 'ERD_PSQL': psql, 'QLOG': str(qlog)})
    asked = qlog.read_text(encoding='utf-8')
    has(asked, "in ('s1''', '''s2')", "a quote inside a schema name is escaped, not left open")
    if "in ('s1'', ''s2')" in asked:
        raise Fail('the old form let the name close the literal and start its own SQL')


def ref_ddl(work):
    """DDL 하나 — FK 가 DDL 밖의 테이블을 가리키므로 parse_ddl 이 DB 를 찾아간다."""
    d = work / 'sql'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text(
        'CREATE TABLE orders (id bigint PRIMARY KEY, m bigint REFERENCES merchants(id));\n',
        encoding='utf-8')
    return d


def fake_psql(work):
    """조회문을 받아 적기만 하는 가짜 psql 명령 한 줄."""
    fake = work / 'fake_psql.py'
    fake.parent.mkdir(parents=True, exist_ok=True)
    fake.write_text(_QUERY_LOG, encoding='utf-8')
    return f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}'


@case("parse: a quote in ERD_REF_SCHEMA or ERD_REF_TABLES is escaped, not left to start "
      'its own SQL')
def _(work):
    # 15R. introspect 쪽에는 같은 케이스가 있는데 **parse_ddl 쪽은 0건**이었다.
    # `_lit` 의 `.replace("'", "''")` 를 지우면 실제로 나가는 SQL 이 이렇게 된다:
    #   where c.table_schema='s1' or '1'='1' and c.table_name in ('x')
    # 두 값 다 환경변수에서 그대로 오고 그대로 **살아 있는 서버**로 나간다. 141개가
    # 전부 초록이었으니 라이브 SQL 인젝션이 통째로 무측정이었던 셈이다.
    d = ref_ddl(work)
    qlog = work / 'queries.txt'
    env = {'ERD_PSQL': fake_psql(work), 'QLOG': str(qlog),
           'ERD_REF_SCHEMA': "s1' or '1'='1", 'ERD_REF_TABLES': "x','y"}
    run('parse_ddl.py', work, sql_dir=d, env=env)
    asked = qlog.read_text(encoding='utf-8')
    has(asked, "c.table_schema='s1'' or ''1''=''1'",
        'a quote in ERD_REF_SCHEMA is doubled, so the value stays one literal')
    if "table_schema='s1' or '1'='1'" in asked:
        raise Fail(f'the schema name closed the literal and started its own SQL:\n{asked}')
    has(asked, "in ('x''','''y')",
        'and a quote in ERD_REF_TABLES is doubled the same way')
    if "in ('x'','y')" in asked:
        raise Fail(f'a table name closed the literal too:\n{asked}')
    # 멀쩡한 이름은 그대로 나가야 한다 — 막기만 하는 검사는 기능을 없앤 것이다
    w2 = work / 'plain'
    d2, qlog2 = ref_ddl(w2), w2 / 'queries.txt'
    run('parse_ddl.py', w2, sql_dir=d2,
        env={'ERD_PSQL': fake_psql(w2), 'QLOG': str(qlog2),
             'ERD_REF_SCHEMA': 'src', 'ERD_REF_TABLES': 'lookup'})
    has(qlog2.read_text(encoding='utf-8'), "c.table_schema='src'",
        'a name with no quote in it is asked for exactly as written')


@case('parse: ERD_REF_TABLES without ERD_REF_SCHEMA is named, not silently ignored')
def _(work):
    # 15R. 반쪽만 준 것은 안 준 것과 다르다. 14라운드가 그 말을 네 카탈로그에 넣어
    # 두었는데 `grep -rn 'ref_tables_ignored' scripts/selftest*.py` 는 **0건**이었다 —
    # 문구까지 있는데 아무도 안 부르므로, 그 print 를 지워도 아무 데서도 빨강이
    # 뜨지 않는다. 사용자는 적어 둔 원천 테이블이 왜 그림에 없는지 알 길이 없다.
    d = ref_ddl(work)
    r = run('parse_ddl.py', work, sql_dir=d, env={'ERD_REF_TABLES': 'lookup, codes'})
    has(r.stdout, 'ERD_REF_SCHEMA', 'the half that is missing is named')
    has(r.stdout, 'lookup', 'and what was asked for but not fetched')

    # 둘 다 주면 조용히 가져온다
    w2 = work / 'both'
    d2, qlog2 = ref_ddl(w2), w2 / 'queries.txt'
    r = run('parse_ddl.py', w2, sql_dir=d2,
            env={'ERD_PSQL': fake_psql(w2), 'QLOG': str(qlog2),
                 'ERD_REF_SCHEMA': 'src', 'ERD_REF_TABLES': 'lookup'})
    if 'ERD_REF_SCHEMA' in r.stdout:
        raise Fail(f'a pair that is complete must not warn:\n{r.stdout}')
    has(qlog2.read_text(encoding='utf-8'), "'lookup'", 'and the table is actually asked for')

    # 아무것도 안 준 사람에게 말을 걸어서도 안 된다
    w3 = work / 'neither'
    d3 = ref_ddl(w3)
    r = run('parse_ddl.py', w3, sql_dir=d3)
    if 'ERD_REF' in r.stdout:
        raise Fail(f'a variable nobody set must not be mentioned:\n{r.stdout}')


@case('parse: ERD_DEFAULT_PK either fills the PK without a database or says why it did not')
def _(work):
    # `for n in existing_names: if n not in db: continue` 안쪽에 있어서, 접속이 없으면
    # db={} 로 루프가 한 번도 안 돌았다 — DDL 만으로 그리는 사람에게는 **영원히 무효인
    # 스위치**인데 화면에는 한 글자도 안 나왔다. SKILL.md 도 DB 가 필요하다는 말을 안 한다.
    sql = 'CREATE TABLE orders (id bigint PRIMARY KEY, m bigint REFERENCES merchants(id));'
    d = work / 'sql'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text(sql, encoding='utf-8')
    r = run('parse_ddl.py', work, sql_dir=d, env={'ERD_DEFAULT_PK': 'id'})
    s = json.loads((work / 'schema.json').read_text(encoding='utf-8'))
    has(r.stdout, 'ERD_DEFAULT_PK', 'with no database it says the switch did nothing')
    has(r.stdout, 'merchants', 'and which table kept no primary key')
    eq(s['merchants']['pk'], [],
       'a column the table does not have must not be written down as its PK')

    # 접속이 있으면 예전처럼 채운다 — 말만 하고 안 채우면 그것도 고친 것이 아니다.
    # 17R: parse_ddl 이 config.psql_rows() 로 옮겨 **행마다 JSON 한 줄**을 받고,
    # 기존 테이블 컬럼 조회는 맨 앞에 table_schema 가 붙어 5필드가 됐다.
    # (selftest_schema.py 의 _FAKE_PSQL_JSON 과 같은 프로토콜이다.)
    fake = work / 'fake_psql.py'
    fake.write_text(
        "import json\n"
        "import re\n"
        "import sys\n"
        "a = sys.argv\n"
        "q = a[a.index('-c') + 1]\n"
        "if 'information_schema.columns' in q:\n"
        "    m = re.search(r'_r\\(([^()]*)\\)\\s*$', q)\n"
        "    names = [c.strip() for c in m.group(1).split(',')] if m else []\n"
        "    row = ['public', 'merchants', 'id', 'bigint', 'NO']\n"
        "    sys.stdout.write(json.dumps(dict(zip(names, row))) + chr(10))\n",
        encoding='utf-8')
    w2 = work / 'withdb'
    d2 = w2 / 'sql'
    d2.mkdir(parents=True, exist_ok=True)
    (d2 / 'a.sql').write_text(sql, encoding='utf-8')
    run('parse_ddl.py', w2, sql_dir=d2, env={
        'ERD_DEFAULT_PK': 'id',
        'ERD_PSQL': f'{shlex.quote(sys.executable)} {shlex.quote(str(fake))}'})
    s2 = json.loads((w2 / 'schema.json').read_text(encoding='utf-8'))
    eq([c['name'] for c in s2['merchants']['columns']], ['id'],
       'the database filled the column in')
    eq(s2['merchants']['pk'], ['id'], 'and ERD_DEFAULT_PK still names it the PK')


@case('parse: ERD_LABEL labels the DDL path the same way it labels introspection')
def _(work):
    # 16R. SKILL.md:132 · SKILL.ko.md:122 는 `ERD_LABEL` 을 **범용 표**에 싣고
    # "여러 DB 를 합칠 때 붙일 라벨(schema.<라벨>.json)" 이라 적는데, 그것을 보는
    # 스크립트는 introspect.py 뿐이었다:
    #   ERD_LABEL=shop python3 parse_ddl.py → schema.json (라벨 없는 파일명)
    #   키도 ['users','user_profiles'] 로 무라벨.  경고 한 줄이 없었다.
    # 조용히 무시하는 것이 특히 나쁜 이유는 **그 다음 단계**다. 라벨이 안 붙은
    # schema.*.json 을 merge_schemas.py 로 섞으면 이름이 같은 테이블이 서로를
    # 덮어쓴다 — 3라운드 발견이 그대로 재현된다. 라벨을 적은 사람은 제가 적었다고
    # 믿고 있으므로 그 소실을 볼 길이 없다.
    def ddl_at(w, text):
        d = w / 'sql'
        d.mkdir(parents=True, exist_ok=True)
        (d / 'a.sql').write_text(text, encoding='utf-8')
        return d

    d = ddl_at(work, 'CREATE TABLE users (id bigint PRIMARY KEY);\n'
                     'CREATE TABLE user_profiles (id bigint PRIMARY KEY,\n'
                     '  user_id bigint REFERENCES users(id));\n')
    run('parse_ddl.py', work, sql_dir=d, env={'ERD_LABEL': 'shop'})
    if (work / 'schema.json').exists():
        raise Fail('ERD_LABEL means schema.<label>.json — merge_schemas.py looks for '
                   'exactly that name and nothing else')
    s = json.loads((work / 'schema.shop.json').read_text(encoding='utf-8'))
    eq(sorted(s), ['shop.user_profiles', 'shop.users'], 'the keys carry the label')
    eq(s['shop.user_profiles']['fks'][0]['ref_table'], 'shop.users',
       'and so does every FK parent — a relationship that misses the rename disappears')
    eq(s['shop.users']['db'], 'shop', 'the table says which database it came from')
    eq(s['shop.users']['schema'], 'shop.public',
       'the schema is qualified the way introspect.py qualifies it')

    # 그리고 실제로 그 다음 단계가 산다 — 이름이 같은 테이블 둘이 살아남는다
    a = work / 'shop'
    b = work / 'mart'
    for w, label in ((a, 'shop'), (b, 'mart')):
        dd = ddl_at(w, 'CREATE TABLE users (id bigint PRIMARY KEY);\n')
        run('parse_ddl.py', work, sql_dir=dd, env={'ERD_LABEL': label})
    merged = run_argv('merge_schemas.py', work, ['shop', 'mart'])
    got = sorted(json.loads((work / 'schema.json').read_text(encoding='utf-8')))
    eq(got, ['mart.users', 'shop.users'],
       f'two DDL trees with the same table name merge without eating each other: '
       f'{merged.stdout}')

    # 라벨을 안 준 실행은 예전 그대로다 — 붙이기만 하는 기능은 고친 것이 아니다
    w = work / 'plain'
    dd = ddl_at(w, 'CREATE TABLE users (id bigint PRIMARY KEY);\n')
    run('parse_ddl.py', w, sql_dir=dd)
    eq(sorted(json.loads((w / 'schema.json').read_text(encoding='utf-8'))), ['users'],
       'no label means the plain schema.json with plain keys, as before')

    # 파일 이름이 될 수 없는 라벨은 introspect.py 와 같은 자리에서 같은 말로 멈춘다 —
    # DDL 을 다 읽고 마지막 쓰기에서 죽으면 그 왕복이 통째로 버려진다
    w = work / 'badname'
    dd = ddl_at(w, 'CREATE TABLE users (id bigint PRIMARY KEY);\n')
    r = run('parse_ddl.py', w, sql_dir=dd, env={'ERD_LABEL': 'a/b'}, expect_ok=False)
    no_traceback(r, 'a label that cannot be a file name must be a message')
    has(r.stdout + r.stderr, 'ERD_LABEL', 'the message names the variable')
    stray = sorted(p.name for p in w.glob('schema*.json'))
    eq(stray, [], f'and nothing is half-written under a made-up name: {stray}')


@case('parse: a DDL that asks nothing of the database is not stopped by a broken '
      'ERD_PSQL')
def _(work):
    # 16R. 14라운드가 config 의 판정을 늦추고 15라운드가 그 범위를 좁혔는데, 이
    # 자리까지는 오지 않았다. `has_db = config_has_db()` 가 **무조건** 불려서,
    # FK 가 DDL 밖을 안 가리키는 순수 DDL —
    #   create table t (id bigint primary key);
    # 도 `ERD_PSQL='psql "unclosed'` 하나로 rc 1 이었다. 물어볼 것이 없는 실행이
    # 접속 설정의 오타에 걸려 죽는 것은 'ERD_PSQL 이 깨졌다' 와 다른 일이다.
    # (`parse: a DDL-only project never reaches for a database` 는 **쓸 수 있는**
    # ERD_PSQL 로 '손을 뻗지 않는가' 를 재고, 여기서는 **못 쓰는** 값으로 '분해조차
    # 하지 않는가' 를 잰다. 뻗지 않아도 분해는 하고 있었다.)
    d = work / 'sql'
    d.mkdir(parents=True, exist_ok=True)
    (d / 'a.sql').write_text('CREATE TABLE t (id bigint PRIMARY KEY);\n', encoding='utf-8')
    r = run('parse_ddl.py', work, sql_dir=d, env={'ERD_PSQL': 'psql "unclosed'})
    eq(sorted(json.loads((work / 'schema.json').read_text(encoding='utf-8'))), ['t'],
       'the DDL alone still produced the schema')
    if 'ERD_PSQL' in r.stdout + r.stderr:
        raise Fail(f'a variable this run never needed must not be mentioned:\n{r.stdout}')

    # 물을 것이 있으면 예전처럼 시작 자리에서 이름을 대고 멈춘다 — 검사를 없앤 것이
    # 아니라 **물을 때만** 하도록 옮긴 것이다.
    w = work / 'needs'
    d2 = w / 'sql'
    d2.mkdir(parents=True, exist_ok=True)
    (d2 / 'a.sql').write_text(
        'CREATE TABLE orders (id bigint PRIMARY KEY, m bigint REFERENCES merchants(id));\n',
        encoding='utf-8')
    r = run('parse_ddl.py', w, sql_dir=d2, env={'ERD_PSQL': 'psql "unclosed'},
            expect_ok=False)
    no_traceback(r, 'a broken ERD_PSQL must still be a message when it is actually used')
    has(r.stdout + r.stderr, 'ERD_PSQL',
        'the run that does need the database still names the variable')


# ── 말 ──────────────────────────────────────────────────────────────────────

# 코드가 키를 **만들어** 부르는 자리. 글자 그대로 안 적히므로 아래 정규식에 안 걸린다.
# 접두어만 믿지 않고 그 접두어를 조립하는 파일이 아직 그 일을 하는지 함께 본다 —
# 그 자리가 사라지면 그 접두어의 키들은 진짜 죽은 키가 된다.
DYNAMIC = {'common.': 'merge_desc.py', 'verify.': 'erd.py'}

# 아직 아무도 안 부르지만 **일부러** 넣어 둔 키. 16라운드에 다른 갈래가 쓸 자리를
# 먼저 만들어 둔 것이다 — 카탈로그는 한 사람이 소유하고 부르는 코드는 남이 고치므로,
# 키가 먼저 있고 호출이 나중에 온다. **쓰이기 시작하면 여기서 지운다.** 이 목록이
# 줄지 않고 자라기만 하면 그것 자체가 신호다.
RESERVED = {
    'log.row_truncated': 'doc.meta·doc.sources·doc.mapping·doc.open_items 의 남는 칸이 '
                         '말없이 버려지는 것 (build_docx.py·build_html.py)',
    # 'col.null' 은 17R 에 build_html.py:274 가 실제로 부르기 시작해서 뺐다 —
    # 예고된 정상 경로다(위 '쓰이기 시작하면 여기서 지운다').
    'html.badge_cols': "build_html.py 의 하드코딩 'cols {n}' 배지",
    'html.badge_tables': "build_html.py 의 하드코딩 '{n} tables' 배지",
}


@case('i18n: a key nobody calls does not sit in the four catalogs unnoticed')
def _(work):
    # 16R. `selftest.py` 의 `i18n: every key used by the code exists` 는 **한 방향**
    # 만 본다 — 코드가 부르는데 카탈로그에 없는 키. 반대쪽은 아무도 안 봤다.
    # `log.html_missing` 이 네 언어에 다 있으면서 **어느 코드도 안 부르고** 있었다
    # (같은 일을 하는 말은 `log.figs_missing` 으로 따로 있다). 죽은 키는 조용히
    # 틀린다: 네 언어로 번역하는 품이 계속 들고, 문구를 고쳐도 아무 데도 안 나오며,
    # 다음 사람은 그것이 쓰이는 줄 알고 그 문구에 맞춰 코드를 짠다.
    sys.path.insert(0, str(HERE))
    import lang.en as en
    keys = set(en.M)
    families = sorted({k.split('.')[0] for k in keys})
    rx = re.compile(r"""['"]((?:%s)\.[a-z0-9_]+)['"]""" % '|'.join(families))

    used = set()
    for f in sorted(HERE.glob('*.py')):
        if f.name.startswith('selftest'):
            continue            # 시험 파일은 배포물이 아니다 — 여기 있는 키는 예시다
        used |= set(rx.findall(f.read_text(encoding='utf-8')))

    # 조립해 부르는 자리가 아직 살아 있는지부터 본다
    for prefix, owner in sorted(DYNAMIC.items()):
        src = (HERE / owner).read_text(encoding='utf-8')
        if f"'{prefix}" not in src and f'"{prefix}' not in src:
            raise Fail(f'{owner} no longer builds any {prefix}* key — then every '
                       f'{prefix}* string in the four catalogs is dead, and this case '
                       f'is letting them through on a promise that expired')
        used |= {k for k in keys if k.startswith(prefix)}

    dead = sorted(keys - used - set(RESERVED))
    eq(dead, [], 'message keys the shipped code never asks for — delete them, or call '
                 'them, or say in RESERVED who is going to')

    # 예약 목록도 거짓말을 하면 안 된다: 이미 쓰이기 시작한 키가 남아 있으면 지운다
    stale = sorted(set(RESERVED) & used)
    eq(stale, [], 'RESERVED says nobody calls these yet, but the code does — take them '
                  'out of the list')
    # 그리고 예약 이름이 실제로 카탈로그에 있어야 한다 (오타면 봐주는 것이 없어진다)
    ghost = sorted(set(RESERVED) - keys)
    eq(ghost, [], 'RESERVED names a key that is not in lang/en.py')


# ── 17R. 손으로 적는 값이 조용히 안 듣던 자리 ────────────────────────────────

@case('erd: ERD_EXCLUDE matches the table name even with a label in front of the key')
def _(work):
    # 17R 뮤테이션. `excluded()` 가 제가 받은 문자열에 정규식을 그대로 걸던 동안,
    # SKILL.md 가 약속한 '제외할 **테이블** 정규식' 은 라벨을 쓰는 사람에게 안
    # 들었다 — 키가 `shop.public.tmp_cache` 라 `^tmp_` 가 라벨에 막혔다. 그런데
    # 화면에는 한 글자도 안 나왔다: 원치 않는 테이블이 그냥 문서에 실렸다.
    write_schema(work, {
        'shop.public.orders': table('orders', [col('id')], pk=['id'],
                                    schema='shop.public', db='shop'),
        'shop.public.tmp_cache': table('tmp_cache', [col('id')], pk=['id'],
                                       schema='shop.public', db='shop')})
    run('build_erd.py', work, env={'ERD_EXCLUDE': '^tmp_'})
    run('build_html.py', work, env={'ERD_EXCLUDE': '^tmp_'})
    html = (work / 'T.html').read_text(encoding='utf-8')
    if 'tmp_cache' in html:
        raise Fail('a table the user excluded by name still reached the document '
                   'because a label was sitting in front of its key')
    has(html, 'orders', 'and the table that was not excluded is still there')


@case('errors: a spec file that is not utf-8 names ERD_SPEC instead of a traceback')
def _(work):
    # 17R 뮤테이션. JSONDecodeError 만 잡던 자리라, utf-8 이 아닌 spec 은
    # `UnicodeDecodeError` 가 **raw 트레이스백**으로 나갔다 — 사용자는 제 변수
    # 이름 대신 파이썬의 말을 봤다. as_file·as_dir 이 줄곧 없애 온 그 모양이다.
    write_schema(work, {'t': table('t', [col('id')], pk=['id'])})
    # cp949 로 저장된 한글 spec — 윈도우에서 손으로 만들면 실제로 이렇게 나온다
    (work / 'erd.spec.json').write_bytes(
        '{"areas": [["A", "주문", "public", ["t"]]]}'.encode('cp949'))
    r = run('build_erd.py', work, expect_ok=False)
    no_traceback(r, 'a spec that is not utf-8 must be a message, not a traceback')
    if r.returncode == 0:
        raise Fail('a spec that could not be read at all was passed over in silence')
    has(r.stdout + r.stderr, 'ERD_SPEC', 'the message names the variable to look at')


@case('i18n: a placeholder typo in one line does not cost the whole run')
def _(work):
    # 17R 뮤테이션. 번역판의 자리표시자가 영어판과 어긋나면 `str.format` 이 문구를
    # **쓰는 자리**에서 터진다. 그것을 그대로 두면 오타 하나에 그림도 문서도 없이
    # 역추적만 남는다. 카탈로그를 못 읽을 때와 같은 판단을 댄다: 그림은 계속 그리되
    # 왜 말이 바뀌었는지는 알려 준다.
    #
    # 깨진 카탈로그는 **검사 대상 트리 밖**(복사본)에 쓴다 — `i18n: a catalog that
    # cannot be read …` 가 15라운드에 간헐 실패로 배운 자리다.
    import shutil
    tree = work.parent / 'scripts'
    shutil.copytree(HERE, tree, symlinks=True,
                    ignore=shutil.ignore_patterns('__pycache__', 'out', 'erd-build'))
    (tree / 'lang' / 'zz.py').write_text(
        "M = {'word.fig_no': '[Fig. {num}]'}\n", encoding='utf-8')   # en 은 {n} 이다
    if (HERE / 'lang' / 'zz.py').exists():
        raise Fail('the broken catalog was written into the tree under test, not the copy')
    write_schema(work, {'t': table('t', [col('id')], pk=['id'])})
    r = run(str(tree / 'build_erd.py'), work, env={'ERD_LANG': 'zz'}, expect_ok=False)
    if r.returncode != 0:
        raise Fail('one mistyped placeholder took the whole run down:\n'
                   + (r.stdout + r.stderr)[-500:])
    if not list((work / 'out').glob('*.png')):
        raise Fail('the run survived but drew nothing — a broken line must not cost '
                   'the diagrams')
    has(r.stdout + r.stderr, 'word.fig_no',
        'and the line that could not be rendered is named, not swallowed')


@case('errors: a schema.json that is not utf-8 names ERD_WORK instead of a traceback')
def _(work):
    # 17R 뮤테이션. spec 과 **같은 결함의 나머지 절반**이다. 옛 판이 cp949 로 써 둔
    # schema.json 은 `import erd` 한 줄에서 UnicodeDecodeError 로 터졌고, 사용자는
    # 제 파일 이야기 대신 파이썬의 말을 봤다. 문서 빌더 셋이 모두 이 import 를
    # 지나므로 그날은 산출물이 하나도 안 나온다.
    work.mkdir(parents=True, exist_ok=True)
    (work / 'schema.json').write_bytes(
        '{"t": {"name": "t", "note": "주문", "columns": []}}'.encode('cp949'))
    r = run('build_erd.py', work, expect_ok=False)
    no_traceback(r, 'a schema.json that is not utf-8 must be a message, not a traceback')
    if r.returncode == 0:
        raise Fail('a schema.json that could not be read at all was passed over')
    has(r.stdout + r.stderr, 'ERD_WORK', 'the message names the variable to look at')


if __name__ == '__main__':
    raise SystemExit(main(load_all=False))
