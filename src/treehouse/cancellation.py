import threading

from .errors import UserCancelled


class CancellationToken:
    def __init__(self) -> None:
        self._event = threading.Event()

    def cancel(self) -> None:
        self._event.set()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def check(self) -> None:
        if self.cancelled:
            raise UserCancelled("任务已停止。")

    def wait(self, seconds: float) -> None:
        if self._event.wait(seconds):
            self.check()
