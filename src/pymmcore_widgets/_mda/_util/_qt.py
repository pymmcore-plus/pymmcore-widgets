from superqt import QRangeSlider
from qtpy import QtCore, QtWidgets, QtGui
from useq import Channel

class ChannelBox(QtWidgets.QFrame):
    """Box that represents a channel and gives some way of interaction."""

    clicked = QtCore.Signal(str)

    def __init__(self, channel: Channel, CMAPS:list = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.channel = channel.config
        self.setLayout(QtWidgets.QGridLayout())
        self.show_channel = QtWidgets.QCheckBox(channel.config)
        self.show_channel.setChecked(True)
        self.show_channel.setStyleSheet("font-weight: bold")
        self.layout().addWidget(self.show_channel, 0, 0)
        self.color_choice = QColorComboBox()

        CMAPS = CMAPS or ["grays", "reds", "greens"]
        for cmap in CMAPS:
            self.color_choice.addColors([list(cmap.colors[-1].RGB[0])])

        # self.color_choice.setStyle(QtWidgets.QStyleFactory.create('fusion'))
        self.layout().addWidget(self.color_choice, 0, 1)
        self.autoscale = QtWidgets.QCheckBox("Auto")
        self.autoscale.setChecked(False)
        self.layout().addWidget(self.autoscale, 0, 2)
        self.slider = QRangeSlider(QtCore.Qt.Horizontal)
        self.layout().addWidget(self.slider, 1, 0, 1, 3)
        self.setStyleSheet("ChannelBox{border: 1px solid}")

    def mousePressEvent(self, event):
        self.setStyleSheet("ChannelBox{border: 3px solid}")
        self.clicked.emit(self.channel)


class QColorComboBox(QtWidgets.QComboBox):
    ''' A drop down menu for selecting colors '''
    #Adapted from https://stackoverflow.com/questions/64497029/a-color-drop-down-selector-for-pyqt5

    # signal emitted if a color has been selected
    selectedColor = QtCore.Signal(QtGui.QColor)

    def __init__(self, parent = None, enableUserDefColors = False):
        ''' if the user shall not be able to define colors on its own, then set enableUserDefColors=False '''
        # init QComboBox
        super(QColorComboBox, self).__init__(parent)

        # enable the line edit to display the currently selected color
        self.setEditable(True)
        # read only so that there is no blinking cursor or sth editable
        self.lineEdit().setReadOnly(True)
        # self.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        # text that shall be displayed for the option to pop up the QColorDialog for user defined colors
        self._userDefEntryText = 'New'
        # add the option for user defined colors
        if (enableUserDefColors):
            self.addItem(self._userDefEntryText)

        self._currentColor = None

        self.activated.connect(self._color_selected)
        # self.setStyleSheet("QComboBox:drop-down {image: none; background: red; border: 1px grey;}")


    def addColors(self, colors):
        ''' Adds colors to the QComboBox '''
        for a_color in colors:
            # if input is not a QColor, try to make it one
            if (not (isinstance(a_color, QtGui.QColor))):
                try:
                    a_color = QtGui.QColor(a_color)
                except TypeError:
                    if max(a_color) < 2:
                        a_color = [int(x*255) for x in a_color]
                    a_color = QtGui.QColor(*a_color)

            # avoid dublicates
            if (self.findData(a_color) == -1):
                # add the new color and set the background color of that item
                self.addItem('', userData = a_color)
                self.setItemData(self.count()-1, QtGui.QColor(a_color), QtCore.Qt.BackgroundRole)

    def addColor(self, color):
        ''' Adds the color to the QComboBox '''
        self.addColors([color])

    def setColor(self, color):
        ''' Adds the color to the QComboBox and selects it'''
        if isinstance(color, int):
            self.setCurrentIndex(color)
            self._currentColor = self.itemData(color)
            self.lineEdit().setStyleSheet("background-color: "+self._currentColor.name())
        else:
            self._color_selected(self.findData(color), False)

    def getCurrentColor(self):
        ''' Returns the currently selected QColor
            Returns None if non has been selected yet
        '''
        return self._currentColor

    def _color_selected(self, index, emitSignal = True):
        ''' Processes the selection of the QComboBox '''
        # if a color is selected, emit the selectedColor signal
        if (self.itemText(index) == ''):
            self._currentColor = self.itemData(index)
            if (emitSignal):
                self.selectedColor.emit(self._currentColor)

        # if the user wants to define a custom color
        elif(self.itemText(index) == self._userDefEntryText):
            # get the user defined color
            new_color = QtWidgets.QColorDialog.getColor(self._currentColor
                                                        if self._currentColor else QtCore.Qt.white)
            if (new_color.isValid()):
                # add the color to the QComboBox and emit the signal
                self.addColor(new_color)
                self._currentColor = new_color
                if (emitSignal):
                    self.selectedColor.emit(self._currentColor)

        # make sure that current color is displayed
        if (self._currentColor):
            self.setCurrentIndex(self.findData(self._currentColor))
            self.lineEdit().setStyleSheet("background-color: "+self._currentColor.name())


class QLabeledSlider(QtWidgets.QWidget):
    """Slider that shows name of the axis and current value."""
    valueChanged = QtCore.Signal([int], [int, str])
    sliderPressed = QtCore.Signal()
    sliderMoved = QtCore.Signal()
    sliderReleased = QtCore.Signal()

    def __init__(self, name: str = "", orientation=QtCore.Qt.Horizontal , *args, **kwargs):
        # super().__init__(self, *args, **kwargs)
        super().__init__()
        self.name = name

        self.label = QtWidgets.QLabel()
        self.label.setText(name.upper())
        self.label.setAlignment(QtCore.Qt.AlignRight)
        self.label.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)
        self.slider = QtWidgets.QSlider(orientation)
        for function in ["blockSignals", "setTickInterval","setTickPosition", "tickInterval",
                         "tickPosition", "minimum", "maximum", "setTracking", "value"]:
            func = getattr(self.slider, function)
            setattr(self, function, func)

        self.current_value = QtWidgets.QLabel()
        self.current_value.setText("0")
        self.current_value.setAlignment(QtCore.Qt.AlignLeft)
        self.current_value.setSizePolicy(QtWidgets.QSizePolicy.Fixed, QtWidgets.QSizePolicy.Fixed)

        self.play_btn = QtWidgets.QPushButton("▶")
        self.play_btn.setStyleSheet("QPushButton {padding: 2px;}")
        self.play_btn.setFont(QtGui.QFont("Times", 14))
        self.play_btn.clicked.connect(self.play_clk)

        # self.layout = QtWidgets.QHBoxLayout(self)
        self.setLayout(QtWidgets.QHBoxLayout())
        self.layout().addWidget(self.label)
        self.layout().addWidget(self.play_btn)
        self.layout().addWidget(self.slider)
        self.layout().addWidget(self.current_value)
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)

        self.slider.valueChanged.connect(self.on_drag_timer)
        self.slider.sliderPressed.connect(self.sliderPressed)
        self.slider.sliderMoved.connect(self.sliderMoved)
        self.slider.sliderReleased.connect(self.sliderReleased)
        self.playing = False


        self.play_timer = QtCore.QTimer(interval=10)
        self.play_timer.timeout.connect(self.on_play_timer)

        self.drag_timer = QtCore.QTimer(interval=10)
        self.drag_timer.timeout.connect(self.on_drag_timer)

    def _start_play_timer(self, playing):
        if playing:
            self.play_timer.start(0.01)
        else:
            self.play_timer.stop()

    def on_play_timer(self, _=None):
        value = self.value() + 1
        value = value % self.maximum()
        self.setValue(value)

    def setMaximum(self, maximum: int):
        self.current_value.setText(f"{str(self.value())}/{str(maximum)}")
        self.slider.setMaximum(maximum)

    def setRange(self, minimum, maximum):
        self.current_value.setText(f"{str(self.value())}/{str(maximum)}")
        self.slider.setMaximum(maximum)

    def setValue(self, value):
        self.current_value.setText(f"{str(value)}/{str(self.maximum())}")
        self.slider.setValue(value)

    def play_clk(self):
        if self.playing:
            self.play_btn.setText("▶")
            self.play_timer.stop()
        else:
            self.play_btn.setText("■")
            self.play_timer.start()
        self.playing = not self.playing

    def on_slider_press(self):
        self.slider.valueChanged.disconnect(self.on_drag_timer)
        self.drag_timer.start()

    def on_slider_release(self):
        self.drag_timer.stop()
        self.slider.valueChanged.connect(self.on_drag_timer)

    def on_drag_timer(self):
        self.valueChanged[int, str].emit(self.value(), self.name)

class LabeledVisibilitySlider(QLabeledSlider):
    def __init__(self, name, *args, **kwargs):
        super().__init__(name, *args, **kwargs)

    def _visibility(self, settings):
        if not settings['index'] == self.name:
            return
        if settings['show']:
            self.show()
        else:
            self.hide()
        self.setRange(0, settings['max'])

if __name__ == "__main__":
    import sys
    from vispy import color
    CMAPS = [color.Colormap([[0, 0, 0], [1, 1, 0]]), color.Colormap([[0, 0, 0], [1, 0, 1]]),
             color.Colormap([[0, 0, 0], [0, 1, 1]]), color.Colormap([[0, 0, 0], [1, 0, 0]]),
             color.Colormap([[0, 0, 0], [0, 1, 0]]), color.Colormap([[0, 0, 0], [0, 0, 1]])]

    app = QtWidgets.QApplication(sys.argv)
    w = ChannelBox(Channel(config="empty"), CMAPS=CMAPS)
    w.show()
    s = QLabeledSlider("test")
    s.show()
    sys.exit(app.exec_())