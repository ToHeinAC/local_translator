from app.document import Block, Kind
from app.segment import (
    Unit,
    clean_output,
    decode_segment,
    encode_segment,
    pack,
    plan_units,
    protect,
    restore,
    split_sentences,
)


def _units(*texts: str) -> list[Unit]:
    return [Unit(i, i, None, 0, t) for i, t in enumerate(texts)]


def test_plan_units_skips_untranslatable_and_splits_tables() -> None:
    doc = [
        Block(Kind.HEADING, "Titel", level=1),
        Block(Kind.CODE, "print('x')", translate=False),
        Block(Kind.PARAGRAPH, "123 456"),
        Block(Kind.TABLE, rows=(("Name", "3"), ("Haus", "Dach"))),
    ]
    units = plan_units(doc, 100)
    assert [(u.block, u.cell, u.text) for u in units] == [
        (0, None, "Titel"),
        (3, (0, 0), "Name"),
        (3, (1, 0), "Haus"),
        (3, (1, 1), "Dach"),
    ]
    assert [u.idx for u in units] == [0, 1, 2, 3]


def test_plan_units_splits_long_block_at_sentences() -> None:
    doc = [Block(Kind.PARAGRAPH, "Erster Satz. Zweiter Satz. Dritter Satz.")]
    units = plan_units(doc, 20)
    assert [u.text for u in units] == ["Erster Satz.", "Zweiter Satz.", "Dritter Satz."]
    assert [u.piece for u in units] == [0, 1, 2]


def test_split_sentences_keeps_overlong_sentence_whole() -> None:
    assert split_sentences("Ein sehr langer Satz ohne Ende", 5) == [
        "Ein sehr langer Satz ohne Ende"
    ]


def test_pack_groups_up_to_limit() -> None:
    segments = pack(_units("aaaa", "bbbb", "cccc"), 8)
    assert [[u.text for u in s] for s in segments] == [["aaaa", "bbbb"], ["cccc"]]


def test_protect_and_restore_round_trip() -> None:
    text = "Siehe `code`, https://a.b/c?x=1, a@b.de, {name} und 5 mm, 1,5 kg, 20 %."
    protected, spans = protect(text, 1)
    assert "https" not in protected
    assert "`code`" not in protected
    assert "{name}" not in protected
    assert protected.count("⟦P") == 7
    assert restore(protected, spans) == text


def test_protect_leaves_plain_words_and_units_inside_words() -> None:
    text = "3 Monate und 5 sec"
    assert protect(text, 1)[0] == text


def test_encode_decode_valid_and_restores_tokens() -> None:
    enc = encode_segment(_units("Siehe `x` hier", "Zwei"))
    assert enc.body.startswith("[[1]] Siehe ⟦P1⟧ hier\n[[2]] Zwei")
    assert decode_segment("[[1]] See ⟦P1⟧ here\n[[2]] Two", enc) == ["See `x` here", "Two"]


def test_decode_strips_preamble_think_and_keeps_multiline() -> None:
    enc = encode_segment(_units("a", "b"))
    raw = "<think>hm\n[[9]] x</think>\nHere is the translation:\n[[1]] A\nmore\n[[2]] B\n"
    assert decode_segment(raw, enc) == ["A\nmore", "B"]


def test_decode_rejects_missing_extra_duplicate_ids_and_missing_token() -> None:
    enc = encode_segment(_units("a `x`", "b"))
    assert decode_segment("[[1]] A ⟦P1⟧", enc) is None
    assert decode_segment("[[1]] A ⟦P1⟧\n[[2]] B\n[[3]] C", enc) is None
    assert decode_segment("[[1]] A ⟦P1⟧\n[[1]] A\n[[2]] B", enc) is None  # last copy lacks ⟦P1⟧
    assert decode_segment("[[1]] A\n[[2]] B", enc) is None
    assert decode_segment("no markers", enc) is None


def test_clean_output_removes_think_tags() -> None:
    assert clean_output("<think>x</think> Hallo ") == "Hallo"


def test_footnote_references_are_protected() -> None:
    protected, spans = protect("Der Bericht[^1] und die Quelle[^note-2] sind belegt.", 1)
    assert protected == "Der Bericht⟦P1⟧ und die Quelle⟦P2⟧ sind belegt."
    assert spans == {"⟦P1⟧": "[^1]", "⟦P2⟧": "[^note-2]"}


def test_bilingual_answer_keeps_the_last_line_per_id() -> None:
    enc = encode_segment(_units("How it works", "Next step"))
    raw = "[[1]] How it works\n[[1]] Wie es funktioniert\n[[2]] Next step\n[[2]] Nächster Schritt"
    assert decode_segment(raw, enc) == ["Wie es funktioniert", "Nächster Schritt"]


def test_ids_out_of_order_or_missing_are_still_rejected() -> None:
    enc = encode_segment(_units("a", "b"))
    assert decode_segment("[[2]] B\n[[1]] A", enc) is None
    assert decode_segment("[[1]] A\n[[1]] A2", enc) is None
