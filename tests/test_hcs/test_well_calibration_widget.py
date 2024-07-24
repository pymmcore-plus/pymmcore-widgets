from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from pymmcore_widgets.hcs._well_calibration_widget import (
    COMBO_ROLE,
    MODES,
    WellCalibrationWidget,
)

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot
    from qtpy.QtWidgets import QLabel

YELLOW = "#ffff00"
GREEN = "#00ff00"


def get_icon_color(qlabel: QLabel):
    pixmap = qlabel.pixmap()
    image = pixmap.toImage()
    pixel_color = image.pixelColor(image.width() // 2, image.height() // 2)
    return pixel_color.name()


def test_well_calibration_widget(qtbot: QtBot, global_mmcore: CMMCorePlus) -> None:
    """Test the WellCalibrationWidget."""
    wdg = WellCalibrationWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    # make sure the table has the correct number of rows and columns
    assert not wdg._table.rowCount()
    assert not list(wdg._table.positions())
    assert wdg._table.columnCount() == 2

    # get the icon color
    assert get_icon_color(wdg._calibration_icon) == YELLOW


@pytest.mark.parametrize("circular", [True, False])
def test_well_calibration_widget_modes(
    qtbot: QtBot, global_mmcore: CMMCorePlus, circular: bool
) -> None:
    """Test the WellCalibrationWidget."""
    wdg = WellCalibrationWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    # set circular well property
    wdg.setCircularWell(circular)
    assert wdg.circularWell() == circular
    # get the modes form the combobox
    combo = wdg._calibration_mode_wdg
    modes = [combo.itemData(i, COMBO_ROLE) for i in range(combo.count())]
    # make sure the modes are correct
    assert modes == MODES[circular]
    # make sure that the correct number of rows are displayed when the mode is changed
    for idx, mode in enumerate(modes):
        # set the mode
        combo.setCurrentIndex(idx)
        # get the number of rows
        assert wdg._table.rowCount() == mode.points


def test_well_calibration_widget_positions(
    qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    """Test the WellCalibrationWidget."""
    wdg = WellCalibrationWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setCircularWell(True)

    assert get_icon_color(wdg._calibration_icon) == YELLOW

    assert wdg._table.rowCount() == 1
    assert not list(wdg._table.positions())

    assert wdg._mmc.getXPosition() == 0
    assert wdg._mmc.getYPosition() == 0

    # make sure nothing happens when the set button is clicked multiple times if
    # the number of rows is already the maximum
    for _ in range(2):
        wdg._on_set_clicked()
        assert wdg._table.rowCount() == 1
        assert list(wdg._table.positions()) == [(0, 0, 0)]

    # the well should be calibrated and icon should be green
    assert get_icon_color(wdg._calibration_icon) == GREEN

    # set 3 points mode
    wdg._calibration_mode_wdg.setCurrentIndex(1)
    assert wdg._table.rowCount() == 3
    assert not list(wdg._table.positions())

    # icon should be yellow since we changed the mode
    assert get_icon_color(wdg._calibration_icon) == YELLOW

    wdg._on_set_clicked()
    assert wdg._table.rowCount() == 3
    assert list(wdg._table.positions()) == [(0, 0, 0)]

    # make sure you cannot add the same position twice
    with patch("qtpy.QtWidgets.QMessageBox.critical") as mock_critical:
        wdg._on_set_clicked()
        mock_critical.assert_called_once()

    # add 2 more positions
    global_mmcore.setXYPosition(10, 10)
    global_mmcore.waitForSystem()
    wdg._on_set_clicked()
    assert (1, 10, 10) in list(wdg._table.positions())

    # well still not calibrated
    assert get_icon_color(wdg._calibration_icon) == YELLOW

    global_mmcore.setXYPosition(10, -10)
    global_mmcore.waitForSystem()
    with qtbot.waitSignal(wdg.calibrationChanged):
        wdg._on_set_clicked()
    assert (2, 10, -10) in list(wdg._table.positions())

    # well should be calibrated and icon should be green
    center = wdg.wellCenter()
    assert center is not None
    assert (round(center[0]), round(center[1])) == (10, 0)
    assert get_icon_color(wdg._calibration_icon) == GREEN


def test_well_calibration_widget_clear(
    qtbot: QtBot, global_mmcore: CMMCorePlus
) -> None:
    """Test the WellCalibrationWidget."""
    wdg = WellCalibrationWidget(mmcore=global_mmcore)
    qtbot.addWidget(wdg)
    wdg.show()

    wdg.setCircularWell(True)
    wdg._calibration_mode_wdg.setCurrentIndex(1)

    values = [(0, 0), (10, 10), (10, -10)]
    for r in range(3):
        wdg._table.selectRow(r)
        wdg._table.set_selected(*values[r])

    assert len(list(wdg._table.positions())) == 3

    # test the clear button
    wdg._table.selectRow(1)
    wdg._clear_button.click()
    assert len(list(wdg._table.positions())) == 2

    # test clear all
    wdg._clear_all_button.click()
    assert not list(wdg._table.positions())
