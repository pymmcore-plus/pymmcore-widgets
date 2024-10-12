from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pymmcore_plus.model import Microscope
from qtpy import API_NAME
from qtpy.QtCore import Qt
from qtpy.QtGui import QCloseEvent, QFocusEvent

from pymmcore_widgets.hcwizard import devices_page
from pymmcore_widgets.hcwizard._dev_setup_dialog import DeviceSetupDialog
from pymmcore_widgets.hcwizard._peripheral_setup_dialog import PeripheralSetupDlg
from pymmcore_widgets.hcwizard.config_wizard import (
    ConfigWizard,
    QFileDialog,
    QMessageBox,
)
from pymmcore_widgets.hcwizard.finish_page import DEST_CONFIG

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot

TEST_CONFIG = Path(__file__).parent / "test_config.cfg"


def test_config_wizard_new_empty(
    global_mmcore: CMMCorePlus, qtbot, tmp_path: Path
) -> None:
    global_mmcore.loadSystemConfiguration()
    wiz = ConfigWizard("", core=global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.next()
    out = tmp_path / "out.cfg"
    wiz.setField(DEST_CONFIG, str(out))
    wiz.accept()
    assert "Property,Core,Camera" not in out.read_text()


def test_config_wizard(global_mmcore: CMMCorePlus, qtbot, tmp_path: Path):
    out = tmp_path / "out.cfg"
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.next()
    wiz.setField(DEST_CONFIG, str(out))
    wiz.accept()
    assert out.exists()

    global_mmcore.loadSystemConfiguration(str(TEST_CONFIG))
    st1 = global_mmcore.getSystemState()

    global_mmcore.loadSystemConfiguration(str(out))
    st2 = global_mmcore.getSystemState()

    assert st1 == st2
    wiz._model.devices.pop()

    with patch.object(
        QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Save
    ):
        with patch.object(QFileDialog, "getSaveFileName", lambda *_: (str(out), "")):
            with qtbot.waitSignal(wiz.accepted):
                wiz.closeEvent(QCloseEvent())


def test_config_wizard_rejection(global_mmcore: CMMCorePlus, qtbot, tmp_path: Path):
    global_mmcore.loadSystemConfiguration(str(TEST_CONFIG))
    st1 = global_mmcore.getSystemState()

    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.reject()

    # Assert system state prior to wizard execution still present
    st2 = global_mmcore.getSystemState()

    assert st1 == st2


def test_config_wizard_devices(
    global_mmcore: CMMCorePlus, qtbot: QtBot, tmp_path: Path, qapp
):
    global_mmcore.unloadAllDevices()
    assert global_mmcore.getLoadedDevices() == ("Core",)

    wiz = ConfigWizard(core=global_mmcore)
    wiz.show()
    dev_page = wiz.page(1)
    assert isinstance(dev_page, devices_page.DevicesPage)
    qtbot.addWidget(wiz)
    out = tmp_path / "out.cfg"
    wiz.setField(DEST_CONFIG, str(out))
    wiz.next()

    assert dev_page.available.table.rowCount()

    # test sorting
    dev_page.available.table.horizontalHeader().sectionClicked.emit(1)
    assert dev_page.available._sorted_col == 1

    # enter text in filter and select a row
    dev_page.available.filter.setText("Demo Camera")
    for r in range(dev_page.available.table.rowCount()):
        item = dev_page.available.table.item(r, 1)
        if item.text() == "DHub":
            break
    dev_page.available.table.selectRow(r)
    assert dev_page.available.table.selectedItems()

    exec_ = "exec_" if API_NAME == "PySide2" else "exec"
    with patch.object(devices_page.DeviceSetupDialog, exec_, lambda *_: 1):
        with patch.object(devices_page.PeripheralSetupDlg, exec_, lambda *_: 1):
            dev_page.available._add_selected_device()

    dev_page.current.table.selectAll()
    assert dev_page.current.table.selectedItems()
    dev_page.current._remove_selected_devices()
    assert not dev_page._model.devices


def test_device_setup_dialog(qtbot, global_mmcore: CMMCorePlus):
    dlg = DeviceSetupDialog.for_loaded_device(global_mmcore, "Camera")
    dlg.show()
    qtbot.addWidget(dlg)
    dlg._on_ok_clicked()
    dlg._reload_device()
    dlg.reject()
    assert "Camera" in global_mmcore.getLoadedDevices()
    dlg.close()

    global_mmcore.unloadAllDevices()
    assert "DHub" not in global_mmcore.getLoadedDevices()
    dlg2 = DeviceSetupDialog.for_new_device(global_mmcore, "DemoCamera", "DHub")
    qtbot.addWidget(dlg2)
    assert "DHub" in global_mmcore.getLoadedDevices()

    with qtbot.waitSignal(dlg2.name_edit.editingFinished):
        dlg2.name_edit.focusInEvent(QFocusEvent(QFocusEvent.Type.FocusIn))
        dlg2.name_edit.setText("MyHub")
        dlg2.name_edit.editingFinished.emit()
    assert "DHub" not in global_mmcore.getLoadedDevices()
    assert "MyHub" in global_mmcore.getLoadedDevices()
    assert dlg2.deviceLabel() == "MyHub"

    dlg2._on_ok_clicked()
    dlg2._reload_device()
    dlg2.reject()
    assert "MyHub" not in global_mmcore.getLoadedDevices()


def test_peripheral_setup_dialog(qtbot, global_mmcore: CMMCorePlus):
    model = Microscope.create_from_core(global_mmcore)

    with pytest.raises(ValueError):
        dlg = PeripheralSetupDlg(model.get_device("Camera"), model, global_mmcore)

    dlg = PeripheralSetupDlg(model.get_device("DHub"), model, global_mmcore)
    dlg.show()
    qtbot.addWidget(dlg)

    assert dlg.table.rowCount()
    assert not list(dlg.selectedPeripherals())

    item = dlg.table.item(1, 0)
    item.setCheckState(Qt.CheckState.Checked)
    item.setText("SomeDevice")
    assert list(dlg.selectedPeripherals())
    dlg.accept()
    assert "SomeDevice" in global_mmcore.getLoadedDevices()
