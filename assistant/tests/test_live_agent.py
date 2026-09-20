import pytest

from backend.app.core.config import get_settings

settings = get_settings()

pytestmark = pytest.mark.skipif(
    settings.llm_provider == "groq" and not settings.groq_api_key,
    reason="no LLM configured",
)


@pytest.mark.live
def test_the_model_can_choose_a_tool():
    from langchain_core.tools import tool

    from assistant.agent.llm import get_llm

    @tool
    def get_account(account_id: int) -> str:
        """Look up a bank account."""
        return "active"

    response = get_llm().bind_tools([get_account]).invoke("Is account 887 active?")
    assert response.tool_calls
    assert response.tool_calls[0]["name"] == "get_account"
    assert response.tool_calls[0]["args"]["account_id"] == 887
