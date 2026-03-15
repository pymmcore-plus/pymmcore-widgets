from __future__ import annotations

import os
from copy import deepcopy
from typing import TYPE_CHECKING, Any

from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QPoint,
    QSize,
    Qt,
    QTransposeProxyModel,
)
from qtpy.QtWidgets import (
    QHeaderView,
    QMenu,
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

from ._device_property_selector import DevicePropertySelector
from ._property_setting_delegate import PropertySettingDelegate
from ._undo_commands import (
    DuplicatePresetCommand,
    RemovePresetCommand,
    UpdatePresetPropertiesCommand,
    UpdatePresetSettingsCommand,
    undo_macro,
)
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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setItemDelegate(PropertySettingDelegate(self))
        self._transpose_proxy: QTransposeProxyModel | None = None
        self._pivot_model: ConfigGroupPivotModel | None = None
        self._undo_stack: QUndoStack | None = None
        self._loaded_devices: tuple[Device, ...] = ()

        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)

        # Only open editors on explicit user gestures handled below
        self.setEditTriggers(
            QTableView.EditTrigger.DoubleClicked | QTableView.EditTrigger.EditKeyPressed
        )

        # In normal mode, presets are columns — only allow column selection
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectColumns)
        if vh := self.verticalHeader():
            vh.setSectionsClickable(False)

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

        matrix.modelReset.connect(self._update_section_sizes)

    def resizeEvent(self, event: Any) -> None:
        """Adaptive column sizing based on available viewport space."""
        super().resizeEvent(event)
        self._update_section_sizes()

    def _update_section_sizes(self) -> None:
        """Recalculate column widths for the current viewport."""
        if (model := self.model()) is None:
            return  # pragma: no cover

        if (hh := self.horizontalHeader()) is None:
            return  # pragma: no cover

        col_count = model.columnCount()
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
        """Transpose the table view.

        Note: this replaces the model, which creates a new selectionModel().
        External code that connects to selectionModel().selectionChanged should
        reconnect after calling this method.
        """
        # Remember which preset index was selected
        selected: int | None = None
        if sm := self.selectionModel():
            if indices := sm.selectedIndexes():
                idx = indices[0]
                selected = idx.row() if self.isTransposed() else idx.column()

        pivot = self.model()
        if isinstance(pivot, ConfigGroupPivotModel):
            self._transpose_proxy = QTransposeProxyModel()
            self._transpose_proxy.setSourceModel(pivot)
            super().setModel(self._transpose_proxy)
            self._update_section_sizes()
        elif isinstance(pivot, QTransposeProxyModel):
            # Already transposed, revert to original model
            if self._pivot_model:
                super().setModel(self._pivot_model)
                self._transpose_proxy = None
                self._update_section_sizes()

        self._update_selection_behavior()

        # Restore selection in the new orientation
        if selected is not None:
            if self.isTransposed():
                self.selectRow(selected)
            else:
                self.selectColumn(selected)

    def isTransposed(self) -> bool:
        """Check if the table view is currently transposed."""
        return isinstance(self.model(), QTransposeProxyModel)

    def _update_selection_behavior(self) -> None:
        """Set selection to follow presets: columns normally, rows when transposed."""
        transposed = self.isTransposed()
        if transposed:
            self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        else:
            self.setSelectionBehavior(QTableView.SelectionBehavior.SelectColumns)
        if hh := self.horizontalHeader():
            hh.setSectionsClickable(not transposed)
        if vh := self.verticalHeader():
            vh.setSectionsClickable(transposed)

    def _pivot_coords(self, idx: QModelIndex) -> tuple[int, int]:
        """Map a view index to pivot (row, col), accounting for transpose."""
        if self.isTransposed():
            return idx.column(), idx.row()
        return idx.row(), idx.column()

    # --- header context menu ------------------------------------------------

    def _on_header_context_menu(self, pos: QPoint) -> None:
        """Show context menu on column header for per-preset property actions."""
        if (
            (hh := self.horizontalHeader()) is None
            or (col := hh.logicalIndexAt(pos)) < 0
            or (model := self.model()) is None
        ):
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

        props = DevicePropertySelector.promptForProperties(self, self._loaded_devices)
        if props and self._undo_stack is not None:
            cmd = UpdatePresetPropertiesCommand(
                self.sourceModel(), src_idx, list(props)
            )
            self._undo_stack.push(cmd)

    # --- cell-level interactions --------------------------------------------

    def mousePressEvent(self, event: Any) -> None:
        """Single left-click on a cell opens the editor (spreadsheet-like)."""
        super().mousePressEvent(event)
        mods = event.modifiers()
        extend = Qt.KeyboardModifier.ShiftModifier | Qt.KeyboardModifier.ControlModifier
        if event.button() == Qt.MouseButton.LeftButton and not (mods & extend):
            idx = self.indexAt(event.pos())
            if idx.isValid() and self.state() != QTableView.State.EditingState:
                self.edit(idx)

    def mouseDoubleClickEvent(self, event: Any) -> None:
        """Double-click on an empty cell adds the property to that preset."""
        idx = self.indexAt(event.pos())
        if idx.isValid() and idx.data(Qt.ItemDataRole.UserRole) is None:
            self._add_cell_setting(idx)
            return
        super().mouseDoubleClickEvent(event)  # pragma: no cover

    def contextMenuEvent(self, event: Any) -> None:
        """Right-click context menu: add/remove property for a single cell."""
        idx = self.indexAt(event.pos())
        if not idx.isValid():  # pragma: no cover
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

    # def keyPressEvent(self, event: Any) -> None:
    #     """Handle Delete/Backspace to remove property from one preset."""
    #     if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
    #         sm = self.selectionModel()
    #         if sm:
    #             for idx in sm.selectedIndexes():
    #                 if idx.data(Qt.ItemDataRole.UserRole) is not None:
    #                     self._remove_cell_setting(idx)
    #                     break
    #     else:
    #         super().keyPressEvent(event)

    def _add_cell_setting(self, idx: QModelIndex) -> None:
        """Add a placeholder setting for the cell at *idx*."""
        pivot = self._get_pivot_model()
        p_row, p_col = self._pivot_coords(idx)
        src_idx = pivot.get_source_index_for_column(p_col)
        if not src_idx.isValid():
            return  # pragma: no cover

        if self._undo_stack is not None:
            preset = src_idx.data(Qt.ItemDataRole.UserRole)
            if preset is None:
                return  # pragma: no cover
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
            return  # pragma: no cover

        target_key = pivot._rows[p_row]
        preset = src_idx.data(Qt.ItemDataRole.UserRole)
        if preset is None:
            return  # pragma: no cover
        filtered = [s for s in preset.settings if s.key() != target_key]

        if self._undo_stack is not None:
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
        self.transpose_action = tb.addAction(
            StandardIcon.TRANSPOSE.icon(), "Transpose", self.view.transpose
        )
        if self.transpose_action:
            self.transpose_action.setCheckable(True)

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
        source_indices = self._get_selected_preset_indices()
        if not source_indices:
            return

        source_model = self.view.sourceModel()
        if self._undo_stack is not None:
            if len(source_indices) == 1:
                self._undo_stack.push(
                    RemovePresetCommand(source_model, source_indices[0])
                )
            else:
                with undo_macro(
                    self._undo_stack, f"Remove {len(source_indices)} Presets"
                ):
                    # Remove in reverse row order so indices stay valid
                    for idx in sorted(
                        source_indices, key=lambda i: i.row(), reverse=True
                    ):
                        self._undo_stack.push(RemovePresetCommand(source_model, idx))
        else:
            for idx in sorted(source_indices, key=lambda i: i.row(), reverse=True):
                source_model.remove(idx, ask_confirmation=NOT_TESTING)

    def _on_duplicate_action(self) -> None:
        source_indices = self._get_selected_preset_indices()
        if not source_indices:
            return

        source_model = self.view.sourceModel()
        if (stack := self._undo_stack) is not None:
            if len(source_indices) == 1:
                stack.push(DuplicatePresetCommand(source_model, source_indices[0]))
            else:
                with undo_macro(stack, f"Duplicate {len(source_indices)} Presets"):
                    for idx in source_indices:
                        stack.push(DuplicatePresetCommand(source_model, idx))
        else:
            for idx in source_indices:
                source_model.duplicate_preset(idx)

    def _get_selected_preset_indices(self) -> list[QModelIndex]:
        """Get all selected presets from the source model."""
        sm = self.view.selectionModel()
        if sm is None:
            return []  # pragma: no cover

        if self.view.isTransposed():
            view_indices = sm.selectedRows()
            cols = [idx.row() for idx in view_indices]
        else:
            view_indices = sm.selectedColumns()
            cols = [idx.column() for idx in view_indices]

        if not cols:
            return []

        pivot_model = self.view._get_pivot_model()
        result = []
        for col in cols:
            src_idx = pivot_model.get_source_index_for_column(col)
            if src_idx.isValid():
                result.append(src_idx)
        return result
