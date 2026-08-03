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
  ✓ python-docx
  ✓ pillow

4. DB への接続手段 (どちらか一つ)
  ✓ psql   psql (PostgreSQL) 16.2

5. 描画フォント
  ✓ 本文:   …/Pretendard-Regular.otf
  ✓ 等幅:   …/Menlo.ttc

結果
  ✓ インストール完了
```

`--check` は何も変えないので配置は飛ばす。ただし入っているはずの場所に `SKILL.md` が
あるかは見る — `/erd` が出てこないとき、まず確かめるのがそれだからだ。

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

**`[警告] DB クエリ失敗`**
`ERD_PSQL` / `ERD_DB` の値を確認する。まず同じコマンドをシェルで直接叩いて、つながるか
見る。両方設定されていれば `ERD_PSQL` が勝つ。

**PNGの文字が □ になる**
その文字をカバーするフォントがない。`install.sh` を再実行してPretendardを入れるか、
`ERD_FONT` で自分でフォントを指定する。漢字はPretendardに入っていない — 漢字が
□ になるなら、日本語フォント(Hiragino Sans / Noto Sans CJK)を入れる。

**説明のないカラムの一覧が出力された**
それが意図した動作だ。`merge_desc.py` の `MANUAL` 辞書に書き込んで、もう一度回す。
詳しくは `SKILL.md` の「カラム説明」の節。

**出力が見つからない**
`.graphml` と `.docx` は `$ERD_PROJ`、PNGは `$ERD_WORK/out/` にある。
