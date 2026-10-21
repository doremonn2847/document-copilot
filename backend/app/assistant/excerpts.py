"""Choose verbatim, question-relevant windows without changing retrieved IDs."""

import re
from bisect import bisect_right

SENTENCE_BREAK = re.compile(r"(?<=[.!?])\s+|\n+")

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
