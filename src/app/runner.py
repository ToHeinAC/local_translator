"""Background job handle: the UI polls it, the work never touches Streamlit."""

import threading
from collections.abc import Callable

from app.pipeline import JobResult

Progress = Callable[[int, int], None]
Work = Callable[[Progress, Callable[[], bool]], JobResult]


class JobHandle:
    """Runs ``work(progress, cancel)`` on one daemon thread; result or error is kept."""

    def __init__(self, work: Work) -> None:
        self._work = work
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._cancel = threading.Event()
        self._started = False
        self.done = 0
        self.total = 0
        self.result: JobResult | None = None
        self.error: Exception | None = None

    def start(self) -> None:
        if not self._started:
            self._started = True
            self._thread.start()

    def request_cancel(self) -> None:
        self._cancel.set()

    @property
    def cancel_requested(self) -> bool:
        return self._cancel.is_set()

    @property
    def finished(self) -> bool:
        return self._started and not self._thread.is_alive()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def _progress(self, done: int, total: int) -> None:
        self.done, self.total = done, total

    def _run(self) -> None:
        try:
            self.result = self._work(self._progress, self._cancel.is_set)
        except Exception as exc:
            self.error = exc
