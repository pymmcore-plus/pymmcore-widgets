from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import Qt
from qtpy.QtGui import QUndoStack

from pymmcore_widgets import ConfigGroupsTree
from pymmcore_widgets._models import (
    ConfigGroup,
    Device,
    DevicePropertySetting,
    QConfigGroupsModel,
    QDevicePropertyModel,
    get_loaded_devices,
)
from pymmcore_widgets._models._q_device_prop_model import DevicePropertyFlatProxy
from pymmcore_widgets.config_presets import ConfigPresetsTable
from pymmcore_widgets.config_presets._views._checked_properties_proxy import (
    CheckedProxy,
)
from pymmcore_widgets.config_presets._views._device_property_selector import (
    DevicePropertySelector,
)
from pymmcore_widgets.config_presets._views._device_type_filter_proxy import (
    DeviceTypeFilter,
)
from pymmcore_widgets.config_presets._views._group_preset_selector import (
    GroupsPresetFinder,
)
from pymmcore_widgets.config_presets._views._property_setting_delegate import (
    PropertySettingDelegate,
)
from pymmcore_widgets.config_presets._views._undo_commands import (
    AddGroupCommand,
    AddPresetCommand,
    ChangePropertyValueCommand,
    DuplicateGroupCommand,
    DuplicatePresetCommand,
    RemoveGroupCommand,
    RemovePresetCommand,
    RenameGroupCommand,
    RenamePresetCommand,
    SetChannelGroupCommand,
    UpdatePresetPropertiesCommand,
    UpdatePresetSettingsCommand,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


def test_config_groups_tree(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    tree = ConfigGroupsTree.create_from_core(core)
    qtbot.addWidget(tree)
    tree.show()
    model = tree.model()
    assert isinstance(model, QConfigGroupsModel)

    # test the editor delegate -----------------------------

    delegate = tree.itemDelegateForColumn(2)
    assert isinstance(delegate, PropertySettingDelegate)

    setting_value = model.index(0, 2, model.index(0, 0, model.index(0, 0)))
    assert model.data(setting_value) == "1"

    # open an editor
    tree.edit(setting_value)
    editor = tree.focusWidget()
    assert hasattr(editor, "setValue") and hasattr(editor, "value")
    with qtbot.waitSignal(delegate.commitData):
        editor.setValue("2")

    # make sure the model is updated
    assert model.data(setting_value) == "2"
    group0 = model.get_groups()[0]
    preset0 = next(iter(group0.presets.values()))
    assert preset0.settings[0].value == "2"


def test_config_presets_table(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    table = ConfigPresetsTable.create_from_core(core)
    table.show()
    view = table.view
    model = table.sourceModel()
    assert isinstance(model, QConfigGroupsModel)

    table.setGroup("Channel")
    qtbot.addWidget(table)
    table.show()
    assert isinstance(table.sourceModel(), QConfigGroupsModel)

    assert not view.isTransposed()
    view.transpose()
    assert view.isTransposed()
    assert isinstance(table.sourceModel(), QConfigGroupsModel)

    view.transpose()
    assert not view.isTransposed()

    data = model.index(1).data(Qt.ItemDataRole.UserRole)  # type: ignore[attr-defined]
    assert isinstance(data, ConfigGroup)
    assert len(data.presets) == 4

    # test removing
    view.selectColumn(0)
    table.remove_action.trigger()
    assert len(data.presets) == 3

    # test duplicating
    view.selectColumn(0)
    table.duplicate_action.trigger()
    assert len(data.presets) == 4

    # check name of headers
    vm = view.model()
    assert vm
    header_names = [
        vm.headerData(i, Qt.Orientation.Horizontal) for i in range(vm.columnCount())
    ]
    assert header_names == ["DAPI", "DAPI copy", "FITC", "Rhodamine"]


# ── Fixtures for undo/proxy/widget tests ───────────────────────────


@pytest.fixture
def undo_model() -> tuple[QConfigGroupsModel, QUndoStack]:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    model = QConfigGroupsModel.create_from_core(core)
    stack = QUndoStack()
    return model, stack


# ── Undo Command Tests ─────────────────────────────────────────────


def test_undo_add_remove_group(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    initial = model.rowCount()

    # Add
    stack.push(AddGroupCommand(model, "UndoTestGroup"))
    assert model.rowCount() == initial + 1
    stack.undo()
    assert model.rowCount() == initial
    stack.redo()
    assert model.rowCount() == initial + 1

    # Remove (use a fresh stack to avoid interaction with add command)
    stack2 = QUndoStack()
    idx = model.index_for_group("UndoTestGroup")
    stack2.push(RemoveGroupCommand(model, idx))
    assert model.rowCount() == initial
    stack2.undo()
    assert model.rowCount() == initial + 1


def test_undo_duplicate_rename_group(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    initial = model.rowCount()
    grp0_idx = model.index(0, 0)
    old_name = grp0_idx.data(Qt.ItemDataRole.DisplayRole)

    # Duplicate
    stack.push(DuplicateGroupCommand(model, grp0_idx))
    assert model.rowCount() == initial + 1
    stack.undo()
    assert model.rowCount() == initial
    stack.redo()
    assert model.rowCount() == initial + 1
    stack.undo()  # clean up

    # Rename
    stack.push(RenameGroupCommand(model, grp0_idx, "RenamedGroup"))
    assert grp0_idx.data(Qt.ItemDataRole.DisplayRole) == "RenamedGroup"
    stack.undo()
    assert grp0_idx.data(Qt.ItemDataRole.DisplayRole) == old_name
    stack.redo()
    assert grp0_idx.data(Qt.ItemDataRole.DisplayRole) == "RenamedGroup"


def test_undo_add_remove_preset(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    initial_presets = model.rowCount(grp_idx)

    # Add preset
    stack.push(AddPresetCommand(model, grp_idx, "UndoPreset"))
    assert model.rowCount(grp_idx) == initial_presets + 1
    stack.undo()
    assert model.rowCount(grp_idx) == initial_presets
    stack.redo()
    assert model.rowCount(grp_idx) == initial_presets + 1

    # Remove preset (fresh stack to avoid interaction)
    stack2 = QUndoStack()
    preset_idx = model.index_for_preset(grp_idx, "UndoPreset")
    stack2.push(RemovePresetCommand(model, preset_idx))
    assert model.rowCount(grp_idx) == initial_presets
    stack2.undo()
    assert model.rowCount(grp_idx) == initial_presets + 1


def test_undo_duplicate_rename_preset(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    old_name = preset_idx.data(Qt.ItemDataRole.DisplayRole)
    initial_presets = model.rowCount(grp_idx)

    # Duplicate
    stack.push(DuplicatePresetCommand(model, preset_idx))
    assert model.rowCount(grp_idx) == initial_presets + 1
    stack.undo()
    assert model.rowCount(grp_idx) == initial_presets
    stack.redo()
    assert model.rowCount(grp_idx) == initial_presets + 1
    stack.undo()

    # Rename
    stack.push(RenamePresetCommand(model, preset_idx, "RenamedPreset"))
    assert preset_idx.data(Qt.ItemDataRole.DisplayRole) == "RenamedPreset"
    stack.undo()
    assert preset_idx.data(Qt.ItemDataRole.DisplayRole) == old_name
    stack.redo()
    assert preset_idx.data(Qt.ItemDataRole.DisplayRole) == "RenamedPreset"


def test_undo_change_property_value(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    value_idx = model.index(0, 2, preset_idx)  # value column
    old_value = value_idx.data(Qt.ItemDataRole.DisplayRole)

    stack.push(ChangePropertyValueCommand(model, value_idx, "NewVal"))
    assert value_idx.data(Qt.ItemDataRole.DisplayRole) == "NewVal"
    stack.undo()
    assert value_idx.data(Qt.ItemDataRole.DisplayRole) == old_value
    stack.redo()
    assert value_idx.data(Qt.ItemDataRole.DisplayRole) == "NewVal"


def test_undo_update_preset_settings(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    preset = preset_idx.data(Qt.ItemDataRole.UserRole)
    old_count = len(preset.settings)

    new_settings = [DevicePropertySetting(device="D", property_name="P", value="V")]
    stack.push(UpdatePresetSettingsCommand(model, preset_idx, new_settings))

    updated = preset_idx.data(Qt.ItemDataRole.UserRole)
    assert len(updated.settings) == 1
    stack.undo()
    restored = preset_idx.data(Qt.ItemDataRole.UserRole)
    assert len(restored.settings) == old_count
    stack.redo()
    assert len(preset_idx.data(Qt.ItemDataRole.UserRole).settings) == 1


def test_undo_update_preset_properties(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    preset = preset_idx.data(Qt.ItemDataRole.UserRole)
    old_count = len(preset.settings)

    new_props = [
        DevicePropertySetting(device="NewDev", property_name="NewProp", value="x")
    ]
    stack.push(UpdatePresetPropertiesCommand(model, preset_idx, new_props))
    updated = preset_idx.data(Qt.ItemDataRole.UserRole)
    assert len(updated.settings) == 1

    stack.undo()
    restored = preset_idx.data(Qt.ItemDataRole.UserRole)
    assert len(restored.settings) == old_count


def test_undo_redo_across_add_and_rename(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    """Redo of rename must work after the target was removed and re-added."""
    model, stack = undo_model
    initial = model.rowCount()

    # add group 0
    stack.push(AddGroupCommand(model, "G0"))
    assert model.rowCount() == initial + 1

    # add group 1
    stack.push(AddGroupCommand(model, "G1"))
    assert model.rowCount() == initial + 2
    g1_idx = model.index(initial + 1, 0)
    assert g1_idx.data(Qt.ItemDataRole.DisplayRole) == "G1"

    # rename group 1 -> "asdf"
    stack.push(RenameGroupCommand(model, g1_idx, "asdf"))
    assert model.index(initial + 1, 0).data(Qt.ItemDataRole.DisplayRole) == "asdf"

    # undo rename
    stack.undo()
    assert model.index(initial + 1, 0).data(Qt.ItemDataRole.DisplayRole) == "G1"

    # undo add group 1
    stack.undo()
    assert model.rowCount() == initial + 1

    # redo add group 1
    stack.redo()
    assert model.rowCount() == initial + 2
    assert model.index(initial + 1, 0).data(Qt.ItemDataRole.DisplayRole) == "G1"

    # redo rename -> should rename group 1 to "asdf"
    stack.redo()
    assert model.index(initial + 1, 0).data(Qt.ItemDataRole.DisplayRole) == "asdf"


def test_undo_set_channel_group(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model

    # Find the current channel group
    old_channels = {g.name for g in model.get_groups() if g.is_channel_group}
    assert "Channel" in old_channels

    # Set Camera as channel group
    cam_idx = model.index_for_group("Camera")
    stack.push(SetChannelGroupCommand(model, cam_idx))
    new_channels = {g.name for g in model.get_groups() if g.is_channel_group}
    assert "Camera" in new_channels
    assert "Channel" not in new_channels

    stack.undo()
    restored = {g.name for g in model.get_groups() if g.is_channel_group}
    assert "Channel" in restored

    stack.redo()
    assert "Camera" in {g.name for g in model.get_groups() if g.is_channel_group}

    # Unset channel group
    stack.push(SetChannelGroupCommand(model, None))
    assert not any(g.is_channel_group for g in model.get_groups())
    stack.undo()
    assert "Camera" in {g.name for g in model.get_groups() if g.is_channel_group}


# ── Proxy Model Tests ──────────────────────────────────────────────


def test_checked_proxy() -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    model = QDevicePropertyModel.create_from_core(core)
    proxy = CheckedProxy(check_column=0, parent=None)
    proxy.setSourceModel(model)

    # With nothing checked, the proxy should have no leaf rows
    # (devices with no checked children should be filtered out)
    for i in range(proxy.rowCount()):
        dev_idx = proxy.index(i, 0)
        assert (
            proxy.rowCount(dev_idx) == 0
            or proxy.data(dev_idx, Qt.ItemDataRole.CheckStateRole)
            == Qt.CheckState.Checked
        )

    # Check a property
    dev_idx = model.index(0, 0)
    prop_idx = model.index(0, 0, dev_idx)
    prop = prop_idx.data(Qt.ItemDataRole.UserRole)
    if isinstance(prop, DevicePropertySetting) and not (
        prop.is_read_only or prop.is_pre_init
    ):
        model.setData(prop_idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        # Proxy should now show this device and its checked child
        assert proxy.rowCount() > 0

        # Uncheck
        model.setData(prop_idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)


def test_device_type_filter() -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    model = QDevicePropertyModel.create_from_core(core)
    filt = DeviceTypeFilter(allowed={DeviceType.Camera}, parent=None)
    filt.setSourceModel(model)

    # Only camera device should pass
    for i in range(filt.rowCount()):
        idx = filt.index(i, 0)
        dev = idx.data(Qt.ItemDataRole.UserRole)
        if isinstance(dev, Device):
            assert dev.type == DeviceType.Camera

    # Toggle read-only visibility
    filt.setReadOnlyVisible(True)
    filt.setReadOnlyVisible(False)

    # Toggle pre-init visibility
    filt.setPreInitVisible(True)
    filt.setPreInitVisible(False)

    # Filter by text
    filt.setFilterFixedString("Binning")
    # After text filter, properties shown should contain "Binning"
    count = 0
    for i in range(filt.rowCount()):
        dev_idx = filt.index(i, 0)
        for j in range(filt.rowCount(dev_idx)):
            prop_name = filt.index(j, 0, dev_idx).data(Qt.ItemDataRole.DisplayRole)
            if prop_name:
                assert "Binning" in prop_name or "binning" in prop_name.lower()
                count += 1
    assert count > 0

    # Change allowed types
    filt.setAllowedDeviceTypes({DeviceType.Any})


# ── DevicePropertySelector Tests ───────────────────────────────────


def test_device_property_selector_basic(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    devices = list(get_loaded_devices(core))

    selector = DevicePropertySelector()
    qtbot.addWidget(selector)
    selector.setAvailableDevices(devices)
    assert selector.tree.model() is not None

    # Check some properties
    settings = []
    for d in devices:
        for p in d.properties:
            if not p.is_read_only and not p.is_pre_init:
                settings.append(p)
                if len(settings) >= 2:
                    break
        if len(settings) >= 2:
            break

    if settings:
        selector.setCheckedProperties(settings)
        checked = selector.checkedProperties()
        assert len(checked) == len(settings)

        selector.clearCheckedProperties()
        assert len(selector.checkedProperties()) == 0


def test_device_property_selector_view_modes(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    devices = list(get_loaded_devices(core))

    selector = DevicePropertySelector()
    qtbot.addWidget(selector)
    selector.setAvailableDevices(devices)

    # Default is flat (table) mode
    assert isinstance(selector.tree.model(), DevicePropertyFlatProxy)

    # Switch to tree view
    selector._toggle_view_mode(True)
    assert isinstance(selector.tree.model(), DeviceTypeFilter)

    # Switch back to table view
    selector._toggle_view_mode(False)
    assert isinstance(selector.tree.model(), DevicePropertyFlatProxy)

    # Enable checked-only mode
    selector._toggle_checked_only(True)
    assert isinstance(selector.tree.model(), DevicePropertyFlatProxy)
    assert not selector._tb2.act_toggle_view.isEnabled()
    assert not selector._dev_type_btns.isEnabled()

    # Disable checked-only mode
    selector._toggle_checked_only(False)
    assert selector._tb2.act_toggle_view.isEnabled()
    assert selector._dev_type_btns.isEnabled()


# ── GroupsPresetFinder Tests ───────────────────────────────────────


def test_groups_preset_finder(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    model = QConfigGroupsModel.create_from_core(core)

    finder = GroupsPresetFinder()
    qtbot.addWidget(finder)
    finder.setModel(model)

    # Set current group
    with qtbot.waitSignal(finder.currentGroupChanged):
        idx = finder.setCurrentGroup("Channel")
    assert idx.isValid()
    assert finder.currentGroup().isValid()

    # Set current preset
    with qtbot.waitSignal(finder.currentPresetChanged):
        idx = finder.setCurrentPreset("Channel", "DAPI")
    assert idx.isValid()
    assert finder.currentPreset().isValid()

    # View toggle
    finder.showTreeView()
    assert finder.isTreeViewActive()
    assert finder.currentIndex() == 1

    finder.showColumnView()
    assert not finder.isTreeViewActive()
    assert finder.currentIndex() == 0

    # Clear selection
    finder.clearSelection()
    assert not finder.currentGroup().isValid()


def test_groups_preset_finder_remove_duplicate(qtbot: QtBot) -> None:
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    model = QConfigGroupsModel.create_from_core(core)
    stack = QUndoStack()

    finder = GroupsPresetFinder()
    qtbot.addWidget(finder)
    finder.setModel(model)
    finder.setUndoStack(stack)

    initial_groups = model.rowCount()

    # Select and duplicate a group
    finder.setCurrentGroup("Camera")
    finder.group_list.setFocus()
    finder.duplicateSelected()
    assert model.rowCount() == initial_groups + 1

    # Undo
    stack.undo()
    assert model.rowCount() == initial_groups


def test_device_property_selector_prompt(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test promptForProperties with mocked dialog exec."""
    from qtpy.QtWidgets import QDialog

    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    core = CMMCorePlus()
    core.loadSystemConfiguration()
    devices = list(get_loaded_devices(core))
    result = DevicePropertySelector.promptForProperties(devices=devices)
    assert result == ()
