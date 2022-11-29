from __future__ import annotations

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon


class _MDAChannelTable(QGroupBox):

    valueUpdated = Signal()

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self._create_ch_gui()

    def _create_ch_gui(self) -> None:

        self.setTitle("Channels")

        group_layout = QGridLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # channel table
        self.channel_tableWidget = QTableWidget()
        hdr = self.channel_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self.channel_tableWidget.verticalHeader().setVisible(False)
        self.channel_tableWidget.setTabKeyNavigation(True)
        self.channel_tableWidget.setColumnCount(2)
        self.channel_tableWidget.setRowCount(0)
        self.channel_tableWidget.setHorizontalHeaderLabels(
            ["Channel", "Exposure Time (ms)"]
        )
        group_layout.addWidget(self.channel_tableWidget, 0, 0)

        # buttons
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        min_size = 100
        self.add_ch_button = QPushButton(text="Add")
        self.add_ch_button.setMinimumWidth(min_size)
        self.add_ch_button.setSizePolicy(btn_sizepolicy)
        self.remove_ch_button = QPushButton(text="Remove")
        self.remove_ch_button.setMinimumWidth(min_size)
        self.remove_ch_button.setSizePolicy(btn_sizepolicy)
        self.clear_ch_button = QPushButton(text="Clear")
        self.clear_ch_button.setMinimumWidth(min_size)
        self.clear_ch_button.setSizePolicy(btn_sizepolicy)

        self.add_ch_button.clicked.connect(self._add_channel)
        self.remove_ch_button.clicked.connect(self._remove_channel)
        self.clear_ch_button.clicked.connect(self._clear_channel)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_ch_button)
        layout.addWidget(self.remove_ch_button)
        layout.addWidget(self.clear_ch_button)
        layout.addItem(spacer)

        group_layout.addWidget(wdg, 0, 1)

    def _add_channel(self) -> bool:
        """Add, remove or clear channel table.  Return True if anyting was changed."""
        if len(self._mmc.getLoadedDevices()) <= 1:
            return False

        channel_group = self._mmc.getChannelGroup()
        if not channel_group:
            return False

        idx = self.channel_tableWidget.rowCount()
        self.channel_tableWidget.insertRow(idx)

        # create a combo_box for channels in the table
        channel_comboBox = QComboBox(self)
        channel_exp_spinBox = QSpinBox(self)
        channel_exp_spinBox.setRange(0, 10000)
        channel_exp_spinBox.setValue(100)
        channel_exp_spinBox.valueChanged.connect(self._on_exp_changed)

        if channel_group := self._mmc.getChannelGroup():
            channel_list = list(self._mmc.getAvailableConfigs(channel_group))
            channel_comboBox.addItems(channel_list)

        self.channel_tableWidget.setCellWidget(idx, 0, channel_comboBox)
        self.channel_tableWidget.setCellWidget(idx, 1, channel_exp_spinBox)

        self.valueUpdated.emit()

        return True

    def _on_exp_changed(self) -> None:
        self.valueUpdated.emit()

    def _remove_channel(self) -> None:
        # remove selected position
        rows = {r.row() for r in self.channel_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.channel_tableWidget.removeRow(idx)

        self.valueUpdated.emit()

    def _clear_channel(self) -> None:
        # clear all positions
        self.channel_tableWidget.clearContents()
        self.channel_tableWidget.setRowCount(0)

        self.valueUpdated.emit()


class _MDATimeWidget(QGroupBox):

    valueUpdated = Signal()

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._create_time_gui()

        self.toggled.connect(self._on_value_changed)
        self.interval_spinBox.valueChanged.connect(self._on_value_changed)
        self.timepoints_spinBox.valueChanged.connect(self._on_value_changed)
        self.time_comboBox.currentIndexChanged.connect(self._on_value_changed)

    def _create_time_gui(self) -> None:

        self.setTitle("Time")

        self.setCheckable(True)
        self.setChecked(False)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        group_layout = QGridLayout()
        group_layout.setSpacing(5)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # Timepoints
        wdg = QWidget()
        wdg_lay = QHBoxLayout()
        wdg_lay.setSpacing(5)
        wdg_lay.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_lay)
        lbl = QLabel(text="Timepoints:")
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.timepoints_spinBox = QSpinBox()
        self.timepoints_spinBox.setMinimum(1)
        self.timepoints_spinBox.setMaximum(1000000)
        self.timepoints_spinBox.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        )
        self.timepoints_spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wdg_lay.addWidget(lbl)
        wdg_lay.addWidget(self.timepoints_spinBox)
        group_layout.addWidget(wdg, 0, 0)

        # Interval
        wdg1 = QWidget()
        wdg1_lay = QHBoxLayout()
        wdg1_lay.setSpacing(5)
        wdg1_lay.setContentsMargins(0, 0, 0, 0)
        wdg1.setLayout(wdg1_lay)
        lbl1 = QLabel(text="Interval:  ")
        lbl1.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.interval_spinBox = QDoubleSpinBox()
        self.interval_spinBox.setValue(1.0)
        self.interval_spinBox.setMinimum(0)
        self.interval_spinBox.setMaximum(100000)
        self.interval_spinBox.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.interval_spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        wdg1_lay.addWidget(lbl1)
        wdg1_lay.addWidget(self.interval_spinBox)
        group_layout.addWidget(wdg1)

        self.time_comboBox = QComboBox()
        self.time_comboBox.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.time_comboBox.addItems(["ms", "sec", "min", "hours"])
        self.time_comboBox.setCurrentText("sec")
        wdg1_lay.addWidget(self.time_comboBox)
        group_layout.addWidget(wdg1, 0, 1)

        wdg2 = QWidget()
        wdg2_lay = QHBoxLayout()
        wdg2_lay.setSpacing(5)
        wdg2_lay.setContentsMargins(0, 0, 0, 0)
        wdg2.setLayout(wdg2_lay)
        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._icon_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        wdg2_lay.addWidget(self._icon_lbl)
        self._time_lbl = QLabel()
        self._time_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._time_lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        wdg2_lay.addWidget(self._time_lbl)
        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        wdg2_lay.addItem(spacer)
        group_layout.addWidget(wdg2, 1, 0, 1, 2)

        self._time_lbl.hide()
        self._icon_lbl.hide()

    def _on_value_changed(self) -> None:
        self.valueUpdated.emit()


class _MDAPositionTable(QGroupBox):
    def __init__(self, header: list[str], *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self.header = header

        self._create_pos_gui()

    def _create_pos_gui(self) -> None:

        self.setTitle("Stage Positions")

        self.setCheckable(True)
        self.setChecked(False)

        group_layout = QHBoxLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # table
        self.stage_tableWidget = QTableWidget()
        self.stage_tableWidget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        hdr = self.stage_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self.stage_tableWidget.verticalHeader().setVisible(False)
        self.stage_tableWidget.setTabKeyNavigation(True)
        self.stage_tableWidget.setColumnCount(4)
        self.stage_tableWidget.setRowCount(0)
        self.stage_tableWidget.setHorizontalHeaderLabels(self.header)
        group_layout.addWidget(self.stage_tableWidget)

        # buttons
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        min_size = 100
        self.add_pos_button = QPushButton(text="Add")
        self.add_pos_button.setMinimumWidth(min_size)
        self.add_pos_button.setSizePolicy(btn_sizepolicy)
        self.remove_pos_button = QPushButton(text="Remove")
        self.remove_pos_button.setMinimumWidth(min_size)
        self.remove_pos_button.setSizePolicy(btn_sizepolicy)
        self.clear_pos_button = QPushButton(text="Clear")
        self.clear_pos_button.setMinimumWidth(min_size)
        self.clear_pos_button.setSizePolicy(btn_sizepolicy)
        self.grid_button = QPushButton(text="Grid")
        self.grid_button.setMinimumWidth(min_size)
        self.grid_button.setSizePolicy(btn_sizepolicy)
        self.go = QPushButton(text="Go")
        self.go.clicked.connect(self._move_to_position)
        self.go.setMinimumWidth(min_size)
        self.go.setSizePolicy(btn_sizepolicy)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_pos_button)
        layout.addWidget(self.remove_pos_button)
        layout.addWidget(self.clear_pos_button)
        layout.addWidget(self.grid_button)
        layout.addWidget(self.go)
        layout.addItem(spacer)

        group_layout.addWidget(wdg)

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self.stage_tableWidget.currentRow()
        x_val = self.stage_tableWidget.item(curr_row, 1).text()
        y_val = self.stage_tableWidget.item(curr_row, 2).text()
        z_val = self.stage_tableWidget.item(curr_row, 3).text()
        self._mmc.setXYPosition(float(x_val), float(y_val))
        self._mmc.setPosition(self._mmc.getFocusDevice(), float(z_val))


class _MDAControlButtons(QWidget):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)

        self._create_btns_gui()

    def _create_btns_gui(self) -> None:

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        wdg_layout = QHBoxLayout()
        wdg_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(10, 5, 10, 10)
        self.setLayout(wdg_layout)

        acq_wdg = QWidget()
        acq_wdg_layout = QHBoxLayout()
        acq_wdg_layout.setSpacing(0)
        acq_wdg_layout.setContentsMargins(0, 0, 0, 0)
        acq_wdg.setLayout(acq_wdg_layout)
        acquisition_order_label = QLabel(text="Acquisition Order:")
        acquisition_order_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.acquisition_order_comboBox = QComboBox()
        self.acquisition_order_comboBox.setMinimumWidth(100)
        self.acquisition_order_comboBox.addItems(["tpcz", "tpzc", "ptzc", "ptcz"])
        acq_wdg_layout.addWidget(acquisition_order_label)
        acq_wdg_layout.addWidget(self.acquisition_order_comboBox)

        btn_sizepolicy = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        min_width = 130
        icon_size = 40
        self.run_button = QPushButton(text="Run")
        self.run_button.setEnabled(False)
        self.run_button.setMinimumWidth(min_width)
        self.run_button.setStyleSheet("QPushButton { text-align: center; }")
        self.run_button.setSizePolicy(btn_sizepolicy)
        self.run_button.setIcon(icon(MDI6.play_circle_outline, color=(0, 255, 0)))
        self.run_button.setIconSize(QSize(icon_size, icon_size))
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet("QPushButton { text-align: center; }")
        self.pause_button.setSizePolicy(btn_sizepolicy)
        self.pause_button.setIcon(icon(MDI6.pause_circle_outline, color="green"))
        self.pause_button.setIconSize(QSize(icon_size, icon_size))
        self.pause_button.hide()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("QPushButton { text-align: center; }")
        self.cancel_button.setSizePolicy(btn_sizepolicy)
        self.cancel_button.setIcon(icon(MDI6.stop_circle_outline, color="magenta"))
        self.cancel_button.setIconSize(QSize(icon_size, icon_size))
        self.cancel_button.hide()

        spacer = QSpacerItem(
            10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        wdg_layout.addWidget(acq_wdg)
        wdg_layout.addItem(spacer)
        wdg_layout.addWidget(self.run_button)
        wdg_layout.addWidget(self.pause_button)
        wdg_layout.addWidget(self.cancel_button)

    def _on_mda_paused(self, paused: bool) -> None:
        self.pause_button.setText("Resume" if paused else "Pause")


class _MDATimeLabel(QWidget):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        wdg_lay = QHBoxLayout()
        wdg_lay.setSpacing(5)
        wdg_lay.setContentsMargins(10, 5, 10, 5)
        wdg_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(wdg_lay)

        self._total_time_lbl = QLabel()
        self._total_time_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._total_time_lbl.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        wdg_lay.addWidget(self._total_time_lbl)
