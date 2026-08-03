---
name: erd
description: Generates an ERD and schema documentation from any PostgreSQL database — DataGrip-style dark PNG/SVG (overview + per-area detail), GraphML for yEd, and a docx/HTML schema reference carrying column descriptions. Line overlap and label clipping are verified automatically. Output language follows ERD_LANG (en·ko·ja·es). Use for requests like "draw the ERD", "generate an ERD", "table relationship diagram", "document the DB structure", "schema reference", "document the schema"; 한국어 — "ERD 그려줘", "ERD 만들어", "테이블 관계도", "DB 구조 문서", "스키마 정의서", "스키마 문서화"; 日本語 —「ERD を描いて」「ER図を作って」「テーブル関連図」「DB 構造ドキュメント」「スキーマ定義書」; Español — «dibuja el ERD», «diagrama entidad-relación», «diagrama de tablas», «documentar el esquema», «documento de esquema».
---

# ERD generation

Connects to the database, reads the live schema, and builds the ERD. Nothing is drawn by
hand, so **the diagram cannot drift from the database.**

To include changes that are not in the database yet, run `parse_ddl.py` **instead of**
`introspect.py` — it reads `*.sql` and writes the same `schema.json`. It is a separate path,
not something the normal run picks up automatically.

(Korean original of this document: `SKILL.ko.md`.)

## Output language

Everything a person reads — console output, the HTML/docx documents, the diagram legend —
follows `ERD_LANG`: `en`, `ko`, `ja`, `es`. Without it, the locale decides; failing that,
English.

**Match the language the user is speaking.** If they asked in Japanese, export
`ERD_LANG=ja` before running the scripts. `erd.spec.json` values (area names, roles, the
document title) are written by the user and are used verbatim — they override the catalog.

Adding a language means dropping one file into `scripts/lang/` — that directory is the
list of supported languages. Missing keys fall back to English.

## Quick start

If it is not installed yet, run `bash install.sh` first — it handles dependencies and
fonts (see `INSTALL.md`).

```bash
cd .claude/skills/erd/scripts
pip3 install -r ../requirements.txt        # skip if install.sh already ran

export ERD_PROJ=/path/to/project          # where documents are written
export ERD_WORK=/tmp/erd-build            # intermediate artifacts
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='Our Service ERD'
export ERD_LANG=en                        # en · ko · ja · es

python3 introspect.py    # ① DB → schema.json
python3 merge_desc.py    # ② fill in column descriptions
python3 build_erd.py     # ③ GraphML + PNG + SVG
python3 build_html.py    # ④ HTML schema reference   ← for reading on screen
python3 build_docx.py    # ⑤ docx document           ← for submission and print
```

It works without `erd.spec.json` — areas are classified automatically from schema names
and table-name prefixes, and colors are assigned.

**Automatic classification is for getting a first draft on screen.** With inconsistent
naming, tables that match nothing collect under "Other" (measured at 24% on an 80-table
database). The bigger that area gets, the taller and less readable the diagram becomes.
If the output is going into a document, define the areas in a spec — **the areas become
the document's table of contents**, and those are better decided by a human.

**Several databases in one document** — read each with a label, then merge:

```bash
ERD_LABEL=shop ERD_DB='shop-postgres:app:shop' python3 introspect.py
ERD_LABEL=mart ERD_PSQL='psql postgresql://app:pw@localhost:5433/mart' python3 introspect.py
python3 merge_schemas.py shop mart     # table keys become e.g. 'shop.orders'
```

## Output

| File | Contents |
|---|---|
| `$ERD_PROJ/<docname>.html` | **Schema reference** — contents · overview ERD · per-area ERDs · per-table column tables · full ERD. One self-contained HTML with the diagrams embedded |
| `$ERD_PROJ/<docname>.docx` | Diagrams + per-table column description tables + FK list |
| `$ERD_PROJ/<docname>.graphml` | Open in yEd to rearrange and re-export. Includes column descriptions |
| `$ERD_WORK/out/erd_overview.png·svg` | Relationship overview (structure only, no columns) |
| `$ERD_WORK/out/erd_full.png·svg` | Full ERD (every column + descriptions) |
| `$ERD_WORK/out/erd_area_*.png·svg` | Per-area detail |

**PNG and SVG are the same picture.** Coordinates and font widths are measured identically
with PIL; only the drawing back end becomes vector (`svg_canvas.py`). SVG is a tenth the
size and does not blur when enlarged, so it goes into the HTML; PNG goes wherever a raster
is required (docx, slides).

## HTML schema reference

`build_html.py` produces a document meant for reading and searching on screen. The
contents jump straight to a table, and clicking an ERD opens it at full size (vector, so
the text survives). The images live inside the file, so **you send one HTML and nothing
else.**

The order follows the document: ① cover · DB summary · legend ② contents ③ overall
structure overview ④ DB > area > table (each area's ERD before its tables) ⑤ appendix:
full detail ERD.

If a previous edition exists, **the column descriptions in it are inherited.** This is what
keeps hand-polished wording from being lost on every regeneration:

```bash
ERD_DOC_HTML=previous.html python3 merge_desc.py
#   column descriptions carried over from previous.html: 1123
```

## Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `ERD_PROJ` | current directory | where documents and GraphML are written |
| `ERD_WORK` | `$ERD_PROJ/erd-build` | schema.json · PNG |
| `ERD_SPEC` | `$ERD_WORK/erd.spec.json` | diagram skeleton (optional) |
| `ERD_DOCNAME` | `ERD` | output file name (without extension) |
| `ERD_LANG` | locale, else `en` | output language: `en` · `ko` · `ja` · `es` |
| **`ERD_PSQL`** | — | the psql command itself, e.g. `psql postgresql://u:p@h:5432/db` |
| **`ERD_DB`** | — | via docker. Format: `container:user:db` |
| `ERD_SCHEMAS` | `public` | target schemas (comma separated) |
| `ERD_EXCLUDE` | — | regex of tables to exclude |
| `ERD_MAX_AREAS` | `12` | cap on the number of auto-classified areas |
| `ERD_SQL_DIR` | `$ERD_PROJ/sql` | only when parsing DDL |
| `ERD_SQL_FILES` | — | DDL parsing: name the files directly (comma separated; default is every `*.sql` in the directory) |
| `ERD_REF_SCHEMA` | — | DDL parsing: a read-only source schema to include as well |
| `ERD_REF_TABLES` | — | DDL parsing: which tables to take from that schema (comma separated) |
| `ERD_DEFAULT_PK` | — | DDL parsing: column to assume as the PK of an existing table when none is found |
| `ERD_MODEL_DIR` | `$ERD_PROJ/models` | extract descriptions from ORM comments |
| `ERD_LABEL` | — | label for merging several databases (`schema.<label>.json`) |
| `ERD_DOC_HTML` | — | inherit column descriptions from previous editions (comma separated) |
| `ERD_SVG` | `1` | write an SVG next to each PNG |
| `ERD_SVG_TITLE` | `0` | draw the title inside the SVG (off by default — documents add their own caption) |
| `ERD_HTML_STATS` | `0` | show row counts and size on the HTML badges (off — they are statistics) |
| `ERD_HTML_FULL` | `1` | the full detail ERD in the HTML appendix |
| `ERD_HTML_SVG` | `1` | set to `0` to embed PNG instead of SVG |
| `ERD_HTML_OUT` | `$ERD_PROJ/<docname>.html` | set the HTML path directly |
| `ERD_FONT`·`ERD_MONO` | auto-detected | PNG/SVG font files (`_BOLD` suffix for bold) |
| `ERD_DOC_FONT`·`ERD_DOC_MONO` | follows `ERD_LANG` | docx font **names** (en: `Calibri`·`Consolas`, ko: `Pretendard`·`D2Coding`) |

Either `ERD_PSQL` or `ERD_DB` is enough. If both are set, `ERD_PSQL` wins.

The server must be **PostgreSQL 9.4 or later** — `introspect.py` reads the version first
and stops with a message on anything older, rather than handing back a schema it could
only half read. Verified on 9.4, 9.6, 10, 11, 12, 16 and 17; the foreign-key query drops
its partition-copy filter on servers below 11, where `pg_constraint.conparentid` does not
exist yet (and neither do per-partition copies).

## Column descriptions (the important part)

An ERD is worth something because of its descriptions. They are filled in this order:

**manual dictionary > DB comment > previous edition > ORM comment > common-column dictionary**

```
$ python3 merge_desc.py
columns by description source: {'ddl': 268, 'doc': 951, 'orm': 0, 'manual': 16, 'common': 0, 'none': 0}
```

If `none` is not 0, the list is printed. Add them to the `MANUAL` dictionary in
`merge_desc.py` and run it again. **Undescribed columns are not quietly waved through.**

The common dictionary already covers `seq`, `created_at` and similar — its wording comes
from the language catalog, so it follows `ERD_LANG`. Project-wide columns can be added
there instead of being repeated per table.

## erd.spec.json — the skeleton of the diagram

Only needed when automatic classification is not good enough. Everything is optional;
anything absent is inferred.

```json
{
  "areas":    [["A", "Orders", "public", ["orders", "order_items"]]],
  "layer_of": {"orders": "TX", "order_items": "TX"},
  "layers":   {"TX": ["#25324D", "#35507D", "#4A80C0", "Transactional"]},
  "roles":    {"orders": "Order header"},
  "derives":  [["ext_feed", "orders", "External feed"]],
  "doc":      {"title": "Storefront ERD", "meta": [["Author", "Jane Doe", "", ""]]}
}
```

| Key | Meaning |
|---|---|
| `areas` | `[code, area name, schema, [tables…]]` — both the group box and the layout unit |
| `layer_of` / `layers` | table→layer, layer→`[fill, header, border, legend label]` |
| `roles` | role name for a table (falls back to the DB table comment) |
| `derives` | ETL flow — data flow that is not an FK. Brown dashed line |
| `doc` | title, cover information, purpose, scope, basis, chapter 6 and 7 data |

The text in a spec is used exactly as written, in whatever language the user wrote it —
this is how a document mixes an English UI with, say, Korean area names.

If `doc.mapping` / `doc.open_items` are present, chapter 6 (design vs. built) and
chapter 7 (open items) are added; otherwise those chapters are omitted.

The HTML document uses a few more `doc` keys — all optional.

| Key | Meaning |
|---|---|
| `doc.intro` | preface under the cover (HTML tags allowed) |
| `doc.area_desc` | `{area code: text}` — a note under each area heading |
| `doc.db_names` | `{label: human-readable DB name}` — when several databases are merged |

Examples: `examples/minimal.spec.json` (minimal), `examples/full.spec.json` (everything)

## Rules that are not negotiable

These documents get reviewed. Break these and the review fails.

**Color = layer, grouping = schema/area.** Source data and derived layers must not share a
color. Rounded group boxes enclose schemas and functional areas.

**Only two kinds of line.** FK (grey solid), ETL flow (brown dashed). Splitting delete
rules (CASCADE/SET NULL) by color makes it look like four kinds of line — those belong in
the document tables only.

**Orthogonal routing.** Vertical movement happens only in the corridors between columns;
crossing a column happens in the gaps between that column's nodes. A line that cuts through
a table makes its endpoints impossible to trace. Lines leave and enter at the **actual
column row**, not at the center of the node.

**Crossings hop over as semicircles.** Where a horizontal line crosses a vertical one — so
that a crossing is not mistaken for a connection.

**Labels are drawn after nodes.** Otherwise nodes cover them. Do not put them on the line;
offset them above or below, and exclude any position that overlaps a table (hard
constraint).

**The canvas is measured in two passes.** Draw once onto a 1×1 dummy to measure the real
extent, then add margins and draw for real. Sizing from node positions alone clips the
labels, relationship lines and group boxes that reach outside them.

**Document insertion fits both width and height.** Setting width alone lets a tall diagram
run off the page. On landscape A4 the usable area is 26.7 × 18.0 cm.

## Automatic verification

Printed on every render. Do not judge it by eye.

```
verify erd_overview.png: label↔table n/a · label↔label n/a · line↔table 0 · vertical overlap 0 · horizontal overlap 0
verify erd_full.png: label↔table 0 · label↔label 0 · line↔table 0 · vertical overlap 0 · horizontal overlap 0
verify erd_area_A.png: label↔table 0 · label↔label 0 · line↔table 0 · vertical overlap 0 · horizontal overlap 0
```

A counter that must be 0 but is not gets a `[warn] must be 0: …` tail on the same line —
**a `[warn]` means a regression.** A non-zero the caller has declared acceptable for that
diagram prints as `3(tolerated)` instead of warning.

`n/a` means the check **did not run on that diagram**, and is never a substitute for 0. The
overview draws no relationship labels, so the two label counters have nothing to measure
there; printing 0 would claim a clean result from a check that never happened.

- **label↔table** — must be 0. Otherwise widen the candidate range in `flush_labels()`.
- **line↔table** — must be 0. A line running through a table is invisible (nodes are
  drawn over the edges), so this counter is the only way to see it. Non-zero means a
  corridor overflowed; widen `hgap` in the layout call, or split the area.
- **vertical overlap** — must be 0. Happens when `slot()` gives up finding a lane. Very
  dense areas can still hit this; it is a real defect, not noise.
- **horizontal overlap** — must be 0 on every diagram. Two things are deliberately not
  counted, because the router does not choose them: merges into the same column row, and
  two entry/exit tails grazing each other. A tail's y is the **actual column row** the line
  leaves from — a hard invariant of this layout — so when two unrelated tables happen to
  have a row at the same height, their short tails must overlap. Everything the router does
  choose (corridor lanes, self-loop arms) is counted, and drawing the same line twice is
  counted. A non-zero means a lane landed on a row it should have avoided — widen `hgap`,
  or split that area in the spec.
- **label↔label** — must be 0. Two labels sitting on top of each other.

The counters are also written as JSONL to `$ERD_VERIFY_LOG` when that variable is set, one
record per diagram (`{"file": …, "counts": {…}, "tolerated": […], "warn": […]}`, with `null`
for a check that did not run). `selftest.py` reads that, not the printed line: the line is
formatted for people and changes shape, and when `(tolerated)` and `[warn]` tails were added
the suite's number-scraping regex silently stopped seeing the last counter — precisely when
it was non-zero. Nothing else should parse the printed line.

## Regression test

`selftest.py` runs the whole skill against synthetic input and checks the result. No
database, no docker — about five seconds.

```bash
python3 selftest.py            # everything
python3 selftest.py parse      # only cases whose name contains 'parse'
```

Diagram quality is verified on every render, but nothing measured the rest — so each fix
kept quietly breaking something else. Inline `--` comments spent two releases as empty
strings, and two self-referencing loops drew on top of each other while the verifier printed
zeros. Every case in there is something that broke silently at least once.

**When you fix something, leave a case behind that would have caught it.** That is the point
of the file.

Check the inserted size too:

```python
from docx import Document
for s in Document('<doc>.docx').inline_shapes:
    print(s.width.cm, s.height.cm)      # within 26.7 × 18.0
```

## File layout

```
INSTALL.md        installation guide (also .ko / .ja / .es)
install.sh        automated install (placement · dependencies · fonts)
requirements.txt  Python dependencies
scripts/
  selftest.py     regression test — runs the skill on synthetic input, no DB needed
  i18n.py         picks the output language, resolves message keys
  lang/           message catalogs — en.py · ko.py · ja.py · es.py
  config.py       paths · DB connection · spec loading · automatic area classification
  introspect.py   DB → schema.json          (enough on its own, no DDL needed)
  parse_ddl.py    DDL parsing → schema.json (to include changes not yet applied)
  merge_schemas.py several databases' schema.<label>.json into one
  merge_desc.py   column description merge. MANUAL wins over everything
  erd.py          layout · render · GraphML
  svg_canvas.py   ImageDraw-compatible SVG canvas (vector output, same coordinates as PNG)
  build_erd.py    PNG · SVG · GraphML runner
  build_html.py   HTML schema reference
  build_docx.py   docx document
examples/
  minimal.spec.json                    minimal example
  full.spec.json                       full example (areas · layers · ETL · document meta)
  *.ko.spec.json                       the same two with Korean text
```

`parse_ddl.py` first makes copies of the SQL with string literals, `$tag$` blocks and
comments blanked out, then counts brackets and splits on commas using those. Anything else
leaks: `DEFAULT '('` used to swallow the next column, and a `--` inside a string literal
swallowed the one after it. The psql output separator is `\x1f`; `|` shows up inside
defaults and comments.

## Other databases and platforms

- **MySQL and others** — the queries in `introspect.py` follow PostgreSQL's
  `information_schema`. MySQL's is standard too, so the column, PK and FK queries carry
  over nearly unchanged — use `columns.column_comment` in place of `col_description`.
- **Fonts** — body text uses **Pretendard**, columns use a monospace face (Menlo, DejaVu
  Sans Mono). `erd.py` walks a per-OS candidate list, falling back to a system font that
  covers the script in use (Apple SD Gothic Neo, Hiragino, Noto CJK, DejaVu). Override with
  `ERD_FONT`·`ERD_FONT_BOLD`·`ERD_MONO`·`ERD_MONO_BOLD` (file paths). docx takes a **font
  name**, not a file — `ERD_DOC_FONT` (default follows `ERD_LANG`: `Calibri` for English,
  `Pretendard` for Korean). `install.sh` installs Pretendard for you.
