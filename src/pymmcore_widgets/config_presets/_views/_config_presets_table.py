from __future__ import annotations

import os
from contextlib import suppress
from typing import TYPE_CHECKING

from qtpy.QtCore import (
    QAbstractItemModel,
    QModelIndex,
    QSize,
    Qt,
    QTimer,
    QTransposeProxyModel,
)
from qtpy.QtWidgets import QTableView, QToolBar, QVBoxLayout, QWidget

from pymmcore_widgets._icons import StandardIcon
from pymmcore_widgets._models import ConfigGroupPivotModel, QConfigGroupsModel

from ._property_setting_delegate import PropertySettingDelegate

if TYPE_CHECKING:
    from pymmcore_plus import CMMCorePlus
    from PyQt6.QtGui import QAction

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

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setItemDelegate(PropertySettingDelegate(self))
        self._transpose_proxy: QTransposeProxyModel | None = None
        self._pivot_model: ConfigGroupPivotModel | None = None

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
        matrix.dataChanged.connect(self._ensure_persistent_editors)

        # this is a bit magical... but it looks better
        # will only happen once
        if not getattr(self, "_have_stretched_headers", False):
            QTimer.singleShot(0, self.stretchHeaders)

    def stretchHeaders(self) -> None:
        with suppress(RuntimeError):
            if hh := self.horizontalHeader():
                for col in range(hh.count()):
                    hh.setSectionResizeMode(col, hh.ResizeMode.Stretch)
                self._have_stretched_headers = True

    def _ensure_persistent_editors(self) -> None:
        """Ensure persistent editors are open for all cells after model changes."""
        # Use a single-shot timer to avoid opening editors during model updates
        QTimer.singleShot(0, self.openPersistentEditors)

    def openPersistentEditors(self) -> None:
        """Override to open persistent editors for all items."""
        if model := self.model():
            for row in range(model.rowCount()):
                for col in range(model.columnCount()):
                    idx = model.index(row, col)
                    if idx.isValid():
                        self.openPersistentEditor(idx)

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
        # Ensure persistent editors are reopened after group change
        # (the model reset from setGroup will close them)
        QTimer.singleShot(0, self.openPersistentEditors)

    def transpose(self) -> None:
        """Transpose the table view."""
        pivot = self.model()
        if isinstance(pivot, ConfigGroupPivotModel):
            self._transpose_proxy = QTransposeProxyModel()
            self._transpose_proxy.setSourceModel(pivot)
            super().setModel(self._transpose_proxy)
            # Ensure persistent editors are maintained after transposing
            QTimer.singleShot(0, self.openPersistentEditors)
        elif isinstance(pivot, QTransposeProxyModel):
            # Already transposed, revert to original model
            if self._pivot_model:
                super().setModel(self._pivot_model)
                self._transpose_proxy = None
                # Ensure persistent editors are maintained after un-transposing
                QTimer.singleShot(0, self.openPersistentEditors)

    def isTransposed(self) -> bool:
        """Check if the table view is currently transposed."""
        return isinstance(self.model(), QTransposeProxyModel)


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
        return obj

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = ConfigPresetsTableView(self)

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

    def _on_remove_action(self) -> None:
        source_idx = self._get_selected_preset_index()
        if not source_idx.isValid():
            return

        source_model = self.view.sourceModel()
        source_model.remove(source_idx, ask_confirmation=NOT_TESTING)

    def _on_duplicate_action(self) -> None:
        if not self.view.isTransposed():
            source_idx = self._get_selected_preset_index()
            if not source_idx.isValid():
                return

            source_model = self.view.sourceModel()
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
