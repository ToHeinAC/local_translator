"""Language detection for the skip-if-already-translated rule (langdetect, deterministic)."""

# langdetect ships no type information.
# pyright: reportUnknownVariableType=false, reportUnknownMemberType=false
# pyright: reportMissingTypeStubs=false, reportUnknownArgumentType=false

from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

DetectorFactory.seed = 0
MIN_CHARS = 40


def is_in_language(text: str, lang: str) -> bool:
    """True if ``text`` has at least 40 characters and is detected as ``lang``."""
    if len(text) < MIN_CHARS:
        return False
    try:
        return str(detect(text)).split("-")[0] == lang
    except LangDetectException:
        return False
