from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from ollama import ResponseError

from app import llm_ollama
from app.llm_ollama import OllamaUnavailableError, installed_tags, make_llm, unload_all
from app.translate import FatalLlmError

HOST = "http://gpu-host:11434"


class StubClient:
    """Stands in for ``ollama.Client``; ``chat_results`` are returned or raised in order."""

    def __init__(self, chat_results: list[Any] | None = None) -> None:
        self.chat_results = list(chat_results or [])
        self.chat_calls: list[dict[str, Any]] = []
        self.generate_calls: list[dict[str, Any]] = []
        self.tags: Any = SimpleNamespace(models=[])
        self.loaded: Any = SimpleNamespace(models=[])

    def chat(self, **kwargs: Any) -> Any:
        self.chat_calls.append(kwargs)
        result = self.chat_results.pop(0)
        if isinstance(result, Exception):
            raise result
        return {"message": {"content": result}}

    def list(self) -> Any:
        if isinstance(self.tags, Exception):
            raise self.tags
        return self.tags

    def ps(self) -> Any:
        if isinstance(self.loaded, Exception):
            raise self.loaded
        return self.loaded

    def generate(self, **kwargs: Any) -> None:
        self.generate_calls.append(kwargs)
        if kwargs["model"] == "broken":
            raise RuntimeError("boom")


def test_request_parameters_and_content() -> None:
    client = StubClient(["[[1]] Hallo"])
    assert make_llm(client, "gemma4:e4b", HOST)("prompt") == "[[1]] Hallo"
    (call,) = client.chat_calls
    assert call["model"] == "gemma4:e4b"
    assert call["messages"] == [{"role": "user", "content": "prompt"}]
    assert call["think"] is False
    assert call["options"] == {"temperature": 0.1, "num_ctx": 8192}
    assert call["keep_alive"] == "30m"  # no reload between segments of a long job


def test_make_client_passes_host_and_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class Recorder:
        def __init__(self, **kwargs: Any) -> None:
            seen.update(kwargs)

    monkeypatch.setattr(llm_ollama, "Client", Recorder)
    llm_ollama.make_client(HOST, 90.0)
    assert seen == {"host": HOST, "timeout": 90.0}


def test_response_error_is_retried_once() -> None:
    client = StubClient([ResponseError("runner crashed", 500), "ok"])
    assert make_llm(client, "m", HOST)("p") == "ok"
    assert len(client.chat_calls) == 2


def test_second_response_error_propagates() -> None:
    client = StubClient([ResponseError("a", 500), ResponseError("b", 500)])
    with pytest.raises(ResponseError):
        make_llm(client, "m", HOST)("p")
    assert len(client.chat_calls) == 2


def test_unreachable_host_gives_typed_error_with_host_name() -> None:
    client = StubClient([ConnectionError("refused"), ConnectionError("refused")])
    with pytest.raises(OllamaUnavailableError, match="gpu-host") as info:
        make_llm(client, "m", HOST)("p")
    assert isinstance(info.value, FatalLlmError)
    assert info.value.host == HOST


def test_http_timeout_becomes_builtin_timeout_without_retry() -> None:
    client = StubClient([httpx.ReadTimeout("slow")])
    with pytest.raises(TimeoutError):
        make_llm(client, "m", HOST)("p")
    assert len(client.chat_calls) == 1


def test_installed_tags_from_stubbed_tags_response() -> None:
    client = StubClient()
    client.tags = SimpleNamespace(
        models=[SimpleNamespace(model="gemma4:e4b"), SimpleNamespace(model="qwen3:14b")]
    )
    assert installed_tags(client, HOST) == {"gemma4:e4b", "qwen3:14b"}


def test_installed_tags_unreachable_raises_typed_error() -> None:
    client = StubClient()
    client.tags = ConnectionError("refused")
    with pytest.raises(OllamaUnavailableError, match="gpu-host"):
        installed_tags(client, HOST)


def test_unload_all_evicts_each_loaded_model_and_ignores_failures() -> None:
    client = StubClient()
    client.loaded = SimpleNamespace(
        models=[SimpleNamespace(model="a"), SimpleNamespace(model="broken")]
    )
    assert unload_all(client) == ["a", "broken"]
    assert [c["keep_alive"] for c in client.generate_calls] == [0, 0]


def test_unload_all_returns_empty_when_ps_fails() -> None:
    client = StubClient()
    client.loaded = ConnectionError("refused")
    assert unload_all(client) == []


def test_system_part_of_the_prompt_becomes_a_system_message() -> None:
    from app.prompt import SYSTEM_SPLIT

    client = StubClient(["ok"])
    make_llm(client, "m", HOST)(f"rules{SYSTEM_SPLIT}text")
    assert client.chat_calls[0]["messages"] == [
        {"role": "system", "content": "rules"},
        {"role": "user", "content": "text"},
    ]
