from pymmcore_plus.model import Setting
from qtpy.QtCore import QAbstractItemModel, QModelIndex, Qt
from qtpy.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QWidget

from pymmcore_widgets.device_properties import PropertyWidget


class PropertySettingDelegate(QStyledItemDelegate):
    """Item delegate that uses a PropertyWidget for editing PropertySetting values."""

    def createEditor(
        self, parent: QWidget | None, option: QStyleOptionViewItem, index: QModelIndex
    ) -> QWidget | None:
        if not isinstance((setting := index.data(Qt.ItemDataRole.UserRole)), Setting):
            return super().createEditor(parent, option, index)
        dev, prop, *_ = setting
        widget = PropertyWidget(dev, prop, parent=parent, connect_core=False)
        widget.setValue(setting.property_value)
        widget.valueChanged.connect(lambda: self.commitData.emit(widget))
        widget.setAutoFillBackground(True)
        return widget

    def setEditorData(self, editor: QWidget | None, index: QModelIndex) -> None:
        setting = index.data(Qt.ItemDataRole.UserRole)
        if not isinstance(setting, Setting) or not isinstance(editor, PropertyWidget):
            super().setEditorData(editor, index)
            return

        editor.setValue(setting.property_value)

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
