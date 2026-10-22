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


def test_padded_table_keeps_year_header_and_relevant_amount_rows():
    # Live: cutting a padded segment table at its limit kept only headers.
    from app.assistant.excerpts import focus_terms, table_rows

    pad = " " * 60
    table = "\n".join(
        [
            f"|{pad}|{pad}| 2023 |{pad}| 2024 |",
            "|---|---|---|---|---|",
            f"| Operating Income (Loss) |{pad}|{pad}|{pad}|{pad}|",
            f"| North America |{pad}| 14,877 |{pad}| 24,967 |",
            f"| International |{pad}| (2,656) |{pad}| 3,792 |",
            f"| AWS |{pad}| 24,631 |{pad}| 39,834 |",
            f"| Consolidated |{pad}| 36,852 |{pad}| 68,593 |",
        ]
    )
    rows = table_rows(table, 900, focus_terms("AWS operating income North America"))
    assert all(row in table for row in rows)
    assert [row.split("|")[1].strip() for row in rows] == [
        "",
        "North America",
        "AWS",
    ]


def test_table_units_row_is_kept_with_the_year_headers():
    # Live: NVIDIA's "Total revenue 130,497" row was shown without the table's
    # "(In millions)" row, so the correct answer failed the quoted-scale check.
    from app.assistant.excerpts import focus_terms, table_rows

    pad = " " * 60
    table = "\n".join(
        [
            f"|{pad}| Year Ended |{pad}|",
            f"|{pad}| Jan 26, 2025 |{pad}| Jan 28, 2024 |",
            f"| Geographic Revenue: |{pad}| (In millions) |{pad}|",
            f"| United States |{pad}| $ 61,257 |{pad}| $ 26,966 |",
            f"| Total revenue |{pad}| $ 130,497 |{pad}| $ 60,922 |",
        ]
    )
    rows = table_rows(table, 900, focus_terms("total revenue"))
    assert any("(In millions)" in row for row in rows)
    assert any("130,497" in row for row in rows)
    assert not any("61,257" in row for row in rows)
