from typing import TYPE_CHECKING, cast

from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget

from pymmcore_widgets.device_properties import PropertyWidget

if TYPE_CHECKING:
    from pymmcore_widgets.config_presets._qmodel._config_model import _Node


class PropertyValueDelegate(QStyledItemDelegate):
    """Item delegate that uses a PropertyWidget for editing PropertySetting values."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget | None:
        node = cast("_Node", index.internalPointer())
        if not (model := index.model()) or (index.column() != 2) or not node.is_setting:
            return super().createEditor(parent, option, index)

        row = index.row()
        device = model.data(index.sibling(row, 0))
        prop = model.data(index.sibling(row, 1))
        widget = PropertyWidget(device, prop, parent=parent, connect_core=False)
        widget.valueChanged.connect(lambda: self.commitData.emit(widget))
        widget.setAutoFillBackground(True)
        return widget

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:
        if (model := index.model()) and isinstance(editor, PropertyWidget):
            data = model.data(index, Qt.ItemDataRole.EditRole)
            editor.setValue(data)
        else:
            super().setEditorData(editor, index)

    def setModelData(
        self,
        editor: QWidget | None,
        model: QAbstractItemModel | None,
        index: QModelIndex,
    ) -> None:
        if model and isinstance(editor, PropertyWidget):
            model.setData(index, editor.value(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)
