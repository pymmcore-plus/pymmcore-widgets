from pathlib import Path
from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, QTimer
from qtpy.QtWidgets import QMessageBox

from pymmcore_widgets.hcwizard._dev_setup_dialog import DeviceSetupDialog
from pymmcore_widgets.hcwizard._peripheral_setup_dialog import PeripheralSetupDlg
from pymmcore_widgets.hcwizard.config_wizard import ConfigWizard
from pymmcore_widgets.hcwizard.devices_page import DevicesPage
from pymmcore_widgets.hcwizard.finish_page import DEST_CONFIG

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot

TEST_CONFIG = Path(__file__).parent / "test_config.cfg"


def _non_empty_lines(path: Path) -> list[str]:
    return [
        ln
        for line in path.read_text().splitlines()
        if (ln := line.strip()) and not ln.startswith("#")
    ]


def test_config_wizard(global_mmcore: CMMCorePlus, qtbot, tmp_path: Path):
    out = tmp_path / "out.cfg"
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
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


# TODO: Long integration test here... maybe split it up
def test_config_wizard_devices(
    global_mmcore: CMMCorePlus, qtbot: "QtBot", tmp_path: Path, qapp
):
    global_mmcore.unloadAllDevices()
    assert global_mmcore.getLoadedDevices() == ("Core",)

    wiz = ConfigWizard(core=global_mmcore)
    wiz.show()
    page = wiz.page(1)
    assert isinstance(page, DevicesPage)
    qtbot.addWidget(wiz)
    out = tmp_path / "out.cfg"
    wiz.setField(DEST_CONFIG, str(out))
    wiz.next()

    assert page.available.table.rowCount()

    # test sorting
    page.available.table.horizontalHeader().sectionClicked.emit(1)
    assert page.available._sorted_col == 1

    # enter text in filter and select a row
    page.available.filter.setText("Demo Camera")
    for r in range(page.available.table.rowCount()):
        item = page.available.table.item(r, 1)
        if item.text() == "DHub":
            break
    page.available.table.selectRow(r)
    assert page.available.table.selectedItems()

    # simulate pressing enter and adding a hub
    NAME = "MyCAM"

    def accept1():
        # accept the device setup dialog
        d = next(i for i in qapp.topLevelWidgets() if isinstance(i, DeviceSetupDialog))
        QTimer.singleShot(10, accept2)
        with qtbot.waitSignal(d.accepted):
            d.accept()

    def accept2():
        # check the second row of the peripherals dialog
        # change name, and accept
        d = next(i for i in qapp.topLevelWidgets() if isinstance(i, PeripheralSetupDlg))
        item = d.table.item(1, 0)
        item.setCheckState(Qt.CheckState.Checked)
        item.setText(NAME)
        d.accept()

    QTimer.singleShot(10, accept1)

    # trigger the device setup dialog
    qtbot.keyPress(page.available, Qt.Key.Key_Return)
    # confirm it's been added
    d = wiz._model.devices
    assert len(d) == 2
    assert d[-1].name == NAME

    # confirm added to top table
    assert page.current.table.rowCount() == 2

    wiz.next()
    wiz.back()

    def accept3():
        # accept the device setup dialog
        d = next(i for i in qapp.topLevelWidgets() if isinstance(i, DeviceSetupDialog))
        with qtbot.waitSignal(d.accepted):
            d.accept()

    # select 2nd row and edit
    page.current.table.selectRow(1)
    QTimer.singleShot(100, accept3)
    page.current.edit_btn.click()

    def accept4():
        # accept the device setup dialog
        d = next(i for i in qapp.topLevelWidgets() if isinstance(i, QMessageBox))
        with qtbot.waitSignal(d.accepted):
            d.accept()

    page.current.table.selectAll()
    QTimer.singleShot(100, accept4)
    qtbot.keyPress(page.current, Qt.Key.Key_Delete)
    assert page.current.table.rowCount() == 0
    assert not wiz._model.devices
    assert global_mmcore.getLoadedDevices() == ("Core",)
