# 설치 가이드

[English](INSTALL.md) · **한국어** · [日本語](INSTALL.ja.md) · [Español](INSTALL.es.md)

## 한 줄 설치

```bash
unzip erd-skill.zip && bash erd/install.sh
```

이게 전부다. `install.sh` 가 아래를 알아서 한다:

1. Python 3.9+ 확인
2. 스킬을 `~/.claude/skills/erd` 로 복사
3. `requirements.txt` 로 `python-docx` · `pillow` 설치
4. `psql` / `docker` 유무 확인
5. **Pretendard 폰트**가 없으면 받아서 설치 (물어본 뒤 진행)

끝나면 **Claude Code를 새로 띄운다.** 스킬은 시작할 때 읽으므로 실행 중이던 세션은
스킬을 못 본다. 그다음 "ERD 그려줘" 라고 하면 된다.

설치 스크립트는 영어·한국어·일본어·스페인어로 말한다. 로케일(`LANG` / `LC_ALL`)을
따르며, 고정하려면 `ERD_LANG=ko`(또는 `en`·`ja`·`es`)를 준다.

### 옵션

| 명령 | 하는 일 |
|---|---|
| `bash install.sh` | `~/.claude/skills/erd` 에 설치 (기본) |
| `bash install.sh --project` | 현재 프로젝트 `./.claude/skills/erd` 에 설치 |
| `bash install.sh --here` | 복사 없이 지금 자리에서 의존성만 설치 |
| `bash install.sh --check` | 아무것도 바꾸지 않고 점검만 — 문제 생겼을 때 |

## 손으로 설치할 때

`install.sh` 를 못 쓰는 상황(권한·정책·오프라인)이면 아래 넷을 직접 한다.

**① 압축 풀기** — zip 안에 `erd/` 폴더가 통째로 있으므로 skills 디렉토리에 그대로 푼다.

```bash
mkdir -p ~/.claude/skills && unzip erd-skill.zip -d ~/.claude/skills
```

`~/.claude/skills/erd/SKILL.md` 경로가 되어야 한다. 한 단계 더 깊거나
(`skills/erd/erd/SKILL.md`) 얕으면 Claude Code가 못 찾는다.

**② 파이썬 패키지**

```bash
pip3 install -r ~/.claude/skills/erd/requirements.txt
```

`python-docx` 와 `pillow` 둘뿐이다. 가상환경을 쓰면 그 환경을 켠 셸에서 스크립트도 돌려야 한다.

**③ DB 클라이언트** — `psql` 또는 `docker` 중 하나. macOS는
`brew install libpq && brew link --force libpq`, Debian은 `apt install postgresql-client`.

**④ 폰트** — 본문은 Pretendard, 컬럼은 고정폭 폰트를 쓴다.

```bash
# Pretendard — Regular · Bold 두 개만 있으면 된다
curl -fsSLo /tmp/p.zip https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip
unzip -j /tmp/p.zip 'public/static/Pretendard-Regular.otf' 'public/static/Pretendard-Bold.otf' \
  -d ~/Library/Fonts            # Linux 는 ~/.local/share/fonts  (설치 후 fc-cache -f)
```

없으면 OS 기본 한글 폰트(Apple SD Gothic Neo · 나눔고딕 · Noto CJK)로 자동으로 내려간다.
그림은 나오되 서체만 달라진다. 한글 폰트가 **하나도** 없으면 글자가 □ 로 나온다.

## 설치 확인

```bash
bash ~/.claude/skills/erd/install.sh --check
```

이렇게 나오면 정상이다:

```
1. Python 확인
  ✓ Python 3.12.13  (/usr/bin/python3)

2. 스킬 배치 (건너뜀 — check)
  ✓ 현재 위치: /path/to/erd-skill
  ✓ SKILL.md 확인  (~/.claude/skills/erd)

3. 파이썬 패키지
  ✓ python-docx
  ✓ pillow

4. DB 접속 수단 (둘 중 하나)
  ✓ psql   psql (PostgreSQL) 16.2

5. 렌더링 폰트
  ✓ 본문:   …/Pretendard-Regular.otf
  ✓ 고정폭: …/Menlo.ttc

결과
  ✓ 설치 완료
```

`--check` 는 아무것도 바꾸지 않으므로 배치는 건너뛴다. 다만 설치됐어야 할 자리에
`SKILL.md` 가 있는지는 본다 — `/erd` 가 안 뜰 때 제일 먼저 볼 것이 그것이기 때문이다.

## 첫 실행

Claude에게 맡기지 않고 직접 돌릴 때:

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project                              # 문서 저장 위치
export ERD_WORK=/tmp/erd-build                                # 중간 산출물
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='우리서비스 ERD'

python3 introspect.py && python3 merge_desc.py && \
python3 build_erd.py && python3 build_docx.py
```

DB가 docker 안이면 `ERD_PSQL` 대신 `export ERD_DB='컨테이너명:계정:DB명'`.

`introspect.py` 가 테이블 수를 출력하면 접속 성공이다. 0개면 `ERD_SCHEMAS`(기본
`public`)를 실제 스키마 이름으로 바꾼다. 나머지 환경변수·spec 작성은 `SKILL.ko.md` 를 본다.

## 폰트 환경변수

자동 탐지 결과를 무시하고 직접 지정할 때 쓴다.

| 변수 | 용도 |
|---|---|
| `ERD_FONT` / `ERD_FONT_BOLD` | PNG 본문 폰트 파일 경로 (기본: Pretendard 자동 탐지) |
| `ERD_MONO` / `ERD_MONO_BOLD` | PNG 고정폭 폰트 파일 경로 |
| `ERD_DOC_FONT` | docx 본문 **폰트 이름** (기본은 `ERD_LANG` 을 따른다 — ko 는 `Pretendard`, en 은 `Calibri`) |
| `ERD_DOC_MONO` | docx 고정폭 폰트 이름 (ko 는 `D2Coding`, 그 밖은 `Consolas`) |

PNG는 파일 경로, docx는 폰트 이름이다 — docx는 여는 PC에 그 폰트가 있어야 그대로
보이고, 없으면 Word가 대체한다. 배포처에 Pretendard가 없을 게 확실하면
`export ERD_DOC_FONT='맑은 고딕'` 로 돌린다.

## 자주 걸리는 것

**`ModuleNotFoundError: No module named 'docx'`**
`pip install docx` 가 아니라 `python-docx` 다. 이름이 다르다.
`install.sh --check` 를 돌리면 어느 파이썬을 보고 있는지 같이 나온다.

**설치는 됐는데 import 가 안 된다**
`pip3` 와 `python3` 가 서로 다른 설치본일 때다. `python3 -m pip install -r requirements.txt`
처럼 **같은 파이썬으로** 설치한다. install.sh 는 이 방식을 쓴다.

**`/erd` 가 목록에 없다**
① `ls ~/.claude/skills/erd/SKILL.md` 가 나오는지 ② Claude Code를 재시작했는지
③ `SKILL.md` 첫 줄이 `---` 로 시작하고 `name: erd` 가 있는지 — 이 순서로 본다.

**`[경고] DB 조회 실패`**
`ERD_PSQL` / `ERD_DB` 값을 확인한다. 같은 명령을 셸에서 직접 쳐서 붙는지 먼저 본다.
둘 다 설정되어 있으면 `ERD_PSQL` 이 이긴다.

**PNG 한글이 □ 로 나온다**
한글 폰트가 없다. `install.sh` 를 다시 돌려 Pretendard를 설치하거나 `ERD_FONT` 로 지정한다.

**설명 없는 컬럼 목록이 출력됨**
정상 동작이다. `merge_desc.py` 의 `MANUAL` 사전에 채우고 다시 돌린다. 자세한 건
`SKILL.ko.md` 의 "컬럼 설명" 절.

**산출물이 안 보인다**
`.graphml` · `.docx` 는 `$ERD_PROJ`, PNG는 `$ERD_WORK/out/` 에 있다.
