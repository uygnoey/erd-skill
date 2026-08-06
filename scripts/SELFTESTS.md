# Self-test layout

`python3 selftest.py` is the full-suite entry point. A substring argument filters case
names, for example `python3 selftest.py "parse:"`. Output is grouped by the prefix before
`:` so failures appear under the product area they exercise.

| File | Area |
|---|---|
| `selftest.py` | Core cases and full-suite entry point |
| `selftest_schema.py` | DDL parsing, introspection, schema merge, ERD structure |
| `selftest_config.py` | Configuration, environment variables, spec validation, i18n |
| `selftest_render.py` | Layout, routing, fonts, overlap verification, fuzz/board tools |
| `selftest_build.py` | HTML, DOCX, GraphML, cross-artifact consistency |
| `selftest_install.py` | Installer, dependency checks, documentation contracts |
| `selftest_kit.py` | Registration, fixtures, subprocess runner, assertions |

Every module reports `EXPECT_CASES`; loading fails if it registers a different count. An
independent total floor also prevents a renamed or deleted module from silently producing
a smaller green run.
