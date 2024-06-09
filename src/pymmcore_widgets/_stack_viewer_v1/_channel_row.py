from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

import cmap
from qtpy import QtCore, QtGui, QtWidgets
from superqt import QColormapComboBox, QRangeSlider

if TYPE_CHECKING:
    from qtpy.QtGui import QMouseEvent
    from useq import Channel

try:
    pass
except ImportError as e:
    raise ImportError(
        "vispy is required for Channel_row. "
        "Please run `pip install pymmcore-widgets[image]`"
    ) from e


CMAPS = ["gray", "BOP_Blue", "BOP_Purple"]


def try_cast_colormap(val: Any) -> cmap.Colormap | None:
    """Try to cast `val` to a cmap.Colormap instance, return None if it fails."""
    if isinstance(val, cmap.Colormap):
        return val
    with suppress(Exception):
        return cmap.Colormap(val)
    return None


class ChannelRow(QtWidgets.QWidget):
    """Row of channel boxes."""

    visible = QtCore.Signal(bool, int)
    autoscale = QtCore.Signal(bool, int)
    new_clims = QtCore.Signal(tuple, int)
    new_cmap = QtCore.Signal(cmap.Colormap, int)
    selected = QtCore.Signal(int)
    new_channel = QtCore.Signal(str, int)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.restore_data()

        self.setLayout(QtWidgets.QHBoxLayout())
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )
        self.boxes: dict[int, ChannelBox] = {}
        self.new_cmap.connect(self._handle_channel_cmap)
        self.visible.connect(self.channel_visibility)
        self.new_channel.connect(self._add_channel)
        self.current_channel: int | None = None

    def add_channel(self, channel: Channel | None, index: int | None = None) -> None:
        """Add a channel to the row."""
        if index is None:
            index = len(self.boxes)
        if channel is None:
            name = "Default"
        else:
            name = channel.config
        self.new_channel.emit(name, index)

    def _add_channel(self, name: str, index: int) -> None:
        channel_box = ChannelBox(name, cmaps=self.cmap_names, parent=self)
        self.boxes[index] = channel_box

        channel_box.show_channel.stateChanged.connect(self.emit_visible)
        channel_box.autoscale_chbx.stateChanged.connect(self.emit_autoscale)
        channel_box.slider.sliderMoved.connect(self.emit_new_clims)
        channel_box.color_choice.currentColormapChanged.connect(self.emit_new_cmap)

        channel_box.color_choice.setCurrentIndex(index)
        channel_box.clicked.connect(self._handle_channel_choice)
        self.layout().addWidget(channel_box)
        channel_box.color_choice.setCurrentColormap(
            self.channel_cmaps.get(name, "gray")
        )

    def emit_visible(self, state: int) -> None:
        sender = self.sender()
        self.visible.emit(bool(state), list(self.boxes.values()).index(sender.parent()))

    def emit_autoscale(self, state: int) -> None:
        sender = self.sender()
        self.autoscale.emit(
            bool(state), list(self.boxes.values()).index(sender.parent())
        )

    def emit_new_clims(self, value: tuple[int, int]) -> None:
        sender = self.sender()
        self.new_clims.emit(value, list(self.boxes.values()).index(sender.parent()))

    def emit_new_cmap(self, cmap: cmap.Colormap) -> None:
        sender = self.sender()
        self.new_cmap.emit(cmap, list(self.boxes.values()).index(sender.parent()))

    def _disconnect(self) -> None:
        for box in self.boxes.values():
            box.show_channel.stateChanged.disconnect(self.emit_visible)
            box.autoscale_chbx.stateChanged.disconnect(self.emit_autoscale)
            box.slider.sliderMoved.disconnect(self.emit_new_clims)
            box.color_choice.currentColormapChanged.disconnect(self.emit_new_cmap)
            box.clicked.disconnect(self._handle_channel_choice)

    def channel_visibility(self, visible: bool, channel: int) -> None:
        """If the current channel is made invisible, choose a different one."""
        if self.current_channel == channel and not visible:
            channel_to_set = abs(channel - 1)
            for idx, cbox in enumerate(self.boxes.values()):
                if cbox.show_channel.isChecked():
                    channel_to_set = idx
                    break
            while channel_to_set > len(self.boxes) - 1:
                channel_to_set -= 1
            self._handle_channel_choice(self.boxes[channel_to_set].channel)

    def _handle_channel_choice(self, channel: str) -> None:
        """Channel was chosen, adjust GUI and send signal."""
        if len(self.boxes) == 1:
            return
        for idx, channel_box in enumerate(self.boxes.values()):
            if channel_box.channel != channel:
                channel_box.setStyleSheet("ChannelBox{border: 1px solid}")
            else:
                channel_box.setStyleSheet("ChannelBox{border: 3px solid}")
                channel_box.show_channel.setChecked(True)
                self.selected.emit(idx)
                self.current_channel = idx

    def _handle_channel_cmap(self, colormap: cmap.Colormap | str, i: int) -> None:
        color = colormap if isinstance(colormap, str) else colormap.name
        if color in self.cmap_names:
            self.cmap_names.remove(color)
        self.cmap_names.insert(0, color)
        self.boxes[i].color_choice.addColormap(color)
        self.boxes[i].color_choice.setCurrentColormap(color)
        self.channel_cmaps[self.boxes[i].channel] = color
        self.qt_settings.setValue("channel_cmaps", self.channel_cmaps)
        self.qt_settings.setValue("cmap_names", self.cmap_names)

    def restore_data(self) -> None:
        """Restore data from previous session."""
        self.qt_settings = QtCore.QSettings("pymmcore_widgets", self.__class__.__name__)
        self.cmap_names = self.qt_settings.value(
            "cmap_names", ["gray", "magenta", "cyan"]
        )
        self.channel_cmaps = self.qt_settings.value("channel_cmaps", {})


class ChannelBox(QtWidgets.QWidget):
    """Box that represents a channel and gives some way of interaction."""

    clicked = QtCore.Signal(str)

    def __init__(
        self,
        name: str | None = None,
        cmaps: list | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent=parent)
        if name is None:
            name = "Default"
        self.channel = name
        grid_layout = QtWidgets.QGridLayout(self)
        self.show_channel = QtWidgets.QCheckBox(name)
        self.show_channel.setChecked(True)
        self.show_channel.setStyleSheet("font-weight: bold")
        grid_layout.addWidget(self.show_channel, 0, 0)
        self.color_choice = QColormapComboBox(allow_user_colormaps=True)

        if cmaps is None:
            cmaps = CMAPS
        for my_cmap in cmaps:
            self.color_choice.addColormap(my_cmap)

        grid_layout.addWidget(self.color_choice, 0, 1)
        self.autoscale_chbx = QtWidgets.QCheckBox("Auto")
        self.autoscale_chbx.setChecked(True)
        grid_layout.addWidget(self.autoscale_chbx, 0, 2)
        self.slider = QRangeSlider(QtCore.Qt.Orientation.Horizontal)
        grid_layout.addWidget(self.slider, 2, 0, 1, 3)
        self.setStyleSheet("ChannelBox{border: 1px solid}")

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        self.clicked.emit(self.channel)


class QColorComboBox(QtWidgets.QComboBox):
    """A drop down menu for selecting colors."""

    # Adapted from https://stackoverflow.com/questions/64497029/a-color-drop-down-selector-for-pyqt5

    # signal emitted if a color has been selected
    selectedColor = QtCore.Signal(QtGui.QColor)

    def __init__(
        self, parent: QtWidgets.QWidget | None = None, enableUserDefColors: bool = False
    ) -> None:
        # init QComboBox
        super().__init__(parent)

        # enable the line edit to display the currently selected color
        self.setEditable(True)
        # read only so that there is no blinking cursor or sth editable
        self.lineEdit().setReadOnly(True)
        # self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # text that shall be displayed for the option
        # to pop up the QColorDialog for user defined colors
        self._userDefEntryText = "New"
        # add the option for user defined colors
        if enableUserDefColors:
            self.addItem(self._userDefEntryText)

        self._currentColor: QtGui.QColor = QtGui.QColor()

        self.activated.connect(self._color_selected)
        # self.setStyleSheet("QComboBox:drop-down {
        # image: none; background: red; border: 1px grey;}")

    def addColors(
        self, colors: list[list[QtGui.QColor]] | list[list[int]] | list[list[float]]
    ) -> None:
        """Adds colors to the QComboBox."""
        for a_color in colors:
            # if input is not a QColor, try to make it one
            if not (isinstance(a_color, QtGui.QColor)):
                try:
                    a_color = QtGui.QColor(a_color)
                except TypeError:
                    if max(a_color) < 2:
                        a_color = [int(x * 255) for x in a_color]
                    a_color = QtGui.QColor(*a_color)

            # avoid duplicates
            if self.findData(a_color) == -1:
                # add the new color and set the background color of that item
                self.addItem("", userData=a_color)
                self.setItemData(
                    self.count() - 1,
                    QtGui.QColor(a_color),
                    QtCore.Qt.ItemDataRole.BackgroundRole,
                )

    def addColor(self, color: QtGui.QColor) -> None:
        """Adds the color to the QComboBox."""
        self.addColors([color])

    def setColor(self, color: QtGui.QColor) -> None:
        """Adds the color to the QComboBox and selects it."""
        if isinstance(color, int):
            self.setCurrentIndex(color)
            self._currentColor = self.itemData(color)
            self.lineEdit().setStyleSheet(
                "background-color: " + self._currentColor.name()
            )
        else:
            self._color_selected(self.findData(color), False)

    def getCurrentColor(self) -> QtGui.QColor | None:
        """Returns the currently selected QColor or None if not yet selected."""
        return self._currentColor

    def _color_selected(self, index: int, emitSignal: bool = True) -> None:
        """Processes the selection of the QComboBox."""
        # if a color is selected, emit the selectedColor signal
        if self.itemText(index) == "":
            self._currentColor = self.itemData(index)
            if emitSignal:
                self.selectedColor.emit(self._currentColor)

        # if the user wants to define a custom color
        elif self.itemText(index) == self._userDefEntryText:
            # get the user defined color
            new_color = QtWidgets.QColorDialog.getColor(
                self._currentColor
                if self._currentColor
                else QtCore.Qt.GlobalColor.white
            )
            if new_color.isValid():
                # add the color to the QComboBox and emit the signal
                self.addColor(new_color)
                self._currentColor = new_color
                if emitSignal:
                    self.selectedColor.emit(self._currentColor)

        # make sure that current color is displayed
        if self._currentColor:
            self.setCurrentIndex(self.findData(self._currentColor))
            self.lineEdit().setStyleSheet(
                "background-color: " + self._currentColor.name()
            )


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    w = ChannelBox("empty", cmaps=CMAPS)
    w.show()

    sys.exit(app.exec())
