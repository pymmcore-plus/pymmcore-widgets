from __future__ import annotations

from typing import TYPE_CHECKING

from qtpy.QtWidgets import QApplication

from pymmcore_widgets import CoreLogWidget

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


def test_core_log_widget_init(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    """Asserts that the CoreLogWidget initializes with the entire log to this point."""
    wdg = CoreLogWidget()
    qtbot.addWidget(wdg)

    # Assert log path is in the widget LineEdit
    log_path = global_mmcore.getPrimaryLogFile()
    assert log_path == wdg._log_path.text()

    # Assert log content is in the widget TextEdit
    # This is a bit tricky because more can be appended to the log file.
    with open(log_path) as f:
        log_content = [s.strip() for s in f.readlines()]
    edit_content = [s.strip() for s in wdg._text_area.toPlainText().splitlines()]
    min_length = min(len(log_content), len(edit_content))
    for i in range(min_length):
        assert log_content[i] == edit_content[i]


def test_core_log_widget_update(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = CoreLogWidget()
    qtbot.addWidget(wdg)

    # Log something new
    current_lines = len(wdg._text_area.toPlainText().splitlines())
    new_message = "Test message"
    global_mmcore.logMessage(new_message)

    def wait_for_update() -> None:
        # Assert the new log message is in the TextEdit
        lines = wdg._text_area.toPlainText().splitlines()[current_lines:]
        for line in lines:
            print(line, "\n")
            if f"[IFO,App] {new_message}" in line:
                return
        raise AssertionError("New message not found in log widget.")

    qtbot.waitUntil(wait_for_update, timeout=1000)


def test_core_log_widget_autoscroll(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = CoreLogWidget()
    qtbot.addWidget(wdg)
    # Note that we must show the widget for the scrollbar maximum to be computed
    wdg.show()
    sb = wdg._text_area.verticalScrollBar()
    assert sb is not None

    def add_new_line() -> None:
        wdg._text_area.append("Test message")
        QApplication.processEvents()

    # Make sure we have a scrollbar with nonzero size to test with
    while sb.maximum() == 0:
        add_new_line()

    # Assert that adding a new line does not scroll if not at the bottom
    sb.setValue(sb.minimum())
    add_new_line()
    assert sb.value() == sb.minimum()

    # Assert that adding a new line does not scroll if not at the bottom
    old_max = sb.maximum()
    sb.setValue(old_max)
    add_new_line()
    assert sb.maximum() > old_max
    assert sb.value() == sb.maximum()
