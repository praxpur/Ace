"""Thread-safe GUI boundary: Playwright lives entirely on the worker thread."""
import queue
import threading
from dataclasses import asdict
from uuid import uuid4

from .cancellation import CancellationToken
from .errors import ConfigurationError, UserCancelled
from .models import Event, Outcome
from .workflow import Workflow


class SelectionBroker:
    def __init__(self, emit):
        self.emit = emit
        self.lock = threading.Lock()
        self.pending = {}

    def choose(self, title, choices, token):
        token.check()
        request_id = uuid4().hex
        response = queue.Queue(maxsize=1)
        with self.lock:
            self.pending[request_id] = response
        try:
            self.emit(Event("selection_request", {
                "request_id": request_id, "title": title,
                "multiple": True,
                "choices": [asdict(choice) for choice in choices],
            }))
            while True:
                token.check()
                try:
                    value = response.get(timeout=0.1)
                    if value is None:
                        raise UserCancelled("已取消选择。")
                    keys = {choice.key for choice in choices}
                    selected = [value] if isinstance(value, str) else value
                    if (not isinstance(selected, (list, tuple)) or not selected
                            or any(not isinstance(key, str) or key not in keys for key in selected)):
                        raise ConfigurationError("选择的项目不存在。")
                    return value if isinstance(value, str) else list(dict.fromkeys(selected))
                except queue.Empty:
                    continue
        finally:
            with self.lock:
                self.pending.pop(request_id, None)

    def resolve(self, request_id, key):
        with self.lock:
            response = self.pending.pop(request_id, None)
        if response is None:
            return False
        response.put_nowait(key)
        return True

    def cancel_all(self):
        with self.lock:
            responses = list(self.pending.values())
            self.pending.clear()
        for response in responses:
            response.put_nowait(None)


class JobController:
    def __init__(self, workflow_factory=Workflow):
        self.events = queue.Queue()
        self.factory = workflow_factory
        self.worker = None
        self.token = CancellationToken()
        self.run_id = ""
        self.broker = None

    @property
    def running(self):
        return bool(self.worker and self.worker.is_alive())

    def start(self, settings):
        settings.validate()
        if self.running:
            raise ConfigurationError("已有任务正在运行。")
        self.run_id = uuid4().hex
        self.token = CancellationToken()
        run_id = self.run_id
        emit = lambda event: self.events.put((run_id, event))
        self.broker = SelectionBroker(emit)

        def run():
            try:
                outcome = self.factory(
                    settings, self.broker.choose, emit, self.token
                ).run()
            except Exception as error:
                outcome = Outcome("error", str(error), "")
            emit(Event("finished", asdict(outcome)))

        self.worker = threading.Thread(target=run, name="treehouse-worker", daemon=True)
        self.worker.start()
        return self.run_id

    def stop(self):
        self.token.cancel()
        if self.broker:
            self.broker.cancel_all()

    def resolve(self, request_id, key):
        return self.broker.resolve(request_id, key) if self.broker else False
