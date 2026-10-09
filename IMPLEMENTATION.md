# IMPLEMENTATION

Current state of the code, and the only place for phase status. What and why: [PRD.md](PRD.md).
Rules: [AGENTS.md](AGENTS.md). Design: [docs/architecture.md](docs/architecture.md).

## 1. Run and verify

| Task | Command |
|---|---|
| Install (once per clone) | `uv sync && uv run pre-commit install` |
| Tests (fast loop) | `uv run pytest` or `uv run pytest tests/test_core.py` |
| Full gate | `uv run pre-commit run --all-files` |

## 2. Phase status

One row per PRD milestone. Status: `planned`, `in progress`, `done`.

| Phase | Milestone | Status | Verified by |
|---|---|---|---|
| 0 | Blueprint skeleton (no PRD milestone) | done | full gate green |
| 1 | M1: Document model and Markdown round trip | done | `tests/test_document.py`, full gate green |
| 2 | M2: Glossary | done | `tests/test_glossary.py`, `tests/test_glossary_readers.py`, full gate green |
| 3 | M3: Translation core with fake LLM | planned | |
| 4 | M4: Input readers | planned | |
| 5 | M5: Ollama adapter and model registry | planned | |
| 6 | M6: Output writers | planned | |
| 7 | M7: DOCX in-place translation | planned | |
| 8 | M8: Streamlit UI | planned | |
| 9 | M9: Deployment and landing page integration | planned | |
| 10 | M10: Scanned PDFs (optional, not in v1) | planned | |

## 3. Module map

| Module | Responsibility |
|---|---|
| `src/app/document.py` | Block model, Markdown parse/write, `same_structure` (M1). |
| `src/app/glossary.py` | Glossary entries per language pair, match, verify, template (M2). |
| `src/app/readers.py` | Input adapters; so far csv/tsv/xlsx/md glossary rows (M2). |
| `src/app/core.py` | Example of pure logic (`slugify`). Replace it with your own. |
| `tests/conftest.py` | Shared fixtures; blocks network access in all tests. |
| `tests/test_code_rules.py` | Enforces functions ≤ 50 lines in `src/`, `tests/`, `.claude/hooks/`. |
| `tests/test_docs.py` | Enforces doc size limits and resolvable local links. |
| `.claude/hooks/format_on_edit.py` | PostToolUse hook: ruff-formats each `.py` file Claude edits. |
| `.claude/hooks/stop_gate.py` | Stop hook: runs the gate if `.py` files changed; blocks the stop on failure. |

## 4. Open issues

- None.
