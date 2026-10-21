import asyncio
from uuid import uuid4

import pytest

from app.assistant.rendering import render_answer
from app.database.chats import completed_turn, recent_history, save_turn
from tests.assistant.test_grounding import answer_and_registry


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls = []

    def execute(self, sql, params):
        self.calls.append((sql, params))
        return self

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return {"next": 0}


def test_history_drops_older_complete_pairs_before_truncating():
    c = Connection(
        [
            {"role": "ASSISTANT", "sequence": 3, "content": "new answer"},
            {"role": "USER", "sequence": 2, "content": "new question"},
            {"role": "ASSISTANT", "sequence": 1, "content": "old answer"},
            {"role": "USER", "sequence": 0, "content": "old question"},
        ]
    )
    history = asyncio.run(recent_history(c, uuid4(), pairs=6, characters=22))
    assert [m["content"] for m in history] == ["new question", "new answer"]


def test_rendered_metadata_and_normalized_citations_are_saved_in_same_transaction():
    answer, registry = answer_and_registry()
    reply = render_answer(answer, registry)
    c = Connection([])
    asyncio.run(save_turn(c, uuid4(), uuid4(), uuid4(), "Q", reply))
    assert "INSERT INTO public.chat_messages" in c.calls[1][0]
    assert c.calls[1][1][-1].obj == reply.parts
    assert "INSERT INTO public.message_citations" in c.calls[2][0]
    assert c.calls[2][1][2] == reply.parts[1]["data"]["chunk_id"]
    assert reply.parts[1]["data"]["fiscal_year"] is None
    assert reply.parts[1]["data"]["page"] is None


def test_completed_replay_preserves_citations_and_reused_question_rejected():
    from fastapi import HTTPException

    answer, registry = answer_and_registry()
    reply = render_answer(answer, registry)
    user, assistant = uuid4(), uuid4()
    c = Connection(
        [
            {"id": user, "content": "Q", "parts": []},
            {"id": assistant, "content": reply.text, "parts": reply.parts},
        ]
    )
    assert asyncio.run(completed_turn(c, uuid4(), user, assistant, "Q")) == reply
    with pytest.raises(HTTPException) as error:
        asyncio.run(completed_turn(c, uuid4(), user, assistant, "different"))
    assert error.value.status_code == 409
