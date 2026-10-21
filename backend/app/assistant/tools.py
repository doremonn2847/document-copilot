import asyncio
import json
import re
from functools import wraps
from itertools import product
from uuid import UUID

from pydantic_ai import ModelRetry, RunContext

from app.assistant.deps import MAX_EVIDENCE_SPANS, BudgetExceeded, DocumentAgentDeps
from app.assistant.excerpts import focus_terms, focused_excerpt, relevance, table_rows
from app.assistant.facts import calculate_from_facts, prepare_facts
from app.assistant.outputs import MAX_QUOTE_CHARS, GroundedAnswer
from app.assistant.rendering import calculation_text
from app.assistant.selection import SelectedClaim, final_answer
from app.grounding.judge import InvalidSupportReport
from app.retrieval.types import RetrievedPassage, SearchFilters


def bounded_tool(function):
    @wraps(function)
    async def call(ctx, *args, **kwargs):
        try:
            output = await function(ctx, *args, **kwargs)
        except BudgetExceeded:
            return "[Tool budget exhausted. No operation executed. Return supported partial claims or explicit evidence gaps now; do not call more tools.]"
        remaining = max(0, ctx.deps.settings.assistant_tool_calls - ctx.deps.tool_calls)
        return (
            output
            + f"\n[Remaining tool calls: {remaining}. Prioritize a supported final answer; report gaps rather than exhausting the budget.]"
        )

    return call


def expose_groups(
    deps: DocumentAgentDeps,
    groups: list[tuple[str, list[RetrievedPassage]]],
    *,
    full: bool = False,
    selectable: bool = True,
    focus: str | None = None,
    limit: int | None = None,
) -> str:
    # Reserve every target's coverage and candidate IDs before allocating excerpts.
    headers = [
        f"{label}: {'matched' if items else 'NO EVIDENCE'}; IDs: {', '.join(str(p.chunk_id) for p in items)}"
        for label, items in groups
    ]
    output = "\n".join(headers) + "\n"
    limit = limit or deps.settings.assistant_tool_chars
    if len(output) + 100 > limit:
        raise ValueError("Coverage headers exceed tool response limit")
    nonempty = sum(bool(items) for _, items in groups)
    share = (limit - len(output) - 900) // max(nonempty, 1)
    seen = set()
    primary_ids = {p.chunk_id for _, items in groups for p in items}
    omitted = 0
    terms = focus_terms(focus or "")
    for label, items in groups:
        remaining = share
        neighbors = [
            n for p in items for n in p.neighbors if n.chunk_id not in primary_ids
        ]
        for p in [*items, *neighbors]:
            if p.chunk_id in seen:
                continue
            seen.add(p.chunk_id)
            if (
                p.chunk_id not in deps.registry.passages
                and len(deps.registry.passages) >= deps.settings.assistant_max_chunks
            ):
                omitted += 1
                continue
            prefix = (
                f"\n[{p.chunk_id}] {p.ticker} {p.form}; corpus={p.corpus_year}; "
                f"fiscal_year={p.fiscal_year or 'unverified'}; filed={p.filing_date}; "
                f"report={p.report_date}; page={p.page or 'unverified'}; chunk={p.chunk_index}\n"
            )
            context_output = ""
            if selectable and (
                not terms or relevance("\n".join(p.source_context), terms)
            ):
                for source_span in p.source_context:
                    room = min(
                        remaining - len(prefix) - len(context_output) - 45,
                        deps.settings.assistant_evidence_chars
                        - deps.registry.exposed_characters,
                    )
                    spans = [source_span]
                    # Whole tables can exceed one quote's limit even when they fit
                    # the room; a live search tool failed on such a span.
                    if len(source_span) > min(room, MAX_QUOTE_CHARS):
                        spans = (
                            table_rows(source_span, room, terms)
                            if source_span.startswith("|")
                            else []
                        )
                    for span in spans:
                        if len(deps.registry.evidence_refs) >= MAX_EVIDENCE_SPANS:
                            break
                        key = deps.registry.evidence_id(p, span)
                        context_output += f"[{key}] {span}\n"
            if context_output:
                prefix += "[Verbatim original-source table context]\n" + context_output
            room = min(
                remaining - len(prefix) - 30,
                deps.settings.assistant_evidence_chars
                - deps.registry.exposed_characters,
            )
            excerpt = focused_excerpt(
                p.text,
                max(0, min(room, len(p.text) if full else 800)),
                terms if selectable else set(),
            )
            if not excerpt and not context_output:
                omitted += 1
                continue
            displayed = excerpt
            truncated = excerpt != p.text
            if selectable:
                pieces = []
                budget = remaining - len(prefix) - 30
                source_parts = re.split(r"(?<=[.!?])\s+|\n+", p.text)
                complete_spans = {
                    part.strip() for part in source_parts[:-1] if part.strip()
                }
                if source_parts[-1].strip().endswith((".", "!", "?")):
                    complete_spans.add(source_parts[-1].strip())
                for span in re.split(r"(?<=[.!?])\s+|\n+", excerpt):
                    span = span.strip()
                    if not span:
                        continue
                    if len(deps.registry.evidence_refs) >= MAX_EVIDENCE_SPANS:
                        truncated = True
                        omitted += 1
                        break
                    original_span = span
                    # Reserve ID syntax before registering only text actually emitted.
                    span = span[
                        : max(
                            0,
                            min(
                                4000,
                                budget - 14,
                                deps.settings.assistant_evidence_chars
                                - deps.registry.exposed_characters,
                            ),
                        )
                    ]
                    truncated = truncated or span != original_span
                    if not span:
                        break
                    if span in complete_spans:
                        key = deps.registry.evidence_id(p, span)
                        piece = f"[{key}] {span}\n"
                    else:
                        label = "[Preview; read_chunk before citing] "
                        span = span[: max(0, budget - len(label) - 1)]
                        if not span:
                            break
                        deps.registry.expose(p, span)
                        piece = f"{label}{span}\n"
                    pieces.append(piece)
                    budget -= len(piece)
                displayed = "".join(pieces)
            block = prefix + displayed + ("\n[excerpt truncated]" if truncated else "")
            output += block
            remaining -= len(block)
            if not selectable:
                deps.registry.expose(p, excerpt)
    return (
        output
        + f"\n[Only displayed text is evidence. {omitted} passages omitted by output/evidence/chunk/span limits; use narrower reads within remaining budget.]"
    )


@bounded_tool
async def search_filings(
    ctx: RunContext[DocumentAgentDeps], query: str, filters: SearchFilters | None = None
) -> str:
    """Hybrid search of SEC filings. Year filters are corpus years unless explicitly verified fiscal years."""
    d = ctx.deps
    if d.searches == 0 and d.question and query != d.question:
        query = f"{d.question}\nSearch focus: {query}"
    await d.begin("searching", search=True)
    result = await d.retriever.search(query, filters=filters)
    d.completed_retrievals += 1
    if filters:
        d.registry.record_unmatched(filters, result.passages)
    d.retrieval_usage.append(result.usage.model_dump())
    return (
        expose_groups(
            d, [("Search", result.passages)], focus=result.lexical_query or query
        )
        + "\nWarnings: "
        + json.dumps(result.warnings)[:500]
    )


@bounded_tool
async def compare_filings(
    ctx: RunContext[DocumentAgentDeps], query: str, targets: list[SearchFilters]
) -> str:
    """Search each explicit company/year target, retaining empty targets. Up to 25 targets."""
    d = ctx.deps
    if d.searches == 0 and d.question and query != d.question:
        query = f"{d.question}\nSearch focus: {query}"
    await d.begin("searching", search=True)
    if not 1 <= len(targets) <= 25:
        raise ValueError("Comparison requires 1 to 25 targets")
    expanded = []
    for target in targets:
        for corpus_year, fiscal_year in product(
            target.corpus_years or [None], target.fiscal_years or [None]
        ):
            expanded.append(
                target.model_copy(
                    update={
                        "corpus_years": [corpus_year]
                        if corpus_year is not None
                        else None,
                        "fiscal_years": [fiscal_year]
                        if fiscal_year is not None
                        else None,
                    }
                )
            )
            if len(expanded) > 25:
                return "[Comparison rejected: more than 25 individual company/year targets. Narrow the requested coverage.]"
    targets = expanded
    result = await d.retriever.compare(query, targets=targets)
    d.completed_retrievals += 1
    for target in targets:
        if target not in d.registry.comparison_targets:
            d.registry.comparison_targets.append(target.model_copy(deep=True))
    for t in result.targets:
        d.registry.record_unmatched(t.target, t.result.passages)
    d.retrieval_usage.append(result.usage.model_dump())
    warnings = list(
        dict.fromkeys(warning for t in result.targets for warning in t.result.warnings)
    )
    warning_text = json.dumps(warnings)
    if len(warning_text) > 450:
        warning_text = warning_text[:450] + " [warnings truncated]"
    return (
        expose_groups(
            d,
            [
                (
                    f"{t.target.model_dump_json(exclude_none=True)} lexical_available={t.result.lexical_available}",
                    t.result.passages,
                )
                for t in result.targets
            ],
            full=True,
            # A 25-target comparison exposed one citable span inside the plain
            # tool budget; scale with targets within the turn's evidence budget.
            limit=min(
                d.settings.assistant_evidence_chars,
                max(
                    d.settings.assistant_tool_chars,
                    len(targets) * d.settings.assistant_comparison_target_chars,
                ),
            ),
            focus=next(
                (
                    t.result.lexical_query
                    for t in result.targets
                    if t.result.lexical_query
                ),
                query,
            ),
        )
        + "\nWarnings: "
        + warning_text
    )


@bounded_tool
async def read_chunks(ctx: RunContext[DocumentAgentDeps], chunk_ids: list[UUID]) -> str:
    """Read up to five source chunks. A long chunk may be truncated by the evidence budget."""
    d = ctx.deps
    await d.begin("reading")
    if not 1 <= len(chunk_ids) <= d.settings.assistant_read_batch:
        return "[Read rejected: provide 1 to 5 chunk IDs.]"
    values = await asyncio.gather(
        *(d.retriever.read_chunk(i) for i in dict.fromkeys(chunk_ids))
    )
    return expose_groups(
        d,
        [(str(i), [p] if p else []) for i, p in zip(dict.fromkeys(chunk_ids), values)],
        full=True,
        focus=d.question,
    )


@bounded_tool
async def read_chunk(ctx: RunContext[DocumentAgentDeps], chunk_id: UUID) -> str:
    """Read one chunk before citing supporting text beyond search excerpts."""
    return await read_chunks.__wrapped__(ctx, [chunk_id])


@bounded_tool
async def read_surrounding_chunks(
    ctx: RunContext[DocumentAgentDeps], chunk_id: UUID, radius: int = 1
) -> str:
    """Read adjacent chunks from the same filing."""
    d = ctx.deps
    await d.begin("reading")
    if not 0 <= radius <= d.settings.retrieval_neighbor_radius:
        return "[Read rejected: neighbor radius exceeds configured bound.]"
    passages = await d.retriever.read_surrounding_chunks(chunk_id, radius=radius)
    return expose_groups(
        d, [("Surrounding chunks", passages)], full=True, focus=d.question
    )


def numeric_filters_for_question(
    question: str, filters: SearchFilters | None
) -> SearchFilters | None:
    if not filters or not filters.corpus_years:
        return filters
    # Explicit source continuations may legitimately refer to a prior turn's filing.
    if re.search(
        r"\b(?:same|that|this|previous|above)\s+(?:filing|report|document|10-K)\b",
        question,
        re.IGNORECASE,
    ):
        return filters
    years = {int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", question)}
    if not years:
        return filters
    for start, end in re.findall(
        r"\b((?:19|20)\d{2})\s*(?:[-–—]|to|through)\s*((?:19|20)\d{2})\b",
        question,
        re.IGNORECASE,
    ):
        first, last = sorted((int(start), int(end)))
        if last - first < 25:
            years.update(range(first, last + 1))
    kept = [year for year in filters.corpus_years if year in years]
    if kept == filters.corpus_years:
        return filters
    # Removing stale restrictions widens retrieval; it never equates fiscal and corpus years.
    return filters.model_copy(update={"corpus_years": kept or None})


@bounded_tool
async def prepare_calculation(
    ctx: RunContext[DocumentAgentDeps], query: str, filters: SearchFilters | None = None
) -> str:
    """Retrieve and independently verify the two numeric facts for a calculation.

    Use this FIRST for numerical calculations. Pass the complete question, including
    requested measures and periods. It searches and reads evidence automatically.
    It returns two ordered fact IDs only when quotes, units, periods and source
    support pass. Corpus filters locate candidate filings; fiscal periods must be
    explicit in their text. Do not call calculate until preparation succeeds.
    """
    d = ctx.deps
    await d.begin("searching", search=True)
    if d.fact_preparations >= d.settings.assistant_grounding_repairs + 1:
        return "[Numeric preparation budget exhausted. Return an explicit ambiguous_figures gap.]"
    if d.fact_preparations == 0 and len(d.question.split()) > 5:
        query = d.question
    elif d.question and query != d.question:
        query = f"{d.question}\nSearch focus: {query}"
    proposed_filters = filters
    filters = numeric_filters_for_question(d.question, filters)
    adjusted = filters != proposed_filters
    filter_warning = (
        "Removed corpus-year restrictions not present in the current question; fiscal periods still require verification in source text."
        if adjusted
        else ""
    )
    attempt = {
        "proposed_filters": proposed_filters.model_dump(exclude_none=True)
        if proposed_filters
        else {},
        "effective_filters": filters.model_dump(exclude_none=True) if filters else {},
        "filter_adjusted": adjusted,
        "passages": [],
        "outcome": "searching",
    }
    d.numeric_attempts.append(attempt)
    result = await d.retriever.search(query, filters=filters, top_k=3)
    attempt["passages"] = [
        {"chunk_id": str(p.chunk_id), "ticker": p.ticker, "corpus_year": p.corpus_year}
        for p in result.passages
    ]
    d.completed_retrievals += 1
    d.retrieval_usage.append(result.usage.model_dump())
    if not result.passages:
        d.fact_preparations += 1
        attempt["outcome"] = "no_evidence"
        return (
            filter_warning + "\n" if adjusted else ""
        ) + "[No matching evidence for numeric inputs. Report a missing_evidence gap.]"
    if d.progress:
        await d.progress("reading")
    sources = expose_groups(
        d,
        [("Numeric candidate", [p]) for p in result.passages],
        full=True,
        selectable=False,
    )
    report_start = len(d.validation_reports)
    attempt["outcome"] = "preparing_inputs"
    try:
        ready = await prepare_facts(d, sources, query=query)
    except InvalidSupportReport:
        raise
    except ValueError as error:
        attempt["outcome"] = "rejected"
        stages = {report.get("stage") for report in d.validation_reports[report_start:]}
        attempt["rejection_stage"] = (
            "numeric_support"
            if "numeric_facts" in stages
            else "selection_or_input_validation"
            if "numeric_selection" in stages
            else "candidate_extraction"
        )
        d.tool_notes.append("Numeric preparation rejected: " + str(error))
        return (
            (filter_warning + "\n" if adjusted else "")
            + "[Numeric preparation rejected: "
            + str(error)
            + ". Do not invent fact or calculation IDs. Report ambiguous_figures, or make one focused preparation retry if evidence is missing.]"
        )
    attempt["outcome"] = "verified_inputs"
    return json.dumps(
        {
            **ready.model_dump(mode="json"),
            "facts": [
                {
                    "fact_id": str(i),
                    **d.registry.numeric_facts[i].model_dump(mode="json"),
                }
                for i in (ready.first_fact_id, ready.second_fact_id)
            ],
            "warnings": ([filter_warning] if adjusted else []) + result.warnings,
            "next_step": "Call calculate with these first_fact_id and second_fact_id in this order. Do not rebuild the operands.",
        }
    )


async def calculate(
    ctx: RunContext[DocumentAgentDeps], first_fact_id: UUID, second_fact_id: UUID
) -> GroundedAnswer:
    """Calculate using the two ordered verified fact IDs from prepare_calculation.

    No raw numbers, quotes, units or operation are accepted. The backend uses the
    verified operation and operands; IDs must belong to the same preparation in
    this turn and remain in first/second order. This submits the final answer;
    no additional final_result call or model-written calculation prose is needed.
    """
    d = ctx.deps
    try:
        await d.begin("calculating")
        record = calculate_from_facts(first_fact_id, second_fact_id, d.registry)
    except ValueError as error:
        raise ModelRetry(str(error)) from None
    return final_answer(
        ctx,
        [
            SelectedClaim(
                text=calculation_text(record),
                kind="calculation",
                calculation_id=record.id,
            )
        ],
        [],
    )


TOOLS = [
    search_filings,
    compare_filings,
    read_chunk,
    read_chunks,
    read_surrounding_chunks,
    prepare_calculation,
]
