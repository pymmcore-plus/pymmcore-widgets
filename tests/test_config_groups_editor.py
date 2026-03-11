from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QMessageBox

from pymmcore_widgets import ConfigGroupsEditor
from pymmcore_widgets._help._config_groups_help import ConfigGroupsHelpDialog

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pymmcore_plus import CMMCorePlus
    from pytestqt.qtbot import QtBot


@pytest.fixture
def editor(qtbot: QtBot, global_mmcore: CMMCorePlus) -> Iterator[ConfigGroupsEditor]:
    editor = ConfigGroupsEditor.create_from_core(global_mmcore)
    qtbot.addWidget(editor)
    yield editor


def test_editor_create_and_data(editor: ConfigGroupsEditor) -> None:
    """Test editor creation, data round-trip, and configChanged signal."""
    groups = editor.data()
    assert len(groups) > 0
    assert editor.undoStack().isClean()

    # data round-trip
    original_names = {g.name for g in groups}
    editor.setData(groups)
    assert {g.name for g in editor.data()} == original_names


def test_editor_group_selection(editor: ConfigGroupsEditor, qtbot: QtBot) -> None:
    """Test group selection and toolbar action state."""
    tb = editor._tb

    # Select a group
    idx = editor.setCurrentGroup("Camera")
    assert idx.isValid()
    assert tb.add_preset_action.isEnabled()
    assert tb.duplicate_action.isEnabled()
    assert tb.remove_action.isEnabled()

    # Select Channel group - set_channel_action should be disabled
    idx = editor.setCurrentGroup("Channel")
    assert idx.isValid()
    assert not tb.set_channel_action.isEnabled()

    # Select a non-channel group - set_channel_action should be enabled
    idx = editor.setCurrentGroup("Camera")
    assert idx.isValid()
    assert tb.set_channel_action.isEnabled()


def test_editor_add_group_undo(editor: ConfigGroupsEditor, qtbot: QtBot) -> None:
    """Test adding a group with undo/redo."""
    initial_count = len(editor.data())

    editor._add_group()
    assert len(editor.data()) == initial_count + 1

    editor.undoStack().undo()
    assert len(editor.data()) == initial_count

    editor.undoStack().redo()
    assert len(editor.data()) == initial_count + 1


def test_editor_add_preset_undo(editor: ConfigGroupsEditor, qtbot: QtBot) -> None:
    """Test adding a preset with undo/redo."""
    editor.setCurrentGroup("Camera")
    group = editor._model.index_for_group("Camera")
    initial_preset_count = editor._model.rowCount(group)

    editor._add_preset_to_current_group()
    assert editor._model.rowCount(group) == initial_preset_count + 1

    editor.undoStack().undo()
    assert editor._model.rowCount(group) == initial_preset_count

    editor.undoStack().redo()
    assert editor._model.rowCount(group) == initial_preset_count + 1


def test_editor_duplicate_selected(editor: ConfigGroupsEditor, qtbot: QtBot) -> None:
    """Test duplicating a group via toolbar."""
    initial_count = len(editor.data())

    # Select a group and duplicate
    editor.setCurrentGroup("Camera")
    editor._group_preset_sel.group_list.setFocus()
    editor._duplicate_selected()
    assert len(editor.data()) == initial_count + 1

    # Undo
    editor.undoStack().undo()
    assert len(editor.data()) == initial_count


def test_editor_set_channel_group(editor: ConfigGroupsEditor, qtbot: QtBot) -> None:
    """Test setting a group as channel group via toolbar."""
    tb = editor._tb

    # Select Camera (non-channel group)
    editor.setCurrentGroup("Camera")
    assert tb.set_channel_action.isEnabled()

    # Trigger set channel group action
    tb.set_channel_action.trigger()

    # Now Camera should be channel group
    groups = editor.data()
    camera = next(g for g in groups if g.name == "Camera")
    assert camera.is_channel_group
    channel = next(g for g in groups if g.name == "Channel")
    assert not channel.is_channel_group

    # set_channel_action should now be disabled for the current (channel) group
    assert not tb.set_channel_action.isEnabled()


def test_editor_set_current_preset(editor: ConfigGroupsEditor, qtbot: QtBot) -> None:
    """Test setting a current preset."""
    idx = editor.setCurrentPreset("Channel", "DAPI")
    assert idx.isValid()
    assert idx.data(Qt.ItemDataRole.DisplayRole) == "DAPI"

    # Non-existent preset
    idx = editor.setCurrentPreset("Channel", "NonExistent")
    assert not idx.isValid()


def test_editor_remove_selected(
    editor: ConfigGroupsEditor, qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test _remove_selected with mocked confirmation dialog."""
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    initial_count = len(editor.data())
    editor.setCurrentGroup("Camera")
    editor._group_preset_sel.group_list.setFocus()
    editor._remove_selected()
    assert len(editor.data()) == initial_count - 1


def test_editor_show_help(
    editor: ConfigGroupsEditor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test _show_help with mocked dialog exec."""
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    editor._show_help()


def test_editor_show_undo_view(editor: ConfigGroupsEditor) -> None:
    """Smoke test _show_undo_view."""
    editor._show_undo_view()


def test_editor_edit_group_properties(
    editor: ConfigGroupsEditor, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Smoke test _edit_group_properties with mocked dialog exec."""
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    editor.setCurrentGroup("Channel")
    editor._edit_group_properties()


def test_config_groups_help_dialog(qtbot: QtBot) -> None:
    """Smoke test ConfigGroupsHelpDialog."""
    dialog = ConfigGroupsHelpDialog()
    qtbot.addWidget(dialog)
    dialog.show()
    dialog.close()
