from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING, Any

import cmap
from qtpy import QtCore, QtGui, QtWidgets
from superqt import QColormapComboBox, QRangeSlider
from useq import Channel

if TYPE_CHECKING:
    from qtpy.QtGui import QMouseEvent

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

    def __init__(
        self,
        num_channels: int = 5,
    ) -> None:
        super().__init__()
        self.restore_data()

        self.setLayout(QtWidgets.QHBoxLayout())
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.boxes = []
        # TODO: Ideally we would know beforehand how many of these we need.
        for i in range(num_channels):
            channel_box = ChannelBox(Channel(config="empty"), cmaps=self.cmap_names)
            channel_box.show_channel.stateChanged.connect(
                lambda state, i=i: self.visible.emit(state, i)
            )
            channel_box.autoscale_chbx.stateChanged.connect(
                lambda state, i=i: self.autoscale.emit(state, i)
            )
            channel_box.slider.sliderMoved.connect(
                lambda values, i=i: self.new_clims.emit(values, i)
            )
            channel_box.color_choice.currentColormapChanged.connect(
                lambda color, i=i: self.new_cmap.emit(color, i)
            )
            channel_box.color_choice.setCurrentIndex(i)
            channel_box.clicked.connect(self._handle_channel_choice)
            channel_box.mousePressEvent(None)
            channel_box.hide()
            self.current_channel = i
            self.boxes.append(channel_box)
            self.layout().addWidget(channel_box)
        self.new_cmap.connect(self._handle_channel_cmap)
        self.visible.connect(self.channel_visibility)

    def box_visibility(self, i: int, name: str) -> None:
        """Make a box visible and set its name."""
        self.boxes[i].visible = True
        self.boxes[i].show()
        self.boxes[i].autoscale_chbx.setChecked(True)
        self.boxes[i].show_channel.setText(name)
        self.boxes[i].channel = name
        self.boxes[i].color_choice.setCurrentColormap(
            self.channel_cmaps.get(name, "gray")
        )
        if len(self.boxes) > 1:
            self.boxes[i].mousePressEvent(None)
        else:
            self.boxes[0].setStyleSheet("ChannelBox{border: 3px solid}")
            self.selected.emit(0)
        self.new_cmap.emit(try_cast_colormap(self.channel_cmaps.get(name, "gray")), i)

    def channel_visibility(self, visible: bool, channel: int) -> None:
        """If the current channel is made invisible, choose a different one."""
        if self.current_channel == channel and not visible:
            channel_to_set = abs(channel - 1)
            for idx, channel in enumerate(self.boxes):
                if channel.show_channel.isChecked():
                    channel_to_set = idx
                    break
            while channel_to_set > len(self.boxes) - 1:
                channel_to_set -= 1
            self._handle_channel_choice(self.boxes[channel_to_set].channel)

    def _handle_channel_choice(self, channel: str) -> None:
        """Channel was chosen, adjust GUI and send signal."""
        if len(self.boxes) == 1:
            return
        for idx, channel_box in enumerate(self.boxes):
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
        print(self.channel_cmaps)

    def restore_data(self) -> None:
        """Restore data from previous session."""
        self.qt_settings = QtCore.QSettings("pymmcore_widgets", self.__class__.__name__)
        self.cmap_names = self.qt_settings.value(
            "cmap_names", ["gray", "magenta", "cyan"]
        )
        self.channel_cmaps = self.qt_settings.value("channel_cmaps", {})
        print(self.channel_cmaps)


class ChannelBox(QtWidgets.QFrame):
    """Box that represents a channel and gives some way of interaction."""

    clicked = QtCore.Signal(str)

    def __init__(
        self,
        channel: Channel,
        cmaps: list | None = None,
    ) -> None:
        super().__init__()
        self.channel = channel.config
        self.setLayout(QtWidgets.QGridLayout())
        self.show_channel = QtWidgets.QCheckBox(channel.config)
        self.show_channel.setChecked(True)
        self.show_channel.setStyleSheet("font-weight: bold")
        self.layout().addWidget(self.show_channel, 0, 0)
        self.color_choice = QColormapComboBox(allow_user_colormaps=True)

        if cmaps is None:
            cmaps = CMAPS
        for my_cmap in cmaps:
            self.color_choice.addColormap(my_cmap)

        self.layout().addWidget(self.color_choice, 0, 1)
        self.autoscale_chbx = QtWidgets.QCheckBox("Auto")
        self.autoscale_chbx.setChecked(False)
        self.layout().addWidget(self.autoscale_chbx, 0, 2)
        # self.histogram = HistPlot()
        # self.layout().addWidget(self.histogram, 1, 0, 1, 3)
        self.slider = QRangeSlider(QtCore.Qt.Horizontal)
        self.layout().addWidget(self.slider, 2, 0, 1, 3)
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
                    self.count() - 1, QtGui.QColor(a_color), QtCore.Qt.BackgroundRole
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
                self._currentColor if self._currentColor else QtCore.Qt.white
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
    w = ChannelBox(Channel(config="empty"), cmaps=CMAPS)
    w.show()

    sys.exit(app.exec_())
