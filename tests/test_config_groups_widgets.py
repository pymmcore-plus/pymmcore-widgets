from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import QEvent, QPointF, Qt
from qtpy.QtGui import QContextMenuEvent, QKeyEvent, QMouseEvent, QUndoStack
from qtpy.QtWidgets import QDialog, QMenu

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
from pymmcore_widgets.config_presets import ConfigPresetsTable, GroupsPresetFinder
from pymmcore_widgets.config_presets._views._checked_properties_proxy import (
    CheckedProxy,
)
from pymmcore_widgets.config_presets._views._device_property_selector import (
    DevicePropertySelector,
)
from pymmcore_widgets.config_presets._views._device_type_filter_proxy import (
    DeviceTypeFilter,
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
from pymmcore_widgets.config_presets._views._undo_delegates import (
    GroupPresetRenameDelegate,
    PropertyValueDelegate,
    _resolve_source,
)

if TYPE_CHECKING:
    from pytestqt.qtbot import QtBot


# ── Shared fixtures ───────────────────────────────────────────────


@pytest.fixture
def core() -> CMMCorePlus:
    c = CMMCorePlus()
    c.loadSystemConfiguration()
    return c


@pytest.fixture
def undo_model(core: CMMCorePlus) -> tuple[QConfigGroupsModel, QUndoStack]:
    return QConfigGroupsModel.create_from_core(core), QUndoStack()


@pytest.fixture
def finder(qtbot: QtBot, core: CMMCorePlus) -> GroupsPresetFinder:
    model = QConfigGroupsModel.create_from_core(core)
    stack = QUndoStack()
    f = GroupsPresetFinder()
    qtbot.addWidget(f)
    f.setModel(model)
    f.setUndoStack(stack)
    return f


@pytest.fixture
def table(qtbot: QtBot, core: CMMCorePlus) -> ConfigPresetsTable:
    t = ConfigPresetsTable.create_from_core(core)
    qtbot.addWidget(t)
    stack = QUndoStack()
    t.setUndoStack(stack)
    t.setGroup("Channel")
    t.show()
    return t


# ── Tree / delegate tests ─────────────────────────────────────────


def test_config_groups_tree(qtbot: QtBot, core: CMMCorePlus) -> None:
    tree = ConfigGroupsTree.create_from_core(core)
    qtbot.addWidget(tree)
    tree.show()
    model = tree.model()
    assert isinstance(model, QConfigGroupsModel)

    delegate = tree.itemDelegateForColumn(2)
    assert isinstance(delegate, PropertySettingDelegate)

    setting_value = model.index(0, 2, model.index(0, 0, model.index(0, 0)))
    assert model.data(setting_value) == "1"

    tree.edit(setting_value)
    editor = tree.focusWidget()
    assert hasattr(editor, "setValue") and hasattr(editor, "value")
    with qtbot.waitSignal(delegate.commitData):
        editor.setValue("2")

    assert model.data(setting_value) == "2"
    group0 = model.get_groups()[0]
    preset0 = next(iter(group0.presets.values()))
    assert preset0.settings[0].value == "2"


# ── ConfigPresetsTable tests ──────────────────────────────────────


def test_config_presets_table(qtbot: QtBot, core: CMMCorePlus) -> None:
    table = ConfigPresetsTable.create_from_core(core)
    qtbot.addWidget(table)
    table.setGroup("Channel")
    table.show()
    view = table.view
    model = table.sourceModel()
    assert isinstance(model, QConfigGroupsModel)

    # Transpose round-trip
    assert not view.isTransposed()
    view.transpose()
    assert view.isTransposed()
    view.transpose()
    assert not view.isTransposed()

    data = model.index(1).data(Qt.ItemDataRole.UserRole)  # type: ignore[attr-defined]
    assert isinstance(data, ConfigGroup)
    assert len(data.presets) == 4

    # Remove and duplicate
    view.selectColumn(0)
    table.remove_action.trigger()
    assert len(data.presets) == 3
    view.selectColumn(0)
    table.duplicate_action.trigger()
    assert len(data.presets) == 4

    vm = view.model()
    assert vm
    header_names = [
        vm.headerData(i, Qt.Orientation.Horizontal) for i in range(vm.columnCount())
    ]
    assert header_names == ["DAPI", "DAPI copy", "FITC", "Rhodamine"]


def test_table_undo_remove_duplicate(table: ConfigPresetsTable) -> None:
    """Remove and duplicate with undo stack."""
    model = table.sourceModel()
    assert model is not None
    group_idx = model.index_for_group("Channel")
    n = model.rowCount(group_idx)
    stack = table._undo_stack
    assert stack is not None

    # Remove with undo
    table.view.selectColumn(0)
    table._on_remove_action()
    assert model.rowCount(group_idx) == n - 1
    stack.undo()
    assert model.rowCount(group_idx) == n

    # Duplicate with undo
    table.view.selectColumn(0)
    table._on_duplicate_action()
    assert model.rowCount(group_idx) == n + 1
    stack.undo()
    assert model.rowCount(group_idx) == n


def test_table_transposed_operations(table: ConfigPresetsTable) -> None:
    """Remove in transposed mode and selection preservation on transpose."""
    model = table.sourceModel()
    assert model is not None
    group_idx = model.index_for_group("Channel")
    n = model.rowCount(group_idx)

    # Transpose preserves selection
    table.view.selectColumn(1)
    table.view.transpose()
    sm = table.view.selectionModel()
    assert sm is not None
    rows = sm.selectedRows()
    assert len(rows) > 0 and rows[0].row() == 1

    # Remove in transposed mode
    table.view.selectRow(0)
    table._on_remove_action()
    assert model.rowCount(group_idx) == n - 1


@pytest.mark.skip(reason="Corresponding code commented out for now")
def test_table_key_delete(table: ConfigPresetsTable) -> None:
    """Delete key removes a setting; undo restores it."""
    view = table.view
    vm = view.model()
    assert vm is not None
    stack = table._undo_stack
    assert stack is not None

    idx = vm.index(0, 0)
    assert idx.data(Qt.ItemDataRole.UserRole) is not None
    view.setCurrentIndex(idx)
    sm = view.selectionModel()
    assert sm is not None
    sm.select(idx, sm.SelectionFlag.ClearAndSelect)

    event = QKeyEvent(
        QEvent.Type.KeyPress, Qt.Key.Key_Delete, Qt.KeyboardModifier.NoModifier
    )
    view.keyPressEvent(event)
    assert idx.data(Qt.ItemDataRole.UserRole) is None

    stack.undo()
    assert idx.data(Qt.ItemDataRole.UserRole) is not None


# ── Undo Command Tests ─────────────────────────────────────────────


def test_undo_add_remove_group(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    initial = model.rowCount()

    stack.push(AddGroupCommand(model, "UndoTestGroup"))
    assert model.rowCount() == initial + 1
    stack.undo()
    assert model.rowCount() == initial
    stack.redo()
    assert model.rowCount() == initial + 1

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

    stack.push(DuplicateGroupCommand(model, grp0_idx))
    assert model.rowCount() == initial + 1
    stack.undo()
    assert model.rowCount() == initial
    stack.redo()
    assert model.rowCount() == initial + 1
    stack.undo()

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
    n = model.rowCount(grp_idx)

    stack.push(AddPresetCommand(model, grp_idx, "UndoPreset"))
    assert model.rowCount(grp_idx) == n + 1
    stack.undo()
    assert model.rowCount(grp_idx) == n
    stack.redo()
    assert model.rowCount(grp_idx) == n + 1

    stack2 = QUndoStack()
    preset_idx = model.index_for_preset(grp_idx, "UndoPreset")
    stack2.push(RemovePresetCommand(model, preset_idx))
    assert model.rowCount(grp_idx) == n
    stack2.undo()
    assert model.rowCount(grp_idx) == n + 1


def test_undo_duplicate_rename_preset(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    old_name = preset_idx.data(Qt.ItemDataRole.DisplayRole)
    n = model.rowCount(grp_idx)

    stack.push(DuplicatePresetCommand(model, preset_idx))
    assert model.rowCount(grp_idx) == n + 1
    stack.undo()
    assert model.rowCount(grp_idx) == n

    stack.push(RenamePresetCommand(model, preset_idx, "RenamedPreset"))
    assert preset_idx.data(Qt.ItemDataRole.DisplayRole) == "RenamedPreset"
    stack.undo()
    assert preset_idx.data(Qt.ItemDataRole.DisplayRole) == old_name


def test_undo_change_property_value(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    value_idx = model.index(0, 2, preset_idx)
    old_value = value_idx.data(Qt.ItemDataRole.DisplayRole)

    stack.push(ChangePropertyValueCommand(model, value_idx, "NewVal"))
    assert value_idx.data(Qt.ItemDataRole.DisplayRole) == "NewVal"
    stack.undo()
    assert value_idx.data(Qt.ItemDataRole.DisplayRole) == old_value


def test_undo_update_preset_settings(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    old_count = len(preset_idx.data(Qt.ItemDataRole.UserRole).settings)

    new_settings = [DevicePropertySetting(device="D", property_name="P", value="V")]
    stack.push(UpdatePresetSettingsCommand(model, preset_idx, new_settings))
    assert len(preset_idx.data(Qt.ItemDataRole.UserRole).settings) == 1
    stack.undo()
    assert len(preset_idx.data(Qt.ItemDataRole.UserRole).settings) == old_count


def test_undo_update_preset_properties(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model
    grp_idx = model.index(0, 0)
    preset_idx = model.index(0, 0, grp_idx)
    old_count = len(preset_idx.data(Qt.ItemDataRole.UserRole).settings)

    new_props = [
        DevicePropertySetting(device="NewDev", property_name="NewProp", value="x")
    ]
    stack.push(UpdatePresetPropertiesCommand(model, preset_idx, new_props))
    assert len(preset_idx.data(Qt.ItemDataRole.UserRole).settings) == 1
    stack.undo()
    assert len(preset_idx.data(Qt.ItemDataRole.UserRole).settings) == old_count


def test_undo_redo_across_add_and_rename(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    """Redo of rename must work after the target was removed and re-added."""
    model, stack = undo_model
    initial = model.rowCount()

    stack.push(AddGroupCommand(model, "G0"))
    stack.push(AddGroupCommand(model, "G1"))
    g1_idx = model.index(initial + 1, 0)
    stack.push(RenameGroupCommand(model, g1_idx, "asdf"))

    stack.undo()  # undo rename
    stack.undo()  # undo add G1
    assert model.rowCount() == initial + 1

    stack.redo()  # redo add G1
    stack.redo()  # redo rename
    assert model.index(initial + 1, 0).data(Qt.ItemDataRole.DisplayRole) == "asdf"


def test_undo_set_channel_group(
    undo_model: tuple[QConfigGroupsModel, QUndoStack],
) -> None:
    model, stack = undo_model

    cam_idx = model.index_for_group("Camera")
    stack.push(SetChannelGroupCommand(model, cam_idx))
    assert "Camera" in {g.name for g in model.get_groups() if g.is_channel_group}

    stack.undo()
    assert "Channel" in {g.name for g in model.get_groups() if g.is_channel_group}

    stack.redo()
    stack.push(SetChannelGroupCommand(model, None))
    assert not any(g.is_channel_group for g in model.get_groups())
    stack.undo()
    assert "Camera" in {g.name for g in model.get_groups() if g.is_channel_group}


# ── Proxy Model Tests ──────────────────────────────────────────────


def test_checked_proxy(core: CMMCorePlus) -> None:
    model = QDevicePropertyModel.create_from_core(core)
    proxy = CheckedProxy(check_column=0, parent=None)
    proxy.setSourceModel(model)

    dev_idx = model.index(0, 0)
    prop_idx = model.index(0, 0, dev_idx)
    prop = prop_idx.data(Qt.ItemDataRole.UserRole)
    if isinstance(prop, DevicePropertySetting) and not (
        prop.is_read_only or prop.is_pre_init
    ):
        model.setData(prop_idx, Qt.CheckState.Checked, Qt.ItemDataRole.CheckStateRole)
        assert proxy.rowCount() > 0
        model.setData(prop_idx, Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)


def test_device_type_filter(core: CMMCorePlus) -> None:
    model = QDevicePropertyModel.create_from_core(core)
    filt = DeviceTypeFilter(allowed={DeviceType.Camera}, parent=None)
    filt.setSourceModel(model)

    for i in range(filt.rowCount()):
        dev = filt.index(i, 0).data(Qt.ItemDataRole.UserRole)
        if isinstance(dev, Device):
            assert dev.type == DeviceType.Camera

    filt.setReadOnlyVisible(True)
    filt.setReadOnlyVisible(False)
    filt.setPreInitVisible(True)
    filt.setPreInitVisible(False)

    filt.setFilterFixedString("Binning")
    count = 0
    for i in range(filt.rowCount()):
        dev_idx = filt.index(i, 0)
        for j in range(filt.rowCount(dev_idx)):
            prop_name = filt.index(j, 0, dev_idx).data(Qt.ItemDataRole.DisplayRole)
            if prop_name:
                assert "binning" in prop_name.lower()
                count += 1
    assert count > 0

    filt.setAllowedDeviceTypes({DeviceType.Any})


# ── DevicePropertySelector Tests ───────────────────────────────────


def test_device_property_selector(qtbot: QtBot, core: CMMCorePlus) -> None:
    """Check/uncheck properties, view modes, and prompt dialog."""
    devices = list(get_loaded_devices(core))
    selector = DevicePropertySelector()
    qtbot.addWidget(selector)
    selector.setAvailableDevices(devices)
    assert selector.tree.model() is not None

    # Find checkable settings
    settings = [
        p
        for d in devices
        for p in d.properties
        if not p.is_read_only and not p.is_pre_init
    ][:2]
    if settings:
        selector.setCheckedProperties(settings)
        assert len(selector.checkedProperties()) == len(settings)
        selector.clearCheckedProperties()
        assert len(selector.checkedProperties()) == 0

    # View mode toggles
    assert isinstance(selector.tree.model(), DevicePropertyFlatProxy)
    selector._toggle_view_mode(True)
    assert isinstance(selector.tree.model(), DeviceTypeFilter)
    selector._toggle_view_mode(False)
    assert isinstance(selector.tree.model(), DevicePropertyFlatProxy)

    # Checked-only mode
    selector._toggle_checked_only(True)
    assert not selector._tb2.act_toggle_view.isEnabled()
    selector._toggle_checked_only(False)
    assert selector._tb2.act_toggle_view.isEnabled()


def test_device_property_selector_prompt(
    qtbot: QtBot, core: CMMCorePlus, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    devices = list(get_loaded_devices(core))
    assert DevicePropertySelector.promptForProperties(devices=devices) == ()


# ── GroupsPresetFinder Tests ───────────────────────────────────────


def test_groups_preset_finder_basics(finder: GroupsPresetFinder, qtbot: QtBot) -> None:
    """Group/preset selection, view toggle, clear, channel group."""
    model = finder.model()
    assert model is not None

    with qtbot.waitSignal(finder.currentGroupChanged):
        finder.setCurrentGroup("Channel")
    assert finder.currentGroup().isValid()

    with qtbot.waitSignal(finder.currentPresetChanged):
        finder.setCurrentPreset("Channel", "DAPI")
    assert finder.currentPreset().isValid()

    # View toggle
    finder.showTreeView()
    assert finder.isTreeViewActive()
    finder.showColumnView()
    assert not finder.isTreeViewActive()

    # Clear
    finder.clearSelection()
    assert not finder.currentGroup().isValid()

    # Channel group
    finder.setCurrentGroup("Camera")
    finder.setCurrentGroupAsChannelGroup()
    groups = model.get_groups()
    assert next(g for g in groups if g.name == "Camera").is_channel_group


def test_groups_preset_finder_tree_sync(
    finder: GroupsPresetFinder, qtbot: QtBot
) -> None:
    """Tree selection syncs lists; cross-group navigation works."""
    model = finder.model()
    assert model is not None

    # Select preset in tree → syncs both lists
    group_idx = model.index_for_group("Channel")
    preset_idx = model.index(0, 0, group_idx)
    finder.config_groups_tree.setCurrentIndex(preset_idx)
    assert finder.group_list.currentIndex().row() == group_idx.row()
    assert finder.preset_list.currentIndex().row() == preset_idx.row()

    # Navigate to different group in tree
    finder.showTreeView()
    camera_idx = model.index_for_group("Camera")
    with qtbot.waitSignal(finder.currentGroupChanged):
        finder.config_groups_tree.setCurrentIndex(camera_idx)
    assert finder.group_list.currentIndex().row() == camera_idx.row()


def test_groups_preset_finder_undo_operations(
    finder: GroupsPresetFinder, qtbot: QtBot
) -> None:
    """Remove/duplicate group and preset with undo."""
    model = finder.model()
    assert model is not None
    stack = finder._undo_stack
    assert stack is not None

    n_groups = model.rowCount()
    group_idx = model.index_for_group("Channel")
    n_presets = model.rowCount(group_idx)

    # Duplicate group
    finder.setCurrentGroup("Camera")
    finder.group_list.setFocus()
    finder.duplicateSelected()
    assert model.rowCount() == n_groups + 1
    stack.undo()
    assert model.rowCount() == n_groups

    # Duplicate preset
    finder.setCurrentPreset("Channel", "DAPI")
    finder.preset_list.setFocus()
    finder.duplicateSelected()
    assert model.rowCount(group_idx) == n_presets + 1
    stack.undo()

    # Remove preset
    finder.setCurrentPreset("Channel", "DAPI")
    finder.preset_list.setFocus()
    finder.removeSelected()
    assert model.rowCount(group_idx) == n_presets - 1
    stack.undo()
    assert model.rowCount(group_idx) == n_presets


def test_groups_preset_finder_selected_index_fallback(
    finder: GroupsPresetFinder,
) -> None:
    """_selected_index works without explicit focus and in tree mode."""
    finder.setCurrentGroup("Camera")
    finder.setFocus()  # no list has focus
    assert finder._selected_index().isValid()

    finder.showTreeView()
    finder.config_groups_tree.setFocus()
    assert finder._selected_index().isValid()


# ── Undo Delegates Tests ──────────────────────────────────────────


def test_rename_delegates(finder: GroupsPresetFinder, qtbot: QtBot) -> None:
    """Renaming group/preset via delegates creates undo commands."""
    model = finder.model()
    assert model is not None
    stack = finder._undo_stack
    assert stack is not None

    # Rename group
    group_idx = model.index_for_group("Camera")
    finder.group_list.edit(group_idx)
    editor = finder.group_list.focusWidget()
    if editor and hasattr(editor, "setText"):
        editor.setText("RenamedCamera")
        delegate = finder.group_list.itemDelegate()
        assert isinstance(delegate, GroupPresetRenameDelegate)
        delegate.commitData.emit(editor)
        finder.group_list.commitData(editor)
        assert group_idx.data(Qt.ItemDataRole.DisplayRole) == "RenamedCamera"
        stack.undo()
        assert group_idx.data(Qt.ItemDataRole.DisplayRole) == "Camera"

    # Rename preset
    finder.setCurrentPreset("Channel", "DAPI")
    preset_idx = finder.preset_list.currentIndex()
    finder.preset_list.edit(preset_idx)
    editor = finder.preset_list.focusWidget()
    if editor and hasattr(editor, "setText"):
        editor.setText("RenamedDAPI")
        delegate = finder.preset_list.itemDelegate()
        assert isinstance(delegate, GroupPresetRenameDelegate)
        delegate.commitData.emit(editor)
        finder.preset_list.commitData(editor)
        assert preset_idx.data(Qt.ItemDataRole.DisplayRole) == "RenamedDAPI"
        stack.undo()
        assert preset_idx.data(Qt.ItemDataRole.DisplayRole) == "DAPI"


def test_property_value_delegate_undo(table: ConfigPresetsTable) -> None:
    """Changing a property value via the table pushes an undo command."""
    view = table.view
    assert isinstance(view.itemDelegate(), PropertyValueDelegate)
    stack = table._undo_stack
    assert stack is not None

    src_model = view.sourceModel()
    pivot = view._get_pivot_model()
    setting_idx = src_model.index(0, 2, pivot.get_source_index_for_column(0))
    old_value = setting_idx.data(Qt.ItemDataRole.DisplayRole)

    stack.push(ChangePropertyValueCommand(src_model, setting_idx, "NEW"))
    assert setting_idx.data(Qt.ItemDataRole.DisplayRole) == "NEW"
    stack.undo()
    assert setting_idx.data(Qt.ItemDataRole.DisplayRole) == old_value


def test_property_value_delegate_undo_via_pivot(table: ConfigPresetsTable) -> None:
    """Delegate resolves pivot model indices and pushes undo commands."""
    view = table.view
    delegate = view.itemDelegate()
    assert isinstance(delegate, PropertyValueDelegate)
    stack = table._undo_stack
    assert stack is not None

    pivot = view._get_pivot_model()
    src_model = view.sourceModel()

    # Find a cell with data in the pivot model
    pivot_idx = pivot.index(0, 0)
    assert pivot_idx.isValid()
    setting = pivot_idx.data(Qt.ItemDataRole.UserRole)
    assert isinstance(setting, DevicePropertySetting)
    old_value = setting.value

    # Simulate what the delegate does: resolve through pivot to source
    resolved_model, resolved_idx = pivot.mapToSourceSettingIndex(pivot_idx)
    assert resolved_model is src_model
    assert resolved_idx.isValid()

    # Push command via the resolved source model/index
    stack.push(ChangePropertyValueCommand(resolved_model, resolved_idx, "TEST_VAL"))
    assert setting.value == "TEST_VAL"
    assert pivot_idx.data(Qt.ItemDataRole.EditRole) == "TEST_VAL"

    stack.undo()
    assert setting.value == old_value
    assert pivot_idx.data(Qt.ItemDataRole.EditRole) == old_value


def test_property_value_delegate_undo_via_transpose(table: ConfigPresetsTable) -> None:
    """Delegate resolves transposed pivot indices and pushes undo commands."""
    view = table.view
    stack = table._undo_stack
    assert stack is not None

    pivot = view._get_pivot_model()
    src_model = view.sourceModel()

    # Get a reference value before transposing
    pivot_idx = pivot.index(0, 0)
    setting = pivot_idx.data(Qt.ItemDataRole.UserRole)
    assert isinstance(setting, DevicePropertySetting)
    old_value = setting.value

    # Transpose the view
    view.transpose()
    assert view.isTransposed()

    # In transposed view, rows and columns are swapped
    transposed_model = view.model()
    transposed_idx = transposed_model.index(0, 0)

    # _resolve_source should unwrap transpose -> pivot -> source
    resolved_model, resolved_idx = _resolve_source(transposed_model, transposed_idx)
    assert resolved_model is src_model
    assert resolved_idx.isValid()

    stack.push(ChangePropertyValueCommand(resolved_model, resolved_idx, "TRANSPOSED"))
    assert setting.value == "TRANSPOSED"

    stack.undo()
    assert setting.value == old_value


# ── ConfigPresetsTable additional coverage ─────────────────────────


def test_table_multi_select_remove_with_undo(table: ConfigPresetsTable) -> None:
    """Multi-select remove pushes a macro on the undo stack."""
    model = table.sourceModel()
    assert model is not None
    group_idx = model.index_for_group("Channel")
    n = model.rowCount(group_idx)
    stack = table._undo_stack
    assert stack is not None

    # Select two columns (presets)
    table.view.selectColumn(0)
    sm = table.view.selectionModel()
    assert sm is not None
    vm = table.view.model()
    assert vm is not None
    # Add column 1 to selection
    for row in range(vm.rowCount()):
        sm.select(vm.index(row, 1), sm.SelectionFlag.Select)

    table._on_remove_action()
    assert model.rowCount(group_idx) == n - 2
    stack.undo()
    assert model.rowCount(group_idx) == n


def test_table_multi_select_duplicate_with_undo(table: ConfigPresetsTable) -> None:
    """Multi-select duplicate pushes a macro on the undo stack."""
    model = table.sourceModel()
    assert model is not None
    group_idx = model.index_for_group("Channel")
    n = model.rowCount(group_idx)
    stack = table._undo_stack
    assert stack is not None

    # Select two columns
    table.view.selectColumn(0)
    sm = table.view.selectionModel()
    assert sm is not None
    vm = table.view.model()
    assert vm is not None
    for row in range(vm.rowCount()):
        sm.select(vm.index(row, 1), sm.SelectionFlag.Select)

    table._on_duplicate_action()
    assert model.rowCount(group_idx) == n + 2
    stack.undo()
    assert model.rowCount(group_idx) == n


def test_table_no_selection_returns_empty(table: ConfigPresetsTable) -> None:
    """No selected presets returns empty list and actions are no-ops."""
    sm = table.view.selectionModel()
    assert sm is not None
    sm.clearSelection()

    assert table._get_selected_preset_indices() == []
    # These should be no-ops when nothing is selected
    table._on_remove_action()
    table._on_duplicate_action()


def test_table_add_and_remove_cell_setting(table: ConfigPresetsTable) -> None:
    """Add/remove a single cell setting via _add_cell_setting/_remove_cell_setting."""
    view = table.view
    stack = table._undo_stack
    assert stack is not None
    pivot = view._get_pivot_model()

    # Find a cell that has data
    idx_with_data = pivot.index(0, 0)
    assert idx_with_data.data(Qt.ItemDataRole.UserRole) is not None

    # Remove it
    view._remove_cell_setting(idx_with_data)
    assert idx_with_data.data(Qt.ItemDataRole.UserRole) is None
    stack.undo()
    assert idx_with_data.data(Qt.ItemDataRole.UserRole) is not None

    # Find a cell without data (if any exist), or create one by removing first
    view._remove_cell_setting(idx_with_data)
    assert idx_with_data.data(Qt.ItemDataRole.UserRole) is None

    # Now add it back via _add_cell_setting
    view._add_cell_setting(idx_with_data)
    assert idx_with_data.data(Qt.ItemDataRole.UserRole) is not None
    stack.undo()
    assert idx_with_data.data(Qt.ItemDataRole.UserRole) is None


def test_table_pivot_coords_transposed(table: ConfigPresetsTable) -> None:
    """_pivot_coords swaps row/col when transposed."""
    view = table.view
    pivot = view._get_pivot_model()
    idx = pivot.index(1, 2)

    # Normal: (row, col)
    assert view._pivot_coords(idx) == (1, 2)

    view.transpose()
    assert view.isTransposed()
    # Transposed: (col, row)
    assert view._pivot_coords(idx) == (2, 1)


def test_table_transpose_restores_column_selection(table: ConfigPresetsTable) -> None:
    """Transpose from transposed back to normal restores column selection."""
    view = table.view

    # Select column 1, transpose (-> row 1), then transpose back (-> column 1)
    view.selectColumn(1)
    view.transpose()  # now transposed, row 1 selected
    view.transpose()  # back to normal

    sm = view.selectionModel()
    assert sm is not None
    cols = sm.selectedColumns()
    assert len(cols) > 0
    assert cols[0].column() == 1


def test_table_mouse_click_opens_editor(
    table: ConfigPresetsTable, qtbot: QtBot
) -> None:
    """Single left-click on a data cell opens the editor."""
    view = table.view
    view.show()
    qtbot.waitExposed(view)

    pivot = view._get_pivot_model()
    idx = pivot.index(0, 0)
    assert idx.isValid()
    rect = view.visualRect(idx)
    pos = QPointF(rect.center())

    event = QMouseEvent(
        QEvent.Type.MouseButtonPress,
        pos,
        QPointF(view.mapToGlobal(pos.toPoint())),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mousePressEvent(event)


def test_table_double_click_empty_cell(table: ConfigPresetsTable, qtbot: QtBot) -> None:
    """Double-click on an empty cell calls _add_cell_setting."""
    view = table.view
    stack = table._undo_stack
    assert stack is not None
    pivot = view._get_pivot_model()
    view.show()
    qtbot.waitExposed(view)

    # Remove a cell to make it empty
    idx = pivot.index(0, 0)
    view._remove_cell_setting(idx)
    assert idx.data(Qt.ItemDataRole.UserRole) is None

    rect = view.visualRect(idx)
    pos = QPointF(rect.center())
    event = QMouseEvent(
        QEvent.Type.MouseButtonDblClick,
        pos,
        QPointF(view.mapToGlobal(pos.toPoint())),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    view.mouseDoubleClickEvent(event)
    # The double-click on empty cell should add the setting back
    assert idx.data(Qt.ItemDataRole.UserRole) is not None


def test_table_context_menu_remove(
    table: ConfigPresetsTable,
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-click context menu on a data cell shows remove action."""
    import pymmcore_widgets.config_presets._views._config_presets_table as _table_mod

    view = table.view
    stack = table._undo_stack
    assert stack is not None
    pivot = view._get_pivot_model()
    view.show()
    qtbot.waitExposed(view)

    idx = pivot.index(0, 0)
    assert idx.data(Qt.ItemDataRole.UserRole) is not None
    rect = view.visualRect(idx)
    pos = rect.center()

    # Subclass QMenu so .exec() is a Python method (patchable on PySide6)
    class _AutoSelectMenu(QMenu):
        def exec(self, *_: object) -> object:  # type: ignore[override]
            return self.actions()[0]

    monkeypatch.setattr(_table_mod, "QMenu", _AutoSelectMenu)

    gpos = view.mapToGlobal(pos)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, gpos)
    view.contextMenuEvent(event)
    assert idx.data(Qt.ItemDataRole.UserRole) is None

    stack.undo()
    assert idx.data(Qt.ItemDataRole.UserRole) is not None


def test_table_context_menu_add(
    table: ConfigPresetsTable,
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Right-click context menu on an empty cell shows add action."""
    import pymmcore_widgets.config_presets._views._config_presets_table as _table_mod

    view = table.view
    stack = table._undo_stack
    assert stack is not None
    pivot = view._get_pivot_model()
    view.show()
    qtbot.waitExposed(view)

    # Remove cell to make it empty
    idx = pivot.index(0, 0)
    view._remove_cell_setting(idx)
    assert idx.data(Qt.ItemDataRole.UserRole) is None

    rect = view.visualRect(idx)
    pos = rect.center()

    class _AutoSelectMenu(QMenu):
        def exec(self, *_: object) -> object:  # type: ignore[override]
            return self.actions()[0]

    monkeypatch.setattr(_table_mod, "QMenu", _AutoSelectMenu)

    gpos = view.mapToGlobal(pos)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, pos, gpos)
    view.contextMenuEvent(event)
    assert idx.data(Qt.ItemDataRole.UserRole) is not None
