from typing import List, Optional

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QAbstractSpinBox,
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
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon


class MDAChannelTable(QGroupBox):
    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

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
        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_ch_button)
        layout.addWidget(self.remove_ch_button)
        layout.addWidget(self.clear_ch_button)
        layout.addItem(spacer)

        group_layout.addWidget(wdg, 0, 1)


class MDATimeWidget(QGroupBox):
    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

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


class MDAStackWidget(QGroupBox):
    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.setTitle("Z Stack")

        self.setCheckable(True)
        self.setChecked(False)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # tab
        self.z_tabWidget = QTabWidget()
        z_tab_layout = QVBoxLayout()
        z_tab_layout.setSpacing(0)
        z_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.z_tabWidget.setLayout(z_tab_layout)
        group_layout.addWidget(self.z_tabWidget)

        # top bottom
        tb = QWidget()
        tb_layout = QGridLayout()
        tb_layout.setContentsMargins(10, 10, 10, 10)
        tb.setLayout(tb_layout)

        self.set_top_button = QPushButton(text="Set Top")
        self.set_bottom_button = QPushButton(text="Set Bottom")

        lbl_range_tb = QLabel(text="Range (µm):")
        lbl_range_tb.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.z_top_doubleSpinBox = QDoubleSpinBox()
        self.z_top_doubleSpinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.z_top_doubleSpinBox.setMinimum(0.0)
        self.z_top_doubleSpinBox.setMaximum(100000)
        self.z_top_doubleSpinBox.setDecimals(2)

        self.z_bottom_doubleSpinBox = QDoubleSpinBox()
        self.z_bottom_doubleSpinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.z_bottom_doubleSpinBox.setMinimum(0.0)
        self.z_bottom_doubleSpinBox.setMaximum(100000)
        self.z_bottom_doubleSpinBox.setDecimals(2)

        self.z_range_topbottom_doubleSpinBox = QDoubleSpinBox()
        self.z_range_topbottom_doubleSpinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.z_range_topbottom_doubleSpinBox.setMaximum(10000000)
        self.z_range_topbottom_doubleSpinBox.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.z_range_topbottom_doubleSpinBox.setReadOnly(True)

        tb_layout.addWidget(self.set_top_button, 0, 0)
        tb_layout.addWidget(self.z_top_doubleSpinBox, 1, 0)
        tb_layout.addWidget(self.set_bottom_button, 0, 1)
        tb_layout.addWidget(self.z_bottom_doubleSpinBox, 1, 1)
        tb_layout.addWidget(lbl_range_tb, 0, 2)
        tb_layout.addWidget(self.z_range_topbottom_doubleSpinBox, 1, 2)

        self.z_tabWidget.addTab(tb, "TopBottom")

        # range around
        ra = QWidget()
        ra_layout = QHBoxLayout()
        ra_layout.setSpacing(10)
        ra_layout.setContentsMargins(10, 10, 10, 10)
        ra.setLayout(ra_layout)

        lbl_range_ra = QLabel(text="Range (µm):")
        lbl_range_ra.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self.zrange_spinBox = QSpinBox()
        self.zrange_spinBox.setValue(5)
        self.zrange_spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zrange_spinBox.setMaximum(100000)

        self.range_around_label = QLabel(text="-2.5 µm <- z -> +2.5 µm")
        self.range_around_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        ra_layout.addWidget(lbl_range_ra)
        ra_layout.addWidget(self.zrange_spinBox)
        ra_layout.addWidget(self.range_around_label)

        self.z_tabWidget.addTab(ra, "RangeAround")

        # above below wdg
        ab = QWidget()
        ab_layout = QGridLayout()
        ab_layout.setContentsMargins(10, 0, 10, 15)
        ab.setLayout(ab_layout)

        lbl_above = QLabel(text="Above (µm):")
        lbl_above.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.above_doubleSpinBox = QDoubleSpinBox()
        self.above_doubleSpinBox.setValue(2)
        self.above_doubleSpinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.above_doubleSpinBox.setMinimum(0.05)
        self.above_doubleSpinBox.setMaximum(10000)
        self.above_doubleSpinBox.setSingleStep(0.5)
        self.above_doubleSpinBox.setDecimals(2)

        lbl_below = QLabel(text="Below (µm):")
        lbl_below.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.below_doubleSpinBox = QDoubleSpinBox()
        self.below_doubleSpinBox.setValue(2)
        self.below_doubleSpinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.below_doubleSpinBox.setMinimum(0.05)
        self.below_doubleSpinBox.setMaximum(10000)
        self.below_doubleSpinBox.setSingleStep(0.5)
        self.below_doubleSpinBox.setDecimals(2)

        lbl_range = QLabel(text="Range (µm):")
        lbl_range.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.z_range_abovebelow_doubleSpinBox = QDoubleSpinBox()
        self.z_range_abovebelow_doubleSpinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.z_range_abovebelow_doubleSpinBox.setMaximum(10000000)
        self.z_range_abovebelow_doubleSpinBox.setButtonSymbols(
            QAbstractSpinBox.ButtonSymbols.NoButtons
        )
        self.z_range_abovebelow_doubleSpinBox.setReadOnly(True)

        ab_layout.addWidget(lbl_above, 0, 0)
        ab_layout.addWidget(self.above_doubleSpinBox, 1, 0)
        ab_layout.addWidget(lbl_below, 0, 1)
        ab_layout.addWidget(self.below_doubleSpinBox, 1, 1)
        ab_layout.addWidget(lbl_range, 0, 2)
        ab_layout.addWidget(self.z_range_abovebelow_doubleSpinBox, 1, 2)

        self.z_tabWidget.addTab(ab, "AboveBelow")

        # step size wdg
        step_wdg = QWidget()
        step_wdg_layout = QHBoxLayout()
        step_wdg_layout.setSpacing(15)
        step_wdg_layout.setContentsMargins(0, 10, 0, 0)
        step_wdg.setLayout(step_wdg_layout)

        s = QWidget()
        s_layout = QHBoxLayout()
        s_layout.setSpacing(0)
        s_layout.setContentsMargins(0, 0, 0, 0)
        s.setLayout(s_layout)
        lbl = QLabel(text="Step Size (µm):")
        lbl.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.step_size_doubleSpinBox = QDoubleSpinBox()
        self.step_size_doubleSpinBox.setValue(1)
        self.step_size_doubleSpinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.step_size_doubleSpinBox.setMinimum(0.05)
        self.step_size_doubleSpinBox.setMaximum(10000)
        self.step_size_doubleSpinBox.setSingleStep(0.5)
        self.step_size_doubleSpinBox.setDecimals(2)
        s_layout.addWidget(lbl)
        s_layout.addWidget(self.step_size_doubleSpinBox)

        self.n_images_label = QLabel(text="Number of Images:")

        step_wdg_layout.addWidget(s)
        step_wdg_layout.addWidget(self.n_images_label)
        group_layout.addWidget(step_wdg)


class MDAPositionTable(QGroupBox):
    def __init__(self, header: List[str], *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self.setTitle("Stage Positions")

        self.setCheckable(True)
        self.setChecked(False)
        # self.setMinimumHeight(230)

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
        self.stage_tableWidget.setHorizontalHeaderLabels(header)
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


class MDAControlButtons(QWidget):
    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

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


class MDATimeLabel(QWidget):
    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
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
