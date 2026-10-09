from types import SimpleNamespace

from app.llm_ollama import loaded_models
from app.runner import JobHandle


def test_handle_runs_work_and_records_progress() -> None:
    def work(progress, cancel):  # type: ignore[no-untyped-def]
        progress(1, 2)
        progress(2, 2)
        return "result"

    handle = JobHandle(work)  # type: ignore[arg-type]
    handle.start()
    handle.join()
    assert handle.finished
    assert (handle.done, handle.total) == (2, 2)
    assert handle.result == "result"
    assert handle.error is None


def test_handle_captures_errors_and_passes_cancel() -> None:
    def work(progress, cancel):  # type: ignore[no-untyped-def]
        assert cancel()
        raise RuntimeError("kaputt")

    handle = JobHandle(work)  # type: ignore[arg-type]
    handle.request_cancel()
    handle.start()
    handle.join()
    assert str(handle.error) == "kaputt"
    assert handle.result is None


def test_second_start_is_ignored() -> None:
    calls: list[int] = []

    def work(progress, cancel):  # type: ignore[no-untyped-def]
        calls.append(1)
        return None

    handle = JobHandle(work)  # type: ignore[arg-type]
    handle.start()
    handle.start()
    handle.join()
    assert calls == [1]


def test_loaded_models_lists_name_and_vram() -> None:
    class Client:
        def ps(self):  # type: ignore[no-untyped-def]
            return SimpleNamespace(
                models=[SimpleNamespace(model="gemma4:e4b", size_vram=3 * 2**30)]
            )

    assert loaded_models(Client()) == [("gemma4:e4b", 3 * 2**30)]  # type: ignore[arg-type]

    class Down:
        def ps(self):  # type: ignore[no-untyped-def]
            raise ConnectionError

    assert loaded_models(Down()) == []  # type: ignore[arg-type]
