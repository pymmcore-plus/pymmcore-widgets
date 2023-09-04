from __future__ import annotations
from typing import Optional

from qtpy import QtCore, QtGui, QtWidgets
from qtpy.QtGui import QMouseEvent
from superqt import QRangeSlider
from useq import Channel

try:
    from vispy import color
except ImportError as e:
    raise ImportError(
        "vispy is required for Channel_row. "
        "Please run `pip install pymmcore-widgets[image]`"
    ) from e


CMAPS = [
    color.Colormap([[0, 0, 0], [1, 1, 0]]),
    color.Colormap([[0, 0, 0], [1, 0, 1]]),
    color.Colormap([[0, 0, 0], [0, 1, 1]]),
    color.Colormap([[0, 0, 0], [1, 0, 0]]),
    color.Colormap([[0, 0, 0], [0, 1, 0]]),
    color.Colormap([[0, 0, 0], [0, 0, 1]]),
]


class ChannelRow(QtWidgets.QWidget):
    """Row of channel boxes."""

    visible = QtCore.Signal(bool, int)
    autoscale = QtCore.Signal(bool, int)
    new_clims = QtCore.Signal(tuple, int)
    new_cmap = QtCore.Signal(QtGui.QColor, int)
    selected = QtCore.Signal(int)

    def __init__(
        self,
        num_channels: int = 5,
        # https://cmap-docs.readthedocs.io/en/latest/
        cmaps: list[
            color.Colormap
        ] = CMAPS,  # TODO: go with cmap to avoid vispy dependency
    ) -> None:
        super().__init__()
        self.cmaps = cmaps

        self.setLayout(QtWidgets.QHBoxLayout())
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        self.boxes = []
        # TODO: Ideally we would know beforehand how many of these we need.
        for i in range(num_channels):
            channel_box = ChannelBox(Channel(config="empty"), cmaps=self.cmaps)
            channel_box.show_channel.stateChanged.connect(
                lambda state, i=i: self.visible.emit(state, i)
            )
            channel_box.autoscale_chbx.stateChanged.connect(
                lambda state, i=i: self.autoscale.emit(state, i)
            )
            channel_box.slider.sliderMoved.connect(
                lambda values, i=i: self.new_clims.emit(values, i)
            )
            channel_box.color_choice.selectedColor.connect(
                lambda color, i=i: self.new_cmap.emit(color, i)
            )
            channel_box.color_choice.setColor(i)
            channel_box.clicked.connect(self._handle_channel_choice)
            channel_box.mousePressEvent(None)
            channel_box.hide()
            self.current_channel = i
            self.boxes.append(channel_box)
            self.layout().addWidget(channel_box)

    def box_visibility(self, i: int, name: Optional[str] = None) -> None:
        self.boxes[i].visible = True
        self.boxes[i].show()
        self.boxes[i].autoscale_chbx.setChecked(True)
        self.boxes[i].show_channel.setText(name)
        self.boxes[i].channel = name
        self.boxes[i].mousePressEvent(None)

    def _handle_channel_choice(self, channel: str) -> None:
        for idx, channel_box in enumerate(self.boxes):
            if channel_box.channel != channel:
                channel_box.setStyleSheet("ChannelBox{border: 1px solid}")
            else:
                self.selected.emit(idx)


class ChannelBox(QtWidgets.QFrame):
    """Box that represents a channel and gives some way of interaction."""

    clicked = QtCore.Signal(str)

    def __init__(
        self,
        channel: Channel,
        cmaps: Optional[list] = None,
    ) -> None:
        super().__init__()
        self.channel = channel.config
        self.setLayout(QtWidgets.QGridLayout())
        self.show_channel = QtWidgets.QCheckBox(channel.config)
        self.show_channel.setChecked(True)
        self.show_channel.setStyleSheet("font-weight: bold")
        self.layout().addWidget(self.show_channel, 0, 0)
        self.color_choice = QColorComboBox()

        if cmaps is None:
            cmaps = CMAPS
        for cmap in cmaps:
            self.color_choice.addColors([list(cmap.colors[-1].RGB[0])])

        # self.color_choice.setStyle(QtWidgets.QStyleFactory.create('fusion'))
        self.layout().addWidget(self.color_choice, 0, 1)
        self.autoscale_chbx = QtWidgets.QCheckBox("Auto")
        self.autoscale_chbx.setChecked(False)
        self.layout().addWidget(self.autoscale_chbx, 0, 2)
        self.slider = QRangeSlider(QtCore.Qt.Horizontal)
        self.layout().addWidget(self.slider, 1, 0, 1, 3)
        self.setStyleSheet("ChannelBox{border: 1px solid}")

    def mousePressEvent(self, event: QMouseEvent | None) -> None:
        self.setStyleSheet("ChannelBox{border: 3px solid}")
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

    from vispy import color

    CMAPS = [
        color.Colormap([[0, 0, 0], [1, 1, 0]]),
        color.Colormap([[0, 0, 0], [1, 0, 1]]),
        color.Colormap([[0, 0, 0], [0, 1, 1]]),
        color.Colormap([[0, 0, 0], [1, 0, 0]]),
        color.Colormap([[0, 0, 0], [0, 1, 0]]),
        color.Colormap([[0, 0, 0], [0, 0, 1]]),
    ]

    app = QtWidgets.QApplication(sys.argv)
    w = ChannelBox(Channel(config="empty"), cmaps=CMAPS)
    w.show()

    sys.exit(app.exec_())
