# IMPLEMENTATION

Current state of the code, and the only place for phase status. What and why: [PRD.md](PRD.md).
Rules: [AGENTS.md](AGENTS.md). Design: [docs/architecture.md](docs/architecture.md).

## 1. Run and verify

| Task | Command |
|---|---|
| Install (once per clone) | `uv sync && uv run pre-commit install` |
| Run the app | `uv run streamlit run src/app/ui.py` (port 8560, path `/trns/`) |
| Tests (fast loop) | `uv run pytest` or `uv run pytest tests/test_core.py` |
| Full gate | `uv run pre-commit run --all-files` |

## 2. Phase status

One row per PRD milestone. Status: `planned`, `in progress`, `done`.

| Phase | Milestone | Status | Verified by |
|---|---|---|---|
| 0 | Blueprint skeleton (no PRD milestone) | done | full gate green |
| 1 | M1: Document model and Markdown round trip | done | `tests/test_document.py`, full gate green |
| 2 | M2: Glossary | done | `tests/test_glossary.py`, `tests/test_glossary_readers.py`, full gate green |
| 3 | M3: Translation core with fake LLM | done | `tests/test_segment.py`, `tests/test_prompt.py`, `tests/test_translate.py`, full gate green |
| 4 | M4: Input readers | done | `tests/test_readers_docx.py`, `tests/test_readers_pdf.py`, full gate green |
| 5 | M5: Ollama adapter and model registry | done | `tests/test_models.py`, `tests/test_llm_ollama.py`, `tests/test_benchmark.py`, [docs/benchmark.md](docs/benchmark.md), full gate green |
| 6 | M6: Output writers | done | `tests/test_writers.py`, `tests/test_inline.py`, full gate green |
| 7 | M7: DOCX in-place translation | done | `tests/test_docx_inplace.py`, `tests/test_run_tags.py`, `tests/test_lang.py`, full gate green |
| 8 | M8: Streamlit UI | done | `tests/test_ui.py`, `tests/test_pipeline.py`, `tests/test_runner.py`, `tests/test_config_auth.py`, full gate green |
| 9 | M9: Deployment and landing page integration | in progress | `tests/test_deployment.py`, [docs/deployment.md](docs/deployment.md); open: server steps and acceptance run (section 4) |
| 10 | M10: Scanned PDFs (optional, not in v1) | planned | |

## 3. Module map

| Module | Responsibility |
|---|---|
| `src/app/document.py` | Block model, Markdown parse/write, `same_structure` (M1). |
| `src/app/glossary.py` | Glossary entries per language pair, match, verify, template (M2). |
| `src/app/readers.py` | Input adapters: glossary rows (M2), `read_document` dispatch for docx/md/txt/pdf (M4). |
| `src/app/docx_reader.py` | DOCX body to blocks (python-docx). |
| `src/app/pdf_reader.py` | Text-layer PDF to blocks (pdfplumber), heading levels from font size. |
| `src/app/segment.py` | Units, packing, protected spans, `[[n]]` wire format (M3). |
| `src/app/prompt.py` | English prompt builder (M3). |
| `src/app/translate.py` | `translate_document` with injected `llm`, retries, progress, cancel (M3). |
| `src/app/models.py` | Model registry, default resolution, availability marks (M5). |
| `src/app/llm_ollama.py` | Ollama adapter: chat (`think=False`), tags, unload, typed unreachable error (M5). |
| `src/app/benchmark.py` | Synthetic fixture and benchmark runner (`python -m app.benchmark`). |
| `src/app/inline.py` | Markdown inline text to formatted runs (shared by the writers, M6). |
| `src/app/writers.py` | Output entry point: `write_md`, file names, MIME types; re-exports the writers (M6). |
| `src/app/docx_writer.py` | `Document` to DOCX (python-docx, default template). |
| `src/app/pdf_writer.py` | `Document` to PDF (reportlab, DejaVu fonts in `src/app/fonts/`). |
| `src/app/run_tags.py` | Run formatting as `<b>/<i>/<u>/<aN>` tags: encode, validate, decode (M7). |
| `src/app/lang.py` | `is_in_language`: langdetect check for the skip rule (M7). |
| `src/app/docx_inplace.py` | `translate_docx`: translate a DOCX in place (M7). |
| `src/app/pipeline.py` | `run_job` (file bytes to md/docx/pdf), `inspect_upload`, `report_csv` (M8). |
| `src/app/runner.py` | `JobHandle`: background thread with progress and cancel (M8). |
| `src/app/config.py` | `load_config`: environment keys to `Config` (M8). |
| `src/app/auth.py` | bcrypt user store in `data/users.json` (M8). |
| `src/app/i18n.py` | DE/EN string catalogue, `t()` (M8). |
| `src/app/theme.py` | FOREST palette and CSS, copied from the summarizer (M8). |
| `src/app/ui.py` | Streamlit entry point: widgets wired to the pipeline (M8). |
| `tunnel.sh` | Starts the app and a Cloudflare quick tunnel on port 8560 (copied from the summarizer). |
| `.streamlit/config.toml` | Port 8560, `baseUrlPath=trns`, XSRF, theme, no usage stats. |
| `src/app/core.py` | Example of pure logic (`slugify`). Replace it with your own. |
| `tests/conftest.py` | Shared fixtures; blocks network access in all tests. |
| `tests/test_code_rules.py` | Enforces functions ≤ 50 lines in `src/`, `tests/`, `.claude/hooks/`. |
| `tests/test_docs.py` | Enforces doc size limits and resolvable local links. |
| `.claude/hooks/format_on_edit.py` | PostToolUse hook: ruff-formats each `.py` file Claude edits. |
| `.claude/hooks/stop_gate.py` | Stop hook: runs the gate if `.py` files changed; blocks the stop on failure. |

## 4. Open issues

- M9 needs the admin on the server: add the `apps.toml` entry and nginx block from
  [docs/deployment.md](docs/deployment.md), run `nginx -t`, and do the smoke test. Not verified
  here: `nginx -t` (no nginx on the dev machine).
- M9 acceptance run: the user provides a real DOCX and glossary in `data/acceptance/` (D-14); the
  human check and its result are recorded here afterwards.
- Real-model check (2026-10-09, local Ollama, `gemma4:e4b`): a synthetic DOCX (heading, bold and
  italic runs, bullet, table, header) with a 3-entry glossary took 21 s through `run_job`. Body,
  table and header were translated, bold/italic stayed on the right words, `5 mSv` was kept,
  3 of 4 glossary hits were enforced. The miss ("Freigabe" in the heading, still untranslated
  after the strict retry) was reported and highlighted as designed. The Streamlit UI itself has
  only run against a stubbed Ollama, and no real document has been checked yet.
- Language consistency (user report: a document came back about 70 % in English): not
  reproduced with the user's file on `gemma4:e2b`/`e4b`. Likely cause, fixed: an echoed answer
  was passed on as context and primed the next segments to echo too. Before/after numbers in
  [docs/benchmark.md](docs/benchmark.md). PRD M3 still says duplicated IDs make an answer
  unusable; adjacent duplicates are now accepted (see docs/architecture.md); the PRD wording
  needs the user's approval to change.
