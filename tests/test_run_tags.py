from collections import Counter

from app.run_tags import Piece, decode, encode, strip_tags, tag_counts

PIECES = [
    Piece("normal "),
    Piece("bold", bold=True),
    Piece(" and "),
    Piece("both", bold=True, italic=True),
    Piece("Link", link=1),
    Piece(" tail", underline=True, link=1),
]


def test_encode_nests_links_outside_formats() -> None:
    assert encode(PIECES) == "normal <b>bold</b> and <b><i>both</i></b><a1>Link<u> tail</u></a1>"


def test_decode_is_inverse_of_encode() -> None:
    text = encode(PIECES)
    back = decode(text, tag_counts(text))
    assert back is not None
    assert encode(back) == text
    assert [p.link for p in back] == [0, 0, 0, 0, 1, 1]


def test_decode_rejects_broken_or_missing_tags() -> None:
    expected = Counter({"b": 1})
    assert decode("a <b>b</b>", expected) is not None
    assert decode("a b", expected) is None  # tag dropped
    assert decode("a <b>b", expected) is None  # unclosed
    assert decode("a <b>b</i>", expected) is None  # mismatched
    assert decode("a <b>b</b> <i>c</i>", expected) is None  # invented tag


def test_literal_angle_brackets_are_plain_text() -> None:
    assert decode("x < 5 und y > 3", Counter()) == [Piece("x < 5 und y > 3")]


def test_strip_tags() -> None:
    assert strip_tags("a <b>b</b> <a2>c</a2>") == "a b c"
