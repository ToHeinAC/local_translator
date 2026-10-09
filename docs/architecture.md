# Architecture

## Code layers

| Layer | Where | Rule |
|---|---|---|
| Core logic | `src/app/*.py` | Pure functions, fully typed, no I/O. Unit-tested directly. |
| Adapters | `src/app/<adapter>.py` (add when needed) | The only place for network, file, or database I/O. |
| Entry points | CLI / app module (add when needed) | Wire adapters to core logic; keep them thin. |

## Quality gate flow

```
Claude edits a .py file  -> PostToolUse hook: ruff format (that file only)
Claude stops             -> Stop hook: if .py files changed, run the gate; exit 2 = keep working
git commit               -> pre-commit: the gate on staged files
push / pull request      -> CI: uv sync --locked, then the gate on all files (Python 3.11 and 3.14)
```

The gate itself is defined once, in `.pre-commit-config.yaml`. The Stop hook and CI only call it.

## Design decisions

- **One gate definition.** The pre-commit config is the only list of checks. The Stop hook and CI
  run `pre-commit run --all-files`, so the three can't drift apart.
- **Tool versions come from `uv.lock`.** The local pre-commit hooks use `language: unsupported`
  (the new name for `system`) and call `uv run <tool>`, so ruff, pyright and pytest aren't
  pinned a second time in the pre-commit config.
- **The edit hook formats but never lint-fixes.** `ruff check --fix` would delete an import
  that Claude adds one edit before its first use.
- **The Stop hook is cheap and can't loop.** It only runs when `.py` files changed. The
  `stop_hook_active` flag allows at most one forced continuation per stop.
- **Coverage runs only in the gate** (`pytest --cov`), not in `addopts`. Running a single test
  file must not fail on the coverage threshold.
- **Function length is checked by an AST test.** ruff has no rule for function lines;
  `tests/test_code_rules.py` has one.

## Known limits

- `pre-commit run --all-files` checks only files git tracks. New untracked files are formatted by
  the edit hook, and pyright and pytest cover the whole project. ruff lint reaches new files at
  commit time.
- gitleaks scans staged changes, so it protects commits but CI doesn't rescan history.
  Contributors must run `uv run pre-commit install`.
- Claude Code permission rules are not a security boundary. `Read(.env)` stops the Read tool,
  not every shell command. Keep real secrets out of the repo directory where you can.

## Document model (`src/app/document.py`)

- **One flat `Block` type** with a `Kind` enum; inline text stays a raw Markdown string.
- **`translate` flag** (extends PRD §5.2): False for HTML, code and image placeholders, so the
  translation core has one check for "leave untouched".
- **Canonical Markdown:** ATX headings, `-` bullets, `1.` renumbered ordered lists, nesting by
  marker width, fenced code, GFM tables. Non-canonical input is normalised, not preserved.
- **Known limitations (flat model):** extra paragraphs, code or tables inside a list item become
  top-level blocks; quote paragraphs become separate `quote` blocks and nested quotes are
  flattened; `---` maps to `page_break`; two adjacent lists of the same type merge on write.
- Empty or image-only input raises `EmptyDocumentError("Dokument enthält keinen Text")`.

## Glossary (`src/app/glossary.py`, `src/app/readers.py`)

- `read_glossary_rows` (adapter) turns any of the four formats into rows; `build_glossary`
  (pure) filters them for one language pair and reports issues with spreadsheet row numbers
  (header = row 1).
- **Duplicates:** identical source and target twice keeps the first and reports the rest. Same
  source with different targets is a conflict: all its rows are dropped and reported.
- **Matching:** suffixes `e en er es n s` apply to source and target terms in every language;
  matching a term as the end of a compound noun applies only when the language is `de`.
  Longer terms claim their text span first. Verification needs the target at least as often
  as the source matched.
- A glossary with 0 usable entries is not an error; the UI warns (M8).

## Translation core (`segment.py`, `prompt.py`, `translate.py`)

- **Units:** each translatable block, table cell or sentence group (for text longer than
  `segment_chars`) is one unit; units without letters are skipped. Units are packed into
  segments of at most `segment_chars`.
- **Per segment:** call 1; if the answer is unusable (ID or protected token missing, extra or
  duplicated) or a glossary term is missing, one strict retry. If the answer stays unusable,
  each unit is translated alone (with the same single retry); a unit that still fails stays in
  the source language and its block is listed in `TranslationResult.failed`. An exception from
  `llm` marks the whole segment failed without retry (network retries belong to the M5 adapter).
- **Term check is per unit**, so a miss is attributed to its block (needed for the DOCX
  highlight in M7). `hits` counts matched entries per unit; `enforced = hits - misses`.
- **Progress** is `progress(done, total)` so the UI can show "Abschnitt n von N"; cancel is
  checked after each segment.
- **Not in M3:** the FR-6a skip of paragraphs already in the target language (needs
  `langdetect`; planned with M7).

## Input readers (`readers.py`, `docx_reader.py`, `pdf_reader.py`)

- `read_document(name, data)` dispatches on the extension. Errors are `DocumentReadError`
  (unsupported type, corrupt file, scanned PDF, > 200 pages) or `EmptyDocumentError`; both carry
  user-facing German messages.
- **DOCX:** body paragraphs and tables in order. Headings from the `Title`/`Heading n` styles or
  an outline level (paragraph or style chain). Lists from `numPr` (paragraph or style chain);
  depth from `ilvl` or a "List Bullet 2" style suffix; ordered if the numbering format is not
  `bullet`. Runs with the same bold/italic are merged into `**`/`*` markup; hyperlinks become
  Markdown links; images become `[Bild: <alt or name>]`. Table cells are joined into one line;
  merged cells repeat their text. Headers, footers and notes are not read here (M7 handles them).
- **PDF:** text lines come with their font size. Lines in the top or bottom 10 % whose text
  (digits normalised) repeats on at least 60 % of the pages (min. 2) are dropped. The most common
  size is body text; sizes at least 15 % larger become headings, ranked by size. Lines join into a
  paragraph unless the gap exceeds half the body size; hyphenated line ends are joined. No tables
  or lists are recovered.
- **Plain text:** blank-line separated paragraphs; inline Markdown characters are not escaped.
- `pillow` (HPND, permissive) arrives as a dependency of reportlab.

## Output writers (`writers.py`, `docx_writer.py`, `pdf_writer.py`, `inline.py`)

- `write_md` is the M1 writer; `output_name(stem, target, ext)` gives `<stem>_<target>.<ext>`.
- **DOCX:** Word's default template. Title, language and author go to the core properties (no
  title paragraph). Headings use `Heading n`; lists `List Bullet|Number [2|3]` (depth above 3 is
  clamped); tables use `Light Grid Accent 1` (header bold via the style, not runs); links are real
  hyperlinks. Quote and code have no reader counterpart and read back as paragraphs. Ordered lists
  share one numbering instance, so a second list continues the count in Word.
- **PDF:** A4, DejaVu Sans/Mono from `src/app/fonts/` (notice in THIRD_PARTY_NOTICES.md). Headings
  are bold with `keepWithNext`; tables repeat their header row on each page. `PAGE_BREAK` is a page
  break in both formats.
- **Wide tables:** if any table has more than 8 columns, the whole document is landscape (PDF
  tables also use a smaller font).
- `inline.py` parses Markdown inline syntax once for both writers; images become `[Bild: alt]`.

## Ollama adapter (`models.py`, `llm_ollama.py`, `benchmark.py`)

- `make_llm(client, model, host)` returns the `llm(prompt) -> str` that `translate_document`
  expects. One `ResponseError` or `ConnectionError` is retried once; a second `ConnectionError`
  raises `OllamaUnavailableError(host)`. HTTP timeouts become the builtin `TimeoutError`.
- `OllamaUnavailableError` derives from `FatalLlmError` (defined in `translate.py`), which aborts
  the whole job instead of marking one segment failed (NFR-7).
- The client is typed by a small protocol so tests pass a stub; there is no network in tests.
- Results of the benchmark are in [benchmark.md](benchmark.md).
