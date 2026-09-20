
from langchain_core.messages import SystemMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from assistant.agent.llm import get_llm
from assistant.agent.prompts import SYSTEM_PROMPT
from assistant.agent.state import AgentState
from assistant.tools.banking import ALL_TOOLS, TOOLS_BY_NAME
from assistant.tools.client import ApiClient

MAX_TOOL_ROUNDS = 6


def call_model(state: AgentState) -> dict:
    model = get_llm().bind_tools(ALL_TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    return {"messages": [model.invoke(messages)]}


def call_tools(state: AgentState) -> dict:
    last = state["messages"][-1]
    client = ApiClient(token=state["token"])
    results = []

    for call in last.tool_calls:
        tool = TOOLS_BY_NAME.get(call["name"])
        if tool is None:
            content = f"Error: unknown tool '{call['name']}'"
        else:
            try:
                content = tool.invoke({**call["args"], "client": client})
            except Exception as exc:
                content = f"Error: {type(exc).__name__}: {exc}"
        results.append(ToolMessage(content=str(content), tool_call_id=call["id"]))

    return {"messages": results}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return END
    tool_rounds = sum(1 for m in state["messages"] if isinstance(m, ToolMessage))
    if tool_rounds >= MAX_TOOL_ROUNDS:
        return END
    return "tools"


def build_graph(checkpointer=None):
    builder = StateGraph(AgentState)
    builder.add_node("agent", call_model)
    builder.add_node("tools", call_tools)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"tools": "tools", END: END})
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer or MemorySaver())


GRAPH = build_graph()


def ask(question: str, token: str, role: str = "analyst", thread_id: str = "cli") -> str:
    """Run one turn and return the assistant's final text. Used by the CLI and tests."""
    from langchain_core.messages import HumanMessage

    result = GRAPH.invoke(
        {"messages": [HumanMessage(content=question)], "token": token, "role": role},
        config={"configurable": {"thread_id": thread_id}},
    )
    return result["messages"][-1].content


def main() -> None:
    import sys

    from backend.app.core.security import User, create_access_token

    question = " ".join(sys.argv[1:]) or "What open fraud flags need review?"
    token = create_access_token(User(username="analyst", role="analyst"))
    print(ask(question, token))


if __name__ == "__main__":
    main()
