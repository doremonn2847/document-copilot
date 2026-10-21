import re
from dataclasses import replace
from decimal import ROUND_HALF_UP, Decimal, DecimalException, localcontext
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field

from app.assistant.deps import TurnRegistry, normalized
from app.assistant.outputs import Contract, EvidenceRef

Operation = Literal["ratio_percent", "percent_change", "difference"]
UNSIGNED_NUMBER = r"(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d+)?"
SOURCE_NUMBER = re.compile(
    rf"\(\s*{UNSIGNED_NUMBER}\s*\)|(?<![\w.,(-])-?{UNSIGNED_NUMBER}(?!\w|[.,]\d|\))"
)


class Operand(Contract):
    raw_number: str = Field(min_length=1, max_length=80)
    value: Decimal
    measure: str = Field(min_length=1, max_length=100)
    entity: str = Field(min_length=1, max_length=100)
    segment: str = Field(min_length=1, max_length=100)
    unit: Literal["USD", "USD millions", "USD billions", "percent", "count"]
    period: str = Field(min_length=1, max_length=100)
    period_type: Literal["annual", "quarter", "instant"]
    evidence: tuple[EvidenceRef, ...] = Field(min_length=1, max_length=5)


class CalculationRecord(Contract):
    id: UUID
    operation: Operation
    operands: tuple[Operand, Operand]
    formula: str
    result: Decimal
    display: str


def parse_number(raw: str) -> Decimal:
    if not re.fullmatch(
        rf"(?:-?{UNSIGNED_NUMBER}|\(\s*{UNSIGNED_NUMBER}\s*\))",
        raw,
    ):
        raise ValueError("Unsupported numeric token")
    value = raw.replace(",", "")
    return (
        Decimal(value[1:-1].strip()).copy_negate()
        if value.startswith("(")
        else Decimal(value)
    )


def quoted_number_is_complete(
    operand: Operand, ref: EvidenceRef, registry: TurnRegistry
) -> bool:
    source = normalized(registry.passages[ref.chunk_id].text)
    quote = normalized(ref.exact_quote)
    raw = normalized(operand.raw_number)
    tokens = [token for token in SOURCE_NUMBER.finditer(source) if token.group() == raw]
    return any(
        occurrence.start() <= token.start() and token.end() <= occurrence.end()
        for occurrence in re.finditer(re.escape(quote), source)
        for token in tokens
    )


SCALES = {
    "USD": Decimal(1),
    "USD millions": Decimal(1000000),
    "USD billions": Decimal(1000000000),
    "percent": Decimal(1),
    "count": Decimal(1),
}


def validate_operand(operand: Operand, registry: TurnRegistry) -> None:
    if (
        not operand.value.is_finite()
        or parse_number(operand.raw_number) != operand.value
    ):
        raise ValueError("Numeric token and finite value must agree")
    for ref in operand.evidence:
        registry.verify(ref)
    if not any(
        quoted_number_is_complete(operand, ref, registry) for ref in operand.evidence
    ):
        raise ValueError("Numeric token absent from cited evidence")
    if operand.unit not in SCALES:
        raise ValueError("Unsupported unit")
    quoted = " ".join(ref.exact_quote for ref in operand.evidence).casefold()
    years = re.findall(r"\b\d{4}\b", operand.period)
    if not years or any(year not in quoted for year in years):
        raise ValueError(
            "Operand period needs an explicit year in its cited source quotes"
        )
    currency_label = bool(re.search(r"\busd\b|\bdollars?\b|\$", quoted))
    if operand.unit == "USD millions" and not (currency_label and "million" in quoted):
        raise ValueError("Cite the currency and millions scale for this operand")
    if operand.unit == "USD billions" and not (currency_label and "billion" in quoted):
        raise ValueError("Cite the currency and billions scale for this operand")
    if operand.unit == "USD" and (
        not re.search(r"\busd\b|\bdollars?\b", quoted)
        or "million" in quoted
        or "billion" in quoted
    ):
        raise ValueError(
            "Cite an explicit unscaled USD unit or use the cited millions/billions scale"
        )
    if operand.unit == "percent" and not ("%" in quoted or "percent" in quoted):
        raise ValueError("Cite a percentage unit for this operand")


def validate_inputs(
    operation: Operation, operands: list[Operand], registry: TurnRegistry
) -> None:
    if len(operands) != 2:
        raise ValueError("Exactly two operands required")
    for operand in operands:
        validate_operand(operand, registry)
    a, b = operands
    currency = lambda unit: unit.startswith("USD")
    if (a.entity, a.segment, a.period_type) != (b.entity, b.segment, b.period_type):
        raise ValueError("Entity, segment and period type must agree")
    if a.unit != b.unit and not (currency(a.unit) and currency(b.unit)):
        raise ValueError("Incompatible units")
    if operation == "ratio_percent" and a.period != b.period:
        raise ValueError("Ratio periods must agree")
    if operation != "ratio_percent" and a.measure != b.measure:
        raise ValueError("Measures must agree")
    if operation in ("ratio_percent", "percent_change") and b.value <= 0:
        raise ValueError("Denominator must be positive")


def calculate(
    operation: Operation, operands: list[Operand], registry: TurnRegistry
) -> CalculationRecord:
    validate_inputs(operation, operands, registry)
    a, b = operands
    currency = lambda unit: unit.startswith("USD")
    try:
        with localcontext() as ctx:
            ctx.prec = 28
            x, y = a.value * SCALES[a.unit], b.value * SCALES[b.unit]
            if operation in ("ratio_percent", "percent_change") and y <= 0:
                raise ValueError("Denominator must be positive")
            if operation == "ratio_percent":
                value, formula, unit = 100 * x / y, "100 * numerator / denominator", "%"
            elif operation == "percent_change":
                value, formula, unit = (
                    100 * (x - y) / y,
                    "100 * (current - prior) / prior",
                    "%",
                )
            elif operation == "difference":
                value, formula = x - y, "first - second"
                unit = (
                    "percentage points"
                    if a.unit == "percent"
                    else "USD"
                    if currency(a.unit)
                    else a.unit
                )
            else:
                raise ValueError("Unsupported operation")
            if not value.is_finite():
                raise ValueError("Non-finite result")
            display = (
                f"{value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)} {unit}"
            )
    except DecimalException as error:
        raise ValueError("Calculation exceeds supported numeric range") from error
    record = CalculationRecord(
        id=uuid4(),
        operation=operation,
        operands=tuple(operands),
        formula=formula,
        result=value,
        display=display,
    )
    registry.calculations[record.id] = record
    return record


def validate_record(record: CalculationRecord, registry: TurnRegistry) -> None:
    # Recompute without mutating the request's accepted calculation registry.
    expected = calculate(
        record.operation, list(record.operands), replace(registry, calculations={})
    )
    if (record.result, record.display, record.formula) != (
        expected.result,
        expected.display,
        expected.formula,
    ):
        raise ValueError("Calculation record does not match its verified inputs")
