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

    wdg.clear()
    with qtbot.waitSignal(global_mmcore.events.systemConfigurationLoaded):
        global_mmcore.loadSystemConfiguration()

    def _check_log() -> None:
        if "Finished initializing" not in wdg._log_view.toPlainText():
            raise AssertionError("CoreLogWidget did not finish initializing.")

    qtbot.waitUntil(_check_log, timeout=1000)


def test_core_log_widget_update(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = CoreLogWidget()
    qtbot.addWidget(wdg)
    # Remove some lines for faster checking later
    wdg._log_view.clear()

    # Log something new
    new_message = "Test message"
    global_mmcore.logMessage(new_message)

    def wait_for_update() -> None:
        # Sometimes, our new message will be flushed before other initialization
        # completes. Thus we need to check all lines after what is currently written to
        # the TextEdit.
        all_lines = wdg._log_view.toPlainText().splitlines()
        for line in reversed(all_lines):
            if f"[IFO,App] {new_message}" in line:
                return
        raise AssertionError("New message not found in CoreLogWidget.")

    qtbot.waitUntil(wait_for_update, timeout=1000)


def test_core_log_widget_clear(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = CoreLogWidget()
    qtbot.addWidget(wdg)

    assert wdg._log_view.toPlainText() != ""
    wdg._clear_btn.click()
    assert wdg._log_view.toPlainText() == ""


def test_core_log_widget_autoscroll(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    wdg = CoreLogWidget()
    qtbot.addWidget(wdg)
    # Note that we must show the widget for the scrollbar maximum to be computed
    wdg.show()
    sb = wdg._log_view.verticalScrollBar()
    assert sb is not None

    def add_new_line() -> None:
        wdg._append_line("Test message")
        QApplication.processEvents()

    # Make sure we have a scrollbar with nonzero size to test with
    # But we don't want it full yet
    wdg._log_view.clear()
    while sb.maximum() == 0:
        add_new_line()

    # Assert that adding a new line does not scroll if not at the bottom
    sb.setValue(sb.minimum())
    add_new_line()
    assert sb.value() == sb.minimum()

    # Assert that adding a new line does scroll if at the bottom
    old_max = sb.maximum()
    sb.setValue(old_max)
    add_new_line()
    assert sb.maximum() == old_max + 1
    assert sb.value() == sb.maximum()
