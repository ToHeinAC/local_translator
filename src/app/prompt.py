"""Prompt construction (pure). Prompts to the model are always in English."""

from collections.abc import Sequence

from app.glossary import Entry
from app.run_tags import has_tags

STRICT_MARKER = "IMPORTANT: the previous answer was rejected."
BODY_MARKER = "Text to translate:\n"
SYSTEM_SPLIT = "\n\n<<<END OF SYSTEM>>>\n\n"  # llm_ollama sends the part before as system message

_LANGUAGES = {
    "de": "German",
    "en": "English",
    "fr": "French",
    "es": "Spanish",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "pl": "Polish",
    "cs": "Czech",
}
SUPPORTED_LANGUAGES = tuple(_LANGUAGES)

_TAG_RULE = """\
- Keep tags such as <b>…</b>, <i>…</i>, <u>…</u> and <a1>…</a1> in place around the matching \
translated words.
"""
_RULES = """\
Rules:
- Return every line with its original ID marker, exactly once. Output nothing else: no source \
text, no comments, no preamble.
- Keep Markdown inline formatting (**bold**, *italic*, [links](...)) in place.
{tags}- Keep tokens like ⟦P1⟧ unchanged and inside the translated line.
- Do not add, omit or explain anything."""


def build_prompt(
    body: str,
    source_lang: str,
    target_lang: str,
    entries: Sequence[Entry],
    context: tuple[str, str] | None,
    *,
    strict: bool = False,
    missed: Sequence[Entry] = (),
    untranslated: bool = False,
) -> str:
    """Assemble the translation prompt for one segment (``body`` = numbered lines)."""
    src = _LANGUAGES.get(source_lang, source_lang)
    tgt = _LANGUAGES.get(target_lang, target_lang)
    parts: list[str] = []
    if entries:
        parts.append(_glossary_section(entries))
    if strict:
        parts.append(_strict_section(missed))
        if untranslated:
            parts.append(f"Translate every line completely into {tgt}; leave nothing in {src}.")
    if context:
        parts.append(
            f"Context (already translated, do not repeat it):\nSource: {context[0]}\n"
            f"Translation: {context[1]}"
        )
    reminder = f"Translate every numbered line into {tgt}. Answer only in {tgt}.\n"
    parts.append(reminder + BODY_MARKER + body)
    return _system(src, tgt, has_tags(body)) + SYSTEM_SPLIT + "\n\n".join(parts)


def _system(src: str, tgt: str, tags: bool) -> str:
    rules = _RULES.format(tags=_TAG_RULE if tags else "")
    return (
        f"You are a professional translator. Translate the numbered lines from {src} to {tgt}."
        f"\n\n{rules}\n\nAnswer format:\n[[1]] <line 1 in {tgt}>\n[[2]] <line 2 in {tgt}>"
    )


def _glossary_section(entries: Sequence[Entry]) -> str:
    lines = ["Mandatory terminology. Use exactly these target terms:"]
    for e in entries:
        note = f" (note: {e.note})" if e.note else ""
        lines.append(f'- "{e.source}" -> "{e.target}"{note}')
    return "\n".join(lines)


def _strict_section(missed: Sequence[Entry]) -> str:
    text = f"{STRICT_MARKER} Follow the ID, token and terminology rules exactly."
    if missed:
        listed = "; ".join(f'"{e.target}" for "{e.source}"' for e in missed)
        text += f" Missing: {listed}"
    return text
