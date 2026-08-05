"""日本語の文言。"""

M = {
    # ── 語彙 ──────────────────────────────────────────────────────────────
    'word.tables': 'テーブル',
    'word.columns': 'カラム',
    'word.areas': '領域',
    'word.layer': 'レイヤー',
    'word.schema': 'スキーマ',
    'word.fkeys': '外部キー',
    'word.pk': '主キー',
    'word.fk': '外部キー',
    'word.unique': 'ユニーク',
    'word.kind': '区分',
    'word.content': '内容',
    'word.basis': '根拠',
    'word.notation': '表記',
    'word.meaning': '意味',
    'word.lines': '線',
    'word.added': '[追加]',
    'word.source': 'ソース',
    'word.extended': '拡張',
    'word.existing': '既存',
    'word.external': '外部',
    'word.solid': '実線',
    'word.dashed': '破線 (茶色)',
    'word.semicircle': '半円',
    'word.crowfoot': '鳥の足 / 直交線',
    'word.child_table': '子テーブル',
    'word.parent_table': '親テーブル',
    'word.delete_rule': '削除規則',
    'word.src_side': 'ソース (ref スキーマ)',
    'word.dst_side': '対象 (public スキーマ)',
    'word.priority': '優先',
    'word.item': '項目',
    'word.target': '対象',
    'word.current': '現状',
    'word.action': '要対応',
    'word.proposed': '設計案 (仮)',
    'word.actual_table': '実際のテーブル',
    'word.applied': '反映',
    'word.reason': '理由',
    'word.fig_no': '[図 {n}]',
    'word.area_other': '{schema} その他',
    'word.font_body': '本文',
    'word.font_mono': '等幅',

    # ── カラム表 ──────────────────────────────────────────────────────────
    'col.name': 'カラム',
    'col.type': '型',
    'col.null': 'Null',
    'col.default': '既定値',
    'col.key': 'キー/参照',
    'col.desc': '説明',

    # ── HTML スキーマ定義書 ───────────────────────────────────────────────
    'html.single_db': '(単一 DB)',
    'html.fig_zoom': '— クリックで原寸表示',
    'html.meta_area_layer': '領域 {area} · レイヤー {layer}',
    'html.role': '役割',
    'html.constraints': '制約 · インデックス ({n}件)',
    'html.rows_note': 'rows ≈ は統計に基づく推定値',
    'html.toc': '目次',
    'html.db_tables': 'DB: {db} · テーブル {n}件',
    'html.badge_cols': 'カラム {n}',
    'html.badge_tables': 'テーブル {n}件',
    'html.overall': '全体構造',
    'html.overview_cap': '{title} — 全体構造の概要図 (テーブル {n}件 · 関係のみ表示)',
    'html.area_cap': '{name} — 領域詳細 ERD',
    'html.full_cap': '{title} — 全体詳細 ERD (全テーブル · 全カラム)',
    'html.appendix': '付録. 全体詳細 ERD',
    'html.appendix_desc': '全テーブルと全カラムを一枚に収めた図である。'
                          '画面ではクリックして拡大表示する。',
    'html.zoomhint': 'クリックまたは Esc で閉じる',

    # ── ERD 図 ────────────────────────────────────────────────────────────
    'erd.ref_of': '[参照] {area} · {role}',
    'erd.readonly_src': '{schema} (読み取り専用)',
    'erd.group_label': '{schema} スキーマ · {code} {name}',
    'erd.node_desc': '[{layer}] [領域 {code} {area}] {note}',
    'erd.lg_new': '新規テーブル',
    'erd.lg_ext': '既存テーブル · カラム追加',
    'erd.lg_src': 'ref スキーマのソース',
    'erd.lg_fk': '外部キー (FK) · ラベル = 子カラム : 親カラム',
    'erd.lg_etl': 'ETL ロードフロー (FK ではない)',
    'erd.lg_hop': '交差 (線が跨いで通過)',
    'erd.sub_overview': '色 = レイヤー / 枠 = スキーマ·領域',
    'erd.sub_full': 'テーブル {tables}件 · カラム {columns}件 · 外部キー {fks}件',
    'erd.sub_etl': ' · ETL フロー {n}件',
    'erd.sub_area': '{schema} スキーマ · テーブル {n}件',
    'erd.sub_ext': ' · 外部参照 {n}件',
    'verify.label_table': 'ラベル↔テーブル',
    'verify.thru': '線↔テーブル',
    'verify.label_x': 'ラベル↔ラベル',
    'verify.v_overlap': '縦線の重なり',
    'verify.h_overlap': '横線の重なり',
    'verify.tolerated': '{n}(許容)',
    'verify.na': '該当なし',
    'verify.warn': '  [警告] 0 でなければならない: {list}',

    # ── docx 文書 ─────────────────────────────────────────────────────────
    'docx.doc_name': '文書名',
    'docx.ch1': '1. 概要',
    'docx.ch1_1': '1.1 目的',
    'docx.purpose': '対象 DB のテーブル構造と関係を ERD として提示する。'
                    '実際のスキーマを読み取って生成するため、図と DB が食い違うことはない。',
    'docx.ch1_2': '1.2 範囲',
    'docx.scope_in': '対象: テーブル {n}件の構造·カラム·関係、スキーマおよびレイヤーの区分。',
    'docx.scope_out': '対象外: マイグレーション手順、API 仕様、画面設計。',
    'docx.ch1_3': '1.3 作成根拠',
    'docx.sources_note': '本 ERD は実際の DB と DDL を読み取って生成した。したがって'
                         'テーブル名·カラム名·型·制約は実際のスキーマと一致する。',
    'docx.src_infoschema': 'テーブル·カラム·型·PK·FK·削除規則の実際の値',
    'docx.src_comment': 'テーブル·カラムのコメント',
    'docx.src_comment_d': '説明の第一情報源',
    'docx.src_orm': 'ORM モデルのコメント',
    'docx.src_orm_d': 'コメントのないカラムの説明',
    'docx.ch1_4': '1.4 表記規則',
    'docx.by_color': '{code} (色分け)',
    'docx.nt_new': '新規作成テーブル',
    'docx.nt_ext': '既存運用テーブル · カラム追加',
    'docx.nt_src': '外部ソース · 読み取り専用',
    'docx.nt_added': '今回の改修で追加されるカラム',
    'docx.nt_solid': '外部キー (FK) · ラベルは「子カラム : 親カラム」',
    'docx.nt_dashed': 'ETL ロードフロー — FK ではなくデータの流れ',
    'docx.nt_hop': '線が交差するとき跨いで通過する印 (接続ではない)',
    'docx.nt_card': '関係の N 側 (子) / 1 側 (親)',
    'docx.ch2': '2. スキーマ · レイヤー構造',
    'docx.ch2_intro': '下図では、色がレイヤーを、枠がスキーマと機能領域を表す。',
    'docx.fig_overview': '{title} — 全体関係の概要',
    'docx.ch2_1': '2.1 全体 ERD',
    'docx.ch2_1_intro': '全 {n}件のテーブルの全カラムと説明を一枚に表示する。'
                        '印刷では縮小されて読みにくいため、詳細の確認には 3 章の'
                        '領域別 ERD または元画像を用いる。',
    'docx.fig_full': '{title} — 全体 (カラム · 説明つき)',
    'docx.ch3': '3. 領域別 ERD',
    'docx.ch3_intro': '領域ごとに全カラムと説明を表示する。領域外の参照先は'
                      '灰色の枠線の簡略ボックスで表記した。',
    'docx.ch3_area': '3.{no} 領域 {code} · {name} ({schema} スキーマ · {n}件)',
    'docx.fig_area': '領域 {code} · {name}',
    'docx.ch4': '4. テーブルの役割とカラム説明',
    'docx.ch4_intro': '全 {tables}件のテーブル · {columns}件のカラム。区分欄の PK は主キー、'
                      'FK は外部キー、[追加] は今回の改修で追加されるカラムを示す。',
    'docx.ch4_area': '4.{no} 領域 {code} · {name}',
    'docx.ch5': '5. 関係定義',
    'docx.ch5_1': '5.1 外部キー (FK)',
    'docx.ch5_1_intro': '全 {n}件。削除規則が CASCADE の関係は親の削除時に子の行も'
                        '併せて削除され、SET NULL の関係は参照だけを外して行は残す。',
    'docx.ch5_2': '5.2 ETL ロードフロー',
    'docx.ch5_2_intro': 'FK ではなくデータの流れである。ref スキーマは読み取り専用のため、'
                        '物理的な制約は設定できない。',
    'docx.ch6': '6. 設計案と実装結果の対照',
    'docx.ch6_intro': '設計案のテーブル名と実際の DDL の名称は異なる。各項目が実際に'
                      'どう反映されたかを以下に対照する。',
    'docx.ch7': '7. 未反映事項と要判断事項',
    'docx.ch7_intro': '本 ERD は構造を定義したものであり、構造があるだけでは動作しない。'
                      '以下の項目はスキーマの外での決定を経なければ値が定まらない。',

    # ── 共通カラム説明 ────────────────────────────────────────────────────
    'common.id': '行識別子 (PK)',
    'common.seq': '行識別子 (PK)',
    'common.uuid': '行識別子 (UUID)',
    'common.created_at': '作成日時',
    'common.updated_at': '更新日時',
    'common.deleted_at': '削除日時 (論理削除)',
    'common.created_by': '作成者',
    'common.updated_by': '更新者',
    'common.loaded_at': 'ロード日時',
    'common.started_at': '開始日時',
    'common.ended_at': '終了日時',
    'common.status': 'ステータス',
    'common.note': '備考',
    'common.remark': '備考',
    'common.sort_order': '表示順',
    'common.rank': '順位',
    'common.version': 'バージョン',
    'common.is_active': '有効フラグ',
    'common.active_yn': '有効フラグ',

    # ── エラー ────────────────────────────────────────────────────────────
    'err.no_conn': 'DB 接続情報がない。次のいずれかを指定すること。',
    'err.no_conn_db': "'コンテナ:ユーザー:DB'        # docker 経由",
    'err.no_schema_tables': '描くテーブルがない。{path} が空か、ERD_EXCLUDE が全部除いた。',
    'err.no_tables': 'テーブルを一つも読めなかった。'
                     'ERD_DB / ERD_PSQL / ERD_SCHEMAS / ERD_EXCLUDE を確認すること。',
    'err.font_env': '{env} で指定したフォントが使えない: {path}',
    'err.font_none': '{kind}フォントが見つからない。install.sh を実行するか、{env} で'
                     '直接指定すること。\n  探索した場所: {looked}',
    'err.merge_usage': '使い方: python3 merge_schemas.py <ラベル> <ラベル> …',
    'err.merge_missing': '{path} が存在しない。まず ERD_LABEL={label} で '
                         'introspect.py を実行すること。',
    'err.no_sql_dir': 'DDL ディレクトリがない: {path}  (ERD_SQL_DIR で指定)',
    'err.spec_no_area': '{path} の areas に実在するテーブルが一つもない。',
    'err.spec_dup_code': '{path}: 二つの領域が同じ領域コード {code} を使っている (もう一方は {other})。\n'
                         '  領域コードはファイル名になる({file})。macOS・Windows では大文字小文字や\n'
                         '  Unicode の形だけが違うコードは同じファイルなので、一方の領域図が\n'
                         '  もう一方を黙って上書きする。別々のコードを与えること。',
    'err.spec_layer': 'レイヤー {key} の形式が不正だ: {value}\n'
                      '  [塗り, ヘッダ, 枠, ラベル] で、色は #rrggbb でなければならない',
    'err.spec_json': '{path} が正しい JSON ではない: {err}',
    'err.fig_unregistered': '図 {stem} に図番号がない — build_erd.py の fig_numbers() が'
                            'その名前を持っていない。\n'
                            '  このスクリプトが描く図は全てその一覧から番号を受け取り、その番号は'
                            'キャプションだけでなく図の中にも描かれる — 登録のない図は'
                            'キャプションと違う番号を持って出ていく。\n'
                            '  登録済み: {known}',
    'err.stale_figs': '図 {n}枚が {path} より古い: {list}\n'
                      '  以前のスキーマを描いた図である — 表と図が別のスキーマを語る'
                      '文書になる。\n'
                      '  build_erd.py を実行し直すか、そのまま入れるなら ERD_STALE=warn。',
    'err.pg_too_old': 'PostgreSQL {found} は古すぎる — {need} 以上が必要である。\n'
                      '  それ以前のサーバはサブクエリの別名を row_to_json のキーにしない'
                      'ため全ての値が空になり、外部キーのクエリに要る WITH ORDINALITY も無い。',
    'err.query_failed': 'DB から {what} を読めなかった: {err}\n'
                        '  何も書いていない。スキーマを半分しか読めなかった実行は、'
                        '完成して見えるだけの文書を作る。',
    'err.query_truncated': '結果が行の途中で切れた',
    'err.env_not_dir': '{env}: {path} はディレクトリではない — そこにすでに別のものがある。',
    'err.env_not_file': '{env}: {path} は読めるファイルではない。',
    'err.env_bad': '{env} は使えない: {why}\n  値: {value}',
    'err.env_empty': '{env} が空の値で設定されている。値を与えるか、既定値を使うなら設定を外す。',
    'err.env_name': '{env}={value} はファイル名に使えない。{safe} のように書く。',
    'err.spec_type': '{path}: "{key}" は {want} の形でなければならない — 受け取ったのは {got}。',
    'err.spec_root': '{path} は "areas" のようなキーを持つ JSON オブジェクトでなければ'
                     'ならない — 受け取ったのは {got}。',

    # ── 進行状況の出力 ────────────────────────────────────────────────────
    'log.query_fail': '  [警告] DB クエリ失敗: {err}',
    'log.query_incomplete': '  [警告] 読めなかったもの: {list} — 文書からちょうどその分が欠ける',
    'log.psql_undecodable': '  [警告] DB の応答が UTF-8 ではなかった — その文字は文書に '
                            '� として残る。\n'
                            '          こちらが起動する psql には PGCLIENTENCODING={enc} を'
                            '渡しているが、docker・ssh で包むとその境界を越えない。\n'
                            '          ERD_PSQL のコマンドの中に直接書くこと: '
                            'docker exec -e PGCLIENTENCODING={enc} … / '
                            'ssh host PGCLIENTENCODING={enc} psql …',
    'log.ddl_not_in_db': '  [警告] 探したスキーマ ({schemas}) にないテーブル {n}件 — '
                         '名前だけの箱として描く: {list}',
    'log.spec_empty': '  [警告] 使えるテーブルがない領域を飛ばす: {list}',
    'log.spec_dup': '  [警告] テーブル {n}件が複数の領域に重複 — 最初の領域だけに置く: {list}',
    'log.spec_missing': '  [警告] spec が指すテーブル {n}件がスキーマにない: {list}',
    'log.max_areas_spec': '  [警告] {env}={value} だが {path} が領域を自分で書いている — {n}個をそのまま描く\n'
                          '          (上限は自動分類にのみ効く。spec が優先される)',
    'log.spec_orphan': '  [警告] どの領域にも入っていないテーブル {n}件 — 別の領域に'
                       'まとめて描く: {list}',
    'log.spec_unknown': '  [警告] spec のトップレベルキー {n}件は知らない名前なので無視した: {list}\n'
                        '    知っているキー: {known}  (_ で始まるキーはコメント)',
    'log.env_not_flag': '  [警告] {env}={value} はオン/オフの値ではない — {used} とする '
                        '(オフになる値: 0 false no off n、空)',
    'log.env_not_number': '  [警告] {env}={value} は数値ではない — {default} を使う',
    'log.env_clamped': '  [警告] {env}={value} は最小値より小さい — {used} に上げる',
    'log.default_pk_skipped': '  [警告] ERD_DEFAULT_PK={column} だがその名前の列がなく、'
                              '{n}件のテーブルは主キーなしのまま: {list}',
    'log.ref_tables_ignored': '  [警告] ERD_REF_TABLES はあるが ERD_REF_SCHEMA がない — '
                              '{n}件のテーブルを取得しなかった: {list}',
    'log.introspected': 'テーブル {tables} · カラム {columns} · FK {fks} → {path}',
    'log.desc_from_db': '  DB コメントから補完したカラム説明 {n}/{total}',
    'log.desc_rest': '  → 残りは merge_desc.py で補完すること',
    'log.dup_names': '  複数のスキーマにまたがる名前のテーブル {n}件 — キーは スキーマ.テーブル とする: {list}',
    'log.exclude_rule': '  除外規則: {rule}',
    'log.exclude_dropped': '  除外規則が取り除いたテーブル {n}件: {list}',
    'log.fk_dropped': '  対象外テーブルを指す FK {n}件を除外',
    'log.per_schema': '  [{schema}] {n}件',
    'log.doc_missing': '  [警告] ERD_DOC_HTML 文書が見つからない: {path}',
    'log.doc_inherited': '  以前の文書からカラム説明 {n}件を引き継ぎ: {name}',
    'log.by_source': '説明の出典別カラム数:',
    'log.no_desc': 'まだ説明のないカラム:',
    'log.desc_ambiguous': '  [警告] 同名のテーブルが複数あるため無視したキー {n}件 — '
                          '前置きを付けたキーを使うこと: {list}',
    'log.merge_part': '  {label} テーブル {tables} · カラム {columns}',
    'log.merge_total': '合計 テーブル {tables} · カラム {columns} · FK {fks} → {path}',
    'log.ddl_parsed': 'テーブル {n}件 → {path}',
    'log.ddl_no_db': '  DDL に定義がなく参照されるだけのテーブル {n}件 — 名前だけの箱で描く (ERD_DB/ERD_PSQL を与えると中身を埋める): {list}',
    'log.ddl_row': 'カラム {columns}{added} FK {fks}  · {note}',
    'log.ddl_added': ' (+{n} 追加)',
    'log.graphml': 'GraphML  ノード {nodes} · 関係 {edges}  → {name}',
    'log.png_overview': 'PNG  概要図 → {name} {size}',
    'log.png_full': 'PNG  全体 ERD → {name} {size}',
    'log.png_area': 'PNG  領域 {code} {name} ({n}件 + 参照 {ext}) → {file}  {size}',
    'log.scale_down': '    [注記] {name}: 図が大きいため倍率を {s}倍に下げた',
    'log.overlap_at': '      重なり: 座標 {a}  [{s0}~{s1}] vs [{t0}~{t1}]',
    'log.verify': '    検証 {name}: {report}',
    'log.verify_log_fail': '  [警告] ERD_VERIFY_LOG を書けなかった。図はそのまま残っている: '
                           '{path} — {err}',
    'log.html_done': 'HTML  テーブル {tables} · 領域 {areas} · 図版 {figs}点  '
                     '{mb}MB → {name}',
    'log.stale_figs': '  [警告] スキーマより古い図 {n}枚をそのまま埋め込む '
                      '(ERD_STALE): {list}',
    'log.docx_saved': '保存: {name} ({kb} KB)',
    'log.figs_missing': '  [警告] 画像ファイルがなく文書から除いた図 {n}点: '
                        '{list}  → 先に build_erd.py を実行する',
    'log.row_truncated': '  [警告] {where}: {n} 行がこの表の桁数({width})より多くの'
                         'セルを持っており、あふれたセルは捨てられた: {list}',
}
