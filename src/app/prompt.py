"""Prompt construction (pure). Prompts to the model are always in English."""

from collections.abc import Sequence

from app.glossary import Entry

STRICT_MARKER = "IMPORTANT: the previous answer was rejected."
BODY_MARKER = "Text to translate:\n"

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

_RULES = """\
Rules:
- Return every line with its original ID marker, for example "[[1]] ...". Output nothing else: \
no comments, no preamble.
- Keep Markdown inline formatting (**bold**, *italic*, [links](...)) in place.
- Keep tags such as <b>…</b>, <i>…</i>, <u>…</u> and <a1>…</a1> in place around the matching \
translated words.
- Keep tokens like ⟦P1⟧ unchanged and inside the translated line.
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
    parts = [
        f"You are a professional translator. Translate the numbered lines from {src} to {tgt}."
    ]
    parts.append(_RULES)
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
    parts.append(BODY_MARKER + body)
    return "\n\n".join(parts)


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
