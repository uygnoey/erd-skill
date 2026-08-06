# インストールガイド

[English](INSTALL.md) · [한국어](INSTALL.ko.md) · **日本語** · [Español](INSTALL.es.md)

## 1行で終わる

```bash
unzip erd-skill.zip && bash erd/install.sh
```

これで全部だ。`install.sh` が以下を引き受ける:

1. Python 3.9+ の確認
2. スキルを `~/.claude/skills/erd` にコピー
3. `requirements.txt` から `python-docx` と `pillow` をインストール
4. `psql` / `docker` の有無を確認
5. **Pretendardフォント** がなければダウンロードしてインストール(確認してから)

「確認してから」は文字どおりだ。尋ねる端末がない場合(CI・パイプ)はダウンロードせず、
すでにあるファイルも上書きしない。そう伝えたうえで先に進む。

終わったら **Claude Code のセッションを新しく開く。** スキルは起動時に読み込まれるので、
すでに動いていたセッションからは見えない。そのうえで「ERDを描いて」と言えばいい。

インストーラは英語・韓国語・日本語・スペイン語を話す。ロケール(`LANG` / `LC_ALL`)に
従い、固定したければ `ERD_LANG=ja`(または `en`・`ko`・`es`)を設定する。

### オプション

| コマンド | 動作 |
|---|---|
| `bash install.sh` | `~/.claude/skills/erd` にインストール(デフォルト) |
| `bash install.sh --project` | 現在のプロジェクトの `./.claude/skills/erd` にインストール |
| `bash install.sh --here` | コピーせず、その場で依存パッケージだけインストール |
| `bash install.sh --check` | 何も変えずにチェックだけ — 何かおかしいときに |

四つは同時に使えない。二つ渡すと黙って一つに畳まず、拒否する — `--check --project` が
`--project` として終わり、38個のファイルを書いていた場所だ。

## 手動でインストールする

`install.sh` が使えない状況(権限・ポリシー・オフライン)なら、次の4つを自分でやる。

**① 展開** — zipには `erd/` フォルダが丸ごと入っているので、skillsディレクトリに
そのまま展開する。

```bash
mkdir -p ~/.claude/skills && unzip erd-skill.zip -d ~/.claude/skills
```

パスが `~/.claude/skills/erd/SKILL.md` になっていなければならない。1階層深くても
(`skills/erd/erd/SKILL.md`)浅くても、Claude Code は見つけられない。

**② Pythonパッケージ**

```bash
pip3 install -r ~/.claude/skills/erd/requirements.txt
```

`python-docx` と `pillow` の2つだけ。virtualenvを使うなら、その環境を有効にした
シェルでスクリプトも実行する。

**③ DBクライアント** — `psql` か `docker` のどちらか。macOSは
`brew install libpq && brew link --force libpq`、Debianは `apt install postgresql-client`。

**④ フォント** — 本文はPretendard、カラムは等幅フォントを使う。`ERD_LANG=ja` では
Pretendardに漢字グリフがないため、日本語対応フォント(Hiragino Sans / Noto Sans JP /
Yu Gothic)があればそちらを優先する。

```bash
# Pretendard — 必要なのは Regular と Bold の2つだけ
curl -fsSLo /tmp/p.zip https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip
unzip -j /tmp/p.zip 'public/static/Pretendard-Regular.otf' 'public/static/Pretendard-Bold.otf' \
  -d ~/Library/Fonts            # Linuxは ~/.local/share/fonts  (その後 fc-cache -f)
```

なければ、対象の文字をカバーするOSフォント(Apple SD Gothic Neo・Nanum Gothic・
Noto CJK)にフォールバックする。図は出るが、書体だけ変わる。カバーするフォントが
**1つも** なければ、文字は □ になる。

## インストールの確認

```bash
bash ~/.claude/skills/erd/install.sh --check
```

正常ならこう出る:

```
1. Python の確認
  ✓ Python 3.12.13  (/usr/bin/python3)

2. スキルの配置 (スキップ — check)
  ✓ 現在の場所: /path/to/erd-skill
  ✓ SKILL.md あり  (~/.claude/skills/erd)

3. Python パッケージ
  ✓ requirements.txt  (~/.claude/skills/erd/requirements.txt)
  ✓ python-docx 1.2.0  (>= 1.1.0)
  ✓ pillow 12.3.0  (>= 10.0.0)

4. DB への接続手段 (どちらか一つ)
  ✓ psql   psql (PostgreSQL) 16.2

5. 描画フォント
  ✓ 本文:   …/Pretendard-Regular.otf
  ✓ 等幅:   …/Menlo.ttc

6. 回帰テスト
  ✓ all 251 passed
  ! 6 cases need a real server and were NOT run (ERD_SELFTEST_DOCKER=1 …)

結果
  ✓ インストール完了
```

`--check` は何も変えないので配置は飛ばす。ただし入っているはずの場所は読む —
`/erd` が出てこないとき、まず確かめるのがそれだからだ。

**木を一つ選び、その木を最後まで測る。** 候補は `~/.claude/skills/erd`、
`./.claude/skills/erd`、`install.sh` が置かれているディレクトリの順で、**存在する**
最初の一つが勝つ。選んだ場所は `SKILL.md` の行にパスとして出るし、6番の回帰テストも
同じ場所で走る。したがって、スキルが入っている状態で clone したばかりの
`install.sh --check` を呼んでも、報告する対象は **インストール済みの方**だ — Claude Code
が実際に読むのはその複製だからだ。

6番は省略できない。選んだ木に読める `scripts/selftest.py` がなければ、飛ばしたのではなく
失敗だ。**誰も測っていないインストールは動くインストールではない。** 集計の上の行には、
本物のDBサーバーが要るために実行しなかった件数が出る。その行はここで捨てられない。

`SKILL.md` はあるだけでは足りず、スキルファイルでなければならない — 1行目が `---`、
frontmatter が二つ目の `---` で閉じられ、その中に `name: erd` があること。0バイトや
途中で切れた `SKILL.md` は壊れていると報告する。

パッケージのバージョンは `requirements.txt` が宣言した下限と照合する。入っていても宣言
した下限より古ければ失敗だ — あの数字は飾りではなく、測る数字だ。

## 初回実行

Claudeに任せず自分で回すなら:

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project                              # 文書の出力先
export ERD_WORK=/tmp/erd-build                                # 中間生成物
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='自社サービス ERD'

python3 introspect.py && python3 merge_desc.py && \
python3 build_erd.py && python3 build_docx.py
```

DBがdockerの中なら、`ERD_PSQL` の代わりに `export ERD_DB='コンテナ:ユーザー:DB'`。

`introspect.py` がテーブル数を出力すれば接続は成功だ。0なら `ERD_SCHEMAS`(デフォルト
`public`)を実際のスキーマ名に変える。残りの環境変数とspecの書き方は `SKILL.md` を見る。

## フォント環境変数

自動検出を上書きしたいときに使う。

| 変数 | 用途 |
|---|---|
| `ERD_FONT` / `ERD_FONT_BOLD` | PNG本文フォントのファイルパス(デフォルト: 自動検出 — `ja` では日本語フォントを優先) |
| `ERD_MONO` / `ERD_MONO_BOLD` | PNG等幅フォントのファイルパス |
| `ERD_DOC_FONT` | docx本文の **フォント名**(デフォルトは `ERD_LANG` に従う — `ja` では `Yu Gothic`) |
| `ERD_DOC_MONO` | docx等幅フォント名(`ja` のデフォルトは `Consolas`) |

PNGはファイルパス、docxはフォント名だ — docxは開くマシンにそのフォントがあって初めて
そのまま表示され、なければWordが代替する。配布先にそのフォントがないと分かっているなら、
`export ERD_DOC_FONT='Meiryo'` のように指定して回す。

## よくつまずく点

**`ModuleNotFoundError: No module named 'docx'`**
パッケージ名は `docx` ではなく `python-docx`。名前が違う。`install.sh --check` を
回すと、どのPythonを見ているかも分かる。

**インストールしたのに import が失敗する**
`pip3` と `python3` が別々のインストールを指しているときだ。
`python3 -m pip install -r requirements.txt` のように **同じPythonで** インストールする。
install.sh はこの方式を使っている。

**`/erd` が一覧にない**
この順で確認する: ① `ls ~/.claude/skills/erd/SKILL.md` が返ってくるか ② Claude Code を
再起動したか ③ `SKILL.md` の1行目が `---` で始まり `name: erd` があるか。
①と③は `install.sh --check` が代わりにやり、どの木を見たかをパスで示す。

**`[警告] DB クエリ失敗`**
`ERD_PSQL` / `ERD_DB` の値を確認する。まず同じコマンドをシェルで直接叩いて、つながるか
見る。両方設定されていれば `ERD_PSQL` が勝つ。

**`図 N枚が …/schema.json より古い` と出て文書が作られない**
故障ではなく**わざと止めている**。以前のスキーマで描いた図を文書に入れると、表と図が
別のことを語るため `build_html.py`・`build_docx.py`・`build_erd.py` が止まる。
`python3 build_erd.py` を実行し直せばよい。文言だけ直して図は本当にそのままでよい場合は
`ERD_STALE=warn`（または `ERD_STALE=1`）で通せる — そのときも通したことを1行で告げる。
`ERD_STALE` は他のスイッチと同じ yes/no 規則に従う — `true`・`on`・`y` も有効、空の
`ERD_STALE=` は**無効**、打ち間違いは黙って有効にならず変数名が出力される。

**PNGの文字が □ になる**
その文字をカバーするフォントがない。`install.sh` を再実行してPretendardを入れるか、
`ERD_FONT` で自分でフォントを指定する。漢字はPretendardに入っていない — 漢字が
□ になるなら、日本語フォント(Hiragino Sans / Noto Sans CJK)を入れる。

**説明のないカラムの一覧が出力された**
それが意図した動作だ。`merge_desc.py` の `MANUAL` 辞書に書き込んで、もう一度回す。
詳しくは `SKILL.md` の「カラム説明」の節。

**出力が見つからない**
`.graphml` と `.docx` は `$ERD_PROJ`、PNGは `$ERD_WORK/out/` にある。
