from __future__ import annotations

import os
from contextlib import suppress
from typing import TYPE_CHECKING, Any

from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QSize,
    Qt,
    QTimer,
    QTransposeProxyModel,
)
from qtpy.QtWidgets import (
    QApplication,
    QHeaderView,
    QTableView,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from pymmcore_widgets._icons import StandardIcon
from pymmcore_widgets._models import (
    ConfigGroupPivotModel,
    QConfigGroupsModel,
    get_loaded_devices,
)

from ._property_setting_delegate import PropertySettingDelegate
from ._undo_commands import DuplicatePresetCommand, RemovePresetCommand
from ._undo_delegates import PropertyValueDelegate

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pymmcore_plus import CMMCorePlus
    from PyQt6.QtGui import QAction
    from qtpy.QtGui import QUndoStack

    from pymmcore_widgets._models import Device

else:
    from qtpy.QtGui import QAction

NOT_TESTING = "PYTEST_VERSION" not in os.environ


class ConfigPresetsTableView(QTableView):
    """Plain QTableView for displaying configuration presets.

    Introduces a pivot model to transform the QConfigGroupsModel (tree model)
    into a 2D table with devices and properties as rows, and presets as columns.

    To use, call `setModel` with a `QConfigGroupsModel`, and then
    `setGroup` with the name or index of the group you want to view.
    """

    MIN_COL_WIDTH = 120
    MAX_COL_WIDTH = 340
    MIN_ROW_HEIGHT = 26
    MAX_ROW_HEIGHT = 48

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setItemDelegate(PropertySettingDelegate(self))
        self._transpose_proxy: QTransposeProxyModel | None = None
        self._pivot_model: ConfigGroupPivotModel | None = None
        self._undo_stack: QUndoStack | None = None
        self._loaded_devices: tuple[Device, ...] = ()

        # Right-click on column headers for per-preset property management
        if hh := self.horizontalHeader():
            hh.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            hh.customContextMenuRequested.connect(self._on_header_context_menu)

    def setAvailableDevices(self, devices: Sequence[Device]) -> None:
        """Set the available devices for property selection dialogs."""
        self._loaded_devices = tuple(devices)

    def setUndoStack(self, undo_stack: QUndoStack) -> None:
        """Set the undo stack and configure undo-aware delegates."""
        self._undo_stack = undo_stack

        if undo_stack is not None:
            # Replace the delegate with an undo-aware one
            self.setItemDelegate(PropertyValueDelegate(undo_stack, self))

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Set the model for the table view."""
        if isinstance(model, QConfigGroupsModel):
            matrix = ConfigGroupPivotModel()
            matrix.setSourceModel(model)
        elif isinstance(model, ConfigGroupPivotModel):  # pragma: no cover
            matrix = model
        else:  # pragma: no cover
            raise TypeError(
                "Model must be an instance of QConfigGroupsModel "
                f"or ConfigGroupPivotModel. Got: {type(model).__name__}"
            )

        self._pivot_model = matrix
        super().setModel(matrix)

        # Connect to model signals to ensure persistent editors are always maintained
        matrix.modelReset.connect(self._ensure_persistent_editors)
        matrix.modelReset.connect(self._update_section_sizes)
        matrix.dataChanged.connect(self._ensure_persistent_editors)

    def resizeEvent(self, event: Any) -> None:
        """Adaptive column/row sizing based on available viewport space."""
        super().resizeEvent(event)
        self._update_section_sizes()

    def _update_section_sizes(self) -> None:
        """Recalculate column widths and row heights for the current viewport."""
        model = self.model()
        if model is None:
            return

        hh = self.horizontalHeader()
        vh = self.verticalHeader()
        if hh is None or vh is None:
            return

        col_count = model.columnCount()
        row_count = model.rowCount()
        vp_width = self.viewport().width()

        # Columns:
        # - Too many to fit at MIN_COL_WIDTH → fixed at MIN_COL_WIDTH (scrollbar)
        # - Natural stretch would exceed MAX_COL_WIDTH → fixed at MAX_COL_WIDTH
        # - Otherwise → stretch to fill
        if col_count > 0:
            natural_width = vp_width // col_count
            if natural_width < self.MIN_COL_WIDTH:
                hh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                hh.setDefaultSectionSize(self.MIN_COL_WIDTH)
            elif natural_width > self.MAX_COL_WIDTH:
                hh.setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
                hh.setDefaultSectionSize(self.MAX_COL_WIDTH)
            else:
                hh.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

        # Rows: fill vertical space, clamped to [MIN_ROW_HEIGHT, MAX_ROW_HEIGHT]
        if row_count > 0:
            vp_height = self.viewport().height()
            row_h = max(
                self.MIN_ROW_HEIGHT,
                min(vp_height // row_count, self.MAX_ROW_HEIGHT),
            )
            vh.setDefaultSectionSize(row_h)

    def _ensure_persistent_editors(self) -> None:
        """Ensure persistent editors are open for all cells after model changes."""
        # Use a single-shot timer to avoid opening editors during model updates
        QTimer.singleShot(0, self.openPersistentEditors)

    def openPersistentEditors(self) -> None:
        """Open persistent editors only for cells that have data."""
        UserRole = Qt.ItemDataRole.UserRole
        with suppress(RuntimeError):  # since this may be a slot
            if model := self.model():
                # Preserve focus: opening persistent editors (e.g. combo boxes)
                # can steal focus from the active view.
                focused = QApplication.focusWidget()
                # Close all existing persistent editors first
                for row in range(model.rowCount()):
                    for col in range(model.columnCount()):
                        idx = model.index(row, col)
                        if idx.isValid():
                            self.closePersistentEditor(idx)
                # Reopen only for cells with data
                for row in range(model.rowCount()):
                    for col in range(model.columnCount()):
                        idx = model.index(row, col)
                        if idx.isValid() and idx.data(UserRole) is not None:
                            self.openPersistentEditor(idx)
                if focused is not None:
                    focused.setFocus()

    def _get_pivot_model(self) -> ConfigGroupPivotModel:
        model = self.model()
        if isinstance(model, QTransposeProxyModel):
            model = model.sourceModel()
        if not isinstance(model, ConfigGroupPivotModel):  # pragma: no cover
            raise ValueError("Source model is not set. Call setSourceModel first.")
        return model

    def sourceModel(self) -> QConfigGroupsModel:
        pivot_model = self._get_pivot_model()
        src_model = pivot_model.sourceModel()
        if not isinstance(src_model, QConfigGroupsModel):  # pragma: no cover
            raise ValueError("Source model is not a QConfigGroupsModel.")
        return src_model

    def setGroup(self, group_name_or_index: str | QModelIndex) -> None:
        """Set the group for the pivot model."""
        model = self._get_pivot_model()
        model.setGroup(group_name_or_index)

    def transpose(self) -> None:
        """Transpose the table view."""
        pivot = self.model()
        if isinstance(pivot, ConfigGroupPivotModel):
            self._transpose_proxy = QTransposeProxyModel()
            self._transpose_proxy.setSourceModel(pivot)
            super().setModel(self._transpose_proxy)
            self._update_section_sizes()
            QTimer.singleShot(0, self.openPersistentEditors)
        elif isinstance(pivot, QTransposeProxyModel):
            # Already transposed, revert to original model
            if self._pivot_model:
                super().setModel(self._pivot_model)
                self._transpose_proxy = None
                self._update_section_sizes()
                QTimer.singleShot(0, self.openPersistentEditors)

    def isTransposed(self) -> bool:
        """Check if the table view is currently transposed."""
        return isinstance(self.model(), QTransposeProxyModel)

    def _pivot_coords(self, idx: QModelIndex) -> tuple[int, int]:
        """Map a view index to pivot (row, col), accounting for transpose."""
        if self.isTransposed():
            return idx.column(), idx.row()
        return idx.row(), idx.column()

    # --- header context menu ------------------------------------------------

    def _on_header_context_menu(self, pos: Any) -> None:
        """Show context menu on column header for per-preset property actions."""
        from qtpy.QtWidgets import QMenu

        hh = self.horizontalHeader()
        if hh is None:
            return

        col = hh.logicalIndexAt(pos)
        if col < 0:
            return

        model = self.model()
        if model is None:
            return

        preset_name = model.headerData(
            col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole
        )

        menu = QMenu(self)
        add_action = menu.addAction(f"Add property to '{preset_name}'...")
        action = menu.exec(hh.mapToGlobal(pos))
        if action == add_action:
            self._add_property_to_preset_column(col)

    def _add_property_to_preset_column(self, col: int) -> None:
        """Add properties to a single preset via dialog."""
        pivot = self._get_pivot_model()
        src_idx = pivot.get_source_index_for_column(col)
        if not src_idx.isValid() or not self._loaded_devices:
            return

        from ._device_property_selector import DevicePropertySelector

        props = DevicePropertySelector.promptForProperties(self, self._loaded_devices)
        if props and self._undo_stack is not None:
            from ._undo_commands import UpdatePresetPropertiesCommand

            cmd = UpdatePresetPropertiesCommand(
                self.sourceModel(), src_idx, list(props)
            )
            self._undo_stack.push(cmd)

    # --- cell-level interactions --------------------------------------------

    def mouseDoubleClickEvent(self, event: Any) -> None:
        """Double-click on an empty cell adds the property to that preset."""
        idx = self.indexAt(event.pos())
        if idx.isValid() and idx.data(Qt.ItemDataRole.UserRole) is None:
            self._add_cell_setting(idx)
            return
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event: Any) -> None:
        """Right-click context menu: add/remove property for a single cell."""
        from qtpy.QtWidgets import QMenu

        idx = self.indexAt(event.pos())
        if not idx.isValid():
            super().contextMenuEvent(event)
            return

        has_data = idx.data(Qt.ItemDataRole.UserRole) is not None
        menu = QMenu(self)
        if has_data:
            remove_act = menu.addAction("Remove property from this preset")
            add_act = None
        else:
            add_act = menu.addAction("Add property to this preset")
            remove_act = None

        chosen = menu.exec(event.globalPos())
        if chosen is not None:
            if chosen == add_act:
                self._add_cell_setting(idx)
            elif chosen == remove_act:
                self._remove_cell_setting(idx)

    def keyPressEvent(self, event: Any) -> None:
        """Handle Delete/Backspace to remove property from one preset."""
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            sm = self.selectionModel()
            if sm:
                for idx in sm.selectedIndexes():
                    if idx.data(Qt.ItemDataRole.UserRole) is not None:
                        self._remove_cell_setting(idx)
                        break
        else:
            super().keyPressEvent(event)

    def _add_cell_setting(self, idx: QModelIndex) -> None:
        """Add a placeholder setting for the cell at *idx*."""
        pivot = self._get_pivot_model()
        p_row, p_col = self._pivot_coords(idx)
        src_idx = pivot.get_source_index_for_column(p_col)
        if not src_idx.isValid():
            return

        if self._undo_stack is not None:
            from copy import deepcopy

            from ._undo_commands import UpdatePresetSettingsCommand

            preset = src_idx.data(Qt.ItemDataRole.UserRole)
            if preset is None:
                return
            new_settings = list(deepcopy(preset.settings))
            new_settings.append(pivot._empty_setting_for_row(p_row))
            cmd = UpdatePresetSettingsCommand(self.sourceModel(), src_idx, new_settings)
            self._undo_stack.push(cmd)
        else:
            pivot.add_setting_at(p_row, p_col)

    def _remove_cell_setting(self, idx: QModelIndex) -> None:
        """Remove the setting at *idx* from its preset."""
        pivot = self._get_pivot_model()
        p_row, p_col = self._pivot_coords(idx)
        src_idx = pivot.get_source_index_for_column(p_col)
        if not src_idx.isValid() or p_row >= len(pivot._rows):
            return

        target_key = pivot._rows[p_row]
        preset = src_idx.data(Qt.ItemDataRole.UserRole)
        if preset is None:
            return
        filtered = [s for s in preset.settings if s.key() != target_key]

        if self._undo_stack is not None:
            from ._undo_commands import UpdatePresetSettingsCommand

            cmd = UpdatePresetSettingsCommand(self.sourceModel(), src_idx, filtered)
            self._undo_stack.push(cmd)
        else:
            pivot.remove_setting_at(p_row, p_col)


class ConfigPresetsTable(QWidget):
    """2D Table for viewing configuration presets.

    Adds buttons to transpose, duplicate, and remove presets.

    With all the presets as columns and the device/property pairs as rows.
    (unless transposed).

    To use, call `setModel` with a `QConfigGroupsModel`, and then
    `setGroup` with the name or index of the group you want to view.
    """

    @classmethod
    def create_from_core(
        cls, core: CMMCorePlus, parent: QWidget | None = None
    ) -> ConfigPresetsTable:
        """Create a PresetsTable from a CMMCorePlus instance."""
        obj = cls(parent)
        model = QConfigGroupsModel.create_from_core(core)
        obj.setModel(model)
        obj.setAvailableDevices(list(get_loaded_devices(core)))
        return obj

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = ConfigPresetsTableView(self)
        self._undo_stack: QUndoStack | None = None

        self._toolbar = tb = QToolBar(self)
        tb.setIconSize(QSize(16, 16))
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        if act := tb.addAction(
            StandardIcon.TRANSPOSE.icon(), "Transpose", self.view.transpose
        ):
            act.setCheckable(True)

        self.remove_action = QAction(StandardIcon.DELETE.icon(), "Remove")
        tb.addAction(self.remove_action)
        self.remove_action.triggered.connect(self._on_remove_action)

        self.duplicate_action = QAction(StandardIcon.COPY.icon(), "Duplicate")
        tb.addAction(self.duplicate_action)
        self.duplicate_action.triggered.connect(self._on_duplicate_action)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._toolbar)
        layout.addWidget(self.view)

    def setAvailableDevices(self, devices: Sequence[Device]) -> None:
        """Set the available devices for property selection dialogs."""
        self.view.setAvailableDevices(devices)

    def setModel(self, model: QAbstractItemModel | None) -> None:
        """Set the model for the table view."""
        self.view.setModel(model)

    def sourceModel(self) -> QConfigGroupsModel | None:
        """Return the source model of the table view."""
        try:
            return self.view.sourceModel()
        except ValueError:  # pragma: no cover
            return None

    def setGroup(self, group_name_or_index: str | QModelIndex) -> None:
        """Set the group to be displayed."""
        self.view.setGroup(group_name_or_index)

    def setUndoStack(self, undo_stack: QUndoStack) -> None:
        """Set the undo stack for remove/duplicate operations."""
        self._undo_stack = undo_stack
        self.view.setUndoStack(undo_stack)

    def _on_remove_action(self) -> None:
        source_idx = self._get_selected_preset_index()
        if not source_idx.isValid():
            return

        source_model = self.view.sourceModel()
        # Use undo stack if available, otherwise fall back to direct operation
        if self._undo_stack is not None:
            command = RemovePresetCommand(source_model, source_idx)
            self._undo_stack.push(command)
        else:
            # Fall back to direct model operation
            source_model.remove(source_idx, ask_confirmation=NOT_TESTING)

    def _on_duplicate_action(self) -> None:
        if not self.view.isTransposed():
            source_idx = self._get_selected_preset_index()
            if not source_idx.isValid():
                return

            source_model = self.view.sourceModel()
            # Use undo stack if available, otherwise fall back to direct operation
            if self._undo_stack is not None:
                command = DuplicatePresetCommand(source_model, source_idx)
                self._undo_stack.push(command)
            else:
                # Fall back to direct model operation
                source_model.duplicate_preset(source_idx)
        # TODO: handle transposed case

    def _get_selected_preset_index(self) -> QModelIndex:
        """Get the currently selected preset from the source model."""
        if self.view.isTransposed():
            return QModelIndex()  # TODO

        if sm := self.view.selectionModel():
            if indices := sm.selectedColumns():
                pivot_model = self.view._get_pivot_model()
                col = indices[0].column()
                return pivot_model.get_source_index_for_column(col)
        return QModelIndex()  # pragma: no cover
