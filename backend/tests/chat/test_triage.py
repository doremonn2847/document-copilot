import asyncio
from types import SimpleNamespace

import pytest

from app.chat.triage import Triage, triage_turn

HISTORY = [
    {"role": "user", "content": "What does Microsoft say Azure provides in 2025?"},
    {
        "role": "assistant",
        "content": "Microsoft says Azure is a comprehensive set of cloud services. [1]",
    },
]


class Agent:
    def __init__(self, output):
        self.output = output
        self.prompts = []

    async def run(self, prompt, **kwargs):
        self.prompts.append(prompt)
        return SimpleNamespace(output=self.output)


def route(question, history, output):
    return asyncio.run(triage_turn(question, history, Agent(output)))


def test_greeting_is_answered_without_the_pipeline():
    result = route(
        "hi there!",
        [],
        Triage(
            route="conversation",
            topic="small_talk",
            reply="Hello! Ask me about the filings in the corpus.",
        ),
    )
    assert result == Triage(
        route="conversation",
        topic="small_talk",
        reply="Hello! Ask me about the filings in the corpus.",
    )


@pytest.mark.parametrize(
    "reply",
    [
        "Apple's revenue grew a lot.",  # names a company
        "Revenue was 391 billion.",  # carries a figure
        "See https://www.sec.gov for that.",  # links out
        "",
        "x" * 601,
    ],
)
def test_conversation_reply_that_could_carry_facts_goes_to_the_pipeline(reply):
    result = route("hi, quick one", [], Triage(route="conversation", reply=reply))
    assert result == Triage(route="filings", standalone_question="hi, quick one")


def test_first_turn_is_never_rewritten():
    result = route(
        "What about cloud?",
        [],
        Triage(
            route="filings", standalone_question="What does Microsoft say about cloud?"
        ),
    )
    assert result.standalone_question == "What about cloud?"


def test_follow_up_is_rewritten_with_conversation_context():
    agent = Agent(
        Triage(
            route="filings",
            standalone_question="What does Microsoft say Azure provides in its 2023 corpus filing?",
        )
    )
    result = asyncio.run(triage_turn("What about the 2023 filing?", HISTORY, agent))
    assert result.standalone_question == (
        "What does Microsoft say Azure provides in its 2023 corpus filing?"
    )
    assert "Azure" in agent.prompts[0] and "latest_message" in agent.prompts[0]


def test_rewrite_that_drops_a_requested_year_is_discarded():
    result = route(
        "What about the 2023 filing?",
        HISTORY,
        Triage(
            route="filings",
            standalone_question="What does Microsoft say Azure provides?",
        ),
    )
    assert result.standalone_question == "What about the 2023 filing?"


def test_failed_triage_falls_back_to_the_pipeline(monkeypatch):
    from app.chat import orchestrator

    async def broken(*_args):
        raise RuntimeError("provider down")

    monkeypatch.setattr(orchestrator, "triage_turn", broken)
    monkeypatch.setattr(orchestrator, "build_triage_agent", lambda *_: None)
    result = asyncio.run(orchestrator.safe_triage("Hello", [], None))
    assert result == Triage(route="filings", standalone_question="Hello")


def test_rewritten_question_is_shown_with_the_answer():
    from app.assistant.rendering import render_answer
    from tests.assistant.test_grounding import answer_and_registry

    answer, registry = answer_and_registry()
    reply = render_answer(answer, registry, interpreted="What about Azure in 2023?")
    assert reply.text.startswith("Answered as: What about Azure in 2023?")


def test_questions_about_the_app_get_the_fixed_help_text():
    # Live: "what can you do?" named the companies and years, so the model reply
    # was refused and the question failed in the pipeline.
    from app.chat.triage import HELP_TEXT

    result = route(
        "what can you do?",
        [],
        Triage(route="conversation", topic="about_app", reply=None),
    )
    assert result == Triage(route="conversation", topic="about_app", reply=HELP_TEXT)
    assert "[1]" in HELP_TEXT and "NVIDIA" in HELP_TEXT
