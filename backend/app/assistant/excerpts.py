"""Choose verbatim, question-relevant windows without changing retrieved IDs."""

import re

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
    starts = [0, *(match.end() for match in re.finditer(r"(?<=[.!?])\s+|\n+", text))]
    start = max(
        starts,
        key=lambda index: (relevance(text[index : index + limit], terms), -index),
    )
    return text[start : start + limit]
