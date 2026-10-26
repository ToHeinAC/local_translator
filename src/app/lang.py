"""Language detection for the skip-if-already-translated rule (langdetect, deterministic)."""

# langdetect ships no type information.
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false

import re

from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

from app.prompt import SUPPORTED_LANGUAGES
from app.run_tags import strip_tags

DetectorFactory.seed = 0
MIN_CHARS = 40
_SENTENCE = re.compile(r"(?<=[.!?])\s+|\n+")


def is_in_language(text: str, lang: str) -> bool:
    """True if ``text`` has at least 40 characters and is detected as ``lang``."""
    if len(text) < MIN_CHARS:
        return False
    try:
        return str(detect(text)).split("-")[0] == lang
    except LangDetectException:
        return False


def detect_language(text: str) -> str | None:
    """The detected code if it is one of the supported languages, else None."""
    try:
        code = str(detect(text[:2000])).split("-")[0]
    except LangDetectException:
        return None
    return code if code in SUPPORTED_LANGUAGES else None


def looks_untranslated(source: str, output: str, source_lang: str, target_lang: str) -> bool:
    """True if ``output`` still reads as the source language (source of 40+ characters only)."""
    if source_lang == target_lang or len(source) < MIN_CHARS:
        return False
    return " ".join(output.split()) == " ".join(source.split()) or (
        detect_language(output) == source_lang
    )


def has_source_sentence(text: str, source_lang: str) -> bool:
    """True if any sentence of 40+ characters in ``text`` is detected as ``source_lang``."""
    sentences = _SENTENCE.split(strip_tags(text))
    return any(len(s) >= MIN_CHARS and detect_language(s) == source_lang for s in sentences)
