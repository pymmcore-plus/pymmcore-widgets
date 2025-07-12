from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from unittest.mock import Mock

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytestqt.qtbot import QtBot
    from qtpy.QtCore import SignalInstance


@contextmanager
def wait_signal(
    qtbot: QtBot, signal: SignalInstance, timeout: int = 2000
) -> Iterator[None]:
    """Context manager to wait for a signal.

    In some (as of yet understood) cases, qtbot.waitSignal() causes segfaults with
    PySide6.  Using manual polling like this seems to work around the issue.
    """
    mock = Mock()
    signal.connect(mock)
    try:
        yield
        qtbot.waitUntil(lambda: mock.call_count > 0, timeout=timeout)
    finally:
        signal.disconnect(mock)
