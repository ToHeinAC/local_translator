# PRD — Lokaler KI-Übersetzer (local_translator)

Status: approved 2026-10-08 (decisions from the review session in §7). Changes need the user's
approval (AGENTS.md §5.1).
Sibling apps referenced: `local_summarizer` (look and feel, https://ai.brenk.com/smrz/) and
`local_app-orchestrator` (landing page, https://ai.brenk.com/).

## 1. Problem & goal

Documents (DOCX, Markdown, PDF) regularly need translating into another language. Cloud translators
are not acceptable for internal documents, and generic tools ignore company-specific terminology
and flatten the document structure.

**Goal:** a local web app that translates a document into a selected target language using a
locally hosted LLM (Ollama). It always uses the terms from an uploaded glossary, keeps the
document structure (headings, sections, lists, tables, emphasis), and returns the result as
Markdown, DOCX and PDF. It looks like the KI-Zusammenfassung app and is listed on the
ai.brenk.com landing page.

**Solved means:** a user uploads `Bericht.docx` and `Glossar.csv`, picks "English" and
`gemma4:e4b`, clicks "Übersetzen". They see progress and download `Bericht_en.md/.docx/.pdf` with
the same heading tree. Every glossary term found in the source appears in the translation as
specified, or is listed in a term report.

## 2. Users and usage

| User | Need |
|---|---|
| Staff with internal documents (reports, procedures, specifications) | Fast and confidential translation, no data leaving the network. |
| Domain experts | Terminology fixed by a glossary they maintain themselves (Excel/CSV). |
| Admin (T. Hein) | Run, update and stop the service. Pick and pre-pull models. |

Typical input: 1–50 pages, mostly text with headings, lists and tables. Source and target
languages are mainly DE↔EN, sometimes FR/ES/IT/NL/PL/CS.

## 3. Scope

### 3.1 Functional requirements

**FR-1 Input documents.** Upload one file per job: `.docx`, `.md`, `.pdf` (text layer), `.txt`.
Max size 25 MB (configurable via `MAX_UPLOAD_MB`). The file is converted into an internal document
model (§5.2). Unsupported or corrupt files give a clear error, never a crash.

**FR-1a DOCX in place.** A `.docx` input is translated inside a copy of the original file, so
styles, the company template, images, page layout and document properties stay as they are
(§5.9). Translated: body paragraphs, tables, headers and footers. Not translated in v1:
footnotes, endnotes, comments, text boxes, SmartArt, charts. They stay in the source language,
and the term report says so.

**FR-2 Source language.** Auto-detected (`langdetect`) and shown. The user can override it.

**FR-3 Target language.** Selectable from a fixed list: `de, en, fr, es, it, pt, nl, pl, cs`
(Latin script; covered by the PDF font, see R-5). The target cannot equal the source; the UI
blocks this.

**FR-4 Glossary file (optional).** Upload one glossary per job (`.csv`, `.tsv`, `.xlsx`, `.md`
table). Format (§5.4): header row of ISO language codes, one term per row, optional `note`
column. One glossary can therefore serve several language pairs. The app shows how many entries
apply to the selected pair and lists rows it cannot use (empty cell, duplicate source term,
conflicting targets). The UI offers a downloadable template glossary.

**FR-5 Terminology enforcement.** For each segment, only the glossary entries whose source term
occurs in it go into the prompt as binding rules. After translation, a check confirms that each
required target term appears. A segment that fails is retried once with a stricter instruction.
Failures that remain are listed in the term report (FR-9). The output is never blocked. In the
DOCX output, each paragraph that still has a miss gets a yellow highlight. Matching is
case-insensitive, whole-word and inflection-tolerant (§5.4).

**FR-6 Structure preservation.** The code keeps the block structure, not the LLM. Headings (levels
1–6), paragraphs, ordered and unordered lists (with nesting), tables (cell by cell), block quotes
and code blocks pass through unchanged as structure; only their text is translated. Inline
markup (bold, italic, links, inline code) is preserved. The following are never translated: code
blocks, inline code, URLs, e-mail addresses, numbers with units, and placeholders such as `{x}`.

**FR-6a Already in target language.** A paragraph of ≥ 40 characters that `langdetect` already
identifies as the target language is copied unchanged (e.g. English quotes in a German text).
Shorter paragraphs are always translated, because detection is unreliable for them.

**FR-7 Model selection.** A dropdown with a fixed registry (§5.3): `qwen3:4b` (simple),
`gemma4:e2b` (fast, default), `gemma4:e4b` (standard). The app checks `/api/tags` and marks
missing models with the hint `ollama pull <tag>`. Thinking/reasoning output is disabled for all
models.

**FR-8 Output.** The translated document is offered as three downloads: Markdown, DOCX and PDF.
File name: `<stem>_<target>.<ext>`.
- DOCX for a DOCX input: the original file, translated in place (FR-1a); only the language tag
  is set to the target language.
- DOCX for an MD/PDF/TXT input: rebuilt from the block model with Word's default styles (real
  heading styles, lists, tables). Title = file name, language = target, author = logged-in user.
- MD and PDF are always built from the block model of the translated text, so all three outputs
  have the same content. The PDF has a Unicode font, heading hierarchy, lists and tables.

Results exist only in the current session's state (they survive reruns). They are dropped when a
new job starts, on logout and on page reload. There is no history.

**FR-9 Term report.** After the job: number of glossary hits, number enforced, and a table of
remaining misses (segment excerpt, source term, expected target). The report is downloadable as
CSV.

**FR-10 Progress and cancel.** A progress bar shows "Abschnitt n von N". A cancel button stops the
job after the current segment. If a segment fails after retries, the job keeps going: the
segment stays in the source language, is marked, and is listed in the report.

**FR-11 UI language.** German by default, English toggle (same i18n pattern as the summarizer).
Prompts to the model are in English.

**FR-12 Login.** Same login as the summarizer (bcrypt, `data/users.json`, seed passwords from
`.env`), with its own `data/users.json`, because the app is reachable via a public URL.

**FR-13 Safe exit.** An "App beenden" button in the sidebar, visible only to `ADMIN_USERS`
(default "T. Hein"), sends SIGTERM to the app's own PID after a confirmation. It never kills by
port. There is no automatic restart; the landing page then shows the app as stopped.

**FR-14 Admin options (expander).** Same as the summarizer: GPU/VRAM status and "VRAM leeren"
(unload models via `keep_alive=0`).

### 3.2 Non-functional requirements

| ID | Requirement |
|---|---|
| NFR-1 | Fully local: no network calls except to the configured `OLLAMA_HOST`. No telemetry (`browser.gatherUsageStats = false`). |
| NFR-2 | Confidentiality: uploads are processed in memory or in a per-session temp dir under `data/tmp/`, deleted after the job or on session end. No stored history, no document content in logs. |
| NFR-3 | Streamlit on fixed port **8560**, `baseUrlPath = "trns"`, `enableXsrfProtection = true`. |
| NFR-4 | Licenses ≤ Apache-2.0 and permissive only (MIT, BSD, ISC, PSF, Apache-2.0). Explicitly excluded: PyMuPDF (AGPL), fpdf2 (LGPL), pandoc binaries (GPL) (§5.6). |
| NFR-5 | Look and feel identical to the summarizer: `FOREST` palette, Inter + Libre Baskerville, same layout grammar (§5.5). |
| NFR-6 | Throughput target, to be verified in M5: a 10-page text document with `gemma4:e4b` on the target GPU in ≤ 5 min. |
| NFR-7 | Robustness: one failing segment never aborts the job (FR-10). Ollama unreachable → clear UI error with host name. |
| NFR-8 | Quality gate per AGENTS.md §5.4. Offline test suite with a fake LLM. Core logic is pure and has no I/O. |
| NFR-9 | Concurrency: one active job per session. Several sessions share Ollama; requests are not parallelised across sessions (Ollama queues them). |

## 4. Non-goals

- Pixel-perfect layout for MD/PDF inputs and for the PDF output. Only DOCX→DOCX keeps the visual
  layout (FR-1a). Footnotes, comments, text boxes, SmartArt and tracked changes are not
  translated in v1.
- PDF rendering through LibreOffice or other external converters (license constraint, NFR-4).
- A company Word template for rebuilt DOCX files (possible later as `assets/template.docx`).
- Storing translations or a job history.
- Legacy `.doc`, `.odt`, `.rtf`, `.pptx`, `.xlsx` as document input.
- Scanned PDFs / OCR in v1 (possible follow-up, see M10; the summarizer already has a
  `deepseek-ocr` path that can be reused).
- Translating text inside images; images are replaced by a placeholder `[Bild: <alt/name>]`.
- Right-to-left or CJK target languages.
- Cloud LLMs, free model entry, model download from the UI.
- Batch translation of several files, translation memory, editable side-by-side review.
- Glossary editing in the UI (the glossary is maintained in Excel/CSV).
- Changes to the orchestrator code (only its `apps.toml` and nginx config get one entry each).

## 5. Solution outline

### 5.1 Pipeline

```
upload ─► reader adapter (docx|md|pdf|txt) ─► Document model (blocks)
       ─► segmenter (block-aligned, ≤ SEGMENT_CHARS) ─► per segment:
            glossary.match ─► prompt.build ─► llm.translate ─► glossary.verify ─► retry once?
       ─► reassemble Document ─► writers: markdown | docx | pdf  +  term report
```

For a DOCX input, the translated block texts are also written back into the original file (§5.9).

The pipeline is a plain sequence of pure functions plus three adapters (reader, LLM, writer).
LangGraph is not used: the flow is linear, and pure functions are easier to test.

### 5.2 Document model (core, pure)

`Document = list[Block]`. Each block has a kind (`heading(level)`, `paragraph`, `list_item(depth,
ordered)`, `table(rows×cols of cells)`, `quote`, `code`, `image_placeholder`, `page_break`) and
an inline text in Markdown inline syntax. Markdown is the canonical serialisation: every reader
produces a `Document`, and the Markdown writer is its inverse.

Structure invariants (checked in tests and at runtime): the translated document has the same
number of blocks, the same kinds, heading levels, list depths and table shapes as the source.

### 5.3 Segmenting, prompting and models

- **Segment:** consecutive blocks up to `SEGMENT_CHARS` (default 3000). A block is never split
  unless it is longer by itself; then it is split at sentence boundaries. Each table cell is
  translated as its own unit (batched per table).
- **Wire format:** the blocks of a segment are sent as numbered lines (`[[1]] …`, `[[2]] …`) and
  must come back with the same IDs. If an ID is missing or extra, the segment is retried once,
  then falls back to block-by-block translation.
- **Context:** the previous segment's last block (source and translation) is passed as read-only
  context for consistency. Settings: `temperature 0.1`, `num_ctx 8192`, `think=False`.
- **One prompt for all models.** Only the parameters differ. Tune per model only if the M5
  benchmark shows a poor glossary hit rate.
- **Protected spans:** inline code, URLs, e-mails and placeholders are replaced by tokens
  (`⟦P1⟧`) before the call and restored after it. A missing token counts as a failed segment.
- **Model registry** (`models.py`, same shape as the summarizer):

| Key | Tag | Label (de) | Speed | Quality | Default |
|---|---|---|---|---|---|
| simple | `qwen3:4b` | Einfach | ★★★ | ★☆☆ | |
| fast | `gemma4:e2b` | Schnell | ★★★ | ★☆☆ | yes |
| standard | `gemma4:e4b` | Standard | ★★☆ | ★★☆ | |

`DEFAULT_MODEL` in `.env` can override the default; it must be one of the registry tags.

### 5.4 Glossary format and matching

```csv
de,en,fr,note
Abklingbecken,spent fuel pool,piscine de désactivation,
Freigabe,clearance,libération,radiological meaning, not "approval"
```

- Header: ISO 639-1 codes (case-insensitive), plus optional `note`. Delimiter `,` `;` or tab,
  auto-detected. Encoding UTF-8 (with or without BOM); cp1252 as fallback.
- `.xlsx`: first sheet, same header (read with `openpyxl`). `.md`: first pipe table.
- Usable entries: rows where both source and target cells are non-empty. Duplicate source
  terms with different targets → conflict, row ignored, reported.
- **Matching (source):** case-insensitive, Unicode word boundaries, longest match first (so
  "Freigabeverfahren" beats "Freigabe" if both exist). German inflection tolerance: a term
  also matches with suffixes `e, en, er, es, n, s` and as the last part of a compound noun.
- **Verification (target):** the target term (case-insensitive, same suffix tolerance for the
  target language) must occur in the segment's translation at least as often as the source term
  matched. The `note` is passed to the prompt as a hint.

### 5.5 UI (Streamlit, summarizer layout)

- `set_page_config(page_title="KI-Übersetzer", page_icon="🌐", layout="wide")`. Theme and CSS
  copied from the summarizer (`theme.py`, `.streamlit/config.toml` with the `FOREST` palette).
- **Sidebar:** `## 🌐 KI-Übersetzer`, then an "Erweiterte Optionen" expander (GPU status, "VRAM
  leeren"), the logged-in user, Abmelden, the language toggle, and "App beenden" (admin only).
- **Main panel:**
  - `st.title`, intro caption, `---`.
  - Row 1 (two columns): MODELL (with stars) | ZIELSPRACHE.
  - Row 2 (two columns): DOKUMENT uploader | GLOSSAR uploader (+ template download).
  - Info line: detected source language (overridable) and the number of usable glossary entries.
  - Primary button "Übersetzen", then a progress bar and a cancel button.
  - Result in `st.container(border=True)`: a Markdown preview, three download buttons
    (MD / DOCX / PDF), and the term report expander.
- Uppercase captions above controls, labels hidden, as in the summarizer.

### 5.6 Libraries (all permissive)

| Purpose | Library | License |
|---|---|---|
| UI | streamlit | Apache-2.0 |
| LLM | ollama (Python SDK) | MIT |
| DOCX read/write | python-docx | MIT |
| PDF text extraction (+ font sizes for heading detection) | pypdfium2 / pdfplumber | Apache-2.0 or BSD-3 / MIT |
| Markdown parse | markdown-it-py | MIT |
| PDF write | reportlab (open-source edition) | BSD-3 |
| PDF font | DejaVu Sans (bundled TTF) | Bitstream Vera / public domain (permissive) |
| XLSX glossary | openpyxl | MIT |
| Language detection | langdetect | Apache-2.0 |
| Auth | bcrypt | Apache-2.0 |
| Config | python-dotenv | BSD-3 |

The summarizer's `export.py` uses fpdf2 (LGPL-3.0) and can therefore **not** be copied as is;
the PDF writer is rebuilt on reportlab. Every dependency's license is checked when it is added
(M1–M6 acceptance).

### 5.7 Configuration (`.env.example`, keys only)

`OLLAMA_HOST`, `DEFAULT_MODEL`, `DEFAULT_TARGET_LANG`, `SEGMENT_CHARS`, `MAX_UPLOAD_MB`,
`LLM_TIMEOUT_S`, `SEED_PW_HEIN`, `SEED_PW_GAST`, `ADMIN_USERS`. The port (8560) and base path
are fixed in `.streamlit/config.toml`, not in `.env`.

### 5.8 Module plan (`src/app/`)

| Module | Kind | Responsibility |
|---|---|---|
| `document.py` | core | Block model, Markdown (de)serialisation, structure invariants |
| `segment.py` | core | Segmenting, wire format encode/decode, protected spans |
| `glossary.py` | core | Parse rows → entries, match, verify, report rows |
| `prompt.py` | core | Build system/user prompts from a segment and its glossary hits |
| `translate.py` | core | Orchestrate segments with an injected `llm` callable, retries, progress callback, cancel flag |
| `models.py` | core | Model registry |
| `readers.py` | adapter | docx/md/pdf/txt bytes → `Document`; csv/tsv/xlsx/md → glossary rows |
| `writers.py` | adapter | `Document` → md/docx/pdf bytes |
| `docx_inplace.py` | adapter | Read translatable paragraphs from a DOCX and write translations back into a copy (§5.9) |
| `llm_ollama.py` | adapter | Ollama chat call, availability check, unload |
| `i18n.py`, `theme.py`, `auth.py` | UI support | Copied/adapted from the summarizer |
| `ui.py` (`streamlit run src/app/ui.py`) | entry | Thin wiring of widgets to the pipeline |

### 5.9 DOCX in-place translation

- **Units:** each body paragraph, each table-cell paragraph and each header/footer paragraph is
  one block, in document order. The blocks are translated with the same core (M3) as any other
  input.
- **Inline formatting:** each run's bold/italic/underline is encoded as tags (`<b>`, `<i>`, `<u>`)
  in the text sent to the model. After translation, the tags are mapped back to runs; each new
  run takes the font properties of the source run with the same formatting. If tags are missing
  or invalid, the whole paragraph gets a single run with the formatting of its first run.
- **Untouched:** paragraph styles, numbering, images, fields, bookmarks, section and page
  settings. Runs that hold only images or fields stay in place.
- **Misses:** a paragraph with a glossary miss gets a yellow highlight on all its runs.
- **Properties:** all core properties are kept; only the language tag is set to the target.

## 6. Milestones

Each milestone ends with the full gate green and becomes one phase row in IMPLEMENTATION.md.

### M1 — Document model and Markdown round trip
- **Deliverable:** `document.py` with the block model, Markdown parser and writer, and
  structure-invariant check.
- **Acceptance criteria:**
  - A Markdown fixture with H1–H4, nested lists, a table, a quote, a code block and inline
    bold/italic/link/code round-trips: `write(parse(md))` is equivalent to `md` (normalised
    whitespace).
  - `same_structure(a, b)` is true for identical structures. It is false for each of: a changed
    heading level, a missing list item, a different table shape, a changed block kind.
- **Edge cases:** empty document → error "Dokument enthält keinen Text"; a document with only
  images → same; HTML in Markdown → passed through as a paragraph and not translated.
- **Dependencies:** none.

### M2 — Glossary
- **Deliverable:** `glossary.py` plus CSV/TSV/XLSX/MD readers.
- **Acceptance criteria:**
  - All four formats yield identical entries for the same content. `,` `;` and tab delimiters and
    UTF-8 BOM / cp1252 are handled.
  - Entries are filtered for the language pair. Empty-cell, duplicate and conflict rows are
    reported with their row numbers.
  - Matching finds "Freigabe", "Freigaben" and "Anlagenfreigabe" but not "freigeben"; longest
    match wins.
  - Verification passes when the target term is present and fails when it is missing or appears
    less often than required.
  - The template glossary file is valid input.
- **Edge cases:** header without the source or target language → error naming the available
  languages; a glossary with 0 usable entries → warning, job can still run; > 5,000 rows →
  accepted; only matched entries go to the prompt.
- **Dependencies:** none (openpyxl added).

### M3 — Translation core with fake LLM
- **Deliverable:** `segment.py`, `prompt.py` and `translate.py`, driven by an injected
  `llm(prompt) -> str`.
- **Acceptance criteria:**
  - With an echo/uppercase fake LLM, a mixed document comes back with the same structure, all
    protected spans unchanged and code blocks untouched.
  - The prompt contains exactly the glossary entries matched in that segment, with notes.
  - A fake LLM that drops a glossary term triggers exactly one retry with the stricter prompt;
    if it still fails, the miss is in the report.
  - A fake LLM that drops a `[[n]]` ID or token triggers a retry, then a block-by-block fallback.
  - A raised exception or timeout in one segment leaves that segment in the source language,
    marked, and the job finishes.
  - The progress callback is monotonic and ends at 1.0. The cancel flag stops the job after the
    current segment.
- **Edge cases:** a single block longer than `SEGMENT_CHARS` → sentence split; the LLM returns a
  preamble ("Here is the translation:") or `<think>` tags → stripped; the source already in the
  target language → still processed, with a UI warning.
- **Dependencies:** M1, M2.

### M4 — Input readers
- **Deliverable:** `readers.py` for docx, md, txt and pdf (text layer).
- **Acceptance criteria:**
  - **DOCX** (synthetic fixture built with python-docx in the test): Title/Heading 1–3 styles map
    to heading levels; numbered and bulleted lists map with their depth; tables keep their shape;
    bold/italic runs become inline markup; an image becomes a placeholder.
  - **PDF** (synthetic fixture built with reportlab in the test): text is extracted in reading
    order; lines with a larger font size than the body text become headings, with levels ranked
    by size; page headers/footers repeated on every page are removed.
  - A PDF without a text layer → error "Gescanntes PDF wird (noch) nicht unterstützt".
  - A corrupt file or a wrong extension → a clear error, no traceback in the UI.
- **Edge cases:** DOCX with custom heading styles (e.g. "Überschrift 1") → mapped through the
  outline level; hyphenated words at PDF line ends are joined; very long PDFs (> 200 pages) are
  rejected with a message stating the limit.
- **Dependencies:** M1.

### M5 — Ollama adapter and model registry
- **Deliverable:** `llm_ollama.py`, `models.py`.
- **Acceptance criteria:**
  - The registry contains exactly the three models from §5.3, with `gemma4:e2b` as the default.
    An invalid `DEFAULT_MODEL` falls back to it with a warning.
  - Requests carry `think=False`, `temperature=0.1`, `num_ctx=8192` and a timeout of
    `LLM_TIMEOUT_S` (tested against a stub client, no network).
  - The availability check marks missing models from a stubbed `/api/tags` response.
  - Unreachable host → a typed error that the UI shows with the host name.
  - Manual benchmark (documented in `docs/benchmark.md`): one 10-page fixture per model,
    wall-clock time, glossary hit rate. This checks NFR-6.
- **Edge cases:** the model is loaded on another GPU or evicted mid-job → the request is retried
  once; the qwen3 `<think>` block appears despite `think=False` → stripped (M3).
- **Dependencies:** M3.

### M6 — Output writers
- **Deliverable:** `writers.py` for md, docx (rebuilt, for MD/PDF/TXT inputs) and pdf.
- **Acceptance criteria:**
  - **DOCX:** Word's default styles, no company template. Title = file name, language =
    target, author = the given user name. Headings use Word's built-in `Heading n` styles (so the navigation pane and TOC
    work); lists use list styles with depth; tables are real tables; bold/italic are runs.
    Reading the DOCX back with M4's reader gives the same structure (round trip).
  - **PDF:** opens without error; text is extractable; headings are larger and bold; umlauts,
    accents and Polish/Czech characters render (DejaVu); tables are drawn; long tables break
    across pages.
  - **MD:** identical to the M1 writer output.
  - File names follow `<stem>_<target>.<ext>`; MIME types are correct.
- **Edge cases:** a very wide table (> 8 columns) → landscape page or smaller font; a heading
  as the last line of a page → kept with the next block.
- **Dependencies:** M1 (reportlab and the DejaVu TTF added; the font license goes into
  THIRD_PARTY_NOTICES.md).

### M7 — DOCX in-place translation
- **Deliverable:** `docx_inplace.py` (§5.9), wired into the translation core.
- **Acceptance criteria** (synthetic DOCX fixtures built with python-docx in the test, stub LLM):
  - Body paragraphs, table cells, headers and footers are translated. Footnotes, comments and
    text boxes are unchanged and listed in the report.
  - Paragraph styles, numbering, images, section settings and core properties are byte-identical
    to the source; only the language tag changes to the target.
  - A paragraph with "normal **bold** normal *italic*" keeps bold and italic on the translated
    words when the stub returns valid tags. With missing or broken tags it falls back to one run
    with the first run's formatting.
  - A paragraph with a glossary miss has a yellow highlight on all runs; other paragraphs have
    none.
  - A ≥ 40-character paragraph already in the target language is unchanged and not sent to the
    LLM.
  - MD and PDF built for the same job contain the same translated text as the DOCX.
- **Edge cases:** an empty paragraph or one with only an image → skipped; a field (page number,
  TOC) → untouched; nested tables → translated; a hyperlink run → link target kept, text
  translated.
- **Dependencies:** M3, M4, M6.

### M8 — Streamlit UI
- **Deliverable:** `ui.py` with `theme.py`, `i18n.py`, `auth.py` and `.streamlit/config.toml`.
- **Acceptance criteria:**
  - `config.toml` sets port 8560, `baseUrlPath="trns"`, the XSRF protection, the `FOREST` theme,
    and `gatherUsageStats=false`.
  - The layout follows §5.5. All UI strings exist in both DE and EN; a test checks for
    missing keys.
  - The language pair source = target is blocked. An unavailable model shows the `ollama pull`
    hint. A glossary summary is shown before the start.
  - The end-to-end flow works with a stub LLM in Streamlit's `AppTest`: upload, translate, three
    download buttons present, term report shown.
  - "App beenden" is visible only to `ADMIN_USERS` and asks for confirmation. Its handler sends
    SIGTERM to `os.getpid()` (tested with a patched `os.kill`).
  - Results survive a rerun; a new upload clears the old results.
- **Edge cases:** an upload over `MAX_UPLOAD_MB` → message; a double click on "Übersetzen" →
  only one job; the session expires during a job → the temp dir is still cleaned up.
- **Dependencies:** M3–M7.

### M9 — Deployment and landing page integration
- **Deliverable:**
  - `tunnel.sh` (copied from the summarizer, `PORT=8560`).
  - In `docs/deployment.md`: the nginx block pair and the `apps.toml` snippet for the
    orchestrator (applied there by the admin, not by this repo).
- **Acceptance criteria:**
  - `apps.toml` entry: `name = "KI-Übersetzer"`, `hint = "Lokale KI-Übersetzung von Dokumenten
    mit Fachglossar"`, `icon = "🌐"`, `port = 8560`, `url = "https://ai.brenk.com/trns/"`
    (trailing slash). The orchestrator's registry validation accepts it.
  - nginx: `location = /trns { return 308 /trns/; }` and `location /trns/ { proxy_pass
    http://172.16.4.112:8560; … }` with WebSocket headers and `proxy_read_timeout 1000`, exactly
    like `/smrz/`. `nginx -t` passes.
  - Smoke test: `https://ai.brenk.com/trns/_stcore/health` returns 200. The landing page shows
    the app as running, and the Open button leads to the login.
  - Manual end-to-end test on `gemma4:e4b` with a real DE→EN DOCX (5–15 pages, tables, header)
    and a real glossary, both provided by the user in `data/acceptance/` (gitignored). The outputs
    are checked by a human (layout, structure, terms, readability), and the result is recorded in
    IMPLEMENTATION.md.
- **Edge cases:** a long job beyond `proxy_read_timeout` → the WebSocket stays alive through
  progress updates; the app is restarted → the landing page status turns green within one reload.
- **Dependencies:** M8.

### M10 (optional, later) — Scanned PDFs
- OCR path with `deepseek-ocr:3b`, reused from the summarizer's `md_convert.py`. Not part of
  the v1 Definition of Done.

## 7. Decisions (review session 2026-10-08)

| ID | Decision |
|---|---|
| D-1 | DOCX inputs are translated in place (FR-1a, §5.9): body, tables, headers/footers. Footnotes, comments, text boxes and SmartArt are not translated in v1. |
| D-2 | Inline bold/italic/underline go to the model as tags. Fallback: the whole paragraph takes its first run's formatting. |
| D-3 | PDF output with reportlab from the block model. No LibreOffice (license constraint). |
| D-4 | MD and PDF are always built from the block model of the translated text. A rebuilt DOCX (MD/PDF/TXT input) uses Word's default styles. |
| D-5 | Glossary columns are ISO language codes (XLSX or CSV); a template is downloadable. A row with identical source and target means "keep as is". |
| D-6 | Glossary misses are reported, never blocking. In the DOCX the paragraph is highlighted yellow. |
| D-7 | Paragraphs ≥ 40 characters already in the target language are copied unchanged. |
| D-8 | 9 target languages in Latin script; OCR for scanned PDFs deferred to M10. |
| D-9 | One prompt for all three models; only parameters differ. No LangGraph. |
| D-10 | Login as in the summarizer; path `/trns/`; port 8560. "App beenden" only for `ADMIN_USERS` (default "T. Hein"), no automatic restart. |
| D-11 | No stored history; results live only in the session. |
| D-12 | Metadata: title = file name, language = target, author = logged-in user (rebuilt DOCX); in-place DOCX keeps its properties except the language tag. |
| D-13 | Typical input 1–50 pages; long runs are acceptable with progress and cancel. |
| D-14 | The user provides a real DOCX and glossary in `data/acceptance/` before M9. |

## 8. Risks & assumptions

| ID | Risk / assumption | Mitigation / trigger |
|---|---|---|
| R-1 | Small models (`gemma4:e2b`) ignore glossary rules or the `[[n]]` format. | Verification and retry (FR-5), block-by-block fallback; the term report makes misses visible. If the hit rate is < 90 % in the M5 benchmark, mark e2b as "draft quality" in the UI. |
| R-2 | Inflection: German/Polish/Czech target terms appear inflected, so verification gives false negatives. | Suffix tolerance; misses are reported, never silently "fixed". Revisit with lemmatisation only if the report is noisy. |
| R-3 | PDF structure recovery from font sizes is heuristic. | Accept as best effort (non-goal: layout). DOCX/MD are the recommended inputs; the UI says so. |
| R-4 | Throughput: long documents may take > 15 min (about 170 pages: 17 min on `gemma4:e4b`). | Progress, cancel, and benchmark numbers in the UI tooltip. Shared GPU with the summarizer: Ollama queues requests. |
| R-5 | Target languages outside Latin script need other fonts. | Out of scope (§4). The target language list is fixed in code. |
| R-6 | Assumption: the Ollama host has all three models pulled (verified on 2026-10-08 on the dev machine). | Availability check (FR-7). |
| R-7 | Assumption: the app runs on `172.16.4.112` like the other apps, reached only through nginx. | Documented in `docs/deployment.md`. |
| R-8 | Upstream changes to the summarizer theme drift from the copy. | Copy once; note the source commit in THIRD_PARTY_NOTICES/docs. Shared package only if a third app needs it. |

## 9. Definition of done

- [ ] M1–M9 are `done` in IMPLEMENTATION.md, each with its tests listed under "Verified by".
- [ ] Full gate green: ruff, pyright strict, coverage ≥ 85 %, suite ≤ 60 s, offline.
- [ ] All dependencies are permissive (§5.6); bundled font and copied code are recorded in
  THIRD_PARTY_NOTICES.md.
- [ ] The app runs on port 8560 at `https://ai.brenk.com/trns/` and is listed and green on the
  landing page.
- [ ] Manual DE→EN acceptance test passed and recorded: structure identical, all glossary terms
  used or reported, MD/DOCX/PDF open correctly.
- [ ] README quickstart, `docs/architecture.md` and `docs/deployment.md` are up to date.
