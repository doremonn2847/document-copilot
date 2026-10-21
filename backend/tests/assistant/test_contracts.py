from datetime import date
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import AnswerClaim, EvidenceRef, GroundedAnswer
from app.retrieval.types import RetrievedPassage


def assertions_for(quote):
    """A judge assertion anchored to verbatim cited words, as the server requires."""
    from app.grounding.judge import Assertion

    return [Assertion(assertion="Fixture assertion.", supporting_quote=quote)]


def passage(text="Revenue was 100 million dollars."):
    return RetrievedPassage(
        chunk_id=uuid4(),
        document_id=uuid4(),
        chunk_index=0,
        text=text,
        ticker="AAPL",
        form="10-K",
        accession_number="test",
        source_url="https://www.sec.gov/Archives/test",
        filing_date=date(2025, 1, 1),
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"status": "answered", "claims": []},
        {"status": "partial", "claims": [], "gaps": [{"reason": "missing_evidence"}]},
        {"status": "insufficient_evidence", "gaps": []},
    ],
)
def test_answer_contract(payload):
    with pytest.raises(ValidationError):
        GroundedAnswer.model_validate(payload)


@pytest.mark.parametrize("detail", [" ", "Missing [1]", "x" * 401])
def test_gap_detail_rejects_blank_citation_markers_and_unbounded_text(detail):
    from app.assistant.outputs import EvidenceGap

    with pytest.raises(ValidationError):
        EvidenceGap(reason="missing_evidence", missing_detail=detail)


def test_claim_requires_evidence_and_rejects_citation_markers():
    with pytest.raises(ValidationError):
        AnswerClaim(text="Unsupported", evidence=[])
    with pytest.raises(ValidationError):
        AnswerClaim(
            text="Revenue [1]",
            evidence=[EvidenceRef(chunk_id=uuid4(), exact_quote="x")],
        )


def test_registry_only_authorizes_exposed_source():
    p = passage("Visible evidence. Hidden evidence.")
    registry = TurnRegistry()
    registry.expose(p, "Visible evidence.")
    registry.verify(EvidenceRef(chunk_id=p.chunk_id, exact_quote="Visible  evidence."))
    with pytest.raises(ValueError):
        registry.verify(
            EvidenceRef(chunk_id=p.chunk_id, exact_quote="Hidden evidence.")
        )
    assert registry.passages[p.chunk_id].fiscal_year is None
    assert registry.passages[p.chunk_id].page is None


def test_wrong_chunk_id_feedback_identifies_only_exact_observed_alternatives():
    a, b = (
        passage("Revenue was 100."),
        passage("Cash flow was 20. Hidden balance was 50."),
    )
    registry = TurnRegistry()
    registry.expose(a, a.text)
    registry.expose(b, "Cash flow was 20.")
    with pytest.raises(ValueError, match=str(b.chunk_id)):
        registry.verify(
            EvidenceRef(chunk_id=a.chunk_id, exact_quote="Cash flow was 20.")
        )
    with pytest.raises(ValueError) as error:
        registry.verify(
            EvidenceRef(chunk_id=a.chunk_id, exact_quote="Hidden balance was 50.")
        )
    assert str(b.chunk_id) not in str(error.value)


def test_stitched_quote_is_rejected_with_individually_verifiable_repair_spans():
    import json

    p = passage(
        "Azure offers cloud services. Customers can build applications. "
        "Revenue depends on consumption. Azure AI supports businesses."
    )
    registry = TurnRegistry()
    registry.expose(p, p.text)
    quote = "Azure offers cloud services. Customers can build applications. Azure AI supports businesses."
    with pytest.raises(ValueError) as error:
        registry.verify(EvidenceRef(chunk_id=p.chunk_id, exact_quote=quote))
    message = str(error.value)
    assert "non-contiguous" in message
    spans = json.loads(message.split("Exact observed spans: ", 1)[1])
    assert len(spans) == 3
    for span in spans:
        registry.verify(EvidenceRef(chunk_id=p.chunk_id, exact_quote=span))
    assert "Revenue depends" not in message


def test_stitched_quote_feedback_never_supplies_unobserved_or_reworded_text():
    p = passage("Azure offers services. Hidden sentence. Azure AI supports businesses.")
    registry = TurnRegistry()
    registry.expose(p, "Azure offers services.")
    for quote in (
        "Azure offers services. Azure AI supports businesses.",
        "Azure delivers services. Azure AI supports businesses.",
    ):
        with pytest.raises(ValueError) as error:
            registry.verify(EvidenceRef(chunk_id=p.chunk_id, exact_quote=quote))
        assert "Exact observed spans:" not in str(error.value)
