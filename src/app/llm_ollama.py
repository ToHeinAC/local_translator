"""Ollama adapter: chat calls, availability check, unload. The only module that talks to Ollama."""

from typing import Any, Protocol, cast

import httpx
from ollama import Client, ResponseError

from app.translate import FatalLlmError, Llm

TEMPERATURE = 0.1
NUM_CTX = 8192


class OllamaUnavailableError(FatalLlmError):
    """The Ollama host cannot be reached."""

    def __init__(self, host: str) -> None:
        super().__init__(f"Ollama ist nicht erreichbar: {host}")
        self.host = host


class OllamaClient(Protocol):
    """The parts of ``ollama.Client`` used here (lets tests pass a stub)."""

    def chat(self, **kwargs: Any) -> Any: ...
    def list(self) -> Any: ...
    def ps(self) -> Any: ...
    def generate(self, **kwargs: Any) -> Any: ...


def make_client(host: str, timeout_s: float) -> OllamaClient:
    return cast(OllamaClient, Client(host=host, timeout=timeout_s))


def make_llm(client: OllamaClient, model: str, host: str) -> Llm:
    """An ``llm(prompt) -> str`` for ``translate_document``; no thinking, low temperature."""

    def llm(prompt: str) -> str:
        return _chat(client, model, host, prompt)

    return llm


def _chat(client: OllamaClient, model: str, host: str, prompt: str) -> str:
    """One request; a server or connection error is retried once (e.g. model evicted)."""
    for attempt in (1, 2):
        try:
            resp = client.chat(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                think=False,
                options={"temperature": TEMPERATURE, "num_ctx": NUM_CTX},
            )
            return str(resp["message"]["content"])
        except httpx.TimeoutException as exc:
            raise TimeoutError(f"Ollama antwortet nicht rechtzeitig ({model})") from exc
        except (ResponseError, ConnectionError) as exc:
            if attempt == 2:
                if isinstance(exc, ConnectionError):
                    raise OllamaUnavailableError(host) from exc
                raise
    raise AssertionError("unreachable")  # pragma: no cover


def installed_tags(client: OllamaClient, host: str) -> set[str]:
    """Tags of the models pulled on the host (``/api/tags``)."""
    try:
        return {str(m.model) for m in client.list().models}
    except ConnectionError as exc:
        raise OllamaUnavailableError(host) from exc


def unload_all(client: OllamaClient) -> list[str]:
    """Evict every loaded model from VRAM (``keep_alive=0``). Best effort; returns their names."""
    try:
        loaded = [str(m.model) for m in client.ps().models]
    except Exception:
        return []
    for name in loaded:
        try:
            client.generate(model=name, prompt="", keep_alive=0)
        except Exception:
            continue
    return loaded
