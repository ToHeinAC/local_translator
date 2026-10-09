"""Manual benchmark (PRD M5 / NFR-6): synthetic DE document, wall-clock time and glossary hit rate.

Run with ``uv run python -m app.benchmark [model ...]`` against a real Ollama host.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from app.document import Block, Document, Kind
from app.glossary import Glossary, build_glossary
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


def run_benchmark(
    model: str,
    llm: Llm,
    doc: Document,
    glossary: Glossary,
    clock: Callable[[], float] = time.perf_counter,
) -> BenchResult:
    """Translate ``doc`` once and report wall-clock time and glossary enforcement."""
    segments = len(pack(plan_units(doc, _SEGMENT_CHARS), _SEGMENT_CHARS))
    start = clock()
    result = translate_document(doc, glossary, llm, segment_chars=_SEGMENT_CHARS)
    seconds = clock() - start
    return BenchResult(
        model, seconds, segments, result.hits, len(result.misses), len(result.failed)
    )


def format_table(results: list[BenchResult]) -> str:
    lines = [
        "| Model | Time | Segments | Glossary hits | Missed | Hit rate | Failed |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r.model} | {r.seconds:.0f} s | {r.segments} | {r.hits} | {r.misses} "
            f"| {r.hit_rate:.0%} | {r.failed} |"
        )
    return "\n".join(lines)


def main(argv: list[str]) -> None:  # pragma: no cover - needs a live Ollama host
    import os
    import sys

    from app.llm_ollama import installed_tags, make_client, make_llm, unload_all
    from app.models import MODELS

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
    client = make_client(host, float(os.getenv("LLM_TIMEOUT_S", "600")))
    tags = argv or [m.tag for m in MODELS]
    doc, glossary = make_fixture()
    have = installed_tags(client, host)
    results: list[BenchResult] = []
    for tag in (t for t in tags if t in have):
        unload_all(client)
        print(f"running {tag} ...", file=sys.stderr, flush=True)
        results.append(run_benchmark(tag, make_llm(client, tag, host), doc, glossary))
    print(format_table(results))


if __name__ == "__main__":  # pragma: no cover
    import sys

    main(sys.argv[1:])
