from __future__ import annotations

from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget

from pymmcore_widgets._models import DevicePropertySetting
from pymmcore_widgets.device_properties._property_widget import create_property_editor


class PropertySettingDelegate(QStyledItemDelegate):
    """Item delegate that uses a PropertyWidget for editing PropertySetting values."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget | None:
        if not isinstance(
            (setting := index.data(Qt.ItemDataRole.UserRole)), DevicePropertySetting
        ):
            return super().createEditor(parent, option, index)  # pragma: no cover
        widget = create_property_editor(setting)
        widget.setParent(parent)
        widget.setValue(setting.value)  # avoids commitData warnings
        widget.valueChanged.connect(lambda: self.commitData.emit(widget))
        widget.setAutoFillBackground(True)
        # Let right-clicks pass through to the table view's contextMenuEvent
        no_ctx = Qt.ContextMenuPolicy.NoContextMenu
        widget.setContextMenuPolicy(no_ctx)
        for child in widget.findChildren(QWidget):
            child.setContextMenuPolicy(no_ctx)
        return widget

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:
        setting = index.data(Qt.ItemDataRole.UserRole)
        if (
            isinstance(setting, DevicePropertySetting)
            and editor
            and hasattr(editor, "setValue")
        ):
            # Block signals: Qt calls setEditorData before registering the editor
            # in its internal hash, so any valueChanged → commitData emission
            # would warn "editor does not belong to this view".
            editor.blockSignals(True)
            try:
                editor.setValue(setting.value)
            finally:
                editor.blockSignals(False)
        else:  # pragma: no cover
            super().setEditorData(editor, index)

    def setModelData(
        self,
        editor: QWidget | None,
        model: QAbstractItemModel | None,
        index: QModelIndex,
    ) -> None:
        if model and editor and hasattr(editor, "value"):
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)
        else:  # pragma: no cover
            super().setModelData(editor, model, index)
