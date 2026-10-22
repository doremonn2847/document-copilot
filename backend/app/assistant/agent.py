import re
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, Tool, ToolOutput
from pydantic_ai.capabilities import AbstractCapability
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ToolChoice, ToolOrOutput
from pydantic_ai.tools import ToolDefinition

from app.assistant.comparison_citations import prepare_comparison_citations
from app.assistant.comparisons import ComparisonReady, prepare_comparison
from app.assistant.deps import DocumentAgentDeps
from app.assistant.model_settings import StopAtOutputLimit, bounded_settings
from app.assistant.outputs import GroundedAnswer
from app.assistant.selection import final_answer
from app.assistant.tools import TOOLS, calculate

# "For each company ..." answered only Apple in a live run (client Q09) and
# never said the other four were missing.
EVERY_COMPANY = re.compile(
    r"\b(?:each|every|all(?:\s+five)?|the\s+five|these)\s+(?:of\s+the\s+)?compan(?:y|ies)\b",
    re.IGNORECASE,
)


def comparison_first(deps: DocumentAgentDeps) -> bool:
    """A whole-corpus question starts with compare_filings, one target per
    company. The instructions say so, yet a rerun of client Q09 searched only
    Apple twice and answered for Apple alone."""
    return bool(EVERY_COMPANY.search(deps.question)) and deps.tool_calls == 0


class EvidenceChoices(AbstractCapability[DocumentAgentDeps]):
    async def prepare_output_tools(
        self, ctx: RunContext[DocumentAgentDeps], tool_defs: list[ToolDefinition]
    ) -> list[ToolDefinition]:
        if ctx.deps is None:
            return tool_defs
        prepared = []
        calculation_ready = (
            bool(ctx.deps.registry.calculation_pairs)
            and not ctx.deps.registry.calculations
            and ctx.deps.tool_calls < ctx.deps.settings.assistant_tool_calls
        )
        for tool in tool_defs:
            if comparison_first(ctx.deps) and tool.name != "compare_filings":
                continue
            if tool.name == "calculate":
                if not calculation_ready:
                    continue
                schema = deepcopy(tool.parameters_json_schema)
                pairs = list(ctx.deps.registry.calculation_pairs)
                schema["properties"]["first_fact_id"]["enum"] = [
                    str(pair[0]) for pair in pairs
                ]
                schema["properties"]["second_fact_id"]["enum"] = [
                    str(pair[1]) for pair in pairs
                ]
                prepared.append(replace(tool, parameters_json_schema=schema))
                continue
            if calculation_ready:
                continue
            if tool.name == "compare_filings":
                if (
                    not ctx.deps.fact_preparations
                    and ctx.deps.tool_calls < ctx.deps.settings.assistant_tool_calls
                    and ctx.deps.searches < ctx.deps.settings.assistant_search_calls
                ):
                    prepared.append(tool)
                continue
            schema = deepcopy(tool.parameters_json_schema)
            if "ComparisonFact" in schema["$defs"]:
                prepare_comparison_citations(schema, ctx.deps)
            else:
                properties = schema["$defs"]["SelectedClaim"]["properties"]
                if ctx.deps.registry.evidence_refs:
                    properties["evidence_ids"]["items"]["enum"] = list(
                        ctx.deps.registry.evidence_refs
                    )
                properties["calculation_id"]["enum"] = [
                    None,
                    *(str(key) for key in ctx.deps.registry.calculations),
                ]
            if "ComparisonGap" in schema.get("$defs", {}):
                schema["$defs"]["ComparisonGap"]["properties"]["request_id"]["enum"] = (
                    list(ctx.deps.registry.request_spans)
                )
            prepared.append(replace(tool, parameters_json_schema=schema))
        return prepared


def guided_tool_choice(deps: DocumentAgentDeps | None) -> ToolChoice:
    if deps is None:
        return None
    if comparison_first(deps):
        return ToolOrOutput([])
    # Indirect requests can still choose preparation; explicit arithmetic cannot skip it.
    explicit = re.search(
        r"\b(?:calculate|compute)\b|\bratio\s+(?:of|between)\b|\b(?:percentage|percent)\s+change\b|\bpercentage[- ]point\s+difference\b",
        deps.question,
        re.IGNORECASE,
    )
    if not explicit and not deps.fact_preparations:
        return None
    if (
        deps.tool_calls >= deps.settings.assistant_tool_calls
        or deps.registry.calculations
    ):
        return "none"
    if deps.registry.calculation_pairs:
        return "none"
    if not explicit:
        # The model chose arithmetic for a question that did not ask for it,
        # often a change the filing states itself ("Revenue increased $33.2
        # billion"). Live, forcing preparation-or-answer after a rejected pair
        # left only a refusal; let it search for the statement instead.
        return None
    if (
        deps.fact_preparations >= deps.settings.assistant_grounding_repairs + 1
        or deps.searches >= deps.settings.assistant_search_calls
    ):
        return "none"
    if deps.fact_preparations:
        return ToolOrOutput(["prepare_calculation"])
    return ["prepare_calculation"]


def available_tool(
    ctx: RunContext[DocumentAgentDeps], tool: ToolDefinition
) -> ToolDefinition | None:
    if ctx.deps is None:
        return tool
    if ctx.deps.tool_calls >= ctx.deps.settings.assistant_tool_calls:
        return None
    if (
        tool.name in ("search_filings", "compare_filings", "prepare_calculation")
        and ctx.deps.searches >= ctx.deps.settings.assistant_search_calls
    ):
        return None
    return tool


def build_agent(
    settings, client: AsyncOpenAI
) -> Agent[DocumentAgentDeps, GroundedAnswer | ComparisonReady]:
    return Agent(
        OpenAIChatModel(
            settings.openai_chat_model, provider=OpenAIProvider(openai_client=client)
        ),
        deps_type=DocumentAgentDeps,
        capabilities=[EvidenceChoices(), StopAtOutputLimit("answering")],
        output_type=[
            ToolOutput(final_answer, name="final_result", strict=True),
            ToolOutput(calculate, name="calculate", strict=True),
            ToolOutput(prepare_comparison, name="compare_filings", strict=True),
        ],
        tools=[
            Tool(tool, prepare=available_tool, strict=True)
            for tool in TOOLS
            if tool.__name__ != "compare_filings"
        ],
        retries={"output": settings.assistant_output_retries, "tools": 0},
        instructions=Path(__file__)
        .with_name("instructions.md")
        .read_text(encoding="utf-8"),
        model_settings=lambda ctx: {
            **bounded_settings(
                settings.openai_chat_model,
                settings.assistant_output_tokens,
                settings.assistant_reasoning_effort,
            ),
            "parallel_tool_calls": False,
            "tool_choice": guided_tool_choice(ctx.deps),
        },
    )
