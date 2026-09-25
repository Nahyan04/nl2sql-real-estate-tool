from __future__ import annotations

import threading
import time
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator


class ModelBusyError(RuntimeError):
    pass


class RequestDeadlineError(TimeoutError):
    pass


class ModelRuntime:
    """Bound active and waiting model calls within one API worker.

    Deployment-wide admission and spend accounting require the shared limiter
    planned separately; this guard prevents one worker from growing an
    unbounded inference queue in the meantime.
    """

    def __init__(self, concurrency: int, queue_size: int, queue_wait_s: float):
        self._slots = threading.BoundedSemaphore(concurrency)
        self._queue_size = queue_size
        self._queue_wait_s = queue_wait_s
        self._lock = threading.Lock()
        self._waiting = 0

    @contextmanager
    def admit(self, deadline: float) -> Iterator[None]:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RequestDeadlineError("Request deadline reached before the model call")

        if self._slots.acquire(blocking=False):
            acquired = True
        else:
            with self._lock:
                if self._waiting >= self._queue_size:
                    raise ModelBusyError("Model queue is full")
                self._waiting += 1
            try:
                wait_for = min(self._queue_wait_s, remaining)
                acquired = self._slots.acquire(timeout=wait_for)
            finally:
                with self._lock:
                    self._waiting -= 1
            if not acquired:
                if deadline - time.monotonic() <= 0:
                    raise RequestDeadlineError("Request deadline reached waiting for the model")
                raise ModelBusyError("Model capacity is temporarily unavailable")

        try:
            if deadline - time.monotonic() <= 0:
                raise RequestDeadlineError("Request deadline reached before the model call")
            yield
            if deadline - time.monotonic() <= 0:
                raise RequestDeadlineError("Request deadline reached during the model call")
        finally:
            self._slots.release()


@lru_cache(maxsize=16)
def get_model_runtime(concurrency: int, queue_size: int, queue_wait_s: float) -> ModelRuntime:
    return ModelRuntime(concurrency, queue_size, queue_wait_s)
