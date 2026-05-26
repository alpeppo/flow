"""Tests für groq_client.py — httpx-basierter Groq-Client mit Retry und Timeout."""

import httpx
import pytest
import respx

from wnflow.cleanup.groq_client import GroqClient, GroqError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"


@respx.mock
def test_clean_returns_assistant_message() -> None:
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": "Schreib mir eine Mail."}}
                ]
            },
        )
    )
    client = GroqClient(api_key="gsk_test", model="llama-3.3-70b-versatile")
    result = client.clean(system_prompt="System", user_text="Äh schreib mir eine Mail")
    assert result == "Schreib mir eine Mail."


@respx.mock
def test_clean_sends_correct_payload() -> None:
    route = respx.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "ok"}}]},
        )
    )
    client = GroqClient(api_key="gsk_test", model="llama-3.3-70b-versatile")
    client.clean(system_prompt="SYS", user_text="USR")

    assert route.called
    request = route.calls[0].request
    assert request.headers["Authorization"] == "Bearer gsk_test"
    import json
    body = json.loads(request.content)
    assert body["model"] == "llama-3.3-70b-versatile"
    assert body["messages"][0] == {"role": "system", "content": "SYS"}
    assert body["messages"][1] == {"role": "user", "content": "USR"}
    assert body["temperature"] == 0.0


@respx.mock
def test_clean_retries_once_on_5xx() -> None:
    route = respx.post(GROQ_URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(
                200,
                json={"choices": [{"message": {"content": "ok"}}]},
            ),
        ]
    )
    client = GroqClient(api_key="gsk_test", model="m", retry=1)
    result = client.clean(system_prompt="S", user_text="U")
    assert result == "ok"
    assert route.call_count == 2


@respx.mock
def test_clean_raises_after_retries_exhausted() -> None:
    respx.post(GROQ_URL).mock(return_value=httpx.Response(503))
    client = GroqClient(api_key="gsk_test", model="m", retry=1)
    with pytest.raises(GroqError):
        client.clean(system_prompt="S", user_text="U")


@respx.mock
def test_clean_raises_on_401_without_retry() -> None:
    route = respx.post(GROQ_URL).mock(return_value=httpx.Response(401))
    client = GroqClient(api_key="gsk_invalid", model="m", retry=3)
    with pytest.raises(GroqError, match="401"):
        client.clean(system_prompt="S", user_text="U")
    assert route.call_count == 1  # Kein Retry bei 401


@respx.mock
def test_clean_strips_whitespace() -> None:
    respx.post(GROQ_URL).mock(
        return_value=httpx.Response(
            200,
            json={"choices": [{"message": {"content": "  Schreib mir.  \n"}}]},
        )
    )
    client = GroqClient(api_key="gsk_test", model="m")
    result = client.clean(system_prompt="S", user_text="U")
    assert result == "Schreib mir."
