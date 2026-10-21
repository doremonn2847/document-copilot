"""Conservative checks for named-company and financial comparison context.

These reject missing context, not certify semantic support. The judge still
checks row/column binding, meaning, and whether a conclusion follows.
"""

import re

from app.assistant.excerpts import focus_terms
from app.assistant.outputs import AnswerClaim
from app.retrieval.types import RetrievedPassage

COMPANIES = {
    "AAPL": r"\b(?:Apple|AAPL)\b",
    "AMZN": r"\b(?:Amazon|AMZN)\b",
    "GOOGL": r"\b(?:Alphabet|Google|GOOGL)\b",
    "MSFT": r"\b(?:Microsoft|MSFT)\b",
    "NVDA": r"\b(?:NVIDIA|NVDA)\b",
}
FINANCIAL_MEASURE = re.compile(
    r"\b(?:revenues?|gross[- ]margin|net[- ]income|operating[- ]income|sales|profits?|earnings|cash[- ]flow)\b",
    re.IGNORECASE,
)
AMOUNT = re.compile(r"(?<![\w])\d[\d,]*(?:\.\d+)?(?![\w]|-[KQ]\b)")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
PERIOD = re.compile(
    r"\b(?:fiscal(?:\s+years?)?|FY)\s*[-:]?\s*((?:19|20)\d{2})\b|"
    r"\byears?\s+ended\s+[^.;]{0,40}?\b((?:19|20)\d{2})\b",
    re.IGNORECASE,
)
CURRENCY = re.compile(r"\b(?:USD|U\.S\. dollars?|dollars?)\b|\$", re.IGNORECASE)
SCALE = re.compile(r"\b(?:thousands?|millions?|billions?|trillions?)\b", re.IGNORECASE)

# "a majority of the company's supply chain": the quantified subject. A live
# comparison bound "majority" from a net-sales quote to the supply chain and the
# judge accepted it, so the subject must come from the quotes, not paraphrase.
QUANTIFIED = re.compile(
    r"\b(?:majority|most|half|minority|portion|share|percent|%)\s+of\s+(?:the\s+|its\s+|their\s+)?(?:[\w.-]+'s\s+)?([a-z-]+(?:\s+[a-z-]+){0,2})",
    re.IGNORECASE,
)
SUBJECT_END = {
    "from",
    "in",
    "outside",
    "is",
    "are",
    "was",
    "were",
    "comes",
    "come",
    "came",
    "and",
    "or",
    "that",
    "which",
    "to",
    "for",
    "by",
    "with",
}
GENERIC = {"the", "total", "net", "overall", "company", "companies", "its", "our"}

# Six-letter stems (as focus_terms returns) that any claim about a filing may use.
FILLER = {
    "form",
    "says",
    "said",
    "states",
    "mentio",
    "also",
    "compan",
    "discus",
    "descri",
    "report",
}

SOURCE = r"(?:filings?|documents?|reports?|10-[kq]s?)"
ABSENCE = r"(?:never\s+(?:mentions?|discuss(?:es)?|refers?|states?)|(?:does|do|did)\s+not\s+(?:mention|discuss|refer|state)|(?:doesn't|don't|didn't)\s+(?:mention|discuss|refer|state)|(?:contains?|includes?|provides?|makes?)\s+no\s+(?:mention|reference|discussion)|omits?)"


def unsupported_absence_claim(text: str) -> bool:
    """Recognize file-wide absence assertions; the registry contains excerpts only."""
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text.replace("’", "'")):
        if re.search(
            r"\b(?:excerpts?|passages?|snippets?|retrieved (?:text|evidence))\b",
            sentence,
            re.IGNORECASE,
        ) and not re.search(
            r"\b(?:never|entire|whole|anywhere)\b", sentence, re.IGNORECASE
        ):
            continue
        if re.search(
            rf"\b{SOURCE}\s+(?:itself\s+|also\s+|explicitly\s+)?{ABSENCE}\b",
            sentence,
            re.IGNORECASE,
        ):
            return True
        if re.search(
            rf"\b(?:no (?:mention|reference|discussion)|not mentioned|not discussed|absent)\b[^.!?]{{0,120}}\b{SOURCE}\b",
            sentence,
            re.IGNORECASE,
        ):
            return True
    return False


def unquoted_quantified_subjects(claim: AnswerClaim) -> list[str]:
    quotes = {
        word[:5]
        for ref in claim.evidence
        for word in re.findall(r"[a-z]+", ref.exact_quote.lower())
    }
    subjects = []
    for match in QUANTIFIED.finditer(claim.text.replace("’", "'")):
        words = []
        for word in match[1].lower().split():
            if word in SUBJECT_END:
                break
            words.append(word)
        content = [w for w in words if len(w) > 2 and w not in GENERIC]
        if content and not any(w[:5] in quotes for w in content):
            subjects.append(" ".join(words))
    return subjects


def shares_no_wording(claim: AnswerClaim) -> bool:
    """A live judge accepted a claim whose only quote was the heading "Item 8."."""
    quotes = " ".join(ref.exact_quote for ref in claim.evidence)
    return not (focus_terms(claim.text) - FILLER) & focus_terms(quotes)


def financial_context_only(errors: list[str]) -> bool:
    """Only missing financial context, plus uncited numbers in those same claims.

    This authorizes discarding all claims, never accepting an unsupported number.
    Other claims' errors and citation-provenance failures must still fail closed.
    """
    context_pattern = re.compile(
        r"^claim (\d+): financial (?:figures require explicit fiscal periods|amounts require explicit currency|amounts require matching quoted scale)"
    )
    financial_claims = {
        match[1] for error in errors if (match := context_pattern.match(error))
    }
    for error in errors:
        if context_pattern.match(error):
            continue
        number_error = re.match(r"^claim (\d+): uncited numeric tokens ", error)
        if number_error and number_error[1] in financial_claims:
            continue
        return False
    return bool(errors)


def missing_company_evidence(
    claim: AnswerClaim, passages: list[RetrievedPassage]
) -> set[str]:
    named = {
        ticker
        for ticker, pattern in COMPANIES.items()
        if re.search(pattern, claim.text, re.IGNORECASE)
    }
    return (
        named - {p.ticker for p in passages}
        if claim.kind == "interpretation" and len(named) > 1
        else set()
    )


def claim_context_errors(
    claim: AnswerClaim, passages: list[RetrievedPassage]
) -> list[str]:
    if claim.kind == "calculation":
        return []
    errors = []
    if unsupported_absence_claim(claim.text):
        errors.append(
            "selected excerpts cannot establish absence from the entire filing. Omit the file-wide claim and report what the retrieved evidence does not establish."
        )
    if claim.kind == "fact" and shares_no_wording(claim):
        errors.append(
            "the attached quotes share no wording with the claim. Cite the sentences that state it."
        )
    subjects = unquoted_quantified_subjects(claim)
    if subjects:
        errors.append(
            "quantified subjects must appear in the attached quotes: "
            + ", ".join(subjects)
            + ". Say what the quoted share applies to in the source's own terms."
        )
    named = {
        ticker
        for ticker, pattern in COMPANIES.items()
        if re.search(pattern, claim.text, re.IGNORECASE)
    }
    missing = missing_company_evidence(claim, passages)
    if missing:
        errors.append(
            "cite this claim's own evidence for every named company: "
            + ", ".join(sorted(missing))
            + ". Evidence attached to other claims cannot support this synthesis."
        )
    if (
        claim.kind == "interpretation"
        and re.search(r"\b(?:most|least) explicit\b", claim.text, re.IGNORECASE)
        and re.search(
            r"\bacross\b.{0,50}\bfilings\b|\bover time\b", claim.text, re.IGNORECASE
        )
        and not re.search(
            r"\b(?:cannot determine|does not establish|insufficient)\b",
            claim.text,
            re.IGNORECASE,
        )
    ):
        groups = named or {None}
        if any(
            len(
                {
                    p.document_id
                    for p in passages
                    if ticker is None or p.ticker == ticker
                }
            )
            < 2
            for ticker in groups
        ):
            errors.append(
                "comparison superlatives across filings need cited evidence from multiple filings for each compared company. Omit an unsupported ranking and give a specific evidence gap."
            )
    numeric_text = PERIOD.sub("", claim.text)
    amounts = [
        match
        for match in AMOUNT.finditer(numeric_text)
        if not YEAR.fullmatch(match.group())
    ]
    if not amounts or not FINANCIAL_MEASURE.search(claim.text):
        return errors
    quotes = "\n".join(ref.exact_quote for ref in claim.evidence)
    # This layer checks year presence, not an English prose template. The judge
    # establishes fiscal meaning and table-column binding from the attached quotes.
    periods = set(YEAR.findall(claim.text)) | {
        year for pair in PERIOD.findall(claim.text) for year in pair if year
    }
    quoted_periods = set(YEAR.findall(quotes)) | {
        year for pair in PERIOD.findall(quotes) for year in pair if year
    }
    if not periods or not periods <= quoted_periods:
        cause = "missing_claim_year" if not periods else "missing_quoted_year"
        errors.append(
            f"financial figures require explicit fiscal periods: {cause}. State the year and cite its actual source heading; corpus/filing metadata and 'prior column' cannot fill missing quoted years. The judge must still verify fiscal meaning and column binding."
        )
    monetary = any(
        not re.match(r"\s*(?:%|percent\b)", numeric_text[match.end() :], re.IGNORECASE)
        for match in amounts
    )
    if monetary:
        if not CURRENCY.search(claim.text) or not CURRENCY.search(quotes):
            errors.append(
                "financial amounts require explicit currency units in both the claim and its attached quotes."
            )
        claim_scales = {s.lower().rstrip("s") for s in SCALE.findall(claim.text)}
        quote_scales = {s.lower().rstrip("s") for s in SCALE.findall(quotes)}
        if claim_scales != quote_scales:
            errors.append(
                "financial amounts require matching quoted scale (e.g. USD millions); do not omit or infer table units."
            )
    return errors
