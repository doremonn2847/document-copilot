"""Choose verbatim, question-relevant windows without changing retrieved IDs."""

import re
from bisect import bisect_right

SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

STOP_WORDS = {
    "the",
    "and",
    "that",
    "this",
    "with",
    "from",
    "into",
    "about",
    "what",
    "does",
    "which",
    "their",
    "they",
    "have",
    "will",
    "could",
    "would",
    "please",
    "compare",
    "across",
    "filings",
    "filing",
    "corpus",
    "years",
    "year",
    "reported",
    "report",
    "cite",
    "evidence",
    "show",
    "explicit",
    "identify",
    "missing",
    "information",
    "apple",
    "nvidia",
    "microsoft",
    "amazon",
    "alphabet",
    "google",
    "time",
}


def focus_terms(text: str) -> set[str]:
    return {
        word[:6]
        for word in re.findall(r"[a-z]{3,}", text.lower())
        if word not in STOP_WORDS
    }


def relevance(text: str, terms: set[str]) -> int:
    return len(terms & {word[:6] for word in re.findall(r"[a-z]{3,}", text.lower())})


def focused_excerpt(text: str, limit: int, terms: set[str]) -> str:
    if limit <= 0:
        return ""
    if not terms or len(text) <= limit:
        return text[:limit]
    breaks = list(SENTENCE_BREAK.finditer(text))
    starts = [0, *(match.end() for match in breaks)]
    ends = [match.start() for match in breaks] + [len(text)]

    def window(start: int) -> str:
        # End on a sentence boundary: a focus sentence cut at the limit is shown
        # as an uncitable preview (a live AI question lost its evidence this way).
        i = bisect_right(ends, start + limit) - 1
        stop = ends[i] if i >= 0 and ends[i] > start else start + limit
        return text[start:stop]

    start = max(starts, key=lambda index: (relevance(window(index), terms), -index))
    return window(start)


def table_rows(table: str, limit: int, terms: set[str]) -> list[str]:
    """Verbatim year-header rows plus the rows that match the focus terms.

    Docling pads Markdown cells to about 300 characters a row, so cutting a
    table at the limit kept only its headers and none of the AWS or segment
    amounts. Each returned line is an exact source substring, in table order.
    """
    lines = [line for line in table.split("\n") if re.search(r"\w", line)]
    headers = [i for i, line in enumerate(lines[:6]) if YEAR.search(line)]
    # Label-only rows ("Operating Income (Loss)") carry no amounts.
    ranked = sorted(
        (i for i in range(len(lines)) if i not in headers),
        key=lambda i: (not re.search(r"\d", lines[i]), -relevance(lines[i], terms), i),
    )
    chosen, size = [], 0
    for i in [*headers, *ranked]:
        if i not in headers and terms and not relevance(lines[i], terms):
            break
        # Leave room for the "[E12] " ID and newline the caller adds per row.
        if size + len(lines[i]) + 10 > limit:
            continue
        chosen.append(i)
        size += len(lines[i]) + 10
    return [lines[i] for i in sorted(chosen)]
