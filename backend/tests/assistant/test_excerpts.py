from app.assistant.excerpts import focus_terms, focused_excerpt


def test_focused_excerpt_keeps_the_focus_sentence_complete_and_citable():
    # Live AI question: windows cut at the character limit turned the matching
    # sentence into an uncitable preview.
    filler = "The Company sells many products in many markets. " * 12
    focus = (
        "The introduction of new and complex technologies, such as artificial "
        "intelligence features, can increase safety risks for users."
    )
    text = filler + focus + " " + filler
    excerpt = focused_excerpt(text, 400, focus_terms("artificial intelligence"))
    assert focus in excerpt
    assert excerpt.endswith(".")
    assert len(excerpt) <= 400


def test_a_sentence_longer_than_the_limit_is_still_truncated():
    sentence = "Artificial intelligence " + "features " * 80 + "matter."
    excerpt = focused_excerpt(sentence, 100, focus_terms("artificial intelligence"))
    assert excerpt == sentence[:100]
