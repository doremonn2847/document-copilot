import asyncio
from types import SimpleNamespace

import pytest

from app.assistant.outputs import AnswerClaim, EvidenceRef, GroundedAnswer
from app.chat.orchestrator import GroundingRejected, run_grounded
from app.grounding.judge import SupportDecision, SupportReport
from tests.assistant.test_contracts import passage
from tests.assistant.test_tools import deps


class Agent:
    def __init__(self, outputs):
        self.outputs = iter(outputs)
        self.calls = []

    async def run(self, _prompt, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(output=next(self.outputs), all_messages=list)


def test_one_repair_retains_registry_and_cumulative_usage():
    d = deps()
    d.searches = 1
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage("Revenue for fiscal 2025 was 100 million dollars.")
    d.registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text=p.text,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    agent = Agent([answer, answer])
    judge = Agent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        evidence_assessment="Fixture verdict.",
                        claim_index=0,
                        supported=False,
                        reason="unsupported_fact",
                    )
                ]
            ),
            SupportReport(
                decisions=[
                    SupportDecision(
                        evidence_assessment="Fixture verdict.",
                        claim_index=0,
                        supported=True,
                        reason="supported",
                    )
                ]
            ),
        ]
    )
    result = asyncio.run(run_grounded("Revenue?", [], d, agent, judge))
    assert result.answer == answer
    assert len(agent.calls) == len(judge.calls) == 2
    assert agent.calls[0]["usage"] is agent.calls[1]["usage"]


def test_repeated_rejection_fails_closed():
    d = deps()
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage()
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="Unsupported",
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    agent = Agent([answer, answer])
    judge = Agent([])
    with pytest.raises(GroundingRejected):
        asyncio.run(run_grounded("Revenue?", [], d, agent, judge))
    assert judge.calls == []


def test_contradictory_gap_is_repaired_before_judging_and_never_rendered():
    from app.assistant.outputs import EvidenceGap
    from app.retrieval.types import SearchFilters

    d = deps()
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage("Azure provides compute.").model_copy(
        update={"ticker": "MSFT", "corpus_year": 2025}
    )
    d.registry.expose(p, p.text)
    claim = AnswerClaim(
        text=p.text, evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)]
    )
    corrected = GroundedAnswer(status="answered", claims=[claim])
    contradictory = GroundedAnswer(
        status="partial",
        claims=[claim],
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="MSFT", form="10-K", corpus_years=[2025]),
                reason="missing_evidence",
            )
        ],
    )
    agent = Agent([contradictory, corrected])
    judge = Agent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        evidence_assessment="Azure compute is explicitly supported.",
                        claim_index=0,
                        supported=True,
                        reason="supported",
                    )
                ]
            )
        ]
    )
    result = asyncio.run(run_grounded("What does Azure provide?", [], d, agent, judge))
    assert len(agent.calls) == 2 and len(judge.calls) == 1
    assert result.answer.status == "answered"
    assert result.reply.text == "Azure provides compute. [1]"
    assert "missing_detail" in d.validation_reports[0]["errors"][0]


@pytest.mark.parametrize(
    "warranted, detail",
    [
        (
            False,
            "We have cited passages E1 and E2 from the MSFT 10-K corpus; confirm whether there are additional supporting passages in the same filing that define Azure provides and any nuances (e.g., AI Foundry, Azure Foundry) if needed.",
        ),
        (
            False,
            "Need explicit fiscal periods for Azure provisions (e.g., Azure provides ... for fiscal year 2025 vs 2024)",
        ),
        (True, "The requested Azure pricing"),
    ],
)
def test_gap_relevance_is_verified_in_same_call_as_claims(warranted, detail):
    from app.assistant.outputs import EvidenceGap
    from app.grounding.judge import GapDecision
    from app.retrieval.types import SearchFilters

    d = deps()
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage("Azure provides compute.").model_copy(
        update={"ticker": "MSFT", "corpus_year": 2025}
    )
    d.registry.expose(p, p.text)
    claim = AnswerClaim(
        text=p.text, evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)]
    )
    corrected = GroundedAnswer(status="answered", claims=[claim])
    partial = GroundedAnswer(
        status="partial",
        claims=[claim],
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="MSFT", form="10-K", corpus_years=[2025]),
                reason="missing_evidence",
                missing_detail=detail,
            )
        ],
    )
    support = SupportDecision(
        claim_index=0,
        evidence_assessment="Compute is explicitly supported.",
        supported=True,
        reason="supported",
    )
    agent = Agent([partial, corrected])
    judge = Agent(
        [
            SupportReport(
                decisions=[support],
                gap_decisions=[
                    GapDecision(
                        gap_index=0,
                        warranted=warranted,
                        evidence_assessment="Requested pricing is unresolved."
                        if warranted
                        else "The lookup is answered; confirming passages and optional Foundry nuances were not requested.",
                    )
                ],
            ),
            SupportReport(decisions=[support]),
        ]
    )
    question = "What does Microsoft’s 2025 filing say Azure provides? Cite the supporting passages."
    if warranted:
        question += " Also provide pricing."
    result = asyncio.run(run_grounded(question, [], d, agent, judge))
    assert len(judge.calls) == len(agent.calls) == (1 if warranted else 2)
    if warranted:
        assert result.answer.status == "partial"
        assert "The requested Azure pricing" in result.reply.text
    else:
        assert result.answer.status == "answered"
        assert result.reply.text == "Azure provides compute. [1]"
        assert (
            result.diagnostics["validation"][1]["gap_decisions"][0]["warranted"]
            is False
        )


def test_malformed_judge_coverage_is_service_failure_not_evidence_repair():
    from app.grounding.judge import InvalidSupportReport

    d = deps()
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage("Revenue for fiscal 2025 was 100 million dollars.")
    d.registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text=p.text,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    agent, judge = Agent([answer]), Agent([SupportReport(decisions=[])])
    with pytest.raises(InvalidSupportReport):
        asyncio.run(run_grounded("Revenue?", [], d, agent, judge))
    assert len(agent.calls) == 1 and len(judge.calls) == 1


@pytest.mark.parametrize(
    "question,advice",
    [
        ("Should I buy NVIDIA stock based on these filings?", True),
        ("Is Apple a good investment right now?", True),
        ("What is a fair price target for Microsoft?", True),
        ("Buy or sell Amazon after the 2025 10-K?", True),
        ("What does Microsoft say Azure provides in the 2025 filing?", False),
        ("Compare Apple's and NVIDIA's supplier risks.", False),
        ("How much did Microsoft invest in AI infrastructure?", False),
    ],
)
def test_investment_advice_requests_are_detected_without_the_model(question, advice):
    from app.chat.orchestrator import INVESTMENT_ADVICE

    assert bool(INVESTMENT_ADVICE.search(question)) is advice


def test_advice_questions_get_the_fixed_decline_before_the_cited_facts():
    from app.assistant.rendering import ADVICE_NOTICE

    d = deps()
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 0
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage("Investors may lose all or part of their investment.")
    d.registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text=p.text,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    judge = Agent(
        [
            SupportReport(
                decisions=[
                    SupportDecision(
                        claim_index=0,
                        supported=True,
                        reason="supported",
                        evidence_assessment="Quoted.",
                    )
                ]
            )
        ]
    )
    result = asyncio.run(
        run_grounded("Should I buy NVIDIA stock?", [], d, Agent([answer]), judge)
    )
    assert result.reply.text.startswith(ADVICE_NOTICE)


def test_final_attempt_drops_only_unwarranted_gaps_after_supported_claims():
    # Live: drafts kept rebutting "does the filing say nothing about AI?" in a gap.
    from app.assistant.outputs import EvidenceGap
    from app.grounding.judge import GapDecision
    from app.retrieval.types import SearchFilters

    d = deps()
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    p = passage("Risks can increase with artificial intelligence features.").model_copy(
        update={"ticker": "AAPL", "corpus_year": 2025}
    )
    d.registry.expose(p, p.text)
    claim = AnswerClaim(
        text=p.text, evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)]
    )
    draft = GroundedAnswer(
        status="partial",
        claims=[claim],
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="AAPL", form="10-K", corpus_years=[2025]),
                reason="missing_evidence",
                missing_detail="The no-AI premise is not supported.",
            )
        ],
    )

    def report(supported):
        return SupportReport(
            decisions=[
                SupportDecision(
                    claim_index=0,
                    evidence_assessment="Fixture verdict.",
                    supported=supported,
                    reason="supported" if supported else "unsupported_fact",
                )
            ],
            gap_decisions=[
                GapDecision(
                    gap_index=0,
                    warranted=False,
                    evidence_assessment="The claims answer the question.",
                )
            ],
        )

    question = "Does Apple's 2025 10-K say nothing about AI?"
    result = asyncio.run(
        run_grounded(
            question, [], d, Agent([draft, draft]), Agent([report(True), report(True)])
        )
    )
    assert result.answer.gaps == [] and result.answer.status == "answered"
    assert result.reply.text == p.text + " [1]"
    # A failed claim still fails the whole answer closed.
    d = deps()
    d.completed_retrievals = 1
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    d.settings.assistant_max_claims = 20
    d.settings.assistant_claim_refs = 5
    d.registry.expose(p, p.text)
    with pytest.raises(GroundingRejected):
        asyncio.run(
            run_grounded(
                question,
                [],
                d,
                Agent([draft, draft]),
                Agent([report(False), report(False)]),
            )
        )
