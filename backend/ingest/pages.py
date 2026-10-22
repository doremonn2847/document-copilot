"""Assign printed page numbers to indexed chunks from the original SEC HTML.

Docling's Markdown kept page numbers for only some filings, but every original
HTML filing marks page breaks and prints its page number at the end of each
page ("29", "30.", "Apple Inc. | 2025 Form 10-K | 29"). Chunks are placed by
matching 48-character runs of their letters and digits; a chunk stores the
range of pages its text covers, or NULL when that spans more than three pages
or cannot be found. Offline; --write updates document_chunks.page.

    uv run python -m ingest.pages            # report only
    uv run python -m ingest.pages --write    # update the database
"""

import argparse
import html
import json
import re
from bisect import bisect_right
from itertools import accumulate
from pathlib import Path
from typing import NamedTuple

DATA = Path(__file__).resolve().parents[2] / "data"
PAGE_BREAK = re.compile(
    r"<[^>]+page-break-(?:before|after)\s*:\s*always[^>]*>", re.IGNORECASE
)
# The number printed at the end of a page, after optional "... | " or before ".".
PRINTED_PAGE = re.compile(r"(?:\|\s*)?(\d{1,3})\.?\s*$")
ANCHOR = 48  # characters of a chunk's normalized text matched at once
STEP = 24


def normalized(text: str) -> str:
    # Letters and digits only: markup that splits a word across tags and
    # apostrophes lost to a mis-decoded file cannot break a match.
    return re.sub(r"[^a-z0-9]", "", html.unescape(text).lower())


def decode(raw: bytes) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # Older EDGAR filings are Windows-1252 (curly quotes as single bytes).
        return raw.decode("cp1252", errors="replace")


def page_texts(raw: str) -> list[str]:
    raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
    return [
        re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", part))).strip()
        for part in PAGE_BREAK.split(raw)
    ]


def printed_page(text: str) -> str | None:
    match = PRINTED_PAGE.search(text)
    return match[1] if match else None


class Span(NamedTuple):
    """Where a chunk's matched text lies in a filing's normalized stream."""

    first: int
    last: int
    open_start: bool  # text before the first match was not placed
    open_end: bool  # nor text after the last
    unique: bool  # placed by a run that occurs once in the filing


def occurrences(stream: str, anchor: str) -> list[int]:
    positions, at = [], stream.find(anchor)
    while at >= 0 and len(positions) < 50:
        positions.append(at)
        at = stream.find(anchor, at + 1)
    return positions


def locate(stream: str, text: str, cursor: int) -> Span | None:
    anchors = [
        (offset, text[offset : offset + ANCHOR])
        for offset in range(0, len(text) - ANCHOR + 1, STEP)
    ]
    # Table labels and tables of contents repeat through a filing; place the
    # chunk by a run that occurs once, else by the occurrence of its first
    # matching run nearest the previous chunk.
    pivot, unique = None, False
    for offset, anchor in anchors:
        positions = occurrences(stream, anchor)
        if len(positions) == 1:
            pivot, unique = (offset, positions[0]), True
            break
        if positions and pivot is None:
            pivot = (offset, min(positions, key=lambda p: abs(p - offset - cursor)))
    if pivot is None:
        return None
    matched = [pivot]
    for offset, anchor in anchors:
        # Other runs sit near the pivot; flattened tables shift them a bit.
        gap = 2 * abs(offset - pivot[0]) + 200
        if offset < pivot[0]:
            at = stream.rfind(anchor, max(pivot[1] - gap, 0), pivot[1])
        elif offset > pivot[0]:
            at = stream.find(anchor, pivot[1], pivot[1] + gap + ANCHOR)
        else:
            continue
        if at >= 0:
            matched.append((offset, at))
    first, last = min(matched), max(matched)
    return Span(
        first[1],
        last[1] + ANCHOR - 1,
        first[0] > 0,
        last[0] + ANCHOR < len(text),
        unique,
    )


def assign_pages(raw_html: str, chunks: list[dict]) -> dict[str, str | None]:
    """Map chunk id -> printed page range, e.g. "43" or "43–44".

    The range runs from the page of a chunk's first matched text to the page
    of its last. Text that never matches (flattened tables) lies between the
    neighbouring matches, so an unmatched start or end widens the range to the
    previous or next chunk's page. A live check found pages computed from a
    chunk's start alone wrong for sentences later in it.
    """
    pages = page_texts(raw_html)
    printed = [printed_page(text) for text in pages]
    streams = [normalized(text) for text in pages]
    stream = "".join(streams)
    boundaries = list(accumulate(len(part) for part in streams))

    def page_at(position: int) -> int | None:
        page = printed[min(bisect_right(boundaries, position), len(printed) - 1)]
        return int(page) if page and page.isdigit() else None

    ordered = sorted(chunks, key=lambda c: c["chunk_index"])
    spans: dict[str, Span | None] = {}
    lows: dict[str, int | None] = {}
    highs: dict[str, int | None] = {}
    cursor = 0
    for chunk in ordered:
        span = spans[chunk["id"]] = locate(stream, normalized(chunk["text"]), cursor)
        low, high = (page_at(span.first), page_at(span.last)) if span else (None, None)
        if low is None or high is None or high < low:
            low = high = None
        lows[chunk["id"]], highs[chunk["id"]] = low, high
        if span:
            cursor = span.first

    def neighbour(pages: dict, chunk_ids: list[str]) -> int | None:
        return next((pages[i] for i in chunk_ids if pages[i] is not None), None)

    def drop(chunk_id: str) -> None:
        lows[chunk_id] = highs[chunk_id] = None

    # Pages never go backwards through a filing. Among chunks placed by a run
    # that occurs once, keep the longest non-decreasing run of pages.
    ids = [chunk["id"] for chunk in ordered]
    trusted = [i for i in ids if lows[i] is not None and spans[i].unique]
    for chunk_id in out_of_order(trusted, lows):
        drop(chunk_id)
    # A chunk placed only by repeated runs (a table that also appears in the
    # notes) counts only between its trusted neighbours: a live citation was
    # a page off when such a chunk outvoted the prose after it.
    trusted_set = set(trusted)
    for n, chunk_id in enumerate(ids):
        if chunk_id in trusted_set or lows[chunk_id] is None:
            continue
        before = neighbour(highs, [i for i in reversed(ids[:n]) if i in trusted_set])
        after = neighbour(lows, [i for i in ids[n + 1 :] if i in trusted_set])
        if (before and lows[chunk_id] < before) or (after and highs[chunk_id] > after):
            drop(chunk_id)

    found: dict[str, str | None] = {}
    for n, chunk_id in enumerate(ids):
        before = neighbour(highs, list(reversed(ids[:n])))
        after = neighbour(lows, ids[n + 1 :])
        span, low, high = spans[chunk_id], lows[chunk_id], highs[chunk_id]
        if low is None:
            first, last = before, after if after is not None else before
        else:
            first = min(before, low) if span.open_start and before else low
            last = max(after, high) if span.open_end and after else high
        if first is None or last is None or not 0 <= last - first <= 2:
            found[chunk_id] = None
        elif first == last:
            found[chunk_id] = str(first)
        else:
            found[chunk_id] = f"{first}–{last}"
    return found


def out_of_order(chunk_ids: list[str], pages: dict[str, int | None]) -> set[str]:
    """Chunks outside the longest non-decreasing sequence of pages."""
    paged = [(i, pages[i]) for i in chunk_ids if pages[i] is not None]
    tails: list[int] = []  # index into paged of the smallest tail per length
    parent = [-1] * len(paged)
    for i, (_, page) in enumerate(paged):
        length = bisect_right([paged[t][1] for t in tails], page)
        if length:
            parent[i] = tails[length - 1]
        if length == len(tails):
            tails.append(i)
        else:
            tails[length] = i
    keep, i = set(), tails[-1] if tails else -1
    while i >= 0:
        keep.add(paged[i][0])
        i = parent[i]
    return {chunk_id for chunk_id, _ in paged} - keep


def filing_pairs() -> list[tuple[Path, Path]]:
    pairs = []
    for chunk_file in sorted((DATA / "chunks").glob("*.jsonl")):
        accession = chunk_file.stem
        matches = sorted((DATA / "downloads").glob(f"*/*{accession}.htm*"))
        if matches:
            pairs.append((chunk_file, matches[0]))
    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    updates: list[tuple[str | None, str]] = []
    total = matched = 0
    for chunk_file, html_file in filing_pairs():
        chunks = [
            json.loads(line)
            for line in chunk_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        pages = assign_pages(decode(html_file.read_bytes()), chunks)
        hits = sum(page is not None for page in pages.values())
        total += len(pages)
        matched += hits
        print(f"{html_file.name[:40]}: {hits}/{len(pages)} chunks paged")
        updates.extend((page, chunk_id) for chunk_id, page in pages.items())
    print(f"Total: {matched}/{total} ({matched / max(total, 1):.1%})")
    if not args.write:
        return
    import psycopg

    from app.config import settings

    with psycopg.connect(
        str(settings.database_url), connect_timeout=10, prepare_threshold=None
    ) as connection:
        with connection.cursor() as cursor:
            cursor.executemany(
                "UPDATE public.document_chunks SET page = %s WHERE id = %s",
                updates,
            )
        connection.commit()
    print(f"Updated {len(updates)} chunk rows")


if __name__ == "__main__":
    main()
