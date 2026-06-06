"""Tests for the DeltaChannel messages reducer used by `AgentState`.

The reducer wraps upstream's `_messages_delta_reducer` to add
`REMOVE_ALL_MESSAGES` handling — without it, `SummarizationMiddleware` would
silently no-op the conversation reset and message history would grow
unbounded.
"""

from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, RemoveMessage
from langgraph.graph.message import REMOVE_ALL_MESSAGES

from intentkit.abstracts.graph import (
    _messages_reducer,  # pyright: ignore[reportPrivateUsage]
)


def _make_history(n: int) -> list[AnyMessage]:
    msgs: list[AnyMessage] = []
    for i in range(n):
        msgs.append(HumanMessage(content=f"u{i}", id=f"u{i}"))
        msgs.append(AIMessage(content=f"a{i}", id=f"a{i}"))
    return msgs


def test_remove_all_messages_resets_state_and_keeps_post_sentinel_writes():
    history = _make_history(5)
    summary_write = [
        RemoveMessage(id=REMOVE_ALL_MESSAGES),
        AIMessage(content="[Summary]", id="s1"),
        history[-2],
        history[-1],
    ]

    result = _messages_reducer(history, [summary_write])

    assert [m.id for m in result] == ["s1", "u4", "a4"]


def test_normal_append_batching_invariance():
    state: list[AnyMessage] = [AIMessage(content="m0", id="m0")]
    a = [AIMessage(content="c", id="c1")]
    b = [AIMessage(content="d", id="d1")]

    split = _messages_reducer(_messages_reducer(state, [a]), [b])
    batched = _messages_reducer(state, [a, b])

    assert [m.id for m in split] == [m.id for m in batched] == ["m0", "c1", "d1"]


def test_remove_all_in_later_batch_invariance():
    state: list[AnyMessage] = [AIMessage(content="m0", id="m0")]
    a = [AIMessage(content="m1", id="m1")]
    b = [RemoveMessage(id=REMOVE_ALL_MESSAGES), AIMessage(content="m2", id="m2")]

    split = _messages_reducer(_messages_reducer(state, [a]), [b])
    batched = _messages_reducer(state, [a, b])

    assert [m.id for m in split] == [m.id for m in batched] == ["m2"]


def test_remove_all_in_earlier_batch_invariance():
    state: list[AnyMessage] = [AIMessage(content="m0", id="m0")]
    a = [RemoveMessage(id=REMOVE_ALL_MESSAGES), AIMessage(content="x", id="x1")]
    b = [AIMessage(content="y", id="y1")]

    split = _messages_reducer(_messages_reducer(state, [a]), [b])
    batched = _messages_reducer(state, [a, b])

    assert [m.id for m in split] == [m.id for m in batched] == ["x1", "y1"]


def test_double_reset_invariance():
    state: list[AnyMessage] = [AIMessage(content="m0", id="m0")]
    a = [RemoveMessage(id=REMOVE_ALL_MESSAGES), AIMessage(content="p", id="p1")]
    b = [RemoveMessage(id=REMOVE_ALL_MESSAGES), AIMessage(content="q", id="q1")]

    split = _messages_reducer(_messages_reducer(state, [a]), [b])
    batched = _messages_reducer(state, [a, b])

    assert [m.id for m in split] == [m.id for m in batched] == ["q1"]


def test_targeted_remove_message_still_works():
    """Non-REMOVE_ALL `RemoveMessage` should fall through to upstream tombstoning."""
    state: list[AnyMessage] = [
        AIMessage(content="keep", id="k1"),
        AIMessage(content="drop", id="d1"),
    ]
    write = [RemoveMessage(id="d1")]

    result = _messages_reducer(state, [write])

    assert [m.id for m in result] == ["k1"]
