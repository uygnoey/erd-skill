# Installation guide

**English** · [한국어](INSTALL.ko.md) · [日本語](INSTALL.ja.md) · [Español](INSTALL.es.md)

## One line

```bash
unzip erd-skill.zip && bash erd/install.sh
```

That is all. `install.sh` takes care of the following:

1. Checks for Python 3.9+
2. Copies the skill to `~/.claude/skills/erd`
3. Installs `python-docx` and `pillow` from `requirements.txt`
4. Checks whether `psql` / `docker` is present
5. Downloads and installs the **Pretendard font** if it is missing (after asking)

The word *asking* is literal: with no terminal to ask on (CI, a pipe), nothing is
downloaded and nothing already on disk is overwritten. The installer says so and moves on.

When it finishes, **start a new Claude Code session.** Skills are read at startup, so a
session that was already running will not see it. Then say "draw the ERD".

The installer speaks English, Korean, Japanese, and Spanish; it follows your locale
(`LANG` / `LC_ALL`). To force one, set `ERD_LANG=en` (or `ko`, `ja`, `es`).

### Options

| Command | What it does |
|---|---|
| `bash install.sh` | Install into `~/.claude/skills/erd` (default) |
| `bash install.sh --project` | Install into the current project's `./.claude/skills/erd` |
| `bash install.sh --here` | Install dependencies only, leave the files where they are |
| `bash install.sh --check` | Check only, change nothing — for when something has gone wrong |

The four are mutually exclusive: giving two of them is refused rather than silently
resolved. `--check --project` used to end up as `--project` and write 38 files.

## Installing by hand

If `install.sh` is not an option (permissions, policy, offline), do these four things
yourself.

**① Unpack** — the zip contains the whole `erd/` folder, so unpack it directly into your
skills directory.

```bash
mkdir -p ~/.claude/skills && unzip erd-skill.zip -d ~/.claude/skills
```

The path must end up as `~/.claude/skills/erd/SKILL.md`. One level deeper
(`skills/erd/erd/SKILL.md`) or shallower and Claude Code will not find it.

**② Python packages**

```bash
pip3 install -r ~/.claude/skills/erd/requirements.txt
```

Only `python-docx` and `pillow`. If you use a virtualenv, run the scripts from a shell
with that environment activated.

**③ A database client** — either `psql` or `docker`. On macOS,
`brew install libpq && brew link --force libpq`; on Debian, `apt install postgresql-client`.

**④ Fonts** — body text uses Pretendard, columns use a monospace font.

```bash
# Pretendard — Regular and Bold are the only two needed
curl -fsSLo /tmp/p.zip https://github.com/orioncactus/pretendard/releases/download/v1.3.9/Pretendard-1.3.9.zip
unzip -j /tmp/p.zip 'public/static/Pretendard-Regular.otf' 'public/static/Pretendard-Bold.otf' \
  -d ~/Library/Fonts            # on Linux, ~/.local/share/fonts  (run fc-cache -f afterwards)
```

Without it, the renderer falls back to an OS font that covers your script (Apple SD Gothic
Neo, Nanum Gothic, Noto CJK). The diagram still comes out; only the typeface differs. If
**no** covering font exists, the characters render as □.

## Verifying the install

```bash
bash ~/.claude/skills/erd/install.sh --check
```

A healthy run looks like this:

```
1. Python
  ✓ Python 3.12.13  (/usr/bin/python3)

2. Skill placement (skipped — check)
  ✓ current location: /path/to/erd-skill
  ✓ SKILL.md found  (~/.claude/skills/erd)

3. Python packages
  ✓ requirements.txt  (~/.claude/skills/erd/requirements.txt)
  ✓ python-docx 1.2.0  (>= 1.1.0)
  ✓ pillow 12.3.0  (>= 10.0.0)

4. Database client (one of the two)
  ✓ psql   psql (PostgreSQL) 16.2

5. Rendering fonts
  ✓ body:   …/Pretendard-Regular.otf
  ✓ mono:   …/Menlo.ttc

6. Regression test
  ✓ all 181 passed
  ! 6 cases need a real server and were NOT run (ERD_SELFTEST_DOCKER=1 …)

Result
  ✓ installation complete
```

`--check` changes nothing, so it skips placement. It still reads the tree it would have
installed to, since that is the first thing to check when `/erd` does not show up.

**It picks one tree and measures that tree to the end.** The candidates, in order, are
`~/.claude/skills/erd`, `./.claude/skills/erd`, and the directory `install.sh` itself sits
in; the first one that *exists* wins, and its path is printed on the `SKILL.md` line. The
regression test in section 6 runs from that same tree. Running `--check` out of a fresh
clone while a skill is installed therefore reports on the **installed** copy, not on the
clone in your hand — which is the copy Claude Code actually loads.

Section 6 is not optional. If the chosen tree has no readable `scripts/selftest.py`, that is
a failure, not a skipped step: an install nobody measured is not an install that works. The
line above the tally tells you how many cases needed a real database server and were
therefore not run — that count is never silently dropped.

`SKILL.md` has to *be* a skill file, not merely exist: line 1 must be `---`, the frontmatter
must be closed by a second `---`, and it must contain `name: erd`. An empty or truncated
`SKILL.md` is reported as broken.

Package versions are compared against the floors declared in `requirements.txt`. An install
that is present but older than the declared floor is a failure — those numbers are checked,
not decorative.

## First run

To run it yourself instead of leaving it to Claude:

```bash
cd ~/.claude/skills/erd/scripts

export ERD_PROJ=/path/to/project                              # where documents are written
export ERD_WORK=/tmp/erd-build                                # intermediate artifacts
export ERD_PSQL='psql postgresql://user:pass@localhost:5432/mydb'
export ERD_DOCNAME='Our Service ERD'

python3 introspect.py && python3 merge_desc.py && \
python3 build_erd.py && python3 build_docx.py
```

If the database is inside docker, use `export ERD_DB='container:user:db'` instead of
`ERD_PSQL`.

When `introspect.py` prints a table count, the connection worked. If it prints 0, change
`ERD_SCHEMAS` (default `public`) to your actual schema name. For the remaining environment
variables and for writing a spec, see `SKILL.md`.

## Font environment variables

Use these to override auto-detection.

| Variable | Purpose |
|---|---|
| `ERD_FONT` / `ERD_FONT_BOLD` | Path to the PNG body font file (default: Pretendard, auto-detected) |
| `ERD_MONO` / `ERD_MONO_BOLD` | Path to the PNG monospace font file |
| `ERD_DOC_FONT` | docx body **font name** (default follows `ERD_LANG` — `Calibri` for English, `Pretendard` for Korean) |
| `ERD_DOC_MONO` | docx monospace font name (default `Consolas`; `D2Coding` for Korean) |

PNG takes a file path, docx takes a font name — a docx only looks right if the machine
opening it has that font, otherwise Word substitutes. If you know the recipients will not
have Pretendard, run with something like `export ERD_DOC_FONT='Malgun Gothic'`.

## Common snags

**`ModuleNotFoundError: No module named 'docx'`**
The package is `python-docx`, not `docx`. The names differ. Running `install.sh --check`
also tells you which Python it is looking at.

**It installed but the import fails**
`pip3` and `python3` are two different installations. Install with the **same Python**:
`python3 -m pip install -r requirements.txt`. That is what install.sh does.

**`/erd` is not in the list**
Check, in this order: ① does `ls ~/.claude/skills/erd/SKILL.md` return anything ② did you
restart Claude Code ③ does `SKILL.md` start with `---` on line 1 and contain `name: erd`.
`install.sh --check` performs ① and ③ for you and names the tree it looked at.

**`[warn] database query failed`**
Check the value of `ERD_PSQL` / `ERD_DB`. Run the same command in your shell first and see
whether it connects. If both are set, `ERD_PSQL` wins.

**`N diagrams are older than …/schema.json` and no document is written**
This is a gate, not a crash. `build_html.py` / `build_docx.py` / `build_erd.py` refuse to
put figures that were drawn from an older schema into a document, because the tables would
say one thing and the pictures another. The fix is to run `python3 build_erd.py` again.
If the only change was wording and the figures really are still right, `ERD_STALE=warn`
(or `ERD_STALE=1`) lets them through — and still prints one line saying it did.
`ERD_STALE` follows the same yes/no rule as the other switches, so `true`, `on`, `y` all
turn it on, an empty `ERD_STALE=` means **off**, and a typo is named on stdout rather than
being taken as a yes.

**PNG text renders as □**
No font covers those characters. Re-run `install.sh` to install Pretendard, or point
`ERD_FONT` at a font yourself.

**It printed a list of columns with no description**
That is the intended behavior. Fill them into the `MANUAL` dictionary in `merge_desc.py`
and run it again. See the "column descriptions" section of `SKILL.md`.

**I cannot find the output**
`.graphml` and `.docx` are in `$ERD_PROJ`; PNGs are in `$ERD_WORK/out/`.
