from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.types import Command

from assistant.tests.conftest import tool_call

CONFIG = {"configurable": {"thread_id": "test"}}


def run(graph, question: str, role: str = "analyst"):
    return graph.invoke(
        {"messages": [HumanMessage(content=question)], "token": "fake-token", "role": role},
        config=CONFIG,
    )


def last_text(result) -> str:
    return result["messages"][-1].content


def tool_messages(result) -> list[str]:
    return [m.content for m in result["messages"] if isinstance(m, ToolMessage)]


def test_a_plain_answer_never_pauses(scripted):
    graph, _ = scripted([AIMessage(content="There are four open flags.")])
    result = run(graph, "How many flags are open?")
    assert result.get("__interrupt__") is None
    assert last_text(result) == "There are four open flags."


def test_read_tools_run_without_approval(scripted):
    graph, _ = scripted(
        [tool_call("get_account", {"account_id": 887}, "c1"), AIMessage(content="It is active.")]
    )
    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        tools.get.return_value.invoke.return_value = "Account 887 is active."
        result = run(graph, "Is account 887 active?")
    assert result.get("__interrupt__") is None
    assert last_text(result) == "It is active."


def test_an_action_pauses_and_describes_itself(scripted):
    graph, _ = scripted(
        [tool_call("freeze_account", {"account_id": 887, "reason": "stolen card"}, "c1")]
    )
    result = run(graph, "Freeze account 887.")

    request = result["__interrupt__"][0].value
    assert "approval" in request["reason"].lower()
    action = request["actions"][0]
    assert action["id"] == "c1"
    assert action["tool"] == "freeze_account"
    assert action["args"] == {"account_id": 887, "reason": "stolen card"}
    assert "freeze_account(account_id=887" in action["summary"]


def test_a_refused_action_does_not_run(scripted):
    graph, _ = scripted(
        [
            tool_call("freeze_account", {"account_id": 887, "reason": "stolen card"}, "c1"),
            AIMessage(content="I did not freeze the account."),
        ]
    )
    run(graph, "Freeze account 887.")

    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        result = graph.invoke(
            Command(resume={"c1": {"approved": False, "note": "verify with customer first"}}),
            config=CONFIG,
        )
        tools.get.assert_not_called()

    messages = tool_messages(result)
    assert any("did not approve" in m for m in messages)
    assert any("verify with customer first" in m for m in messages)
    assert any("Do not retry" in m for m in messages)


def test_an_approved_action_runs(scripted):
    graph, _ = scripted(
        [
            tool_call("freeze_account", {"account_id": 887, "reason": "stolen card"}, "c1"),
            AIMessage(content="Account 887 is frozen."),
        ]
    )
    run(graph, "Freeze account 887.")

    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        tools.get.return_value.invoke.return_value = "Account 887 is now frozen."
        result = graph.invoke(Command(resume={"c1": {"approved": True, "note": ""}}), config=CONFIG)
        tools.get.return_value.invoke.assert_called_once()

    assert any("now frozen" in m for m in tool_messages(result))


def test_an_empty_resume_runs_nothing(scripted):
    graph, _ = scripted(
        [
            tool_call("freeze_account", {"account_id": 887, "reason": "stolen card"}, "c1"),
            AIMessage(content="I did not act."),
        ]
    )
    run(graph, "Freeze account 887.")

    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        result = graph.invoke(Command(resume={}), config=CONFIG)
        tools.get.assert_not_called()

    assert not tool_messages(result)


def test_a_decision_for_another_action_counts_as_refusal(scripted):
    graph, _ = scripted(
        [
            tool_call("freeze_account", {"account_id": 887, "reason": "stolen card"}, "c1"),
            AIMessage(content="I did not act."),
        ]
    )
    run(graph, "Freeze account 887.")

    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        result = graph.invoke(
            Command(resume={"some-other-id": {"approved": True, "note": ""}}), config=CONFIG
        )
        tools.get.assert_not_called()

    assert any("did not approve" in m for m in tool_messages(result))


def test_a_viewer_cannot_act_even_after_approval(scripted):
    graph, _ = scripted(
        [
            tool_call("freeze_account", {"account_id": 887, "reason": "stolen card"}, "c1"),
            AIMessage(content="I could not act."),
        ]
    )
    run(graph, "Freeze account 887.", role="viewer")

    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        result = graph.invoke(Command(resume={"c1": {"approved": True, "note": ""}}), config=CONFIG)
        tools.get.assert_not_called()

    assert any("analyst role" in m for m in tool_messages(result))


def test_mixed_calls_gate_only_the_action(scripted):
    graph, _ = scripted(
        [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "get_account",
                        "args": {"account_id": 887},
                        "id": "r1",
                        "type": "tool_call",
                    },
                    {
                        "name": "freeze_account",
                        "args": {"account_id": 887, "reason": "stolen"},
                        "id": "a1",
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(content="Looked it up, did not freeze it."),
        ]
    )
    result = run(graph, "Check account 887 and freeze it.")

    actions = result["__interrupt__"][0].value["actions"]
    assert [a["id"] for a in actions] == ["a1"]


def test_the_tool_loop_is_bounded(scripted):
    graph, model = scripted(
        [tool_call("get_account", {"account_id": 887}, f"c{i}") for i in range(20)]
    )
    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        tools.get.return_value.invoke.return_value = "Account 887 is active."
        result = run(graph, "Keep looking it up.")

    rounds = len([m for m in result["messages"] if isinstance(m, ToolMessage)])
    assert rounds <= 8


def test_a_failing_tool_does_not_crash_the_graph(scripted):
    graph, _ = scripted(
        [tool_call("get_account", {"account_id": 887}, "c1"), AIMessage(content="Lookup failed.")]
    )
    with patch("assistant.agent.graph.TOOLS_BY_NAME") as tools:
        tools.get.return_value.invoke.side_effect = RuntimeError("database is down")
        result = run(graph, "Is account 887 active?")

    assert any("Error: RuntimeError: database is down" in m for m in tool_messages(result))
    assert last_text(result) == "Lookup failed."


def test_an_unknown_tool_is_reported(scripted):
    graph, _ = scripted(
        [tool_call("delete_everything", {}, "c1"), AIMessage(content="That tool does not exist.")]
    )
    result = run(graph, "Delete everything.")
    assert any("unknown tool 'delete_everything'" in m for m in tool_messages(result))
