import pytest
from langchain_core.messages import AIMessage
from langgraph.checkpoint.memory import MemorySaver

from assistant.agent.graph import build_graph


class ScriptedModel:
    """Returns a fixed sequence of AI messages, one per call."""

    def __init__(self, replies: list[AIMessage]) -> None:
        self.replies = list(replies)
        self.calls: list[list] = []

    def invoke(self, messages, **kwargs):
        self.calls.append(messages)
        if not self.replies:
            return AIMessage(content="Nothing more to add.")
        return self.replies.pop(0)


def tool_call(name: str, args: dict, call_id: str) -> AIMessage:
    return AIMessage(
        content="",
        tool_calls=[{"name": name, "args": args, "id": call_id, "type": "tool_call"}],
    )


@pytest.fixture
def scripted():
    def build(replies):
        model = ScriptedModel(replies)
        graph = build_graph(checkpointer=MemorySaver(), model=model)
        return graph, model

    return build
