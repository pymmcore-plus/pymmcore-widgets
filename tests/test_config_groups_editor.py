from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import Mock

import pytest
from qtpy.QtCore import QItemSelectionModel, Qt
from qtpy.QtWidgets import QDialog, QMessageBox

from pymmcore_widgets import ConfigGroupsEditor
from pymmcore_widgets._help._config_groups_help import ConfigGroupsHelpDialog
from pymmcore_widgets._models import get_config_groups, set_config_groups

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


@pytest.fixture
def editor(qtbot: QtBot, global_mmcore: CMMCorePlus) -> Iterator[ConfigGroupsEditor]:
    editor = ConfigGroupsEditor.create_from_core(global_mmcore, load_configs=True)
    qtbot.addWidget(editor)
    yield editor


def test_editor_create_and_data(editor: ConfigGroupsEditor, qtbot: QtBot) -> None:
    """Data round-trip, empty data, and configChanged signal."""
    groups = editor.data()
    assert len(groups) > 0
    assert editor.isClean()

    # data round-trip
    original_names = {g.name for g in groups}
    editor.setData(groups)
    assert {g.name for g in editor.data()} == original_names

    # empty data disables add-preset
    editor.setData([])
    assert len(editor.data()) == 0
    assert not editor._tb.add_preset_action.isEnabled()

    # configChanged fires on structural changes
    editor.setData(groups)
    with qtbot.waitSignal(editor.configChanged):
        editor._add_group()


def test_editor_toolbar_states(editor: ConfigGroupsEditor) -> None:
    """Toolbar actions reflect group type: channel, system, empty."""
    tb = editor._tb

    # Regular group
    editor.setCurrentGroup("Camera")
    assert tb.add_preset_action.isEnabled()
    assert tb.set_channel_action.isEnabled()
    assert tb.edit_properties_action.isEnabled()

    # Channel group disables set_channel_action
    editor.setCurrentGroup("Channel")
    assert not tb.set_channel_action.isEnabled()

    # System group also disables set_channel_action
    editor.setCurrentGroup("System")
    assert not tb.set_channel_action.isEnabled()

    # Empty group (no presets) disables edit_properties
    editor._add_group()
    new_name = editor._model.index(len(editor.data()) - 1).data(
        Qt.ItemDataRole.DisplayRole
    )
    editor.setCurrentGroup(new_name)
    assert not tb.edit_properties_action.isEnabled()


def test_editor_add_group_with_undo_navigation(editor: ConfigGroupsEditor) -> None:
    """Add group, undo, redo — redo navigates back to the re-added group."""
    initial_count = len(editor.data())
    editor._add_group()
    assert len(editor.data()) == initial_count + 1
    new_name = editor._model.index(initial_count).data(Qt.ItemDataRole.DisplayRole)

    editor.undoStack().undo()
    assert len(editor.data()) == initial_count

    editor.undoStack().redo()
    current = editor._group_preset_sel.group_list.currentIndex()
    assert current.data(Qt.ItemDataRole.DisplayRole) == new_name


def test_editor_add_preset_undo(editor: ConfigGroupsEditor) -> None:
    """Adding a preset with undo/redo."""
    editor.setCurrentGroup("Camera")
    group = editor._model.index_for_group("Camera")
    n = editor._model.rowCount(group)

    editor._add_preset_to_current_group()
    assert editor._model.rowCount(group) == n + 1
    editor.undoStack().undo()
    assert editor._model.rowCount(group) == n


def test_editor_duplicate_remove_group_and_preset(
    editor: ConfigGroupsEditor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Duplicate/remove for groups and presets, including decline."""
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    n_groups = len(editor.data())

    # Duplicate group
    editor.setCurrentGroup("Camera")
    editor._group_preset_sel.group_list.setFocus()
    editor._duplicate_selected()
    assert len(editor.data()) == n_groups + 1
    editor.undoStack().undo()

    # Remove group
    editor._group_preset_sel.group_list.setFocus()
    editor._remove_selected()
    assert len(editor.data()) == n_groups - 1
    editor.undoStack().undo()

    # Duplicate preset
    editor.setCurrentPreset("Channel", "DAPI")
    group_idx = editor._model.index_for_group("Channel")
    n_presets = editor._model.rowCount(group_idx)
    editor._group_preset_sel.preset_list.setFocus()
    editor._duplicate_selected()
    assert editor._model.rowCount(group_idx) == n_presets + 1
    channel = next(g for g in editor.data() if g.name == "Channel")
    assert any("DAPI" in p and "copy" in p for p in channel.presets)
    editor.undoStack().undo()

    # Remove preset
    editor.setCurrentPreset("Camera", "HighRes")
    group_idx = editor._model.index_for_group("Camera")
    n_presets = editor._model.rowCount(group_idx)
    editor._group_preset_sel.preset_list.setFocus()
    editor._remove_selected()
    assert editor._model.rowCount(group_idx) == n_presets - 1
    editor.undoStack().undo()
    assert editor._model.rowCount(group_idx) == n_presets

    # Decline removal → no change
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No
    )
    editor._group_preset_sel.group_list.setFocus()
    editor._remove_selected()
    assert len(editor.data()) == n_groups


def test_editor_multi_preset_operations(
    editor: ConfigGroupsEditor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Multi-select duplicate and remove for presets."""
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    editor.setCurrentGroup("Channel")
    group_idx = editor._model.index_for_group("Channel")
    n = editor._model.rowCount(group_idx)

    sm = editor._group_preset_sel.preset_list.selectionModel()
    assert sm is not None
    idx0 = editor._model.index(0, 0, group_idx)
    idx1 = editor._model.index(1, 0, group_idx)
    sm.select(idx0, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.select(idx1, QItemSelectionModel.SelectionFlag.Select)

    editor._duplicate_selected()
    assert editor._model.rowCount(group_idx) == n + 2
    editor.undoStack().undo()

    sm.select(idx0, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.select(idx1, QItemSelectionModel.SelectionFlag.Select)
    editor._remove_selected()
    assert editor._model.rowCount(group_idx) == n - 2
    editor.undoStack().undo()


def test_editor_set_channel_group(editor: ConfigGroupsEditor) -> None:
    """Setting a group as channel group via toolbar."""
    editor.setCurrentGroup("Camera")
    editor._tb.set_channel_action.trigger()
    groups = editor.data()
    assert next(g for g in groups if g.name == "Camera").is_channel_group
    assert not next(g for g in groups if g.name == "Channel").is_channel_group


def test_editor_set_current_preset(editor: ConfigGroupsEditor) -> None:
    """Setting a current preset by name."""
    idx = editor.setCurrentPreset("Channel", "DAPI")
    assert idx.isValid() and idx.data(Qt.ItemDataRole.DisplayRole) == "DAPI"
    assert not editor.setCurrentPreset("Channel", "NonExistent").isValid()


def test_editor_view_toggle_and_table_sync(editor: ConfigGroupsEditor) -> None:
    """View toggle, tree sync, and table↔preset-list selection sync."""
    finder = editor._group_preset_sel
    editor.setCurrentGroup("Channel")

    # View toggle
    finder.toggleView()
    assert finder.isTreeViewActive()
    finder.toggleView()
    assert not finder.isTreeViewActive()

    # Tree selection syncs
    finder.showTreeView()
    preset_idx = editor._model.index(0, 0, editor._model.index_for_group("Channel"))
    finder.config_groups_tree.setCurrentIndex(preset_idx)
    assert finder.currentGroup().isValid()
    finder.showColumnView()

    # Table column → preset list
    editor._preset_table.view.selectColumn(1)
    sm = finder.preset_list.selectionModel()
    assert sm is not None and len(sm.selectedIndexes()) >= 1


def test_editor_dialogs(
    editor: ConfigGroupsEditor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test help, undo view, and edit-properties dialogs."""
    editor.show()
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    editor._show_help()
    editor._show_undo_view()
    editor.setCurrentGroup("Channel")
    editor._edit_group_properties()


def test_editor_status_indicator_and_apply_requested(
    editor: ConfigGroupsEditor, qtbot: QtBot
) -> None:
    """Status bar reflects undo stack clean state, Apply emits applyRequested."""
    # After setData, editor is clean
    assert editor.isClean()
    assert editor._status_label.text() == "No changes"
    assert not editor._apply_btn.isEnabled()

    # Making a change marks dirty
    editor._add_group()
    assert not editor.isClean()
    assert editor._status_label.text() == "Unsaved changes"
    assert editor._apply_btn.isEnabled()

    # Clicking Apply emits applyRequested with (changed, deleted)
    with qtbot.waitSignal(editor.applyRequested) as blocker:
        editor._apply_btn.click()
    changed, deleted, channel = blocker.args
    assert len(changed) > 0  # at least the new group
    assert isinstance(deleted, list)
    assert channel is None  # adding a group doesn't change channel designation

    # Undo reverts to clean
    editor.undoStack().undo()
    assert editor.isClean()
    assert editor._status_label.text() == "No changes"
    assert not editor._apply_btn.isEnabled()


def test_editor_set_data_clears_undo_stack(
    editor: ConfigGroupsEditor, qtbot: QtBot
) -> None:
    """setData clears the undo stack and marks the editor clean."""
    editor._add_group()
    assert not editor.isClean()
    assert editor.undoStack().count() > 0

    editor.setData(editor.data())
    assert editor.isClean()
    assert editor.undoStack().count() == 0


def test_editor_set_clean_updates_status(
    editor: ConfigGroupsEditor, qtbot: QtBot
) -> None:
    """Calling setClean() from outside updates the status bar."""
    editor._add_group()
    assert editor._apply_btn.isEnabled()

    # Simulate a consumer marking it clean after applying
    editor.setClean()
    assert editor._status_label.text() == "No changes"
    assert not editor._apply_btn.isEnabled()


def test_set_config_groups_round_trip(global_mmcore: CMMCorePlus) -> None:
    """set_config_groups writes groups to core and preserves channel group."""
    original_groups = list(get_config_groups(global_mmcore))
    original_names = {g.name for g in original_groups}
    original_channel = global_mmcore.getChannelGroup()

    # Rename a group in the data
    modified = list(original_groups)
    modified[0] = modified[0].model_copy(update={"name": f"{modified[0].name}_test"})

    set_config_groups(global_mmcore, modified)

    core_names = set(global_mmcore.getAvailableConfigGroups())
    assert f"{original_groups[0].name}_test" in core_names
    assert original_groups[0].name not in core_names
    assert global_mmcore.getChannelGroup() == original_channel

    # Restore
    set_config_groups(global_mmcore, original_groups)
    assert set(global_mmcore.getAvailableConfigGroups()) == original_names


def test_set_config_groups_emits_signals(global_mmcore: CMMCorePlus) -> None:
    """set_config_groups emits configDefined once per group (not per setting)."""
    groups = list(get_config_groups(global_mmcore))
    defined: list[str] = []
    global_mmcore.events.configDefined.connect(lambda g, *_: defined.append(g))

    set_config_groups(global_mmcore, groups)

    groups_with_settings = [
        g for g in groups if any(s for p in g.presets.values() for s in p.settings)
    ]
    assert len(defined) == len(groups_with_settings)


def test_editor_dirty_groups(editor: ConfigGroupsEditor) -> None:
    """dirtyGroups returns only changed/new groups and deleted group names."""
    # Initially clean
    changed, deleted, channel = editor.dirtyGroups()
    assert changed == []
    assert deleted == []
    assert channel is None

    # Add a group → it appears in changed
    editor._add_group()
    changed, deleted, channel = editor.dirtyGroups()
    assert len(changed) == 1
    assert deleted == []
    assert channel is None

    # setClean resets the baseline
    editor.setClean()
    changed, deleted, channel = editor.dirtyGroups()
    assert changed == []
    assert deleted == []
    assert channel is None


def test_editor_dirty_groups_channel_only(editor: ConfigGroupsEditor) -> None:
    """Changing only the channel group doesn't put groups in changed list."""
    # Set a different group as channel group
    editor.setCurrentGroup("Camera")
    editor._tb.set_channel_action.trigger()

    changed, deleted, channel = editor.dirtyGroups()
    assert changed == []
    assert deleted == []
    assert channel == "Camera"


def test_set_config_groups_incremental(global_mmcore: CMMCorePlus) -> None:
    """set_config_groups with deleted_groups only touches specified groups."""
    original_groups = list(get_config_groups(global_mmcore))
    original_names = {g.name for g in original_groups}

    # Add a new group, delete an existing one
    new_group = original_groups[0].model_copy(
        update={"name": "TestNewGroup", "is_channel_group": False}
    )
    deleted_name = original_groups[1].name

    set_config_groups(global_mmcore, [new_group], deleted_groups=[deleted_name])

    core_names = set(global_mmcore.getAvailableConfigGroups())
    assert "TestNewGroup" in core_names
    assert deleted_name not in core_names
    # Untouched groups should still exist
    untouched = original_names - {original_groups[0].name, deleted_name}
    assert untouched <= core_names

    # Restore
    set_config_groups(global_mmcore, original_groups)
    assert set(global_mmcore.getAvailableConfigGroups()) == original_names


def test_config_group_channel_group_changed_signals(
    editor: ConfigGroupsEditor, global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Changing only the channel group emits channelGroupChanged, not configDefined."""
    mmc = global_mmcore

    @editor.applyRequested.connect
    def _apply(groups: list, deleted: list[str], channel: str | None) -> None:
        set_config_groups(mmc, groups, deleted_groups=deleted, channel_group=channel)
        editor.setClean()

    # "Camera" exists but is not the channel group — set it as channel
    DEV = "Camera"
    assert mmc.getChannelGroup() != DEV
    editor._group_preset_sel.setCurrentGroup(DEV)
    editor._tb.set_channel_action.trigger()

    defined = Mock()
    channel_changed = Mock()
    mmc.events.configDefined.connect(defined)
    mmc.events.channelGroupChanged.connect(channel_changed)

    with qtbot.waitSignal(mmc.events.channelGroupChanged):
        editor._apply_btn.click()

    assert mmc.getChannelGroup() == DEV
    channel_changed.assert_called_with(DEV)
    defined.assert_not_called()


def test_config_group_preset_removed_signals(
    editor: ConfigGroupsEditor,
    global_mmcore: CMMCorePlus,
    qtbot: QtBot,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing a preset emits configDefined for that group only."""
    mmc = global_mmcore

    @editor.applyRequested.connect
    def _apply(groups: list, deleted: list[str], channel: str | None) -> None:
        set_config_groups(mmc, groups, deleted_groups=deleted, channel_group=channel)
        editor.setClean()

    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )

    # Remove HighRes preset from Camera
    editor.setCurrentPreset("Camera", "HighRes")
    editor._group_preset_sel.preset_list.setFocus()
    editor._remove_selected()

    defined = Mock()
    group_deleted = Mock()
    channel_changed = Mock()
    mmc.events.configDefined.connect(defined)
    mmc.events.configGroupDeleted.connect(group_deleted)
    mmc.events.channelGroupChanged.connect(channel_changed)

    with qtbot.waitSignal(mmc.events.configDefined):
        editor._apply_btn.click()

    defined.assert_called_once()
    assert defined.call_args[0][0] == "Camera"
    group_deleted.assert_not_called()
    channel_changed.assert_not_called()


def test_config_group_added_signals(
    editor: ConfigGroupsEditor, global_mmcore: CMMCorePlus, qtbot: QtBot
) -> None:
    """Adding a new group with presets emits configDefined for that group only."""
    mmc = global_mmcore

    @editor.applyRequested.connect
    def _apply(groups: list, deleted: list[str], channel: str | None) -> None:
        set_config_groups(mmc, groups, deleted_groups=deleted, channel_group=channel)
        editor.setClean()

    # Duplicate "Camera" so the new group has presets with settings
    editor.setCurrentGroup("Camera")
    editor._group_preset_sel.group_list.setFocus()
    editor._duplicate_selected()
    new_group_name = "Camera copy"

    defined = Mock()
    group_deleted = Mock()
    channel_changed = Mock()
    mmc.events.configDefined.connect(defined)
    mmc.events.configGroupDeleted.connect(group_deleted)
    mmc.events.channelGroupChanged.connect(channel_changed)

    with qtbot.waitSignal(mmc.events.configDefined):
        editor._apply_btn.click()

    defined.assert_called_once()
    assert defined.call_args[0][0] == new_group_name
    group_deleted.assert_not_called()
    channel_changed.assert_not_called()
    assert new_group_name in mmc.getAvailableConfigGroups()


def test_config_groups_help_dialog(qtbot: QtBot) -> None:
    """Smoke test ConfigGroupsHelpDialog."""
    dialog = ConfigGroupsHelpDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.close()
