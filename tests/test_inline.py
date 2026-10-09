from app.inline import Run, parse_inline


def test_plain_text_is_one_run() -> None:
    assert parse_inline("Hallo Welt") == [Run("Hallo Welt")]


def test_bold_italic_and_nesting() -> None:
    runs = parse_inline("a **b *c*** d")
    assert [(r.text, r.bold, r.italic) for r in runs] == [
        ("a ", False, False),
        ("b ", True, False),
        ("c", True, True),
        (" d", False, False),
    ]


def test_code_link_and_escape() -> None:
    runs = parse_inline(r"`x` [Seite](https://a.example) \*kein\*")
    assert runs[0] == Run("x", code=True)
    assert runs[2] == Run("Seite", href="https://a.example")
    assert "".join(r.text for r in runs[3:]) == " *kein*"


def test_breaks_and_image() -> None:
    runs = parse_inline("eins\nzwei  \ndrei ![Logo](l.png)")
    assert "".join(r.text for r in runs) == "eins zwei\ndrei [Bild: Logo]"
