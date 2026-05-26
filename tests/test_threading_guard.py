"""Tests für threading_guard.py — Main-Thread-Assertion."""

import threading

import pytest

from wnflow.threading_guard import (
    MainThreadViolation,
    assert_main_thread,
    is_main_thread,
)


def test_is_main_thread_in_test_thread() -> None:
    # pytest läuft im Main-Thread
    assert is_main_thread() is True


def test_assert_main_thread_does_not_raise_in_main() -> None:
    assert_main_thread()  # darf nicht raisen


def test_assert_main_thread_raises_in_worker_thread() -> None:
    error_caught = []

    def worker() -> None:
        try:
            assert_main_thread()
        except MainThreadViolation as exc:
            error_caught.append(exc)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert len(error_caught) == 1


def test_assert_main_thread_includes_caller_label_in_message() -> None:
    error_messages = []

    def worker_with_label() -> None:
        try:
            assert_main_thread("my_function")
        except MainThreadViolation as exc:
            error_messages.append(str(exc))

    thread = threading.Thread(target=worker_with_label)
    thread.start()
    thread.join()
    assert len(error_messages) == 1
    assert "my_function" in error_messages[0]
