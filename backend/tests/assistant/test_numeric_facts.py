import asyncio
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.assistant.facts import (
    FactSelection,
    calculate_from_facts,
    numeric_candidates,
    prepare_facts,
)
from app.grounding.judge import SupportDecision, SupportReport
from tests.assistant.test_contracts import passage
from tests.assistant.test_tools import deps


class Agent:
    def __init__(self, output):
        self.output = output
        self.calls = []

    async def run(self, prompt, **kwargs):
        self.calls.append((prompt, kwargs))
        return SimpleNamespace(output=self.output)


def prepared_context():
    d = deps()
    d.question = "Ratio of reported gross-margin increase to revenue increase in fiscal 2022 compared with fiscal 2021?"
    d.settings.openai_agent_request_limit = 20
    d.settings.assistant_grounding_repairs = 1
    p = passage(
        "Fiscal Year 2022 Compared with Fiscal Year 2021\nGross margin increased $19.8 billion.\nRevenue increased $30.2 billion."
    )
    p.ticker = "MSFT"
    d.registry.expose(p, p.text)
    candidates = numeric_candidates(d, p.text)
    ids = {o.raw_number: i for i, o in candidates.items()}
    selection = FactSelection(
        operation="ratio_percent",
        first_candidate_id=ids["19.8"],
        second_candidate_id=ids["30.2"],
        segment="consolidated",
    )
    d.fact_extractor = Agent(selection)
    d.fact_judge = Agent(
        SupportReport(
            decisions=[
                SupportDecision(
                    evidence_assessment="Fixture verdict.",
                    claim_index=i,
                    supported=True,
                    reason="supported",
                )
                for i in range(2)
            ]
        )
    )
    return d, selection, p


def test_only_verified_fact_ids_can_reach_calculator():
    d, _, p = prepared_context()
    with pytest.raises(ValueError):
        calculate_from_facts(uuid4(), uuid4(), d.registry)
    ready = asyncio.run(prepare_facts(d, p.text))
    assert len(d.registry.numeric_facts) == 2
    record = calculate_from_facts(ready.first_fact_id, ready.second_fact_id, d.registry)
    assert record.display == "65.56 %"
    assert [o.raw_number for o in record.operands] == ["19.8", "30.2"]
    assert all(
        o.period == "Fiscal Year 2022 Compared with Fiscal Year 2021"
        for o in record.operands
    )
    with pytest.raises(ValueError):
        calculate_from_facts(ready.second_fact_id, ready.first_fact_id, d.registry)
    with pytest.raises(ValueError):
        calculate_from_facts(ready.first_fact_id, ready.first_fact_id, d.registry)
    assert d.fact_judge.calls and d.fact_extractor.calls


@pytest.mark.parametrize(
    "change",
    [
        {"first_candidate_id": "invented"},
        {"second_candidate_id": "n1"},
        {"operation": "difference"},
    ],
)
def test_invalid_input_never_gets_a_fact_id(change):
    d, selection, p = prepared_context()
    d.fact_extractor.output = selection.model_copy(update=change)
    with pytest.raises(ValueError):
        asyncio.run(prepare_facts(d, p.text))
    assert d.registry.numeric_facts == {} and d.registry.calculation_pairs == {}
    assert d.fact_judge.calls == []


def test_semantic_rejection_cannot_be_calculated():
    d, _, p = prepared_context()
    d.fact_judge.output = SupportReport(
        decisions=[
            SupportDecision(
                evidence_assessment="Fixture verdict.",
                claim_index=0,
                supported=False,
                reason="unit_or_period_mismatch",
            ),
            SupportDecision(
                evidence_assessment="Fixture verdict.",
                claim_index=1,
                supported=True,
                reason="supported",
            ),
        ]
    )
    with pytest.raises(ValueError):
        asyncio.run(prepare_facts(d, p.text))
    assert d.registry.numeric_facts == {} and d.registry.calculation_pairs == {}


def test_fact_ids_are_request_scoped_and_preparation_is_bounded():
    d, _, p = prepared_context()
    ready = asyncio.run(prepare_facts(d, p.text))
    other = deps()
    with pytest.raises(ValueError):
        calculate_from_facts(ready.first_fact_id, ready.second_fact_id, other.registry)
    asyncio.run(prepare_facts(d, p.text))
    with pytest.raises(ValueError):
        asyncio.run(prepare_facts(d, p.text))
    assert len(d.fact_extractor.calls) == 2


def test_no_candidates_without_explicit_period_and_units():
    d = deps()
    for text in (
        "Gross margin increased $19.8 billion.",
        "Fiscal Year 2022\nGross margin = 19.8.",
        "Fiscal Year 2022\nServices = 100. Prior Services = 80.",
    ):
        p = passage(text)
        d.registry.expose(p, p.text)
        assert numeric_candidates(d, p.text) == {}


@pytest.mark.parametrize(
    "question,rate_kept",
    [
        # Live run: offered "or 18%" as an input and divided growth rates.
        (
            "What is the ratio of the gross-margin increase to the revenue increase?",
            False,
        ),
        ("What is the ratio of the two growth rates in percent?", True),
    ],
)
def test_candidates_preserve_exact_numeric_tokens_scale_and_observed_quotes(
    question, rate_kept
):
    d = deps()
    d.question = question
    p = passage(
        "Fiscal Year 2022 Compared with Fiscal Year 2021\nRevenue increased $30.2 billion or 18%.\nLoss was $(100) million."
    )
    d.registry.expose(p, p.text)
    values = list(numeric_candidates(d, p.text).values())
    assert [(o.raw_number, o.unit) for o in values] == [
        ("30.2", "USD billions"),
        *([("18", "percent")] if rate_kept else []),
        ("(100)", "USD millions"),
    ]
    assert values[-1].value == -100
    for operand in values:
        for ref in operand.evidence:
            d.registry.verify(ref)


def test_narrative_year_mentions_do_not_replace_the_comparison_heading():
    d = deps()
    p = passage(
        "Fiscal Year 2022 Compared with Fiscal Year 2021\nGross margin changed because of the fiscal year 2021 accounting estimate.\nRevenue increased $30.2 billion."
    )
    d.registry.expose(p, p.text)
    values = list(numeric_candidates(d, p.text).values())
    assert values[0].period == "Fiscal Year 2022 Compared with Fiscal Year 2021"
