# erd — PostgreSQL ERD · スキーマドキュメント自動生成

[English](README.md) · [한국어](README.ko.md) · **日本語** · [Español](README.es.md)

DBに直接つないで実際のスキーマを読み取り、**ERDとスキーマ定義書を丸ごと生成する** [Claude Code](https://claude.com/claude-code) スキル。

手で描かないので、**図とDBがずれることはない。** スキーマが変わったら、もう一度回せばいい。

```bash
python3 introspect.py && python3 merge_desc.py && python3 build_erd.py && python3 build_html.py
```

100テーブル・1,235カラムのDBから **3.1MBのHTMLファイル1つ** が出てくる — 目次、全体概要図、領域別ERD 17枚、テーブル別カラム表、全体詳細ERDまで、すべてこの中に入っている。

## 何が出てくるか

| 成果物 | 用途 |
|---|---|
| `<文書名>.html` | **スキーマ定義書** — 目次 · 概要ERD · 領域別ERD · テーブル別カラム表 · 全体ERD。図を埋め込んだ自己完結のHTML 1ファイル |
| `<文書名>.docx` | 提出・印刷用の文書(図 + カラム説明表 + FK一覧) |
| `<文書名>.graphml` | yEdで開いて手で再配置・再出力 |
| `out/erd_*.png` · `.svg` | 概要図 · 領域別詳細図 · 全体図 |

HTMLは目次からテーブルへ直接飛べ、**ERDをクリックすると原寸大に開く。**
ベクター(SVG)なので、どれだけ拡大しても文字はつぶれない。共有はファイル1つ送るだけだ。

## なぜ作ったか

DBドキュメントは、作るのは簡単だが維持されない。スキーマが動くとまず図が古くなり、
古い図は誰も見なくなり、やがて誰もドキュメント自体を信用しなくなる。

そこで、3つのことを強制した。

**① 図はDBから出てくる。** 人は描かない。`information_schema` と `pg_catalog` を読んで、
テーブル・カラム・型・PK・FK(削除ルール含む)・ユニーク制約・インデックス・CHECKを
取得する。

**② 説明は失わない。** ERDの価値はカラム説明にあるのに、ドキュメントを作り直すたびに
誰かが磨いた文言が消えるなら、もう誰も説明を書かなくなる。だから **前の版のドキュメント
から説明を引き継ぐ。**

```bash
ERD_DOC_HTML=previous.html python3 merge_desc.py
#   以前の文書からカラム説明 1123件を引き継ぎ: …
#   説明の出典別カラム数: {'ddl': 268, 'doc': 951, 'orm': 0, 'manual': 16, 'common': 0, 'none': 0}
```

`none` が0でなければ、まだ空いているカラムの一覧が出る。**説明のないカラムを黙って
通しはしない。**

**③ 図の品質を目で判断しない。** レンダリングのたびに自己検証の結果が出力される。

```
検証 erd_area_A.png: ラベル↔テーブル 0 · ラベル↔ラベル 0 · 線↔テーブル 0 · 縦線の重なり 0 · 横線の重なり 0
検証 erd_overview.png: ラベル↔テーブル 該当なし · ラベル↔ラベル 該当なし · 線↔テーブル 0 · 縦線の重なり 0 · 横線の重なり 0
```

ラベルがテーブルを覆ったり、線同士が重なったりすれば、数字に表れる。すべての項目が 0
でなければならず、0 であるべき値が 0 でなければ同じ行の末尾に `[警告]` が付く。
`該当なし` はその図にその検査が当てはまらないという意味だ — 概要図は関係ラベルを
描かないので測るものがなく、ここに 0 を出せば、行っていない検査を「きれいだ」と
言うことになる。

## インストール

```bash
git clone git@github.com:uygnoey/erd-skill.git
bash erd-skill/install.sh
```

`install.sh` がスキルの配置(`~/.claude/skills/erd`)、依存パッケージ(`python-docx`・
`pillow`)、Pretendardフォントまで面倒を見る。終わったら **Claude Code のセッションを
新しく開き**、「ERDを描いて」と言うか `/erd` を呼ぶ。

| コマンド | 動作 |
|---|---|
| `bash install.sh` | `~/.claude/skills/erd` にインストール(デフォルト) |
| `bash install.sh --project` | 現在のプロジェクトの `./.claude/skills/erd` にインストール |
| `bash install.sh --check` | 何も変えずにチェックだけ |

詳細は [INSTALL.ja.md](INSTALL.ja.md)。

### 必要なもの

- Python 3.9+ / `python-docx` / `pillow`
- `psql` か `docker` のどちらか
- サーバは PostgreSQL **9.4 以上**(9.4・9.6・10・11・12・16・17 で確認)。それより
  古ければ、半分だけ読んだスキーマを作らずメッセージを出して止まる
- スキーマに必要な文字をカバーするフォント — `ERD_LANG=ja` ではPretendardに漢字
  グリフがないため、日本語対応フォント(Hiragino Sans / Noto Sans JP / Yu Gothic)を
  優先して選ぶ。どれもなければOSデフォルトのフォントにフォールバックする

## 使い方

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project        # 文書の出力先
export ERD_WORK=/tmp/erd-build          # 中間生成物
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='自社サービス スキーマ定義書'
export ERD_LANG=ja                      # en · ko · ja · es

python3 introspect.py    # ① DB → schema.json
python3 merge_desc.py    # ② カラム説明を埋める
python3 build_erd.py     # ③ GraphML + PNG + SVG
python3 build_html.py    # ④ HTMLスキーマ定義書
python3 build_docx.py    # ⑤ docx文書(任意)
```

docker内のDBなら、`ERD_PSQL` の代わりに `export ERD_DB='コンテナ:ユーザー:DB'`。

**④・⑤ は `schema.json` より古い図の上では動かない。** 表と図が別のスキーマを語る文書を
渡す代わりに `図 N枚が … より古い` で止まる — ③ を実行し直せばよい。文言だけ直して図は
本当にそのままでよい場合は `ERD_STALE=warn` がそのまま埋め込み、毎回そのことを1行で
告げる（空の `ERD_STALE=` は、ここの他のスイッチと同じく**無効**）。

**設定ファイルなしでも動く。** スキーマ名とテーブル名のプレフィックスから領域を
自動分類し、色を割り当てる。

ただし自動分類は **まず一枚描いてみるためのもの** だ。命名規則の揃ったDBでなければ、
どこにも当てはまらないテーブルが「その他」領域に集まる — 80テーブルのDBでは24%が
そこに落ちた。「その他」が膨らむほど、その図は縦に伸びて読みにくくなる。**文書として
出すなら、`erd.spec.json` で領域を自分で定義すること** — 領域がそのまま文書の目次になる。

### DBの代わりにDDLファイルから

まだ適用していない変更まで文書に入れたいときは、`introspect.py` の代わりに
`parse_ddl.py` を走らせる — `$ERD_SQL_DIR/*.sql`(既定は `$ERD_PROJ/sql`)を読んで
同じ `schema.json` を書く。

そのDDLの `--` コメントがそのまま説明になる。**コメントがどこに置かれているかが、
誰の説明かを決める:**

```sql
-- 注文1件につき1行             ← CREATE TABLE の上 → テーブルの説明
CREATE TABLE orders (          -- 注文1件につき1行   ← この行 → テーブルの説明(こちらが勝つ)
  id       bigint PRIMARY KEY, -- 行のid             ← カンマの後 → この列
  -- 注文した人                ← 列の上 → その列(複数行は連結される)
  user_id  bigint NOT NULL,
  code     text,
  -- テナントごとに一意        ← 制約の上 → 誰のものでもない
  UNIQUE (user_id, code)
  -- TODO: 通貨の列を追加      ← 最後の列の後 → 誰のものでもない
);
```

`/* … */` ブロックは説明にならない。その中の `--` 行も同じだ。`COMMENT ON
TABLE/COLUMN` は上のすべてを上書きする — だから `pg_dump` のファイルと手書きのファイルが
同じ結果になる。

### 出力言語

人が読むものすべて — コンソール出力、HTML・docx文書、図の凡例、インストーラ — が
`ERD_LANG` に従う: **英語・韓国語・日本語・スペイン語。**
未設定ならロケール(`LANG` / `LC_ALL`)で決まり、最後は英語にフォールバックする。

`erd.spec.json` に自分で書いたテキスト — 領域名、役割名、文書タイトル — はそのまま
使われるので、英語の文書に韓国語の領域名が混ざっても何の問題もない。

言語の追加は、`scripts/lang/` にファイルを1つ置くだけ — このディレクトリ自体が
対応言語の一覧だ。抜けた項目は英語にフォールバックするので、訳しかけのカタログでも動く。

### 複数のDBを1つの文書に

```bash
ERD_LABEL=shop ERD_DB='shop-postgres:app:shop' python3 introspect.py
ERD_LABEL=mart ERD_PSQL='psql postgresql://app:pw@localhost:5433/mart' python3 introspect.py
python3 merge_schemas.py shop mart      # テーブルキーが 'shop.orders' のようになる
```

DB間に物理FKは存在しえないので、DBをまたぐ流れはspecの `derives` に書く。

### erd.spec.json — 図の骨格

すべて任意項目で、ないものは自動推論される。

```json
{
  "areas":    [["A", "注文", "public", ["orders", "order_items"]]],
  "layer_of": {"orders": "TX", "order_items": "TX"},
  "layers":   {"TX": ["#25324D", "#35507D", "#4A80C0", "トランザクション系"]},
  "roles":    {"orders": "注文ヘッダ"},
  "derives":  [["ext_feed", "orders", "外部連携"]],
  "doc":      {"title": "ECサイト スキーマ定義書"}
}
```

| キー | 意味 |
|---|---|
| `areas` | `[コード, 領域名, スキーマ, [テーブル…]]` — グループ枠であり配置単位でもある |
| `layer_of` / `layers` | テーブル→レイヤー、レイヤー→`[塗り, ヘッダ, 枠線, 凡例ラベル]` |
| `roles` | テーブルの役割名(なければDBのテーブルコメント) |
| `derives` | ETLフロー — FKではないデータの流れ。茶色の破線 |
| `doc` | 文書のタイトル・表紙・前書き・領域別の説明 |

例: [`examples/minimal.spec.json`](examples/minimal.spec.json)(最小)、
[`examples/full.spec.json`](examples/full.spec.json)(全部入り)。

環境変数の全リストは [SKILL.md](SKILL.md) にある。

## 描画ルール

レビューされる文書に載せる前提なので、譲らないことがいくつかある。

- **色 = レイヤー、まとまり = スキーマ・領域。** ソース層と派生層が同じ色になることはない
- **線は2種類だけ。** FK(グレー実線)、ETLフロー(茶色破線)。削除ルールは図ではなく
  文書の表に書く
- **直交ルーティング。** 線はテーブルを貫通しない。ノードの中心ではなく **実際の
  カラム行** から出る
- **交差は半円で跳ぶ。** 交差が接続に読まれないように
- **ラベルはノードより後に描く。** そうしないとノードに隠れる
- **キャンバスは2パスで測る。** まず1×1のダミーに一度描いて実寸を測り、それから余白を
  足す。ノード位置だけでサイズを決めると、外にはみ出したラベルや関係線が切れる

## PNGとSVG

同じレイアウトを二度描いたものだ。テーブルの位置と箱の大きさは一度のレイアウト計算から
出るので、両方で同じ場所に置かれる。描画バックエンドだけがベクターに替わる
(`svg_canvas.py` が `ImageDraw` インターフェースを模倣する)。ただしSVG側は別の倍率で
走り、PILの文字幅は倍率に比例しない — そのため関連ラベルはSVGでは別の位置に来ることが
ある(ランダムなスキーマ20件で、ラベル1つが134pxずれた)。**描画のたびに出る検証の
数値はPNGを測ったものだ。**

|  | 概要図 | 領域別 | 全体詳細図 |
|---|---|---|---|
| PNG | 0.70 MB | 0.41 MB | 3.27 MB |
| **SVG** | **0.48 MB** | **0.23 MB** | **0.30 MB** |

SVGは見る側のマシンにあるフォントで文字を描くため、フォントがないと幅が変わって文字が
セルからはみ出す。そこですべての `<text>` に、PILが測った幅を `textLength` で固定した。
**フォントのないマシンでもレイアウトは崩れない。**

## 構成

```
install.sh        自動インストール(配置・依存・フォント)
scripts/
  selftest.py     回帰テスト (DB 不要)
  i18n.py         出力言語の選択
  lang/           メッセージカタログ(en · ko · ja · es)
  config.py       パス・DB接続・spec読み込み・領域の自動分類
  introspect.py   DB → schema.json
  parse_ddl.py    DDLパース → schema.json  (未適用の変更まで含めるとき)
  merge_schemas.py 複数DBのスキーマを1つに
  merge_desc.py   カラム説明のマージ
  erd.py          レイアウト・レンダリング・GraphML
  svg_canvas.py   ImageDraw互換のSVGキャンバス
  build_erd.py    PNG・SVG・GraphML実行
  build_html.py   HTMLスキーマ定義書
  build_docx.py   docx文書
examples/         spec例
```

## 他のDB

`introspect.py` のクエリはPostgreSQL向けだ。MySQLにも標準の `information_schema` が
あるので、カラム・PK・FKのクエリはほぼそのまま使える — `col_description` の代わりに
`columns.column_comment` を使えばいい。

## ライセンス

MIT
