from __future__ import annotations

import threading
import time

import pytest

from app.services.model_runtime import ModelBusyError, ModelRuntime, RequestDeadlineError


def test_rejects_when_active_and_waiting_capacity_are_full() -> None:
    runtime = ModelRuntime(concurrency=1, queue_size=0, queue_wait_s=0.1)
    with runtime.admit(time.monotonic() + 1):
        with pytest.raises(ModelBusyError, match="queue is full"):
            with runtime.admit(time.monotonic() + 1):
                pass


def test_waiter_can_take_released_slot() -> None:
    runtime = ModelRuntime(concurrency=1, queue_size=1, queue_wait_s=0.5)
    entered = threading.Event()

    def wait_for_slot() -> None:
        with runtime.admit(time.monotonic() + 1):
            entered.set()

    with runtime.admit(time.monotonic() + 1):
        worker = threading.Thread(target=wait_for_slot)
        worker.start()
        time.sleep(0.02)
        assert not entered.is_set()
    worker.join(timeout=1)
    assert entered.is_set()


def test_expired_deadline_is_rejected_before_admission() -> None:
    runtime = ModelRuntime(concurrency=1, queue_size=0, queue_wait_s=0.1)
    with pytest.raises(RequestDeadlineError, match="before the model call"):
        with runtime.admit(time.monotonic() - 1):
            pass


def test_call_that_crosses_deadline_is_reported() -> None:
    runtime = ModelRuntime(concurrency=1, queue_size=0, queue_wait_s=0.1)
    with pytest.raises(RequestDeadlineError, match="during the model call"):
        with runtime.admit(time.monotonic() + 0.01):
            time.sleep(0.02)
