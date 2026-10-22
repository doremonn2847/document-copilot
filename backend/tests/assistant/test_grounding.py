import pytest

from app.assistant.deps import TurnRegistry
from app.assistant.outputs import AnswerClaim, EvidenceGap, EvidenceRef, GroundedAnswer
from app.grounding.judge import SupportDecision, SupportReport, support_errors
from app.grounding.validator import structural_errors
from tests.assistant.test_contracts import passage


def answer_and_registry():
    p = passage("Revenue for fiscal 2025 was 100 million dollars.")
    r = TurnRegistry()
    r.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text=p.text,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
            )
        ],
    )
    return answer, r


def test_current_turn_evidence_and_retrieval_required():
    answer, registry = answer_and_registry()
    assert structural_errors(answer, registry, searches=1) == []
    assert structural_errors(answer, registry, searches=0)
    assert structural_errors(answer, TurnRegistry(), searches=1)


def test_numeric_claim_requires_numbers_in_its_actual_cited_quotes():
    p = passage("Revenue was 100 million dollars. Revenue increased.")
    r = TurnRegistry()
    r.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="Revenue was 100 million dollars.",
                evidence=[
                    EvidenceRef(chunk_id=p.chunk_id, exact_quote="Revenue increased.")
                ],
            )
        ],
    )
    assert structural_errors(answer, r, searches=1)


def test_judge_receives_only_the_quotes_attached_to_each_claim():
    import json

    from app.grounding.judge import judge_prompt

    p = passage(
        "Revenue was 100 million dollars. Unrelated claim would only be supported by this hidden-from-citation sentence."
    )
    r = TurnRegistry()
    r.expose(p, p.text)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="Revenue was 100 million dollars.",
                evidence=[
                    EvidenceRef(
                        chunk_id=p.chunk_id,
                        exact_quote="Revenue was 100 million dollars.",
                    )
                ],
            )
        ],
    )
    payload = judge_prompt("Revenue?", answer, r)
    assert "hidden-from-citation" not in payload
    assert (
        json.loads(payload)["proposed_answer"]["claims"][0]["cited_evidence"][0][
            "exact_quote"
        ]
        == answer.claims[0].evidence[0].exact_quote
    )


def test_judge_omits_unknown_metadata_and_keeps_explicit_period_evidence():
    import json

    from app.grounding.judge import judge_prompt

    answer, registry = answer_and_registry()
    ref = answer.claims[0].evidence[0]
    payload = json.loads(judge_prompt("Revenue?", answer, registry))
    evidence = payload["proposed_answer"]["claims"][0]["cited_evidence"][0]
    assert "fiscal_year" not in evidence["metadata"]
    assert "page" not in evidence["metadata"]
    assert evidence["exact_quote"] == ref.exact_quote
    p = registry.passages[ref.chunk_id]
    registry.passages[ref.chunk_id] = p.model_copy(update={"fiscal_year": 2025})
    payload = json.loads(judge_prompt("Revenue?", answer, registry))
    assert (
        payload["proposed_answer"]["claims"][0]["cited_evidence"][0]["metadata"][
            "fiscal_year"
        ]
        == 2025
    )


def test_numeric_input_check_is_explicitly_distinct_from_final_answer_support():
    import json

    from app.grounding.judge import judge_prompt

    answer, registry = answer_and_registry()
    payload = json.loads(
        judge_prompt(
            "Ratio of reported increases?", answer, registry, task="numeric_inputs"
        )
    )
    assert payload["verification_task"] == "numeric_inputs"
    assert payload["actual_user_request"]["text"] == "Ratio of reported increases?"
    assert (
        payload["proposed_answer"]["claims"][0]["cited_evidence"][0]["exact_quote"]
        == answer.claims[0].evidence[0].exact_quote
    )


def test_comparison_cannot_silently_drop_empty_target():
    from app.retrieval.types import SearchFilters

    answer, registry = answer_and_registry()
    target = SearchFilters(ticker="TSLA", corpus_years=[2028])
    registry.comparison_targets.append(target)
    assert structural_errors(answer, registry, searches=1)
    partial = GroundedAnswer(
        status="partial",
        claims=answer.claims,
        gaps=[EvidenceGap(target=target, reason="missing_evidence")],
    )
    assert structural_errors(partial, registry, searches=1) == []


@pytest.mark.parametrize("targeted", [False, True])
def test_blanket_missing_evidence_cannot_contradict_cited_target(targeted):
    from app.retrieval.types import SearchFilters

    answer, registry = answer_and_registry()
    target = SearchFilters(ticker="AAPL", form="10-K") if targeted else None
    partial = GroundedAnswer(
        status="partial",
        claims=answer.claims,
        gaps=[EvidenceGap(target=target, reason="missing_evidence")],
    )
    assert any(
        "missing_detail" in error
        for error in structural_errors(partial, registry, searches=1)
    )


def test_specific_partial_gap_is_preserved_and_rendered_without_blanket_warning():
    from app.assistant.rendering import render_answer
    from app.retrieval.types import SearchFilters

    answer, registry = answer_and_registry()
    partial = GroundedAnswer(
        status="partial",
        claims=answer.claims,
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="AAPL"),
                reason="missing_evidence",
                missing_detail="The requested breakdown by product",
            )
        ],
    )
    assert structural_errors(partial, registry, searches=1) == []
    text = render_answer(partial, registry).text
    assert "Revenue for fiscal 2025 was 100 million dollars." in text
    assert "The requested breakdown by product" in text
    assert "do not provide enough evidence for this target" not in text


def test_other_year_gap_stays_visible_and_unverified_fiscal_year_is_not_covered():
    from app.retrieval.types import SearchFilters

    answer, registry = answer_and_registry()
    ref = answer.claims[0].evidence[0]
    registry.passages[ref.chunk_id] = registry.passages[ref.chunk_id].model_copy(
        update={"corpus_year": 2025}
    )
    for target in (
        SearchFilters(ticker="AAPL", corpus_years=[2024]),
        SearchFilters(ticker="AAPL", fiscal_years=[2025]),
    ):
        partial = GroundedAnswer(
            status="partial",
            claims=answer.claims,
            gaps=[EvidenceGap(target=target, reason="missing_evidence")],
        )
        assert structural_errors(partial, registry, searches=1) == []


def test_calculation_rendering_uses_recorded_result_even_if_draft_is_tampered():
    from app.assistant.calculations import calculate
    from tests.assistant.test_calculations import operands

    registry, values = operands()
    record = calculate("percent_change", values, registry)
    evidence = list(values[0].evidence)
    claim = AnswerClaim(
        text="The annual revenue increase was 25%.",
        kind="calculation",
        calculation_id=record.id,
        evidence=evidence,
    )
    answer = GroundedAnswer(status="answered", claims=[claim])
    assert structural_errors(answer, registry, searches=1) == []
    bad = answer.model_copy(
        update={"claims": [claim.model_copy(update={"text": "The increase was 30%."})]}
    )
    from app.assistant.rendering import render_answer

    rendered = render_answer(bad, registry)
    assert "30%" not in rendered.text and "25.00 %" in rendered.text


def test_only_controlled_clarification_or_scope_bypasses_retrieval():
    for reason in ("outside_scope", "ambiguous_question", "missing_evidence"):
        answer = GroundedAnswer(
            status="insufficient_evidence", gaps=[EvidenceGap(reason=reason)]
        )
        assert bool(structural_errors(answer, TurnRegistry(), searches=0)) == (
            reason == "missing_evidence"
        )


@pytest.mark.parametrize("decisions", [[], [0, 0], [1], [0, 1]])
def test_judge_requires_exact_indexed_coverage(decisions):
    from app.grounding.judge import InvalidSupportReport

    report = SupportReport(
        decisions=[
            SupportDecision(
                evidence_assessment="Fixture verdict.",
                claim_index=i,
                supported=True,
                reason="supported",
            )
            for i in decisions
        ]
    )
    with pytest.raises(InvalidSupportReport):
        support_errors(report, 1)


def test_judge_rejects_reference_that_does_not_support_claim():
    report = SupportReport(
        decisions=[
            SupportDecision(
                evidence_assessment="Fixture verdict.",
                claim_index=0,
                supported=False,
                reason="unit_or_period_mismatch",
            )
        ]
    )
    assert support_errors(report, 1) == [
        "claim 0: unit_or_period_mismatch. Fixture verdict."
    ]


def test_judge_receives_the_actual_gap_and_question_alongside_cited_claims():
    import json

    from app.grounding.judge import judge_prompt

    answer, registry = answer_and_registry()
    detail = "Confirm additional passages E1 and E2 and AI Foundry nuances if needed."
    partial = GroundedAnswer(
        status="partial",
        claims=answer.claims,
        gaps=[EvidenceGap(reason="missing_evidence", missing_detail=detail)],
    )
    question = "What does Azure provide? Cite supporting passages."
    payload = json.loads(judge_prompt(question, partial, registry))
    assert payload["actual_user_request"]["text"] == question
    assert payload["proposed_answer"]["gaps"] == [
        {"gap_index": 0, **partial.gaps[0].model_dump(mode="json")}
    ]
    assert payload["proposed_answer"]["claims"][0]["cited_evidence"]


@pytest.mark.parametrize("indices", [[], [0, 0], [1]])
def test_judge_gap_coverage_must_be_exact_before_acceptance(indices):
    from app.grounding.judge import GapDecision, InvalidSupportReport

    report = SupportReport(
        decisions=[],
        gap_decisions=[
            GapDecision(
                gap_index=i,
                warranted=True,
                evidence_assessment="Requested target is unresolved.",
            )
            for i in indices
        ],
    )
    with pytest.raises(InvalidSupportReport):
        support_errors(report, 0, 1)


@pytest.mark.parametrize(
    "judge_quote, accepted",
    [
        (None, False),
        ("explicit fiscal-period heading", False),
        ("Describe Azure", False),
        ("provide pricing", True),
        # Live Q10: the whole question contains the gap's own quote.
        ("Describe Azure and provide pricing", True),
    ],
)
def test_warranted_gap_requires_same_real_request_anchor(judge_quote, accepted):
    import asyncio

    from app.grounding.judge import GapDecision, judge_answer
    from tests.assistant.test_orchestrator import Agent

    answer, registry = answer_and_registry()
    partial = GroundedAnswer(
        status="partial",
        claims=answer.claims,
        gaps=[
            EvidenceGap(
                reason="missing_evidence",
                missing_detail="Pricing",
                request_quote="provide pricing",
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
                        evidence_assessment="Supported.",
                    )
                ],
                gap_decisions=[
                    GapDecision(
                        gap_index=0,
                        warranted=True,
                        request_quote=judge_quote,
                        evidence_assessment="Proposed limitation is unresolved.",
                    )
                ],
            )
        ]
    )
    report = asyncio.run(
        judge_answer("Describe Azure and provide pricing", partial, registry, judge)
    )
    assert report.gap_decisions[0].warranted is accepted
    assert bool(support_errors(report, 1, 1)) is not accepted


def test_judge_checks_the_canonical_calculation_text_shown_to_the_user():
    import json

    from app.assistant.calculations import calculate
    from app.grounding.judge import judge_prompt
    from tests.assistant.test_calculations import operands

    registry, values = operands()
    record = calculate("percent_change", values, registry)
    claim = AnswerClaim(
        text="Fabricated result was 999%.",
        kind="calculation",
        calculation_id=record.id,
        evidence=list(values[0].evidence),
    )
    answer = GroundedAnswer(status="answered", claims=[claim])
    prompt = json.loads(judge_prompt("Annual revenue increase?", answer, registry))
    assert "999" not in prompt["proposed_answer"]["claims"][0]["text"]
    assert "25.00 %" in prompt["proposed_answer"]["claims"][0]["text"]
    assert prompt["proposed_answer"]["claims"][0]["calculation"]["display"] == "25.00 %"


@pytest.mark.parametrize(
    "change", [{"display": "999.00 %"}, {"result": 999}, {"formula": "invented"}]
)
def test_forged_calculation_is_rejected_before_semantic_approval(change):
    import asyncio

    from app.assistant.calculations import calculate
    from app.grounding.judge import judge_answer
    from tests.assistant.test_calculations import operands
    from tests.assistant.test_orchestrator import Agent

    registry, values = operands()
    record = calculate("percent_change", values, registry)
    registry.calculations[record.id] = record.model_copy(update=change)
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="Revenue change.",
                kind="calculation",
                calculation_id=record.id,
                evidence=list(values[0].evidence),
            )
        ],
    )
    judge = Agent([])
    report = asyncio.run(judge_answer("Revenue change?", answer, registry, judge))
    assert support_errors(report, 1)
    assert judge.calls == []
    assert structural_errors(answer, registry, searches=1)


def test_accounting_negative_cannot_support_positive_factual_amount():
    _, registry = answer_and_registry()
    p = next(iter(registry.passages.values())).model_copy(
        update={"text": "Operating income was USD (100) million."}
    )
    registry.expose(p, p.text)
    claim = AnswerClaim(
        text="Operating income was positive USD 100 million.",
        evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
    )
    assert structural_errors(
        GroundedAnswer(status="answered", claims=[claim]), registry, searches=1
    )


@pytest.mark.parametrize(
    "text,rejected",
    [
        # Live comparison: "majority" moved from net sales to the supply chain.
        (
            "A majority of the company's supply chain comes from outside the U.S.",
            True,
        ),
        (
            "A majority of the company's total net sales come from outside the U.S.",
            False,
        ),
        ("Most of its revenue comes from outside the U.S.", True),
    ],
)
def test_quantified_subject_must_come_from_the_attached_quotes(text, rejected):
    p = passage(
        "The Company has international operations with sales outside the U.S. representing a majority of the Company's total net sales."
    )
    registry = TurnRegistry()
    registry.expose(p, p.text)
    claim = AnswerClaim(
        text=text, evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)]
    )
    errors = structural_errors(
        GroundedAnswer(status="answered", claims=[claim]), registry, searches=1
    )
    assert any("quantified subjects" in e for e in errors) == rejected


def test_fact_quotes_must_share_wording_with_the_claim():
    # Live: the judge accepted an AI claim whose only quote was "Item 8.".
    p = passage("Item 8. Risks may increase with artificial intelligence features.")
    registry = TurnRegistry()
    registry.expose(p, p.text)
    text = (
        "Apple's 2025 Form 10-K mentions artificial intelligence in its risk factors."
    )

    def errors(quote):
        claim = AnswerClaim(
            text=text, evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=quote)]
        )
        return structural_errors(
            GroundedAnswer(status="answered", claims=[claim]), registry, searches=1
        )

    assert any("absent from its attached quotes" in e for e in errors("Item 8."))
    assert errors("Risks may increase with artificial intelligence features.") == []


def test_verified_calculation_inputs_are_not_sent_for_a_second_semantic_verdict():
    import asyncio

    from app.assistant.facts import calculate_from_facts, prepare_facts
    from app.grounding.judge import judge_answer
    from tests.assistant.test_numeric_facts import prepared_context
    from tests.assistant.test_orchestrator import Agent

    d, _, p = prepared_context()
    ready = asyncio.run(prepare_facts(d, p.text))
    record = calculate_from_facts(ready.first_fact_id, ready.second_fact_id, d.registry)
    refs = list(
        {
            (r.chunk_id, r.exact_quote): r for o in record.operands for r in o.evidence
        }.values()
    )
    answer = GroundedAnswer(
        status="answered",
        claims=[
            AnswerClaim(
                text="Ratio of annual increases.",
                kind="calculation",
                calculation_id=record.id,
                evidence=refs,
            )
        ],
    )
    judge = Agent([])
    result = asyncio.run(judge_answer(d.question, answer, d.registry, judge))
    assert support_errors(result, 1) == []
    assert judge.calls == []
    d.registry.calculations[record.id] = record.model_copy(update={"result": 999})
    result = asyncio.run(judge_answer(d.question, answer, d.registry, judge))
    assert support_errors(result, 1)


def test_over_long_judge_text_is_clipped_instead_of_failing_the_verdict():
    # Strict mode moves maxLength into descriptions, so the provider never
    # enforces it; an over-long field must not discard every verdict.
    import asyncio
    import json
    from types import SimpleNamespace

    import httpx
    from openai import AsyncOpenAI

    from app.grounding.judge import build_judge, guided_report_output

    long_assessment = "Supported by the cited quote. " * 40
    claim = {
        "evidence_assessment": long_assessment,
        "supported": True,
        "reason": "supported",
    }
    gap = {
        "request_id": None,
        "request_quote": "r" * 1200,
        "warranted": True,
        "evidence_assessment": long_assessment,
    }

    def respond(request):
        return httpx.Response(
            200,
            json={
                "id": "long",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4.1-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": "v",
                                    "type": "function",
                                    "function": {
                                        "name": "final_result",
                                        "arguments": json.dumps(
                                            {"C0": claim, "G0": gap}
                                        ),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    async def check():
        config = SimpleNamespace(
            openai_grounding_model="gpt-4.1-mini",
            grounding_output_tokens=4000,
            assistant_reasoning_effort="none",
        )
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            result = await build_judge(config, client).run(
                "Question?", output_type=guided_report_output(1, 1)
            )
            return result.output

    report = asyncio.run(check())
    decision, gap_decision = report.decisions[0], report.gap_decisions[0]
    assert len(decision.evidence_assessment) == 500
    assert len(gap_decision.request_quote) == 1000


def test_server_coverage_gap_does_not_claim_the_filings_lack_evidence():
    # Live run 7: NVIDIA 2021/2025 supplier quotes were shown but not cited,
    # and the coverage gap wrongly said the filings lacked evidence.
    from app.assistant.outputs import EvidenceGap
    from app.assistant.rendering import render_answer
    from app.retrieval.types import SearchFilters

    answer, registry = answer_and_registry()
    partial = GroundedAnswer(
        status="partial",
        claims=answer.claims,
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="NVDA", corpus_years=[2021]),
                reason="missing_evidence",
            )
        ],
    )
    text = render_answer(partial, registry).text
    assert (
        "NVDA / corpus years 2021: This answer contains no verified statement for this target"
        in text
    )
    assert "do not provide" not in text


def test_structured_answer_blocks_match_the_plain_text_reply():
    from app.assistant.outputs import EvidenceGap
    from app.assistant.rendering import ADVICE_NOTICE, block_text, render_answer
    from app.retrieval.types import SearchFilters

    answer, registry = answer_and_registry()
    registry.comparison_targets = [SearchFilters(ticker="AAPL")]
    partial = GroundedAnswer(
        status="partial",
        claims=answer.claims,
        gaps=[
            EvidenceGap(
                target=SearchFilters(ticker="NVDA", corpus_years=[2021]),
                reason="missing_evidence",
            )
        ],
    )
    reply = render_answer(partial, registry, withheld=1, advice=True)
    (structured,) = [p for p in reply.parts if p["type"] == "data-answer"]
    blocks = structured["data"]["blocks"]
    assert [b["kind"] for b in blocks] == ["notice", "claim", "gap", "notice"]
    assert blocks[0]["text"] == ADVICE_NOTICE
    claim = blocks[1]
    assert claim["label"] == "AAPL / 10-K / corpus unverified"
    assert claim["citations"] == [1] and claim["claim_kind"] == "fact"
    assert blocks[2]["label"] == "NVDA / corpus years 2021"
    # The text part stays the plain-text join of the same blocks.
    assert reply.text == "\n\n".join(block_text(b) for b in blocks)
    assert reply.text.startswith(
        ADVICE_NOTICE + "\n\nAAPL / 10-K / corpus unverified: "
    )


def test_fact_claim_with_mostly_unquoted_details_fails_structurally():
    # Live Q06: the judge accepted topics the quote never named.
    quote = "The Company is subject to complex and changing laws and regulations worldwide, which exposes the Company to potential liabilities, increased costs and other adverse effects on the Company's business."
    p = passage(quote)
    registry = TurnRegistry()
    registry.expose(p, p.text)

    def errors(text):
        claim = AnswerClaim(
            text=text, evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=quote)]
        )
        return structural_errors(
            GroundedAnswer(status="answered", claims=[claim]), registry, searches=1
        )

    padded = "Apple's 10-K says its global operations are subject to complex and changing laws and regulations, including machine learning and artificial intelligence, import, export and trade, and foreign exchange controls and cash repatriation restrictions."
    assert any("absent from its attached quotes" in e for e in errors(padded))
    faithful = "Apple's 10-K says complex and changing laws and regulations worldwide expose the Company to potential liabilities and increased costs."
    assert errors(faithful) == []


def test_table_row_takes_currency_from_its_own_source_table():
    # Live Q02: Amazon prints $ only on the first and total rows.
    title = "Operating income (loss) by segment is as follows (in millions):"
    header = "| | 2023 | 2024 |"
    aws = "| AWS | 24,631 | 39,834 |"
    table = f"{header}\n| North America | $ 14,877 | $ 24,967 |\n{aws}"
    p = passage("AWS, = 24,631. AWS, = 39,834.").model_copy(
        update={"source_context": [title, table]}
    )
    registry = TurnRegistry()
    for span in (title, header, aws):
        registry.expose(p, span)
    claim = AnswerClaim(
        text="Amazon's AWS operating income was $39,834 million in 2024.",
        evidence=[
            EvidenceRef(chunk_id=p.chunk_id, exact_quote=q)
            for q in (title, header, aws)
        ],
    )
    answer = GroundedAnswer(status="answered", claims=[claim])
    assert not any(
        "currency" in e for e in structural_errors(answer, registry, searches=1)
    )
    # A table without any currency marker still fails.
    bare = p.model_copy(update={"source_context": [title, table.replace("$ ", "")]})
    registry = TurnRegistry()
    for span in (title, header, aws):
        registry.expose(bare, span)
    assert any("currency" in e for e in structural_errors(answer, registry, searches=1))


def test_clarification_gap_uses_fixed_wording_not_not_established():
    # Live: "How did revenue change last year?" read "Not established from the
    # retrieved evidence: The question does not name a company...".
    from app.assistant.rendering import GAPS, render_answer

    answer = GroundedAnswer(
        status="insufficient_evidence",
        gaps=[
            EvidenceGap(
                reason="ambiguous_question",
                missing_detail="The question does not name a company or filing year.",
            )
        ],
    )
    reply = render_answer(answer, TurnRegistry())
    assert reply.text == GAPS["ambiguous_question"]


def test_flattened_table_text_takes_currency_from_its_source_table():
    # Live Q02: drafts cited Docling's flattened copy ("North America, = (2,847).").
    title = "Operating income (loss) by segment is as follows (in millions):"
    header = "| | 2021 | 2022 |"
    table = f"{header}\n| North America | $ 7,271 | $ (2,847) |"
    flat = "North America, = (2,847)."
    p = passage(f"Segments. {flat}").model_copy(
        update={"source_context": [title, table]}
    )

    def errors(source_table):
        registry = TurnRegistry()
        q = p.model_copy(update={"source_context": [title, source_table]})
        for span in (title, flat):
            registry.expose(q, span)
        claim = AnswerClaim(
            text="Amazon's North America operating income was $(2,847) million in 2022.",
            evidence=[
                EvidenceRef(chunk_id=p.chunk_id, exact_quote=s) for s in (title, flat)
            ],
        )
        answer = GroundedAnswer(status="answered", claims=[claim])
        return [
            e
            for e in structural_errors(answer, registry, searches=1)
            if "currency" in e
        ]

    assert errors(table) == []
    assert errors(table.replace("$ ", ""))


def test_claim_may_name_its_filings_own_period_end_date():
    # Live Q01: "fiscal year ended September 30, 2023" left "30" uncited.
    from datetime import date

    p = passage("Net sales were $383,285 million in 2023.").model_copy(
        update={"report_date": date(2023, 9, 30)}
    )
    registry = TurnRegistry()
    registry.expose(p, p.text)

    def errors(text):
        claim = AnswerClaim(
            text=text, evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)]
        )
        return [
            e
            for e in structural_errors(
                GroundedAnswer(status="answered", claims=[claim]), registry, searches=1
            )
            if "uncited numeric tokens" in e
        ]

    assert (
        errors(
            "Apple's net sales were $383,285 million in 2023, for the fiscal year ended September 30, 2023."
        )
        == []
    )
    # The day alone, or another date, still needs a quote.
    assert errors("Apple's net sales were $383,285 million in 2023, up 30%.")
    assert errors(
        "Apple's net sales were $383,285 million in 2023, for the fiscal year ended September 24, 2023."
    )


@pytest.mark.parametrize(
    "detail, kept",
    [
        # Live Q02: judges dropped this although no claim gives a margin.
        ("AWS operating margin is not provided.", True),
        # The claims state operating income, so this gap is unwarranted.
        ("AWS operating income is not provided.", False),
    ],
)
def test_rejected_gap_naming_an_unanswered_requested_aspect_is_kept(detail, kept):
    import asyncio

    from app.grounding.judge import GapDecision, judge_answer
    from tests.assistant.test_orchestrator import Agent

    question = "Compare AWS operating income and margin for 2024."
    quote = "AWS operating income was $39,834 million in 2024."
    p = passage(quote)
    registry = TurnRegistry()
    registry.expose(p, p.text)
    answer = GroundedAnswer(
        status="partial",
        claims=[
            AnswerClaim(
                text=quote,
                evidence=[EvidenceRef(chunk_id=p.chunk_id, exact_quote=quote)],
            )
        ],
        gaps=[
            EvidenceGap(
                reason="missing_evidence",
                request_quote="Compare AWS operating income and margin for 2024.",
                missing_detail=detail,
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
                        evidence_assessment="Supported.",
                    )
                ],
                gap_decisions=[
                    GapDecision(
                        gap_index=0,
                        warranted=False,
                        evidence_assessment="Not a missing-evidence issue.",
                    )
                ],
            )
        ]
    )
    report = asyncio.run(judge_answer(question, answer, registry, judge))
    assert report.gap_decisions[0].warranted is kept


def test_partial_answer_keeps_a_specific_scope_limitation():
    # Live Q01: a partial Apple answer read "this request is outside that scope".
    from app.assistant.rendering import GAPS, render_answer

    answer, registry = answer_and_registry()
    gap = EvidenceGap(
        reason="outside_scope",
        missing_detail="Which category drove the mix shift is an inference.",
    )
    partial = answer.model_copy(update={"status": "partial", "gaps": [gap]})
    assert GAPS["outside_scope"] not in render_answer(partial, registry).text
    whole = GroundedAnswer(status="insufficient_evidence", gaps=[gap])
    assert render_answer(whole, registry).text == GAPS["outside_scope"]
    # Live Q04: an ambiguous_question gap read "Please clarify..." under facts.
    unclear = gap.model_copy(update={"reason": "ambiguous_question"})
    partial = answer.model_copy(update={"status": "partial", "gaps": [unclear]})
    assert GAPS["ambiguous_question"] not in render_answer(partial, registry).text


def test_large_amount_needs_the_scale_its_own_passage_states():
    # Live Q09: "revenue of $130,497" came from a table in millions.
    row = "| Revenue | $ 130,497 | $ 60,922 |"
    text = f"($ in millions, except per share data) Fiscal Year 2025 Summary. {row}"
    p = passage(text)
    registry = TurnRegistry()
    registry.expose(p, row)
    registry.expose(p, "Fiscal Year 2025 Summary.")

    def scale_errors(claim_text):
        claim = AnswerClaim(
            text=claim_text,
            evidence=[
                EvidenceRef(chunk_id=p.chunk_id, exact_quote=q)
                for q in ("Fiscal Year 2025 Summary.", row)
            ],
        )
        answer = GroundedAnswer(status="answered", claims=[claim])
        return [
            e for e in structural_errors(answer, registry, searches=1) if "scale" in e
        ]

    assert scale_errors("NVIDIA reported revenue of $130,497 for fiscal year 2025.")
    # A per-share amount is not a table total.
    p2 = passage(
        "($ in millions, except per share data) Fiscal Year 2025 EPS was $2.94."
    )
    registry.expose(p2, "Fiscal Year 2025 EPS was $2.94.")
    claim = AnswerClaim(
        text="NVIDIA reported diluted EPS of $2.94 for fiscal year 2025.",
        evidence=[
            EvidenceRef(
                chunk_id=p2.chunk_id, exact_quote="Fiscal Year 2025 EPS was $2.94."
            )
        ],
    )
    answer = GroundedAnswer(status="answered", claims=[claim])
    assert not [
        e for e in structural_errors(answer, registry, searches=1) if "scale" in e
    ]
