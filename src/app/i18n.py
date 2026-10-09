"""UI string catalogue: German is the default, English the alternative (pure).

Only strings a user reads live here; prompts to the model are always English (``prompt.py``).
"""

DEFAULT_LANG = "de"
LANGUAGES = {"de": "Deutsch", "en": "English"}  # GUI languages, in toggle order

# Display names of the translation languages.
LANGUAGE_NAMES: dict[str, dict[str, str]] = {
    "de": {"de": "Deutsch", "en": "German"},
    "en": {"de": "Englisch", "en": "English"},
    "fr": {"de": "Französisch", "en": "French"},
    "es": {"de": "Spanisch", "en": "Spanish"},
    "it": {"de": "Italienisch", "en": "Italian"},
    "pt": {"de": "Portugiesisch", "en": "Portuguese"},
    "nl": {"de": "Niederländisch", "en": "Dutch"},
    "pl": {"de": "Polnisch", "en": "Polish"},
    "cs": {"de": "Tschechisch", "en": "Czech"},
}

STRINGS: dict[str, dict[str, str]] = {
    "app_title": {"de": "KI-Übersetzer", "en": "AI Translator"},
    "intro": {
        "de": "Lokale Übersetzung von Dokumenten mit Fachglossar. "
        "Die Daten verlassen das Netzwerk nicht.",
        "en": "Local document translation with a terminology glossary. "
        "Data never leaves the network.",
    },
    # sign-in
    "sign_in_hint": {"de": "Zum Fortfahren anmelden", "en": "Sign in to continue"},
    "username": {"de": "Benutzername", "en": "Username"},
    "password": {"de": "Passwort", "en": "Password"},
    "sign_in": {"de": "Anmelden", "en": "Sign in"},
    "bad_credentials": {
        "de": "Benutzername oder Passwort ist ungültig.",
        "en": "Invalid username or password.",
    },
    "seed_missing": {
        "de": "Keine Start-Passwörter gefunden. Bitte {vars} in .env setzen (siehe .env.example).",
        "en": "No seed passwords found. Set {vars} in .env (see .env.example).",
    },
    "config_error": {
        "de": "Ungültige Konfiguration: {error}",
        "en": "Invalid configuration: {error}",
    },
    # sidebar
    "signed_in_as": {"de": "Angemeldet als **{user}**", "en": "Signed in as **{user}**"},
    "logout": {"de": "Abmelden", "en": "Logout"},
    "advanced_options": {"de": "Erweiterte Optionen", "en": "Advanced options"},
    "vram_status": {"de": "Geladene Modelle (VRAM)", "en": "Loaded models (VRAM)"},
    "vram_model": {"de": "{name}: {gb} GB", "en": "{name}: {gb} GB"},
    "vram_empty": {"de": "Keine Modelle geladen.", "en": "No models loaded."},
    "clear_vram": {"de": "VRAM leeren", "en": "Clear VRAM"},
    "vram_cleared": {"de": "{n} Modell(e) entladen.", "en": "Unloaded {n} model(s)."},
    "exit_app": {"de": "App beenden", "en": "Stop app"},
    "exit_confirm": {
        "de": "Die App für alle Nutzer beenden? Sie startet nicht automatisch neu.",
        "en": "Stop the app for all users? It does not restart automatically.",
    },
    "exit_yes": {"de": "Ja, beenden", "en": "Yes, stop"},
    "exit_no": {"de": "Abbrechen", "en": "Cancel"},
    # settings
    "model_caption": {"de": "MODELL", "en": "MODEL"},
    "model_label": {"de": "Modell", "en": "Model"},
    "speed_quality": {
        "de": "Geschwindigkeit {speed}  Qualität {quality}",
        "en": "Speed {speed}  Quality {quality}",
    },
    "not_installed": {
        "de": "`{tag}` ist nicht installiert. Ausführen: `{hint}`",
        "en": "`{tag}` is not installed. Run: `{hint}`",
    },
    "ollama_down": {
        "de": "Ollama ist nicht erreichbar: {host}",
        "en": "Ollama is not reachable: {host}",
    },
    "target_caption": {"de": "ZIELSPRACHE", "en": "TARGET LANGUAGE"},
    "target_label": {"de": "Zielsprache", "en": "Target language"},
    "document_caption": {"de": "DOKUMENT", "en": "DOCUMENT"},
    "document_label": {"de": "Dokument", "en": "Document"},
    "glossary_caption": {"de": "GLOSSAR (OPTIONAL)", "en": "GLOSSARY (OPTIONAL)"},
    "glossary_label": {"de": "Glossar", "en": "Glossary"},
    "glossary_template": {
        "de": "Glossar-Vorlage herunterladen",
        "en": "Download glossary template",
    },
    "source_caption": {"de": "QUELLSPRACHE", "en": "SOURCE LANGUAGE"},
    "source_label": {"de": "Quellsprache", "en": "Source language"},
    "source_detected": {
        "de": "Erkannte Quellsprache: **{name}**",
        "en": "Detected source language: **{name}**",
    },
    "source_unknown": {
        "de": "Quellsprache nicht erkannt; bitte prüfen.",
        "en": "Source language not detected; please check.",
    },
    "glossary_summary": {
        "de": "Glossar: **{n}** Einträge für {src} → {tgt}",
        "en": "Glossary: **{n}** entries for {src} → {tgt}",
    },
    "glossary_empty": {
        "de": "Das Glossar enthält keine verwendbaren Einträge für dieses Sprachpaar.",
        "en": "The glossary has no usable entries for this language pair.",
    },
    "glossary_issues": {
        "de": "Nicht verwendbare Zeilen ({n})",
        "en": "Rows that cannot be used ({n})",
    },
    "glossary_issue_row": {
        "de": "Zeile {row}: {kind} ({detail})",
        "en": "Row {row}: {kind} ({detail})",
    },
    "issue_empty_cell": {"de": "leere Zelle", "en": "empty cell"},
    "issue_duplicate": {"de": "doppelt", "en": "duplicate"},
    "issue_conflict": {"de": "widersprüchlich", "en": "conflict"},
    "same_language": {
        "de": "Quell- und Zielsprache müssen verschieden sein.",
        "en": "Source and target language must differ.",
    },
    "too_large": {
        "de": "Die Datei ist größer als {mb} MB.",
        "en": "The file is larger than {mb} MB.",
    },
    "read_error": {"de": "Datei nicht lesbar: {error}", "en": "Cannot read file: {error}"},
    # job
    "translate_button": {"de": "Übersetzen", "en": "Translate"},
    "cancel_button": {"de": "Abbrechen", "en": "Cancel"},
    "cancelling": {
        "de": "Wird nach dem aktuellen Abschnitt beendet …",
        "en": "Stopping after the current section …",
    },
    "preparing": {"de": "Wird vorbereitet …", "en": "Preparing …"},
    "progress": {"de": "Abschnitt {done} von {total}", "en": "Section {done} of {total}"},
    "job_failed": {
        "de": "Übersetzung fehlgeschlagen: {error}",
        "en": "Translation failed: {error}",
    },
    # result
    "result_heading": {"de": "Übersetzung", "en": "Translation"},
    "cancelled_notice": {
        "de": "Abgebrochen: Das Ergebnis ist unvollständig.",
        "en": "Cancelled: the result is incomplete.",
    },
    "download_md": {"de": "Markdown (.md)", "en": "Markdown (.md)"},
    "download_docx": {"de": "Word (.docx)", "en": "Word (.docx)"},
    "download_pdf": {"de": "PDF (.pdf)", "en": "PDF (.pdf)"},
    "term_report": {"de": "Terminologiebericht", "en": "Term report"},
    "term_counts": {
        "de": "Glossartreffer: **{hits}**, davon eingehalten: **{enforced}**",
        "en": "Glossary hits: **{hits}**, enforced: **{enforced}**",
    },
    "term_misses": {"de": "Nicht eingehaltene Begriffe", "en": "Terms not enforced"},
    "col_excerpt": {"de": "Textstelle", "en": "Excerpt"},
    "col_source": {"de": "Quellbegriff", "en": "Source term"},
    "col_expected": {"de": "Erwartet", "en": "Expected"},
    "failed_blocks": {
        "de": "{n} Abschnitt(e) blieben in der Quellsprache.",
        "en": "{n} section(s) stayed in the source language.",
    },
    "untouched_features": {
        "de": "Nicht übersetzt (bleibt in der Quellsprache): {features}",
        "en": "Not translated (stays in the source language): {features}",
    },
    "feature_footnotes": {"de": "Fußnoten", "en": "footnotes"},
    "feature_endnotes": {"de": "Endnoten", "en": "endnotes"},
    "feature_comments": {"de": "Kommentare", "en": "comments"},
    "feature_text boxes": {"de": "Textfelder", "en": "text boxes"},
    "download_report": {"de": "Bericht (CSV)", "en": "Report (CSV)"},
}


def t(key: str, lang: str, **fmt: object) -> str:
    """The string for ``key`` in ``lang`` (German fallback), with ``str.format`` applied."""
    entry = STRINGS[key]
    return entry.get(lang, entry[DEFAULT_LANG]).format(**fmt)


def language_name(code: str, lang: str) -> str:
    return LANGUAGE_NAMES[code][lang if lang in LANGUAGES else DEFAULT_LANG]
