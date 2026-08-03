# ERD 생성 (한국어)

`SKILL.md` 의 한국어 원본이다. Claude 가 읽는 것은 영어판 `SKILL.md` 쪽이고,
이 문서는 사람이 읽기 위한 것이다.

DB에 붙어 실제 스키마를 읽고 ERD를 만든다. 손으로 그리지 않으므로 **그림과 DB가
어긋나지 않는다.**

아직 DB에 넣지 않은 변경까지 그리려면 `introspect.py` **대신** `parse_ddl.py` 를 돌린다 —
`*.sql` 을 읽어 같은 `schema.json` 을 쓴다. 별도의 경로이지, 평소 실행이 알아서
집어 오는 것이 아니다.

## 출력 언어

사람이 읽는 것 — 콘솔 출력, HTML·docx 문서, 그림의 범례 — 은 `ERD_LANG` 을 따른다.
`en`·`ko`·`ja`·`es` 중 하나이고, 없으면 로케일, 그것도 없으면 영어다.

**사용자가 쓰는 말에 맞춘다.** 일본어로 물었으면 스크립트를 돌리기 전에
`export ERD_LANG=ja`. `erd.spec.json` 의 값(영역명·역할명·문서 제목)은 사람이 적은
그대로 쓰이므로 카탈로그보다 우선한다.

언어를 늘리려면 `scripts/lang/` 에 파일 하나를 놓으면 된다 — 그 폴더에 있는 것이 곧
지원 언어다. 빠진 키는 영어로 떨어진다.

## 빠른 시작

설치가 안 되어 있으면 먼저 `bash install.sh` — 의존성·폰트까지 알아서 깐다 (`INSTALL.ko.md`).

```bash
cd .claude/skills/erd/scripts
pip3 install -r ../requirements.txt        # install.sh 를 돌렸으면 생략

export ERD_PROJ=/path/to/project          # 문서 저장 위치
export ERD_WORK=/tmp/erd-build            # 중간 산출물
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='우리서비스 ERD'
export ERD_LANG=ko                        # en · ko · ja · es

python3 introspect.py    # ① DB → schema.json
python3 merge_desc.py    # ② 컬럼 설명 채우기
python3 build_erd.py     # ③ GraphML + PNG + SVG
python3 build_html.py    # ④ HTML 스키마 정의서   ← 화면에서 읽을 때
python3 build_docx.py    # ⑤ docx 문서            ← 제출·인쇄할 때
```

`erd.spec.json` 없이도 동작한다 — 스키마와 테이블명 접두어로 영역을 자동 분류하고
색을 배정한다.

**자동 분류는 일단 그려보는 용도다.** 이름 규칙이 고르지 않으면 어디에도 안 붙는
테이블이 '기타' 로 모인다(80개 DB 실측 24%). 기타가 커질수록 그 그림은 세로로 길어져
읽기 나빠진다. 문서로 낼 거면 spec 으로 영역을 직접 잡는다 — **영역 구분이 곧 문서의
목차**가 되므로, 사람이 정하는 편이 결과가 낫다.

**여러 DB를 한 문서로** 묶을 땐 라벨을 붙여 각각 읽고 합친다:

```bash
ERD_LABEL=shop ERD_DB='shop-postgres:app:shop' python3 introspect.py
ERD_LABEL=mart ERD_PSQL='psql postgresql://app:pw@localhost:5433/mart' python3 introspect.py
python3 merge_schemas.py shop mart     # 테이블 키가 'shop.orders' 처럼 된다
```

## 산출물

| 파일 | 내용 |
|---|---|
| `$ERD_PROJ/<문서명>.html` | **스키마 정의서** — 목차 · 개요 ERD · 영역별 ERD · 테이블별 컬럼표 · 전체 ERD. 그림이 파일 안에 든 단일 HTML |
| `$ERD_PROJ/<문서명>.docx` | 그림 + 테이블별 컬럼 설명표 + FK 목록 |
| `$ERD_PROJ/<문서명>.graphml` | yEd에서 열어 재배치·재출력. 컬럼 설명 포함 |
| `$ERD_WORK/out/erd_overview.png·svg` | 전체 관계 개요 (컬럼 없이 구조만) |
| `$ERD_WORK/out/erd_full.png·svg` | 전체 ERD (모든 컬럼 + 설명) |
| `$ERD_WORK/out/erd_area_*.png·svg` | 영역별 상세도 |

**PNG 와 SVG 는 같은 그림이다.** 좌표·폰트 폭을 PIL 로 똑같이 재고 그리기만 벡터로
바꾼다(`svg_canvas.py`). SVG 는 용량이 1/10 이고 확대해도 안 뭉개서 HTML 에 박는 쪽이
쓰고, PNG 는 docx·발표자료처럼 래스터가 필요한 쪽이 쓴다.

## HTML 스키마 정의서

`build_html.py` 는 화면에서 읽고 찾기 위한 문서를 만든다. 목차에서 테이블로 바로
뛰고, ERD 는 클릭하면 원본 크기로 확대된다(벡터라 글자가 살아 있다). 그림이 파일
안에 들어가므로 **HTML 한 개만 보내면 된다.**

구성은 문서 흐름을 따른다 — ① 표지·DB 요약·범례 ② 목차 ③ 전체 구조 개요도
④ DB > 영역 > 테이블 (영역마다 그 영역 ERD가 표 앞에) ⑤ 부록: 전체 상세 ERD.

이전 판 문서가 있으면 **거기 적힌 컬럼 설명을 물려받는다.** 문서를 다시 뽑을 때마다
사람이 다듬어 둔 설명을 잃지 않기 위한 것이다:

```bash
ERD_DOC_HTML=이전문서.html python3 merge_desc.py
#   이전 문서에서 컬럼 설명 1123건 인계: …
```

## 환경변수

| 변수 | 기본값 | 용도 |
|---|---|---|
| `ERD_PROJ` | 현재 디렉토리 | 문서·GraphML 저장 위치 |
| `ERD_WORK` | `$ERD_PROJ/erd-build` | schema.json · PNG |
| `ERD_SPEC` | `$ERD_WORK/erd.spec.json` | 그림 뼈대 정의 (선택) |
| `ERD_DOCNAME` | `ERD` | 산출 파일명 (확장자 제외) |
| `ERD_LANG` | 로케일, 없으면 `en` | 출력 언어: `en` · `ko` · `ja` · `es` |
| **`ERD_PSQL`** | — | psql 명령 직접 지정. 예: `psql postgresql://u:p@h:5432/db` |
| **`ERD_DB`** | — | docker 경유. 형식: `컨테이너:계정:DB` |
| `ERD_SCHEMAS` | `public` | 대상 스키마 (콤마 구분) |
| `ERD_EXCLUDE` | — | 제외할 테이블 정규식 |
| `ERD_MAX_AREAS` | `12` | 자동 분류 시 영역 수 상한 |
| `ERD_SQL_DIR` | `$ERD_PROJ/sql` | DDL 파싱을 쓸 때만 |
| `ERD_SQL_FILES` | — | DDL 파싱: 읽을 파일을 직접 지정 (콤마 구분, 기본은 디렉토리의 `*.sql` 전부) |
| `ERD_REF_SCHEMA` | — | DDL 파싱: 읽기 전용 원천 스키마를 함께 넣을 때 |
| `ERD_REF_TABLES` | — | DDL 파싱: 그 스키마에서 가져올 테이블 (콤마 구분) |
| `ERD_DEFAULT_PK` | — | DDL 파싱: PK 를 못 찾은 기존 테이블에 가정할 컬럼명 |
| `ERD_MODEL_DIR` | `$ERD_PROJ/models` | ORM 주석에서 설명 추출 |
| `ERD_LABEL` | — | 여러 DB를 합칠 때 붙일 라벨 (`schema.<라벨>.json`) |
| `ERD_DOC_HTML` | — | 이전 판 문서에서 컬럼 설명 인계 (콤마로 여러 개) |
| `ERD_SVG` | `1` | PNG 옆에 SVG도 생성 |
| `ERD_SVG_TITLE` | `0` | SVG 안에 제목을 그린다 (문서엔 캡션이 따로 붙어 기본은 끔) |
| `ERD_HTML_STATS` | `0` | HTML 배지에 행수·용량 표시 (통계값이라 기본은 끔) |
| `ERD_HTML_FULL` | `1` | HTML 부록의 전체 상세 ERD |
| `ERD_HTML_SVG` | `1` | HTML에 SVG 대신 PNG를 박으려면 `0` |
| `ERD_HTML_OUT` | `$ERD_PROJ/<문서명>.html` | HTML 경로 직접 지정 |
| `ERD_FONT`·`ERD_MONO` | 자동 탐지 | PNG·SVG 폰트 파일 (`_BOLD` 접미사로 굵은꼴) |
| `ERD_DOC_FONT`·`ERD_DOC_MONO` | `ERD_LANG` 을 따름 | docx 폰트 **이름** (ko: `Pretendard`·`D2Coding`, en: `Calibri`·`Consolas`) |

`ERD_PSQL` 과 `ERD_DB` 중 하나만 있으면 된다. 둘 다 있으면 `ERD_PSQL` 이 이긴다.

서버는 **PostgreSQL 9.4 이상**이어야 한다 — `introspect.py` 가 버전을 먼저 읽고, 그보다
낮으면 반만 읽은 스키마를 넘기는 대신 메시지를 내고 멈춘다. 9.4·9.6·10·11·12·16·17 에서
확인했다. FK 조회는 11 미만에서 파티션 복제본 거르는 술어를 뺀다 —
`pg_constraint.conparentid` 가 아직 없고, 거를 복제본도 없기 때문이다.

## 컬럼 설명 (가장 중요)

ERD의 값어치는 설명에서 나온다. 우선순위대로 채운다:

**수기 사전 > DB 코멘트 > 이전 판 문서 > ORM 주석 > 공통 컬럼 사전**

```
$ python3 merge_desc.py
설명 출처별 컬럼 수: {'ddl': 268, 'doc': 951, 'orm': 0, 'manual': 16, 'common': 0, 'none': 0}
```

`none` 이 0이 아니면 목록이 출력된다. `merge_desc.py` 의 `MANUAL` 사전에 추가하고
다시 돌린다. **설명 없는 컬럼을 남긴 채 넘어가지 않는다.**

`COMMON` 사전에는 `seq`, `created_at` 같은 흔한 컬럼이 이미 들어 있다. 그 문구는
언어 카탈로그에서 오므로 `ERD_LANG` 을 따른다. 프로젝트 공통 컬럼이 있으면 여기에
추가하면 테이블마다 쓸 필요가 없다.

## erd.spec.json — 그림의 뼈대

자동 분류가 아쉬울 때만 쓴다. 전부 선택 항목이고, 없는 항목은 자동 추론된다.

```json
{
  "areas":    [["A", "주문", "public", ["orders", "order_items"]]],
  "layer_of": {"orders": "TX", "order_items": "TX"},
  "layers":   {"TX": ["#25324D", "#35507D", "#4A80C0", "거래계"]},
  "roles":    {"orders": "주문 헤더"},
  "derives":  [["ext_feed", "orders", "외부 연동"]],
  "doc":      {"title": "쇼핑몰 ERD", "meta": [["작성자", "홍길동", "", ""]]}
}
```

| 키 | 뜻 |
|---|---|
| `areas` | `[코드, 영역명, 스키마, [테이블…]]` — 그룹 박스이자 배치 단위 |
| `layer_of` / `layers` | 테이블→레이어, 레이어→`[채움, 헤더, 테두리, 범례라벨]` |
| `roles` | 테이블 한글 역할명 (없으면 DB 테이블 코멘트) |
| `derives` | ETL 흐름 — FK가 아닌 데이터 흐름. 갈색 점선 |
| `doc` | 문서 제목·표지 정보·목적·범위·근거, 6·7장 데이터 |

`doc.mapping` / `doc.open_items` 가 있으면 6장(설계안 대조), 7장(미반영 항목)이
문서에 추가된다. 없으면 그 장은 생략된다.

HTML 문서는 `doc` 의 아래 키를 더 쓴다 — 전부 선택이다.

| 키 | 뜻 |
|---|---|
| `doc.intro` | 표지 아래 들어갈 머리말 (HTML 태그 사용 가능) |
| `doc.area_desc` | `{영역코드: 설명}` — 영역 제목 밑에 붙는 안내문 |
| `doc.db_names` | `{라벨: 사람이 읽는 DB 이름}` — 여러 DB를 합쳤을 때 |

예시: `examples/minimal.ko.spec.json` (최소), `examples/full.ko.spec.json` (전체)

## 지켜야 할 규칙

문서 제출용이라 아래는 타협하지 않는다. 어기면 검토가 안 된다.

**색 = 레이어, 묶음 = 스키마·영역.** 원천 데이터와 가공 계층은 반드시 색이 달라야
한다. 둥근 그룹 박스로 스키마·기능 영역을 묶는다.

**선은 두 종류만.** FK(회색 실선), ETL 흐름(갈색 점선). 삭제 규칙(CASCADE/SET NULL)을
색으로 나누면 선이 네 종류로 보인다 — 그건 문서 표에만 적는다.

**직교 라우팅.** 세로 이동은 열 사이 통로에서만, 열을 건너뛸 땐 그 열의 노드 사이 빈
구간으로 지난다. 선이 테이블을 관통하면 어디서 어디로 가는지 추적이 불가능해진다.
선은 노드 중앙이 아니라 **실제 컬럼 행**에서 나가고 들어간다.

**교차는 반원으로 점프.** 수평선이 수직선을 넘을 때. 연결과 교차를 구분하기 위함.

**라벨은 노드보다 나중에.** 안 그러면 노드가 덮는다. 선 위에 얹지 말고 위·아래로
띄우며, 테이블과 겹치는 자리는 후보에서 제외(강제 조건).

**캔버스는 2단계로 잰다.** 1×1 더미에 한 번 그려 실제 사용 범위를 재고, 거기에 여백을
붙여 그린다. 노드 위치만으로 크기를 잡으면 밖으로 나간 라벨·관계선·그룹 박스가 잘린다.

**문서 삽입은 폭·높이 둘 다 맞춘다.** 폭만 지정하면 세로가 긴 그림이 페이지를 넘어
잘린다. 가로 A4 기준 가용 26.7 × 18.0cm.

## 자동 검증

렌더링할 때마다 출력된다. 눈으로 판단하지 않는다.

```
검증 erd_overview.png: 라벨↔테이블 해당 없음 · 라벨↔라벨 해당 없음 · 선↔테이블 0 · 세로선 중첩 0 · 가로선 중첩 0
검증 erd_full.png: 라벨↔테이블 0 · 라벨↔라벨 0 · 선↔테이블 0 · 세로선 중첩 0 · 가로선 중첩 0
검증 erd_area_A.png: 라벨↔테이블 0 · 라벨↔라벨 0 · 선↔테이블 0 · 세로선 중첩 0 · 가로선 중첩 0
```

0 이어야 하는 항목이 0 이 아니면 같은 줄 끝에 `[경고] 0 이어야 한다: …` 가 붙는다 —
**`[경고]` 가 보이면 회귀다.** 그 그림에서 받아들이기로 한 값은 경고 대신 `3(허용)`
처럼 표시된다.

`해당 없음` 은 **그 그림에서 그 검사를 하지 않았다** 는 뜻이고, 0 의 대용이 아니다.
개요도는 관계 라벨을 그리지 않으므로 라벨 두 항목은 잴 것이 없다 — 여기에 0 을 찍으면
하지도 않은 검사가 깨끗하다고 말하는 셈이 된다.

- **라벨↔테이블** — 반드시 0. 아니면 `flush_labels()` 후보 범위를 넓힌다.
- **선↔테이블** — 반드시 0. 테이블을 관통하는 선은 노드가 덮어 버려 눈에 안 보인다.
  이 숫자만이 그걸 드러낸다. 0이 아니면 통로가 넘친 것이다 — 배치 호출의 `hgap` 을
  넓히거나 영역을 쪼갠다.
- **세로선 중첩** — 반드시 0. `slot()` 이 자리를 못 찾고 포기하면 발생한다. 아주 빽빽한
  영역에서는 아직 나올 수 있고, 그건 소음이 아니라 진짜 결함이다.
- **가로선 중첩** — 모든 그림에서 반드시 0. 라우터가 고르지 않는 두 가지는 일부러 세지
  않는다: 같은 컬럼 행으로 모이는 합류와, 진출입 꼬리끼리 스치는 것. 꼬리의 y 는 선이
  드나드는 **실제 컬럼 행** 이고 그건 이 배치의 불변식이라, 상관없는 두 테이블의 행
  높이가 우연히 겹치면 짧은 꼬리는 반드시 포개진다. 라우터가 고르는 것(통로 lane,
  자기참조 팔)은 모두 세고, 같은 선을 두 번 그린 것도 센다. 0 이 아니면 통로 lane 이
  피했어야 할 행에 얹힌 것이다 — `hgap` 을 넓히거나 spec 에서 그 영역을 쪼갠다.
- **라벨↔라벨** — 반드시 0. 라벨 둘이 포개진 것.

`ERD_VERIFY_LOG` 를 지정하면 같은 결과가 그림 하나당 한 줄씩 JSONL 로도 남는다
(`{"file": …, "counts": {…}, "tolerated": […], "warn": […]}`, 재지 않은 항목은 `null`).
`selftest.py` 는 찍힌 줄이 아니라 이 기록을 읽는다 — 찍힌 줄은 사람 좋으라고 서식이
바뀌는 물건이고, 실제로 `(허용)`·`[경고]` 꼬리가 붙자 숫자를 긁던 정규식이 **마지막
항목을 0 이 아닐 때만** 놓쳤다. 찍힌 줄을 파싱하는 코드를 더 만들지 않는다.

## 회귀 시험

`selftest.py` 는 만들어 낸 입력으로 스킬 전체를 한 번 돌리고 결과를 검사한다.
DB 도 docker 도 필요 없고 5초쯤 걸린다.

```bash
python3 selftest.py            # 전부
python3 selftest.py parse      # 이름에 'parse' 가 든 항목만
```

그림 품질은 렌더링할 때마다 검증이 찍히지만 그 밖의 기능은 재는 것이 없었다. 그래서
고칠 때마다 다른 데가 조용히 죽었다 — 인라인 `--` 주석은 두 판을 통째로 빈 문자열인
채 지나갔고, 자기참조 루프는 둘이 겹쳐 하나로 보이는 동안 검증이 0 을 찍었다.
거기 담긴 항목은 전부 **한 번이라도 조용히 깨졌던 것**이다.

**무언가를 고쳤으면 그것을 잡아 줬을 항목을 하나 남긴다.** 그 파일은 그러라고 있다.

문서 삽입 크기도 확인한다:

```python
from docx import Document
for s in Document('<문서>.docx').inline_shapes:
    print(s.width.cm, s.height.cm)      # 26.7 × 18.0 이내
```

## 파일 구조

```
INSTALL.md        설치 가이드 (.ko · .ja · .es 도 있다)
install.sh        자동 설치 (배치·의존성·폰트)
requirements.txt  파이썬 의존성
scripts/
  selftest.py     회귀 시험 — 만들어 낸 입력으로 스킬을 돌려 본다 (DB 불필요)
  i18n.py         출력 언어를 고르고 메시지 키를 푼다
  lang/           문구 카탈로그 — en.py · ko.py · ja.py · es.py
  config.py       경로·DB 접속·spec 로딩·영역 자동 분류
  introspect.py   DB → schema.json          (DDL 없이 이것만으로 충분)
  parse_ddl.py    DDL 파싱 → schema.json    (미적용 변경까지 반영할 때)
  merge_schemas.py 여러 DB의 schema.<라벨>.json 을 하나로
  merge_desc.py   컬럼 설명 병합. MANUAL 사전이 최우선
  erd.py          레이아웃·렌더·GraphML
  svg_canvas.py   ImageDraw 호환 SVG 캔버스 (PNG와 같은 좌표로 벡터 출력)
  build_erd.py    PNG·SVG·GraphML 실행기
  build_html.py   HTML 스키마 정의서 생성
  build_docx.py   docx 문서 생성
examples/
  minimal.spec.json                    최소 예시
  full.spec.json                       전체 예시 (영역·레이어·ETL·문서 메타)
  *.ko.spec.json                       같은 두 예시의 한국어판
```

`parse_ddl.py` 는 문자열 리터럴·`$tag$` 블록·주석을 지운 사본을 먼저 만들고, 괄호 세기와
콤마 나누기를 그 위에서 한다. 그러지 않으면 반드시 샌다 — `DEFAULT '('` 하나에 다음
컬럼이 사라졌고, 문자열 안의 `--` 에 그 뒤 컬럼이 사라졌다.
psql 출력 구분자는 `\x1f` 다 — `|` 는 기본값·코멘트에 섞여 나온다.

## 다른 DB·OS

- **MySQL 등** — `introspect.py` 의 쿼리는 PostgreSQL `information_schema` 기준이다.
  MySQL도 `information_schema` 는 표준이라 컬럼·PK·FK 쿼리는 거의 그대로 쓸 수 있고,
  `col_description` 대신 `columns.column_comment` 를 쓰면 된다.
- **폰트** — 본문은 **Pretendard**, 컬럼은 고정폭(Menlo·DejaVu Sans Mono)이다.
  `erd.py` 가 OS별 후보를 훑어 자동으로 고르고, 없으면 OS 기본 한글 폰트로 내려간다.
  직접 지정하려면 `ERD_FONT`·`ERD_FONT_BOLD`·`ERD_MONO`·`ERD_MONO_BOLD` (파일 경로).
  docx 는 파일이 아니라 **폰트 이름**을 쓴다 — `ERD_DOC_FONT` (기본은 `ERD_LANG` 을
  따른다 — ko 는 `Pretendard`).
  Pretendard 설치는 `install.sh` 가 해준다.
