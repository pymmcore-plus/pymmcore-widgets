from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pymmcore_plus import FocusDirection, Keyword
from pymmcore_plus.model import Microscope, Setting
from pymmcore_plus.model._config_group import ConfigGroup, ConfigPreset
from qtpy.QtCore import Qt
from qtpy.QtGui import QCloseEvent, QFocusEvent

from pymmcore_widgets.hcwizard import devices_page
from pymmcore_widgets.hcwizard._dev_setup_dialog import DeviceSetupDialog
from pymmcore_widgets.hcwizard._peripheral_setup_dialog import PeripheralSetupDlg
from pymmcore_widgets.hcwizard.config_wizard import (
    ConfigWizard,
    QMessageBox,
)
from pymmcore_widgets.hcwizard.finish_page import DEST_CONFIG
from pymmcore_widgets.hcwizard.labels_page import LabelsPage
from pymmcore_widgets.hcwizard.roles_page import RolesPage

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

    # Closing with unsaved changes and confirming discard should reject
    with patch.object(
        QMessageBox, "question", lambda *_: QMessageBox.StandardButton.Yes
    ):
        with qtbot.waitSignal(wiz.rejected):
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
    assert tuple(global_mmcore.getLoadedDevices()) == ("Core",)

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

    with patch.object(devices_page.DeviceSetupDialog, "exec", lambda *_: 1):
        with patch.object(devices_page.PeripheralSetupDlg, "exec", lambda *_: 1):
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


# ---- _check_configurations ----


def _make_wizard_with_loaded_config(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> ConfigWizard:
    """Create a wizard and navigate past intro to load the config into the model."""
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.next()  # loads config into model via IntroPage
    return wiz


def test_check_configurations_removes_stale_settings(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Stale settings referencing removed devices are cleaned up."""
    wiz = _make_wizard_with_loaded_config(global_mmcore, qtbot)

    stale = Setting(
        device_name="NonExistentDevice", property_name="Foo", property_value="Bar"
    )
    valid = Setting(device_name="Camera", property_name="Binning", property_value="1")
    group = ConfigGroup(name="TestGroup")
    group.presets["mixed"] = ConfigPreset(name="mixed", settings=[valid, stale])
    group.presets["all_stale"] = ConfigPreset(name="all_stale", settings=[stale])
    wiz._model.config_groups["TestGroup"] = group

    wiz._check_configurations()

    # "mixed" keeps only the valid setting; "all_stale" is removed
    assert "mixed" in wiz._model.config_groups["TestGroup"].presets
    mixed = wiz._model.config_groups["TestGroup"].presets["mixed"]
    assert all(s.device_name != "NonExistentDevice" for s in mixed.settings)
    assert "all_stale" not in wiz._model.config_groups["TestGroup"].presets


def test_check_configurations_removes_empty_groups(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Groups left with no presets are removed entirely."""
    wiz = _make_wizard_with_loaded_config(global_mmcore, qtbot)

    stale = Setting(device_name="GoneDevice", property_name="X", property_value="1")
    group = ConfigGroup(name="EmptyGroup")
    group.presets["only"] = ConfigPreset(name="only", settings=[stale])
    wiz._model.config_groups["EmptyGroup"] = group

    wiz._check_configurations()

    assert "EmptyGroup" not in wiz._model.config_groups


def test_check_configurations_cleans_pixel_size_presets(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Pixel size presets with stale device refs are cleaned up."""
    wiz = _make_wizard_with_loaded_config(global_mmcore, qtbot)

    stale = Setting(device_name="RemovedDev", property_name="Label", property_value="X")
    px = wiz._model.pixel_size_group
    px.presets["stale_res"] = ConfigPreset(name="stale_res", settings=[stale])

    wiz._check_configurations()

    assert "stale_res" not in px.presets


def test_check_configurations_keeps_core_device_settings(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Settings referencing the Core device are preserved."""
    wiz = _make_wizard_with_loaded_config(global_mmcore, qtbot)

    core_setting = Setting(
        device_name=Keyword.CoreDevice.value,
        property_name="ChannelGroup",
        property_value="Channel",
    )
    group = ConfigGroup(name="CoreGroup")
    group.presets["p"] = ConfigPreset(name="p", settings=[core_setting])
    wiz._model.config_groups["CoreGroup"] = group

    wiz._check_configurations()

    assert "CoreGroup" in wiz._model.config_groups
    assert len(wiz._model.config_groups["CoreGroup"].presets["p"].settings) == 1


# ---- accept / reject / closeEvent ----


def test_accept_saves_and_reloads(
    global_mmcore: CMMCorePlus, qtbot: QtBot, tmp_path: Path
) -> None:
    """Accept saves the config, unloads, then reloads from file."""
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    for _ in range(5):
        wiz.next()

    out = tmp_path / "out.cfg"
    wiz.setField(DEST_CONFIG, str(out))
    wiz.accept()

    assert out.exists()
    # Core should have been reloaded from the saved file
    assert global_mmcore.systemConfigurationFile() == str(out)


def test_close_event_no_changes_does_not_prompt(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Closing when clean should not show a dialog."""
    wiz = ConfigWizard("", core=global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()

    with patch.object(QMessageBox, "question") as mock_q:
        wiz.closeEvent(QCloseEvent())
        mock_q.assert_not_called()


def test_close_event_cancel_discard(global_mmcore: CMMCorePlus, qtbot: QtBot) -> None:
    """Declining discard on close should ignore the event."""
    wiz = _make_wizard_with_loaded_config(global_mmcore, qtbot)
    wiz._model.devices.pop()  # make dirty

    event = QCloseEvent()
    with patch.object(
        QMessageBox, "question", lambda *_: QMessageBox.StandardButton.No
    ):
        wiz.closeEvent(event)
    assert not event.isAccepted()


# ---- RolesPage focus directions ----


def test_roles_page_focus_directions(global_mmcore: CMMCorePlus, qtbot: QtBot) -> None:
    """Focus direction combos are built for stage devices and update model."""
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()

    roles_page = wiz.page(2)
    assert isinstance(roles_page, RolesPage)

    # Navigate to the roles page
    wiz.next()  # devices
    wiz.next()  # roles

    # Should have combos for stage devices (Z and Z1 from test config)
    assert roles_page._focus_dir_group.isVisible()
    assert len(roles_page._focus_dir_combos) >= 1

    # Change a focus direction and verify it updates the model
    stage_name = next(iter(roles_page._focus_dir_combos))
    combo = roles_page._focus_dir_combos[stage_name]
    combo.setCurrentIndex(1)  # "Toward Sample"

    dev = wiz._model.get_device(stage_name)
    assert dev.focus_direction == FocusDirection.TowardSample

    combo.setCurrentIndex(2)  # "Away From Sample"
    assert dev.focus_direction == FocusDirection.AwayFromSample


def test_roles_page_no_stages_hides_group(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Focus direction group is hidden when no stages exist."""
    global_mmcore.loadSystemConfiguration()
    wiz = ConfigWizard("", core=global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()

    roles_page = wiz.page(2)
    assert isinstance(roles_page, RolesPage)

    wiz.next()  # devices (empty)
    wiz.next()  # roles

    assert not roles_page._focus_dir_group.isVisible()
    assert len(roles_page._focus_dir_combos) == 0


# ---- LabelsPage read from hardware ----


def test_labels_page_read_from_hardware(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Read from Hardware button updates labels from core state."""
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()

    labels_page = wiz.page(4)
    assert isinstance(labels_page, LabelsPage)

    # Navigate to labels page
    for _ in range(4):
        wiz.next()

    # Should have state devices in the combo
    assert labels_page.dev_combo.count() > 0
    dev_name = labels_page.dev_combo.currentText()
    assert dev_name

    # Modify a label in the model to differ from hardware
    dev = wiz._model.get_device(dev_name)
    dev.set_label(0, "MODIFIED_LABEL")
    assert dev.labels[0] == "MODIFIED_LABEL"

    # Click "Read from Hardware" to restore from core
    labels_page._read_labels_from_hardware()

    # The label should now match what the hardware reports
    hw_labels = global_mmcore.getStateLabels(dev_name)
    assert dev.labels[0] == hw_labels[0]


def test_labels_page_read_from_hardware_no_device(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Read from Hardware does nothing when no device is selected."""
    global_mmcore.loadSystemConfiguration()
    wiz = ConfigWizard("", core=global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()

    labels_page = wiz.page(4)
    assert isinstance(labels_page, LabelsPage)

    # No devices loaded, combo should be empty
    for _ in range(4):
        wiz.next()

    assert labels_page.dev_combo.currentText() == ""
    # Should not raise
    labels_page._read_labels_from_hardware()


# ---- DevicesPage two-pass initialize & validatePage ----


def test_two_pass_initialize(global_mmcore: CMMCorePlus, qtbot: QtBot) -> None:
    """Two-pass initialization loads config and initializes devices."""
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.next()  # triggers initializePage on DevicesPage

    dev_page = wiz.page(1)
    assert isinstance(dev_page, devices_page.DevicesPage)

    # Devices should be populated after initialization
    assert len(dev_page._model.devices) > 0
    # Verify table was built
    assert dev_page.current.table.rowCount() > 0


def test_validate_page_syncs_parent_labels(
    global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """validatePage should sync parent labels from core to model."""
    wiz = ConfigWizard(str(TEST_CONFIG), global_mmcore)
    qtbot.addWidget(wiz)
    wiz.show()
    wiz.next()  # DevicesPage init

    dev_page = wiz.page(1)
    assert isinstance(dev_page, devices_page.DevicesPage)

    # Clear a parent_label in the model but leave the core reference intact
    camera_dev = wiz._model.get_device("Camera")
    assert camera_dev.parent_label  # should be "DHub" from config
    camera_dev.parent_label = ""

    dev_page.validatePage()

    # Should have been restored from core
    assert camera_dev.parent_label == "DHub"
