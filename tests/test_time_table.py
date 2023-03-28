from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, cast

from qtpy.QtWidgets import QSpinBox, QTableWidget

from pymmcore_widgets._mda import TimePlanWidget

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

    from pymmcore_widgets._mda._time_plan_widget import _DoubleSpinAndCombo


def _value(table: QTableWidget, row: int):
    duration = cast("_DoubleSpinAndCombo", table.cellWidget(row, 0))
    interval = cast("_DoubleSpinAndCombo", table.cellWidget(row, 1))
    timepoints = cast("QSpinBox", table.cellWidget(row, 2))
    return duration, interval, timepoints


def test_time_table_widget(qtbot: QtBot):
    t = TimePlanWidget()
    qtbot.addWidget(t)

    assert t._table.rowCount() == 0
    t._add_button.click()
    t._add_button.click()
    assert t._table.rowCount() == 2

    duration, _, timepoints = _value(t._table, 0)
    assert not duration.isEnabled()
    assert timepoints.isEnabled()

    duration, _, timepoints = _value(t._table, 1)
    assert not duration.isEnabled()
    assert timepoints.isEnabled()

    t._table.selectRow(0)
    t._remove_button.click()
    assert t._table.rowCount() == 1

    t._clear_button.click()
    assert t._table.rowCount() == 0


def test_set_get_state(qtbot: QtBot):
    t = TimePlanWidget()
    qtbot.addWidget(t)

    state = {
        "phases": [
            {"interval": timedelta(seconds=30), "duration": timedelta(hours=3)},
            {"interval": timedelta(minutes=5), "loops": 5},
        ]
    }

    t.set_state(state)

    assert t._table.rowCount() == 2

    duration, interval, timepoints = _value(t._table, 0)
    assert duration.isEnabled()
    assert duration.value().total_seconds() == 10800
    assert not timepoints.isEnabled()
    assert interval.value().total_seconds() == 30

    duration, interval, timepoints = _value(t._table, 1)
    assert not duration.isEnabled()
    assert timepoints.isEnabled()
    assert timepoints.value() == 5
    assert interval.value().total_seconds() == 300

    assert t.value() == state
