from pydantic_ai.settings import ToolOrOutput

from app.assistant.agent import guided_tool_choice
from tests.assistant.test_tools import deps


def test_explicit_arithmetic_cannot_skip_fact_preparation():
    d = deps()
    d.settings.assistant_grounding_repairs = 1
    d.question = (
        "What is the ratio of the reported gross-margin increase to revenue increase?"
    )
    assert guided_tool_choice(d) == ["prepare_calculation"]
    d.fact_preparations = 1
    choice = guided_tool_choice(d)
    assert isinstance(choice, ToolOrOutput)
    assert choice.function_tools == ["prepare_calculation"]
    d.registry.calculation_pairs[("first", "second")] = "ratio_percent"
    assert guided_tool_choice(d) == "none"
    d.registry.calculations["calculation"] = object()
    assert guided_tool_choice(d) == "none"


def test_failed_preparation_and_exhausted_budgets_can_finish_safely():
    d = deps()
    d.settings.assistant_grounding_repairs = 1
    d.question = "Calculate the percentage change."
    d.fact_preparations = 2
    assert guided_tool_choice(d) == "none"
    d.fact_preparations = 0
    d.tool_calls = d.settings.assistant_tool_calls
    assert guided_tool_choice(d) == "none"


def test_lookups_are_not_forced_into_arithmetic():
    d = deps()
    for question in (
        "What does Azure provide?",
        "What did Tesla report in 2028?",
        "How does Microsoft describe its margin risks?",
    ):
        d.question = question
        assert guided_tool_choice(d) is None
