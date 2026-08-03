# erd — PostgreSQL ERD · schema documentation, generated

**English** · [한국어](README.ko.md) · [日本語](README.ja.md) · [Español](README.es.md)

A [Claude Code](https://claude.com/claude-code) skill that connects to your database,
reads the real schema, and **produces the ERD and the schema reference in one pass.**

Nothing is drawn by hand, so **the diagram cannot drift from the database.**
When the schema changes, run it again.

```bash
python3 introspect.py && python3 merge_desc.py && python3 build_erd.py && python3 build_html.py
```

On a database of 100 tables and 1,235 columns this yields **a single 3.1 MB HTML file** —
table of contents, overview diagram, 17 per-area ERDs, per-table column tables, and the
full detailed ERD, all inside it.

## What you get

| Output | Purpose |
|---|---|
| `<docname>.html` | **Schema reference** — contents · overview ERD · per-area ERDs · per-table column tables · full ERD. One self-contained HTML file with the diagrams embedded |
| `<docname>.docx` | For submission and print (diagrams + column description tables + FK list) |
| `<docname>.graphml` | Open in yEd to rearrange and re-export by hand |
| `out/erd_*.png` · `.svg` | Overview · per-area detail · full diagram |

The HTML jumps straight from the contents to any table, and **clicking an ERD opens it at
full size.** It is vector (SVG), so the text stays sharp no matter how far you zoom.
Sharing is one file, nothing else.

## Why

Database documentation is easy to write and hard to keep. The schema moves, the diagram
goes stale first, nobody looks at a stale diagram, and eventually nobody trusts the
document at all.

So three things are enforced.

**① The diagram comes out of the database.** No one draws it. `information_schema` and
`pg_catalog` are read for tables, columns, types, PKs, FKs (including delete rules),
unique constraints, indexes, and CHECKs.

**② Descriptions are never lost.** An ERD is worth something because of its column
descriptions — and if the wording someone polished disappears every time the document is
regenerated, nobody writes descriptions again. So **descriptions are inherited from the
previous edition of the document.**

```bash
ERD_DOC_HTML=previous.html python3 merge_desc.py
#   column descriptions carried over from …: 1123
#   columns by description source: {'ddl': 268, 'doc': 951, 'orm': 0, 'manual': 16, 'common': 0, 'none': 0}
```

If `none` is not 0, you get the list of columns that are still empty. **Undescribed
columns are not quietly waved through.**

**③ Diagram quality is not judged by eye.** Every render prints its own verification.

```
verify erd_area_A.png: label↔table 0 · line↔table 0 · vertical overlap 0 · horizontal overlap 0
```

A label covering a table, or lines lying on top of each other, shows up as a number.
Per-area detail diagrams must be 0 across the board.

## Install

```bash
git clone git@github.com:uygnoey/erd-skill.git
bash erd-skill/install.sh
```

`install.sh` handles placement (`~/.claude/skills/erd`), dependencies (`python-docx`,
`pillow`), and the Pretendard font. When it finishes, **start a new Claude Code session**
and say "draw the ERD" or call `/erd`.

| Command | What it does |
|---|---|
| `bash install.sh` | Install into `~/.claude/skills/erd` (default) |
| `bash install.sh --project` | Install into the current project's `./.claude/skills/erd` |
| `bash install.sh --check` | Check only, change nothing |

Details in [INSTALL.md](INSTALL.md).

### Requirements

- Python 3.9+ / `python-docx` / `pillow`
- Either `psql` or `docker`
- A font covering the script you write in — body text uses Pretendard (installed
  automatically); with `ERD_LANG=ja` a Japanese-capable face (Hiragino Sans, Noto Sans JP,
  Yu Gothic) is preferred instead, since Pretendard carries no kanji. Failing both, the
  renderer falls back to the OS default

## Usage

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project        # where documents are written
export ERD_WORK=/tmp/erd-build          # intermediate artifacts
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='Our Service Schema Reference'
export ERD_LANG=en                      # en · ko · ja · es

python3 introspect.py    # ① DB → schema.json
python3 merge_desc.py    # ② fill in column descriptions
python3 build_erd.py     # ③ GraphML + PNG + SVG
python3 build_html.py    # ④ HTML schema reference
python3 build_docx.py    # ⑤ docx document (optional)
```

For a database inside docker, use `export ERD_DB='container:user:db'` instead of `ERD_PSQL`.

**It runs without a config file.** Areas are classified automatically from schema names
and table-name prefixes, and colors are assigned.

That said, automatic classification is **for getting a first draft on screen.** Unless the
database has consistent naming, tables that match nothing collect in an "Other" area — on
an 80-table database, 24% of them landed there. The bigger "Other" gets, the taller and
harder to read that diagram becomes. **If the output is going into a document, define the
areas yourself in `erd.spec.json`** — the areas become the document's table of contents.

### Output language

Everything a person reads — console output, the HTML and docx documents, the diagram
legend, the installer — follows `ERD_LANG`: **English, Korean, Japanese, Spanish.**
Without it the locale decides (`LANG` / `LC_ALL`), falling back to English.

Text you write yourself in `erd.spec.json` — area names, roles, the document title — is
used verbatim, so an English document with Korean area names is perfectly fine.

Adding a language is one file in `scripts/lang/` — the directory *is* the list of
supported languages. Anything you leave out falls back to English, so a half-translated
catalog still runs.

### Several databases, one document

```bash
ERD_LABEL=shop ERD_DB='shop-postgres:app:shop' python3 introspect.py
ERD_LABEL=mart ERD_PSQL='psql postgresql://app:pw@localhost:5433/mart' python3 introspect.py
python3 merge_schemas.py shop mart      # table keys become e.g. 'shop.orders'
```

There can be no physical FK between databases, so flows that cross them are written as
`derives` in the spec.

### erd.spec.json — the skeleton of the diagram

Everything is optional; anything absent is inferred.

```json
{
  "areas":    [["A", "Orders", "public", ["orders", "order_items"]]],
  "layer_of": {"orders": "TX", "order_items": "TX"},
  "layers":   {"TX": ["#25324D", "#35507D", "#4A80C0", "Transactional"]},
  "roles":    {"orders": "Order header"},
  "derives":  [["ext_feed", "orders", "External feed"]],
  "doc":      {"title": "Storefront Schema Reference"}
}
```

| Key | Meaning |
|---|---|
| `areas` | `[code, area name, schema, [tables…]]` — both the group box and the layout unit |
| `layer_of` / `layers` | table→layer, layer→`[fill, header, border, legend label]` |
| `roles` | Role name for a table (falls back to the table comment in the DB) |
| `derives` | ETL flow — data flow that is not an FK. Brown dashed line |
| `doc` | Document title, cover page, preface, per-area notes |

Examples: [`examples/minimal.spec.json`](examples/minimal.spec.json) (minimal),
[`examples/full.spec.json`](examples/full.spec.json) (everything).

The full list of environment variables is in [SKILL.md](SKILL.md).

## Drawing rules

These are meant for documents that get reviewed, so a few things are not negotiable.

- **Color = layer, grouping = schema/area.** Source and derived layers never share a color
- **Only two kinds of line.** FK (grey solid), ETL flow (brown dashed). Delete rules go in
  the document tables, not into the diagram
- **Orthogonal routing.** Lines never cut through a table. They leave from the **actual
  column row**, not from the center of the node
- **Crossings hop over as semicircles.** So that a crossing is not read as a connection
- **Labels are drawn after nodes.** Otherwise nodes cover them
- **The canvas is measured in two passes.** Everything is drawn once onto a 1×1 dummy to
  measure the real extent, then margins are added. Sizing from node positions alone clips
  the labels and relationship lines that reach outside them

## PNG and SVG

They are the same picture. Coordinates and font widths are measured identically with PIL;
only the drawing back end changes to vector (`svg_canvas.py` mimics the `ImageDraw`
interface).

|  | Overview | Per-area | Full detail |
|---|---|---|---|
| PNG | 0.70 MB | 0.41 MB | 3.27 MB |
| **SVG** | **0.48 MB** | **0.23 MB** | **0.30 MB** |

An SVG draws its text with whatever font the viewing machine has, so a missing font
changes the width and text spills out of its cell. Every `<text>` therefore pins the width
PIL measured via `textLength`. **The layout does not break on a machine without the font.**

## Layout

```
install.sh        automated install (placement · dependencies · fonts)
scripts/
  selftest.py     regression test (no database needed)
  i18n.py         picks the output language
  lang/           message catalogs (en · ko · ja · es)
  config.py       paths · DB connection · spec loading · automatic area classification
  introspect.py   DB → schema.json
  parse_ddl.py    DDL parsing → schema.json  (to include changes not yet applied)
  merge_schemas.py several databases' schemas into one
  merge_desc.py   column description merge
  erd.py          layout · render · GraphML
  svg_canvas.py   ImageDraw-compatible SVG canvas
  build_erd.py    PNG · SVG · GraphML runner
  build_html.py   HTML schema reference
  build_docx.py   docx document
examples/         spec examples
```

## Other databases

The queries in `introspect.py` target PostgreSQL. MySQL also has a standard
`information_schema`, so the column, PK, and FK queries carry over nearly unchanged — use
`columns.column_comment` in place of `col_description`.

## License

MIT
