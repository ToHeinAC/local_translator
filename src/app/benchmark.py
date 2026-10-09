"""Manual benchmark (PRD M5 / NFR-6): time, calls, glossary hit rate and untranslated texts.

Run against a real Ollama host:
``uv run python -m app.benchmark [model ...] [--file doc.md --source en --target de]``.
Without ``--file`` the synthetic DE→EN fixture is used.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from app.document import Block, Document, Kind
from app.glossary import Glossary, build_glossary
from app.lang import MIN_CHARS, detect_language
from app.readers import read_document
from app.segment import pack, plan_units
from app.translate import Llm, translate_document

TERMS = [
    ("Abklingbecken", "spent fuel pool"),
    ("Freigabe", "clearance"),
    ("Brennelement", "fuel assembly"),
    ("Strahlenschutz", "radiation protection"),
    ("Kontrollbereich", "controlled area"),
    ("Ortsdosisleistung", "ambient dose rate"),
    ("Rückbau", "decommissioning"),
    ("Dekontamination", "decontamination"),
    ("Genehmigungsbehörde", "licensing authority"),
    ("Aktivitätskonzentration", "activity concentration"),
]
_TEMPLATES = [
    "Die {a} wird nach Abschluss der {b} von der zuständigen Stelle geprüft und dokumentiert.",
    "Bei der {a} ist die {b} jederzeit nachvollziehbar zu belegen, sofern keine Ausnahme gilt.",
    "Für die {a} gelten die Vorgaben zur {b}, die im Betriebshandbuch näher beschrieben sind.",
    "Ohne vorherige {a} darf die {b} nicht begonnen werden; Abweichungen sind zu melden.",
    "Die Ergebnisse der {a} fließen in die Bewertung der {b} ein und werden jährlich überprüft.",
]
_PARAGRAPHS_PER_PAGE = 6
_SENTENCES_PER_PARAGRAPH = 5
_SEGMENT_CHARS = 3000


@dataclass(frozen=True)
class BenchResult:
    model: str
    seconds: float
    segments: int
    hits: int
    misses: int
    failed: int
    calls: int  # LLM requests, including retries and fallbacks
    untranslated: int  # texts of 40+ characters still detected as the source language

    @property
    def hit_rate(self) -> float:
        return (self.hits - self.misses) / self.hits if self.hits else 1.0


def make_fixture(pages: int = 10) -> tuple[Document, Glossary]:
    """A deterministic German document (about 2,700 characters per page) and its glossary."""
    doc: Document = []
    counter = 0
    for page in range(1, pages + 1):
        doc.append(Block(Kind.HEADING, f"Abschnitt {page}: Betrieb und Überwachung", level=1))
        for _ in range(_PARAGRAPHS_PER_PAGE):
            sentences: list[str] = []
            for _ in range(_SENTENCES_PER_PARAGRAPH):
                a, b = TERMS[counter % len(TERMS)][0], TERMS[(counter * 3 + 1) % len(TERMS)][0]
                sentences.append(_TEMPLATES[counter % len(_TEMPLATES)].format(a=a, b=b))
                counter += 1
            doc.append(Block(Kind.PARAGRAPH, " ".join(sentences)))
        if page % 3 == 0:
            rows = tuple((t[0], "Wert", "Hinweis zur Prüfung") for t in TERMS[:3])
            doc.append(Block(Kind.TABLE, rows=(("Begriff", "Wert", "Bemerkung"), *rows)))
    glossary = build_glossary([["de", "en"], *[[de, en] for de, en in TERMS]], "de", "en")
    return doc, glossary.glossary


def load_document(path: str, source: str, target: str) -> tuple[Document, Glossary]:
    """A real document for the benchmark, with an empty glossary for the language pair."""
    return read_document(path, Path(path).read_bytes()), Glossary(source, target, ())


def run_benchmark(
    model: str,
    llm: Llm,
    doc: Document,
    glossary: Glossary,
    clock: Callable[[], float] = time.perf_counter,
    segment_chars: int = _SEGMENT_CHARS,
) -> BenchResult:
    """Translate ``doc`` once and report time, calls, glossary enforcement and leftovers."""
    calls: list[int] = []

    def counted(prompt: str) -> str:
        calls.append(1)
        return llm(prompt)

    segments = len(pack(plan_units(doc, segment_chars), segment_chars))
    start = clock()
    result = translate_document(doc, glossary, counted, segment_chars=segment_chars)
    seconds = clock() - start
    left = _untranslated(result.document, glossary.source_lang)
    misses, failed = len(result.misses), len(result.failed)
    return BenchResult(model, seconds, segments, result.hits, misses, failed, len(calls), left)


def _untranslated(doc: Document, source: str) -> int:
    texts = [b.text for b in doc if b.translate] + [c for b in doc for r in b.rows for c in r]
    return sum(1 for t in texts if len(t) >= MIN_CHARS and detect_language(t) == source)


def format_table(results: list[BenchResult]) -> str:
    lines = [
        "| Model | Time | Segments | Calls | Glossary hits | Missed | Hit rate | Failed "
        "| Untranslated |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.model} | {r.seconds:.0f} s | {r.segments} | {r.calls} | {r.hits} "
            f"| {r.misses} | {r.hit_rate:.0%} | {r.failed} | {r.untranslated} |"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> None:  # pragma: no cover - needs a live Ollama host
    import argparse
    import os
    import sys

    from app.llm_ollama import installed_tags, make_client, make_llm, unload_all
    from app.models import MODELS

    parser = argparse.ArgumentParser(prog="python -m app.benchmark")
    parser.add_argument("models", nargs="*", default=[m.tag for m in MODELS])
    parser.add_argument("--file", help="real document instead of the synthetic fixture")
    parser.add_argument("--source", default="en")
    parser.add_argument("--target", default="de")
    parser.add_argument("--segment-chars", type=int, default=_SEGMENT_CHARS)
    args = parser.parse_args(argv)
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    client = make_client(host, float(os.getenv("LLM_TIMEOUT_S", "600")))
    doc, glossary = (
        load_document(args.file, args.source, args.target) if args.file else make_fixture()
    )
    have = {t.lower() for t in installed_tags(client, host)}
    results: list[BenchResult] = []
    for tag in (t for t in args.models if t.lower() in have):
        unload_all(client)
        print(f"running {tag} ...", file=sys.stderr, flush=True)
        llm = make_llm(client, tag, host)
        results.append(run_benchmark(tag, llm, doc, glossary, segment_chars=args.segment_chars))
    print(format_table(results))


if __name__ == "__main__":  # pragma: no cover
    import sys

    main(sys.argv[1:])
