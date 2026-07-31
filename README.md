# erd — PostgreSQL ERD · 스키마 문서 자동 생성 스킬

DB에 직접 붙어 실제 스키마를 읽고 **ERD와 스키마 정의서를 통째로 만드는** [Claude Code](https://claude.com/claude-code) 스킬.

손으로 그리지 않으므로 **그림과 DB가 어긋나지 않는다.** 스키마가 바뀌면 다시 돌리면 된다.

```bash
python3 introspect.py && python3 merge_desc.py && python3 build_erd.py && python3 build_html.py
```

100개 테이블 · 1,235개 컬럼짜리 DB에서 **3.1MB HTML 한 개**가 나온다 — 목차, 전체 개요도,
영역별 ERD 17장, 테이블별 컬럼표, 전체 상세 ERD까지 전부 그 안에 들어 있다.

## 무엇이 나오나

| 산출물 | 쓰임 |
|---|---|
| `<문서명>.html` | **스키마 정의서** — 목차 · 개요 ERD · 영역별 ERD · 테이블별 컬럼표 · 전체 ERD. 그림이 파일 안에 든 단일 HTML |
| `<문서명>.docx` | 제출·인쇄용 문서 (그림 + 컬럼 설명표 + FK 목록) |
| `<문서명>.graphml` | yEd에서 열어 직접 재배치·재출력 |
| `out/erd_*.png` · `.svg` | 개요도 · 영역별 상세도 · 전체도 |

HTML은 목차에서 테이블로 바로 뛰고, **ERD를 클릭하면 원본 크기로 확대된다.**
벡터(SVG)라 아무리 키워도 글자가 살아 있다. 파일 하나만 보내면 되므로 공유가 쉽다.

## 왜 만들었나

DB 문서는 만들기는 쉬운데 **유지되지 않는다.** 스키마가 바뀌면 그림이 먼저 낡고,
낡은 그림은 안 보게 되고, 결국 아무도 문서를 믿지 않게 된다.

그래서 세 가지를 지키게 만들었다.

**① 그림은 DB에서 나온다.** 사람이 그리지 않는다. `information_schema`와 `pg_catalog`를
읽어 테이블·컬럼·타입·PK·FK(삭제 규칙 포함)·유니크·인덱스·CHECK를 가져온다.

**② 설명은 잃어버리지 않는다.** ERD의 값어치는 컬럼 설명에서 나오는데, 문서를 다시 뽑을
때마다 사람이 다듬어 둔 설명이 날아가면 아무도 설명을 안 쓰게 된다. 그래서 **이전 판
문서에서 설명을 물려받는다.**

```bash
ERD_DOC_HTML=이전문서.html python3 merge_desc.py
#   이전 문서에서 컬럼 설명 1123건 인계: …
#   설명 출처별 컬럼 수: {'ddl': 268, 'doc': 951, 'manual': 16, 'none': 0}
```

`none`이 0이 아니면 어느 컬럼이 비었는지 목록으로 알려준다. **설명 없는 컬럼을 남긴 채
넘어가지 않는다.**

**③ 그림 품질을 눈으로 판단하지 않는다.** 렌더링할 때마다 자체 검증 결과가 찍힌다.

```
검증 erd_area_A.png: 라벨↔테이블 0 · 세로선 중첩 0 · 가로선 중첩 0
```

라벨이 테이블을 덮거나 선이 겹치면 숫자로 드러난다. 영역별 상세도는 전부 0이어야 한다.

## 설치

```bash
git clone git@github.com:uygnoey/erd-skill.git
bash erd-skill/install.sh
```

`install.sh`가 스킬 배치(`~/.claude/skills/erd`), 의존성(`python-docx`·`pillow`),
Pretendard 폰트까지 알아서 처리한다. 끝나면 **Claude Code를 새로 띄우고** "ERD 그려줘"
라고 하거나 `/erd`를 부르면 된다.

| 명령 | 하는 일 |
|---|---|
| `bash install.sh` | `~/.claude/skills/erd`에 설치 (기본) |
| `bash install.sh --project` | 현재 프로젝트 `./.claude/skills/erd`에 설치 |
| `bash install.sh --check` | 아무것도 바꾸지 않고 점검만 |

자세한 건 [INSTALL.md](INSTALL.md).

### 준비물

- Python 3.9+ / `python-docx` / `pillow`
- `psql` 또는 `docker` 중 하나
- 한글 폰트 — 본문은 Pretendard(자동 설치), 없으면 OS 기본 한글 폰트로 내려간다

## 쓰는 법

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project        # 문서 저장 위치
export ERD_WORK=/tmp/erd-build          # 중간 산출물
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='우리서비스 스키마 정의서'

python3 introspect.py    # ① DB → schema.json
python3 merge_desc.py    # ② 컬럼 설명 채우기
python3 build_erd.py     # ③ GraphML + PNG + SVG
python3 build_html.py    # ④ HTML 스키마 정의서
python3 build_docx.py    # ⑤ docx 문서 (선택)
```

docker 안의 DB라면 `ERD_PSQL` 대신 `export ERD_DB='컨테이너:계정:DB'`.

**설정 파일 없이도 돌아간다.** 스키마와 테이블명 접두어로 영역을 자동 분류하고 색을
배정한다. 결과가 아쉬울 때만 `erd.spec.json`을 쓰면 된다.

### 여러 DB를 한 문서로

```bash
ERD_LABEL=shop ERD_DB='shop-postgres:app:shop' python3 introspect.py
ERD_LABEL=mart ERD_PSQL='psql postgresql://app:pw@localhost:5433/mart' python3 introspect.py
python3 merge_schemas.py shop mart      # 테이블 키가 'shop.orders' 처럼 된다
```

DB 사이에는 물리 FK가 있을 수 없으므로, 두 DB를 잇는 흐름은 spec의 `derives`로 적는다.

### erd.spec.json — 그림의 뼈대

전부 선택 항목이고, 없는 건 자동 추론된다.

```json
{
  "areas":    [["A", "주문", "public", ["orders", "order_items"]]],
  "layer_of": {"orders": "TX", "order_items": "TX"},
  "layers":   {"TX": ["#25324D", "#35507D", "#4A80C0", "거래계"]},
  "roles":    {"orders": "주문 헤더"},
  "derives":  [["ext_feed", "orders", "외부 연동"]],
  "doc":      {"title": "쇼핑몰 스키마 정의서"}
}
```

| 키 | 뜻 |
|---|---|
| `areas` | `[코드, 영역명, 스키마, [테이블…]]` — 그룹 박스이자 배치 단위 |
| `layer_of` / `layers` | 테이블→레이어, 레이어→`[채움, 헤더, 테두리, 범례라벨]` |
| `roles` | 테이블 역할명 (없으면 DB 테이블 코멘트) |
| `derives` | ETL 흐름 — FK가 아닌 데이터 흐름. 갈색 점선 |
| `doc` | 문서 제목·표지·머리말·영역별 설명 |

예시는 [`examples/minimal.spec.json`](examples/minimal.spec.json)(최소),
[`examples/full.spec.json`](examples/full.spec.json)(전체).

환경변수 전체 목록은 [SKILL.md](SKILL.md)에 있다.

## 그림 규칙

문서 제출용이라 타협하지 않는 것들이 있다.

- **색 = 레이어, 묶음 = 스키마·영역.** 원천과 가공 계층은 반드시 색이 다르다
- **선은 두 종류만.** FK(회색 실선), ETL 흐름(갈색 점선). 삭제 규칙은 문서 표에만 적는다
- **직교 라우팅.** 선이 테이블을 관통하지 않는다. 선은 노드 중앙이 아니라 **실제 컬럼 행**에서 나간다
- **교차는 반원으로 점프.** 연결과 교차를 구분하기 위함
- **라벨은 노드보다 나중에.** 안 그러면 노드가 덮는다
- **캔버스는 2단계로 잰다.** 1×1 더미에 한 번 그려 실제 범위를 재고 여백을 붙인다.
  노드 위치만으로 크기를 잡으면 밖으로 나간 라벨·관계선이 잘린다

## PNG와 SVG

같은 그림이다. 좌표와 폰트 폭을 PIL로 똑같이 재고 그리기만 벡터로 바꾼다
(`svg_canvas.py`가 `ImageDraw` 인터페이스를 흉내 낸다).

|  | 개요도 | 영역별 | 전체 상세도 |
|---|---|---|---|
| PNG | 0.70MB | 0.41MB | 3.27MB |
| **SVG** | **0.48MB** | **0.23MB** | **0.30MB** |

SVG는 보는 PC의 폰트로 글자를 그리므로 폰트가 없으면 폭이 달라져 칸을 넘어간다.
그래서 모든 `<text>`에 PIL이 잰 폭을 `textLength`로 못 박았다. **폰트가 없어도 레이아웃이
깨지지 않는다.**

## 구조

```
install.sh        자동 설치 (배치·의존성·폰트)
scripts/
  config.py       경로·DB 접속·spec 로딩·영역 자동 분류
  introspect.py   DB → schema.json
  parse_ddl.py    DDL 파싱 → schema.json  (미적용 변경까지 반영할 때)
  merge_schemas.py 여러 DB의 schema를 하나로
  merge_desc.py   컬럼 설명 병합
  erd.py          레이아웃·렌더·GraphML
  svg_canvas.py   ImageDraw 호환 SVG 캔버스
  build_erd.py    PNG·SVG·GraphML 실행기
  build_html.py   HTML 스키마 정의서
  build_docx.py   docx 문서
examples/         spec 예시
```

## 다른 DB

`introspect.py`의 쿼리는 PostgreSQL 기준이다. MySQL도 `information_schema`는 표준이라
컬럼·PK·FK 쿼리는 거의 그대로 쓸 수 있고, `col_description` 대신
`columns.column_comment`를 쓰면 된다.

## 라이선스

MIT
