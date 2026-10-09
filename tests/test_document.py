import pytest

from app.document import (
    Block,
    EmptyDocumentError,
    Kind,
    parse_markdown,
    same_structure,
    write_markdown,
)

FIXTURE = """\
# Titel

Ein Absatz mit **fett**, *kursiv*, [Link](https://example.com) und `code`.

## Abschnitt

### Unterabschnitt

#### Detail

- Punkt eins
  - Unterpunkt
- Punkt zwei

1. Erstens
2. Zweitens
   - gemischt

| Name | Wert |
|---|---|
| a \\| b | 2 |
| c | 3 |

> Ein Zitat

```python
print("hi")
```
"""


def test_round_trip_canonical_fixture() -> None:
    assert write_markdown(parse_markdown(FIXTURE)) == FIXTURE


def test_non_canonical_input_is_normalised() -> None:
    src = "Titel\n=====\n\n* a\n* b\n\n3. x\n7. y\n"
    assert write_markdown(parse_markdown(src)) == "# Titel\n\n- a\n- b\n\n1. x\n2. y\n"


def test_block_kinds_and_flags() -> None:
    doc = parse_markdown("## H\n\n- a\n  - b\n\n```sh\nls\n```\n\n<div>x</div>\n")
    assert [b.kind for b in doc] == [
        Kind.HEADING,
        Kind.LIST_ITEM,
        Kind.LIST_ITEM,
        Kind.CODE,
        Kind.PARAGRAPH,
    ]
    assert doc[0].level == 2
    assert [b.depth for b in doc[1:3]] == [0, 1]
    assert [b.translate for b in doc] == [True, True, True, False, False]
    assert doc[4].text == "<div>x</div>"


def test_table_rows_keep_inline_text() -> None:
    (table,) = parse_markdown("| a | **b** |\n|---|---|\n| 1 | 2 |\n")
    assert table.kind is Kind.TABLE
    assert table.rows == (("a", "**b**"), ("1", "2"))


def test_list_continuation_and_quote_flattening() -> None:
    doc = parse_markdown("- a\n\n  more\n\n> q1\n>\n> q2\n>> deep\n")
    assert [(b.kind, b.text) for b in doc] == [
        (Kind.LIST_ITEM, "a"),
        (Kind.PARAGRAPH, "more"),
        (Kind.QUOTE, "q1"),
        (Kind.QUOTE, "q2"),
        (Kind.QUOTE, "deep"),
    ]


def test_image_only_paragraph_is_untranslated_placeholder() -> None:
    doc = parse_markdown("Text\n\n![Logo](logo.png)\n")
    assert doc[1].kind is Kind.IMAGE_PLACEHOLDER
    assert doc[1].text == "[Bild: Logo]"
    assert not doc[1].translate


@pytest.mark.parametrize("src", ["", "  \n\n", "![a](a.png)\n", "---\n"])
def test_empty_document_raises(src: str) -> None:
    with pytest.raises(EmptyDocumentError, match="Dokument enthält keinen Text"):
        parse_markdown(src)


def test_same_structure_true_for_identical_and_retranslated() -> None:
    a = parse_markdown(FIXTURE)
    b = parse_markdown(FIXTURE.replace("Punkt eins", "Item one"))
    assert same_structure(a, a)
    assert same_structure(a, b)


@pytest.mark.parametrize(
    "changed",
    [
        FIXTURE.replace("## Abschnitt", "### Abschnitt"),
        FIXTURE.replace("- Punkt zwei\n", ""),
        FIXTURE.replace("| c | 3 |\n", ""),
        FIXTURE.replace("> Ein Zitat", "Ein Zitat"),
        FIXTURE.replace("  - Unterpunkt", "- Unterpunkt"),
    ],
    ids=["level", "missing-item", "table-shape", "kind", "depth"],
)
def test_same_structure_false_on_change(changed: str) -> None:
    assert not same_structure(parse_markdown(FIXTURE), parse_markdown(changed))


def test_same_structure_false_on_different_length() -> None:
    a = [Block(Kind.PARAGRAPH, "x")]
    assert not same_structure(a, [*a, *a])


def test_code_fence_grows_when_content_has_backticks() -> None:
    doc = [Block(Kind.CODE, "```\nx\n```", info="md", translate=False)]
    assert parse_markdown(write_markdown(doc))[0].text == "```\nx\n```"
