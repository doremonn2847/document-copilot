from decimal import Decimal
from uuid import uuid4

import pytest

from app.assistant.calculations import Operand, calculate
from app.assistant.deps import TurnRegistry
from app.assistant.outputs import EvidenceRef
from tests.assistant.test_contracts import passage


def operands():
    p = passage(
        "2024 annual revenue 1,000 USD millions; 2023 annual revenue 0.8 USD billions."
    )
    registry = TurnRegistry()
    registry.expose(p, p.text)
    ref = EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)
    common = {
        "measure": "revenue",
        "entity": "AAPL",
        "segment": "total",
        "period_type": "annual",
        "evidence": [ref],
    }
    return registry, [
        Operand(
            raw_number="1,000",
            value="1000",
            unit="USD millions",
            period="2024",
            **common,
        ),
        Operand(
            raw_number="0.8", value="0.8", unit="USD billions", period="2023", **common
        ),
    ]


def test_currency_normalization_and_recorded_rounding():
    registry, values = operands()
    record = calculate("percent_change", values, registry)
    assert record.result == Decimal(25)
    assert record.display == "25.00 %"
    assert registry.calculations[record.id] == record


@pytest.mark.parametrize(
    "change",
    [
        {"raw_number": "999", "value": "999"},
        {"value": "NaN"},
        {"value": "0.8", "raw_number": "0.8", "unit": "EUR"},
        {"segment": "unrelated"},
        {"period_type": "quarter"},
    ],
)
def test_reject_forged_or_incompatible_operand(change):
    registry, values = operands()
    with pytest.raises(ValueError):
        values[1] = Operand.model_validate({**values[1].model_dump(), **change})
        calculate("percent_change", values, registry)


def test_unseen_numeric_evidence_rejected():
    registry, values = operands()
    values[0] = values[0].model_copy(
        update={"evidence": [EvidenceRef(chunk_id=uuid4(), exact_quote="1,000")]}
    )
    with pytest.raises(ValueError):
        calculate("difference", values, registry)


def test_ratio_requires_same_period():
    registry, values = operands()
    with pytest.raises(ValueError):
        calculate("ratio_percent", values, registry)


@pytest.mark.parametrize("negative", ["(100)", "( 100 )"])
def test_parenthesized_negative_cannot_be_used_as_a_positive_token(negative):
    p = passage(f"2025 annual revenue {negative} USD; 2024 prior revenue 80 USD")
    registry = TurnRegistry()
    registry.expose(p, p.text)
    ref = EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)
    common = {
        "measure": "revenue",
        "entity": "AAPL",
        "segment": "total",
        "period_type": "annual",
        "unit": "USD",
        "evidence": [ref],
    }
    current = Operand(raw_number="100", value=100, period="2025", **common)
    prior = Operand(raw_number="80", value=80, period="2024", **common)
    with pytest.raises(ValueError):
        calculate("difference", [current, prior], registry)
    signed = Operand(raw_number=negative, value=-100, period="2025", **common)
    assert calculate("difference", [signed, prior], registry).display == "-180.00 USD"


@pytest.mark.parametrize("raw,value", [("0", 0), ("(100)", -100)])
def test_growth_rejects_nonpositive_bases(raw, value):
    registry, values = operands()
    p = passage(f"2023 annual revenue base {raw} USD millions.")
    registry.expose(p, p.text)
    values[1] = Operand.model_validate(
        {
            **values[1].model_dump(),
            "raw_number": raw,
            "value": value,
            "unit": "USD millions",
            "evidence": [EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
        }
    )
    with pytest.raises(ValueError, match="Denominator must be positive"):
        calculate("percent_change", values, registry)


def test_percentage_point_difference_and_round_half_up():
    from decimal import getcontext

    p = passage("2025 margin 12.345 percent; 2024 margin 10 percent.")
    registry = TurnRegistry()
    registry.expose(p, p.text)
    common = {
        "measure": "margin",
        "entity": "AAPL",
        "segment": "total",
        "period_type": "annual",
        "unit": "percent",
        "evidence": [EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
    }
    before = getcontext().prec
    result = calculate(
        "difference",
        [
            Operand(raw_number="12.345", value="12.345", period="2025", **common),
            Operand(raw_number="10", value=10, period="2024", **common),
        ],
        registry,
    )
    assert (
        result.result == Decimal("2.345") and result.display == "2.35 percentage points"
    )
    assert getcontext().prec == before


@pytest.mark.parametrize(
    "quote",
    [
        "Services = 100. Prior Services = 80.",
        "2025 Services = 100. 2024 Services = 80.",
    ],
)
def test_numeric_tokens_without_period_and_unit_evidence_are_not_enough(quote):
    p = passage(quote)
    registry = TurnRegistry()
    registry.expose(p, p.text)
    common = {
        "measure": "Services net sales",
        "entity": "AAPL",
        "segment": "Services",
        "period_type": "annual",
        "unit": "USD",
        "evidence": [EvidenceRef(chunk_id=p.chunk_id, exact_quote=p.text)],
    }
    values = [
        Operand(raw_number="100", value=100, period="2025", **common),
        Operand(raw_number="80", value=80, period="2024", **common),
    ]
    with pytest.raises(ValueError):
        calculate("percent_change", values, registry)


@pytest.mark.parametrize("operation", ["difference", "percent_change"])
def test_same_measure_and_period_is_not_a_change(operation):
    # Live: two segments' "Revenue increased" amounts for the same fiscal-year
    # comparison, both labelled consolidated, were subtracted and accepted.
    registry, values = operands()
    values[1] = values[1].model_copy(update={"period": values[0].period})
    with pytest.raises(ValueError, match="two different periods"):
        calculate(operation, values, registry)
