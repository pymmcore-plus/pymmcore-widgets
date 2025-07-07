#!/usr/bin/env python3
"""Simple test script to verify undo/redo functionality in ConfigGroupsEditor."""

import sys

from qtpy.QtWidgets import QApplication

from pymmcore_widgets._models._py_config_model import (
    ConfigGroup,
    ConfigPreset,
    DevicePropertySetting,
)
from pymmcore_widgets.config_presets import ConfigGroupsEditor


def test_undo_redo():
    """Test basic undo/redo functionality."""
    QApplication.instance() or QApplication(sys.argv)

    # Create an editor
    editor = ConfigGroupsEditor()

    # Create some test data
    group1 = ConfigGroup(
        name="Test Group",
        presets=[
            ConfigPreset(
                name="Preset1",
                settings=[DevicePropertySetting("Camera", "Exposure", "100")],
            )
        ],
    )

    editor.setData([group1])

    # Test undo stack is available
    undo_stack = editor.undoStack()
    assert undo_stack is not None

    # Test adding a group (should be undoable)
    initial_count = len(editor.data())
    editor._add_group()

    # Should have one more group
    assert len(editor.data()) == initial_count + 1

    # Should be able to undo
    assert undo_stack.canUndo()
    undo_stack.undo()

    # Should be back to original count
    assert len(editor.data()) == initial_count

    # Should be able to redo
    assert undo_stack.canRedo()
    undo_stack.redo()

    # Should have the group again
    assert len(editor.data()) == initial_count + 1

    print("✓ Basic undo/redo functionality works!")


if __name__ == "__main__":
    test_undo_redo()
