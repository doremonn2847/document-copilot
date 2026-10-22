import pytest

from ingest.pages import assign_pages, printed_page

BREAK = '<div style="page-break-after: always"></div>'


@pytest.mark.parametrize(
    "page_end,number",
    [
        ("... and stock price. Apple Inc. | 2025 Form 10-K | 29", "29"),
        ("... supply availability. 30.", "30"),
        ("... for additional information. 31", "31"),
        ("Table of Contents", None),
    ],
)
def test_printed_page_number_styles(page_end, number):
    assert printed_page(page_end) == number


def filing(*pages: str) -> str:
    return BREAK.join(f"<p>{text}</p>" for text in pages)


SENTENCES = [
    "Net sales increased primarily because of higher sales of iPhone models in every region.",
    "The Company depends on outsourcing partners located primarily in Asia for manufacturing.",
    "Operating income by segment is presented below for each of the last three fiscal years.",
]


def chunk(index: int, text: str) -> dict:
    return {"id": f"c{index}", "chunk_index": index, "text": text}


def test_a_chunk_spans_from_its_start_page_to_the_next_chunks_start():
    # Live: a cited sentence was on the page after its chunk's start page.
    raw = filing(f"{SENTENCES[0]} 1", f"{SENTENCES[1]} 2", f"{SENTENCES[2]} 3")
    pages = assign_pages(raw, [chunk(i, s) for i, s in enumerate(SENTENCES)])
    assert pages == {"c0": "1–2", "c1": "2–3", "c2": "3"}


def test_a_flattened_table_between_neighbours_gets_their_page_or_a_range():
    raw = filing(f"{SENTENCES[0]} 1", f"{SENTENCES[1]} 2")
    table = "Revenue, = 100. Revenue, = 100. Revenue, = 200."  # never in the HTML
    same = assign_pages(
        raw, [chunk(0, SENTENCES[0]), chunk(1, table), chunk(2, SENTENCES[0][:60])]
    )
    assert same["c1"] == "1"
    spanning = assign_pages(
        raw, [chunk(0, SENTENCES[0]), chunk(1, table), chunk(2, SENTENCES[1])]
    )
    assert spanning["c1"] == "1–2"


def test_a_match_out_of_document_order_is_discarded():
    # The table-of-contents phrase on page 1 repeats on page 3; the chunk that
    # follows page-3 text must not jump back to page 1.
    toc = "Management discussion and analysis of financial condition"
    raw = filing(f"{toc} index 1", f"{SENTENCES[1]} 2", f"{SENTENCES[2]} {toc} 3")
    chunks = [
        chunk(0, SENTENCES[1]),
        chunk(1, SENTENCES[2]),
        chunk(2, toc),
        chunk(3, SENTENCES[2]),
    ]
    pages = assign_pages(raw, chunks)
    assert pages["c2"] in ("3", None)
    assert [p for p in pages.values() if p] == sorted(
        [p for p in pages.values() if p], key=lambda p: int(p.split("–")[0])
    )


def test_a_table_repeated_in_the_notes_does_not_move_the_prose_after_it():
    # Live: a chunk starting with a flattened table matched only the table's
    # copies pages later, so the prose cited from it showed the wrong page.
    table = "Technology and infrastructure costs were thirteen point nine percent"
    raw = filing(
        f"{SENTENCES[0]} {SENTENCES[1]} 1",
        f"{SENTENCES[2]} 2",
        f"Results. {table} 3",
        f"Notes. {table} 4",
    )
    chunks = [chunk(0, SENTENCES[0]), chunk(1, f"{table} {SENTENCES[1]}")]
    assert assign_pages(raw, chunks)["c1"] == "1"
