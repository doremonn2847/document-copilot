from types import SimpleNamespace

import pytest
from pydantic_ai import ModelRetry

from app.assistant.selection import SelectedClaim, final_answer
from app.assistant.tools import expose_groups
from app.retrieval.types import SearchFilters
from tests.assistant.test_contracts import passage
from tests.assistant.test_tools import deps


def test_selected_ids_restore_exact_sources_and_preserve_missing_targets():
    d = deps()
    p = passage(
        "Azure provides compute. Other revenue details. Azure provides storage."
    )
    p = p.model_copy(update={"ticker": "MSFT", "corpus_year": 2025})
    d.registry.comparison_targets = [
        SearchFilters(ticker="MSFT", corpus_years=[year]) for year in (2024, 2025)
    ]
    output = expose_groups(d, [("MSFT", [p])], full=True)
    selected = [
        key
        for key, ref in d.registry.evidence_refs.items()
        if "Azure provides" in ref.exact_quote
    ]
    assert selected and all(key in output for key in selected)
    result = final_answer(
        SimpleNamespace(deps=d),
        [
            SelectedClaim(
                text="Azure provides compute and storage.", evidence_ids=selected
            )
        ],
        [],
    )
    assert result.status == "partial"
    assert result.gaps[0].target.corpus_years == [2024]
    for ref in result.claims[0].evidence:
        d.registry.verify(ref)
        assert ref.chunk_id == p.chunk_id
    from app.assistant.rendering import render_answer

    assert "MSFT / 10-K / corpus 2025:" in render_answer(result, d.registry).text
    assert "Other revenue details" not in " ".join(
        r.exact_quote for r in result.claims[0].evidence
    )


def test_unknown_evidence_id_is_not_replaced_with_a_nearby_source():
    d = deps()
    expose_groups(d, [("Source", [passage()])])
    with pytest.raises(ModelRetry, match="Unknown evidence"):
        final_answer(
            SimpleNamespace(deps=d),
            [
                SelectedClaim(
                    text="Revenue was 100 million dollars.", evidence_ids=["E999"]
                )
            ],
            [],
        )


def test_cross_company_submission_requires_its_own_company_sources():
    d = deps()
    apple = passage("We depend on outsourcing partners.").model_copy(
        update={"ticker": "AAPL", "corpus_year": 2021}
    )
    nvidia = passage("Our suppliers may be unable to meet demand.").model_copy(
        update={"ticker": "NVDA", "corpus_year": 2025}
    )
    expose_groups(d, [("Apple", [apple]), ("NVIDIA", [nvidia])])
    apple_id = next(
        k for k, r in d.registry.evidence_refs.items() if r.chunk_id == apple.chunk_id
    )
    nvidia_id = next(
        k for k, r in d.registry.evidence_refs.items() if r.chunk_id == nvidia.chunk_id
    )
    claim = SelectedClaim(
        text="Apple and NVIDIA describe supplier dependence.",
        kind="interpretation",
        evidence_ids=[apple_id],
    )
    with pytest.raises(ModelRetry, match="NVDA") as failure:
        final_answer(SimpleNamespace(deps=d), [claim], [])
    assert nvidia_id in str(failure.value)
    assert "corpus 2025" in str(failure.value)
    assert d.registry.evidence_refs[apple_id].chunk_id == apple.chunk_id
    assert claim.evidence_ids == [apple_id]
    corrected = claim.model_copy(update={"evidence_ids": [apple_id, nvidia_id]})
    answer = final_answer(SimpleNamespace(deps=d), [corrected], [])
    assert {r.chunk_id for r in answer.claims[0].evidence} == {
        apple.chunk_id,
        nvidia.chunk_id,
    }


def test_company_submission_error_does_not_invent_missing_sources():
    d = deps()
    expose_groups(d, [("Apple", [passage("We depend on suppliers.")])])
    claim = SelectedClaim(
        text="Apple and NVIDIA describe supplier dependence.",
        kind="interpretation",
        evidence_ids=list(d.registry.evidence_refs),
    )
    with pytest.raises(ModelRetry, match="NVDA") as failure:
        final_answer(SimpleNamespace(deps=d), [claim], [])
    assert "Observed candidate IDs" in str(failure.value)
    assert "{}" in str(failure.value)


def test_sdk_repairs_company_citations_at_submission_without_another_agent_run():
    import asyncio
    import json

    import httpx
    from openai import AsyncOpenAI
    from pydantic_ai.usage import UsageLimits

    from app.assistant.agent import build_agent

    d = deps()
    for name, value in {
        "openai_chat_model": "gpt-4o-mini",
        "assistant_output_tokens": 2000,
        "assistant_output_retries": 1,
    }.items():
        setattr(d.settings, name, value)
    apple = passage("We depend on outsourcing partners.")
    nvidia = passage("We depend on third-party suppliers.").model_copy(
        update={"ticker": "NVDA", "corpus_year": 2025}
    )
    expose_groups(d, [("Apple", [apple]), ("NVIDIA", [nvidia])])
    requests = []

    def respond(request):
        body = json.loads(request.content)
        requests.append(body)
        output = {
            "claims": [
                {
                    "text": "Apple and NVIDIA describe supplier dependence.",
                    "kind": "interpretation",
                    "evidence_ids": ["E1"] if len(requests) == 1 else ["E1", "E2"],
                    "calculation_id": None,
                }
            ],
            "gaps": [],
        }
        return httpx.Response(
            200,
            json={
                "id": "submission-repair",
                "object": "chat.completion",
                "created": 0,
                "model": "gpt-4o-mini",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "tool_calls": [
                                {
                                    "id": f"output-{len(requests)}",
                                    "type": "function",
                                    "function": {
                                        "name": "final_result",
                                        "arguments": json.dumps(output),
                                    },
                                }
                            ],
                        },
                    }
                ],
            },
        )

    async def check():
        async with (
            httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http,
            AsyncOpenAI(api_key="unit-test", http_client=http, max_retries=0) as client,
        ):
            result = await build_agent(d.settings, client).run(
                "Compare Apple and NVIDIA.",
                deps=d,
                usage_limits=UsageLimits(request_limit=2),
            )
            assert {r.chunk_id for r in result.output.claims[0].evidence} == {
                apple.chunk_id,
                nvidia.chunk_id,
            }

    asyncio.run(check())
    assert len(requests) == 2
    feedback = json.dumps(requests[1]["messages"])
    assert "Observed candidate IDs" in feedback
    assert "NVDA / corpus 2025" in feedback
    assert d.registry.evidence_refs["E1"].chunk_id == apple.chunk_id


def test_evidence_labels_are_case_insensitive_but_still_exact_ids():
    d = deps()
    expose_groups(d, [("Source", [passage()])])
    key = next(iter(d.registry.evidence_refs))
    answer = final_answer(
        SimpleNamespace(deps=d),
        [
            SelectedClaim(
                text="Revenue was 100 million dollars.", evidence_ids=[key.lower()]
            )
        ],
        [],
    )
    assert answer.claims[0].evidence == [d.registry.evidence_refs[key]]


def test_only_emitted_spans_receive_ids_and_repeated_reads_keep_ids():
    d = deps()
    p = passage("Visible evidence. " + "x" * 1000 + " Hidden ending.")
    first = expose_groups(d, [("Source", [p])])
    ids = dict(d.registry.evidence_refs)
    assert ids
    for ref in ids.values():
        assert ref.exact_quote in first
        assert "Hidden ending" not in ref.exact_quote
    expose_groups(d, [("Source", [p])])
    assert d.registry.evidence_refs == ids


def test_truncated_sentence_is_preview_only_and_cannot_be_selected():
    d = deps()
    first = "Complete disclosed fact."
    p = passage(
        first + " Restrictions on international trade can increase the supply risks."
    )
    d.settings.assistant_evidence_chars = len(
        first + " Restrictions on international trade can increase the"
    )
    output = expose_groups(d, [("Source", [p])])
    assert "Preview" in output
    assert [ref.exact_quote for ref in d.registry.evidence_refs.values()] == [first]
    for key, ref in d.registry.evidence_refs.items():
        assert f"[{key}] {ref.exact_quote}" in output


def test_calculation_uses_registered_input_citations_without_model_transcription():
    from app.assistant.calculations import calculate
    from tests.assistant.test_calculations import operands

    d = deps()
    d.registry, values = operands()
    record = calculate("percent_change", values, d.registry)
    result = final_answer(
        SimpleNamespace(deps=d),
        [
            SelectedClaim(
                text="Revenue increase.", kind="calculation", calculation_id=record.id
            )
        ],
        [],
    )
    assert result.claims[0].evidence == list(values[0].evidence)
    assert result.claims[0].calculation_id == record.id


def test_factual_claim_cannot_combine_different_filings():
    from app.grounding.validator import structural_errors

    d = deps()
    expose_groups(
        d, [("Sources", [passage("Demand grew."), passage("Supply risks remain.")])]
    )
    answer = final_answer(
        SimpleNamespace(deps=d),
        [
            SelectedClaim(
                text="Demand grew and supply risks increased over time.",
                evidence_ids=list(d.registry.evidence_refs),
            )
        ],
        [],
    )
    assert any(
        "one filing" in error
        for error in structural_errors(answer, d.registry, searches=1)
    )


def test_broad_comparison_gaps_become_individual_periods_without_duplicates():
    from app.assistant.outputs import EvidenceGap

    d = deps()
    d.registry.comparison_targets = [
        SearchFilters(ticker="MSFT", corpus_years=[y]) for y in (2021, 2022)
    ]
    d.question = "Compare MSFT 2021 and 2022."
    result = final_answer(
        SimpleNamespace(deps=d),
        [],
        [
            EvidenceGap(
                target=SearchFilters(ticker="MSFT", corpus_years=[2021, 2022]),
                reason="missing_evidence",
                request_quote="MSFT 2021 and 2022",
            )
        ],
    )
    assert [g.target.corpus_years for g in result.gaps] == [[2021], [2022]]


def test_specific_comparison_limitation_is_not_copied_to_supported_years():
    from app.assistant.outputs import EvidenceGap
    from app.assistant.rendering import render_answer
    from app.grounding.validator import structural_errors

    d = deps()
    d.question = "Compare Apple across corpus years 2021–2025 and assess urgency."
    d.registry.comparison_targets = [
        SearchFilters(ticker="AAPL", corpus_years=[year]) for year in range(2021, 2026)
    ]
    claims = []
    for year in range(2022, 2026):
        p = passage("Manufacturing depends on outsourcing partners.").model_copy(
            update={"ticker": "AAPL", "corpus_year": year}
        )
        expose_groups(d, [(str(year), [p])])
        key = next(
            key
            for key, ref in d.registry.evidence_refs.items()
            if ref.chunk_id == p.chunk_id
        )
        claims.append(SelectedClaim(text=p.text, evidence_ids=[key]))
    detail = "The full urgency comparison is limited by missing 2021 evidence."
    gap = EvidenceGap(
        target=SearchFilters(ticker="AAPL", corpus_years=list(range(2021, 2026))),
        reason="missing_evidence",
        missing_detail=detail,
        request_quote="assess urgency",
    )
    answer = final_answer(SimpleNamespace(deps=d), claims, [gap, gap])
    rendered = render_answer(answer, d.registry).text
    assert rendered.count(detail) == 1
    assert answer.gaps[0].target.corpus_years == list(range(2021, 2026))
    assert len(answer.gaps) == 2
    assert answer.gaps[1].target.corpus_years == [2021]
    assert answer.gaps[1].missing_detail is None
    assert not structural_errors(answer, d.registry, searches=1)
    for year in range(2022, 2026):
        assert f"AAPL / corpus years {year}: Not established" not in rendered


def test_source_span_count_stays_within_provider_schema_enum_limit():
    from app.assistant.deps import MAX_EVIDENCE_SPANS

    d = deps()
    for group in range(10):
        p = passage(" ".join(f"Disclosed fact {group}-{i}." for i in range(100)))
        output = expose_groups(d, [("Source", [p])], full=True)
    assert len(d.registry.evidence_refs) == MAX_EVIDENCE_SPANS
    assert "omitted" in output and "span limits" in output


@pytest.mark.parametrize(
    "quote", [None, "Explicit quoted fiscal-period heading", "   "]
)
def test_model_gap_requires_a_real_quote_from_user_request(quote):
    from app.assistant.outputs import EvidenceGap

    d = deps()
    d.question = "What does Microsoft's 2025 filing say Azure provides? Cite the supporting passages."
    p = passage("Azure provides compute.").model_copy(
        update={"ticker": "MSFT", "corpus_year": 2025}
    )
    expose_groups(d, [("MSFT 2025", [p])])
    payload = {
        "reason": "missing_evidence",
        "missing_detail": "Need an explicit fiscal-period heading.",
    }
    if quote is not None:
        payload["request_quote"] = quote
    gap = EvidenceGap.model_construct(**payload)
    with pytest.raises(ModelRetry, match="request_quote"):
        final_answer(
            SimpleNamespace(deps=d),
            [SelectedClaim(text=p.text, evidence_ids=list(d.registry.evidence_refs))],
            [gap],
        )


def test_requested_gap_anchor_and_server_missing_targets_remain_distinct():
    from app.assistant.outputs import EvidenceGap

    d = deps()
    d.question = "Describe Azure and provide its pricing."
    d.registry.comparison_targets = [SearchFilters(ticker="MSFT", corpus_years=[2024])]
    gap = EvidenceGap(
        reason="missing_evidence",
        missing_detail="Azure pricing",
        request_quote="provide its pricing",
    )
    result = final_answer(SimpleNamespace(deps=d), [], [gap])
    assert result.gaps[0].request_quote == "provide its pricing"
    assert result.gaps[1].target.corpus_years == [2024]
    assert result.gaps[1].request_quote is None
