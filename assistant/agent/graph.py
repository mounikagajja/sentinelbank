from functools import lru_cache

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from assistant.agent.llm import get_llm
from assistant.agent.prompts import SYSTEM_PROMPT
from assistant.agent.state import AgentState
from assistant.tools.banking import ACTION_TOOLS, ALL_TOOLS, TOOLS_BY_NAME
from assistant.tools.client import ApiClient

MAX_TOOL_ROUNDS = 8


def describe(call: dict) -> str:
    args = ", ".join(f"{k}={v!r}" for k, v in call["args"].items())
    return f"{call['name']}({args})"


def call_model(state: AgentState) -> dict:
    model = get_llm().bind_tools(ALL_TOOLS)
    messages = [SystemMessage(content=SYSTEM_PROMPT), *state["messages"]]
    return {"messages": [model.invoke(messages)]}


def approve_actions(state: AgentState) -> dict:
    """Pause for a human before any tool that changes a record."""
    last = state["messages"][-1]
    pending = [c for c in last.tool_calls if c["name"] in ACTION_TOOLS]
    if not pending:
        return {"approvals": {}}

    decisions = interrupt(
        {
            "reason": "These actions change real records and need your approval.",
            "actions": [
                {
                    "id": call["id"],
                    "tool": call["name"],
                    "args": call["args"],
                    "summary": describe(call),
                }
                for call in pending
            ],
        }
    )
    return {"approvals": decisions or {}}


def call_tools(state: AgentState) -> dict:
    last = state["messages"][-1]
    approvals = state.get("approvals") or {}
    client = ApiClient(token=state["token"])
    results = []

    for call in last.tool_calls:
        if call["name"] in ACTION_TOOLS:
            decision = approvals.get(call["id"], {})
            if not decision.get("approved"):
                note = decision.get("note") or "no reason given"
                results.append(
                    ToolMessage(
                        content=(
                            f"The analyst did not approve {describe(call)}. "
                            f"Reason: {note}. Do not retry this action."
                        ),
                        tool_call_id=call["id"],
                    )
                )
                continue
            if state.get("role") != "analyst":
                results.append(
                    ToolMessage(
                        content="Error: this action requires the analyst role",
                        tool_call_id=call["id"],
                    )
                )
                continue

        tool = TOOLS_BY_NAME.get(call["name"])
        if tool is None:
            content = f"Error: unknown tool '{call['name']}'"
        else:
            try:
                content = tool.invoke({**call["args"], "client": client})
            except Exception as exc:
                content = f"Error: {type(exc).__name__}: {exc}"
        results.append(ToolMessage(content=str(content), tool_call_id=call["id"]))

    return {"messages": results, "approvals": {}}


def should_continue(state: AgentState) -> str:
    last = state["messages"][-1]
    if not getattr(last, "tool_calls", None):
        return END
    tool_rounds = sum(1 for m in state["messages"] if isinstance(m, ToolMessage))
    if tool_rounds >= MAX_TOOL_ROUNDS:
        return END
    return "approve"


def build_graph(checkpointer=None, model=None):
    if checkpointer is None:
        from langgraph.checkpoint.memory import MemorySaver

        checkpointer = MemorySaver()

    builder = StateGraph(AgentState)
    builder.add_node(
        "agent",
        (lambda s: {"messages": [model.invoke(s["messages"])]}) if model else call_model,
    )
    builder.add_node("approve", approve_actions)
    builder.add_node("tools", call_tools)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, {"approve": "approve", END: END})
    builder.add_edge("approve", "tools")
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer)


@lru_cache
def get_graph():
    """Graph backed by Postgres so conversations survive a restart."""
    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg_pool import ConnectionPool

    from backend.app.core.config import get_settings

    settings = get_settings()
    url = settings.database_url.replace("postgresql+psycopg://", "postgresql://")
    pool = ConnectionPool(url, min_size=1, max_size=5, kwargs={"autocommit": True})
    checkpointer = PostgresSaver(pool)
    checkpointer.setup()
    return build_graph(checkpointer=checkpointer)


def start(question: str, token: str, role: str = "analyst", thread_id: str = "cli") -> dict:
    """Run a turn. Returns either a final answer or a pending approval request."""
    return get_graph().invoke(
        {"messages": [HumanMessage(content=question)], "token": token, "role": role},
        config={"configurable": {"thread_id": thread_id}},
    )


def resume(decisions: dict, thread_id: str = "cli") -> dict:
    """Continue a paused run. decisions maps tool_call_id to {approved: bool, note: str}."""
    from langgraph.types import Command

    return get_graph().invoke(
        Command(resume=decisions), config={"configurable": {"thread_id": thread_id}}
    )


def pending_approval(result: dict) -> dict | None:
    interrupts = result.get("__interrupt__")
    return interrupts[0].value if interrupts else None


def main() -> None:
    import sys

    from backend.app.core.security import User, create_access_token

    question = " ".join(sys.argv[1:]) or "What open fraud flags need review?"
    token = create_access_token(User(username="analyst", role="analyst"))
    result = start(question, token)

    while (request := pending_approval(result)) is not None:
        print(f"\n{request['reason']}")
        decisions = {}
        for action in request["actions"]:
            answer = input(f"  Approve {action['summary']}? [y/N] ").strip().lower()
            approved = answer in {"y", "yes"}
            note = "" if approved else input("  Why not? ").strip()
            decisions[action["id"]] = {"approved": approved, "note": note}
        result = resume(decisions)

    print(f"\n{result['messages'][-1].content}")


if __name__ == "__main__":
    main()
