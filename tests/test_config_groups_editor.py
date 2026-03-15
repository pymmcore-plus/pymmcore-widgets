from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from qtpy.QtCore import QItemSelectionModel, Qt
from qtpy.QtWidgets import QDialog, QMessageBox

from pymmcore_widgets import ConfigGroupsEditor
from pymmcore_widgets._help._config_groups_help import ConfigGroupsHelpDialog

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
    assert editor.undoStack().isClean()

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


def test_config_groups_help_dialog(qtbot: QtBot) -> None:
    """Smoke test ConfigGroupsHelpDialog."""
    dialog = ConfigGroupsHelpDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.close()
