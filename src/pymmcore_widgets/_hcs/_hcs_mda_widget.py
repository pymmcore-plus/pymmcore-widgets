from pathlib import Path
from typing import Optional

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
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
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible
from superqt.fonticon import icon

from .._util import _select_output_unit, _time_in_sec, guess_channel_group

PLATE_DATABASE = Path(__file__).parent / "_well_plate.yaml"
AlignCenter = Qt.AlignmentFlag.AlignCenter
LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class MDAWidget(QWidget):
    """Widget to select channels, z-stack, time and positions."""

    def __init__(self, parent: QWidget, *, mmcore: Optional[CMMCorePlus] = None):
        super().__init__(parent)
        self._tot_time_label_parent = parent
        self._mmc = mmcore or CMMCorePlus.instance()

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        z_selector = self._create_z_stage_selector()
        self.layout().addWidget(z_selector)
        pos = self._create_positions_list_wdg()
        self.layout().addWidget(pos)
        ch = self._create_channel_group()
        self.layout().addWidget(ch)

        mda = self._create_mda_options()
        self.layout().addWidget(mda)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        # toggle connect
        self.time_groupBox.toggled.connect(self._calculate_total_time)
        self.interval_spinBox.valueChanged.connect(self._calculate_total_time)
        self.timepoints_spinBox.valueChanged.connect(self._calculate_total_time)
        self.stack_groupBox.toggled.connect(self._calculate_total_time)
        self.time_comboBox.currentIndexChanged.connect(self._calculate_total_time)

        self._on_sys_cfg_loaded()

    def _create_z_stage_selector(self) -> QGroupBox:

        z_wdg = QGroupBox(title="Z Stage Selector")
        z_layout = QHBoxLayout()
        z_layout.setSpacing(0)
        z_layout.setContentsMargins(10, 10, 10, 10)
        z_wdg.setLayout(z_layout)
        self.z_combo = QComboBox()
        self.z_combo.currentTextChanged.connect(self._set_focus_device)
        self._update_stage_combo()
        z_layout.addWidget(self.z_combo)

        return z_wdg

    def _create_positions_list_wdg(self) -> QGroupBox:

        group = QGroupBox(title="Positions")
        group.setMinimumHeight(300)
        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(group_layout)

        wdg = QWidget()
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        self.position_list_button = QPushButton(text="Create Position List")
        self.remove_position_button = QPushButton(text="Remove Position")
        self.remove_position_button.clicked.connect(self._remove_position)
        self.clear_positions_button = QPushButton(text="Clear List")
        self.clear_positions_button.clicked.connect(self._clear_positions)
        wdg_layout.addWidget(self.position_list_button)
        wdg_layout.addWidget(self.remove_position_button)
        wdg_layout.addWidget(self.clear_positions_button)
        group_layout.addWidget(wdg)

        # table
        self.stage_tableWidget = QTableWidget()
        self.stage_tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.stage_tableWidget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.stage_tableWidget.setMinimumHeight(110)
        hdr = self.stage_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        self.stage_tableWidget.verticalHeader().setVisible(True)
        self.stage_tableWidget.setTabKeyNavigation(True)
        self.stage_tableWidget.setColumnCount(4)
        self.stage_tableWidget.setRowCount(0)
        self.stage_tableWidget.setHorizontalHeaderLabels(["Well", "X", "Y", "Z"])
        group_layout.addWidget(self.stage_tableWidget)
        self.stage_tableWidget.cellDoubleClicked.connect(self._move_to_position)
        self.stage_tableWidget.model().rowsInserted.connect(self._calculate_total_time)

        assign_z_wdg = QWidget()
        assign_z_wdg_layout = QHBoxLayout()
        assign_z_wdg_layout.setSpacing(5)
        assign_z_wdg_layout.setContentsMargins(0, 0, 0, 0)
        assign_z_wdg.setLayout(assign_z_wdg_layout)
        lbl = QLabel(text="Update the Z value of the selected wells:")
        lbl.setSizePolicy(QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed))
        self.assign_z = QPushButton(text="Update")
        self.assign_z.clicked.connect(self._assign_to_wells)
        self.z_doublespinbox = QDoubleSpinBox()
        self.z_doublespinbox.setAlignment(Qt.AlignCenter)
        self.z_doublespinbox.setMaximum(1000000)
        assign_z_wdg_layout.addWidget(lbl)
        assign_z_wdg_layout.addWidget(self.z_doublespinbox)
        assign_z_wdg_layout.addWidget(self.assign_z)
        group_layout.addWidget(assign_z_wdg)

        return group

    def _create_channel_group(self) -> QGroupBox:

        group = QGroupBox(title="Channels")
        group.setMinimumHeight(230)
        group_layout = QGridLayout()
        group_layout.setHorizontalSpacing(15)
        group_layout.setVerticalSpacing(0)
        group_layout.setContentsMargins(10, 0, 10, 0)
        group.setLayout(group_layout)

        # table
        self.channel_tableWidget = QTableWidget()
        self.channel_tableWidget.setMinimumHeight(90)
        hdr = self.channel_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        self.channel_tableWidget.verticalHeader().setVisible(False)
        self.channel_tableWidget.setTabKeyNavigation(True)
        self.channel_tableWidget.setColumnCount(2)
        self.channel_tableWidget.setRowCount(0)
        self.channel_tableWidget.setHorizontalHeaderLabels(
            ["Channel", "Exposure Time (ms)"]
        )
        group_layout.addWidget(self.channel_tableWidget, 0, 0, 3, 1)

        # buttons
        btn_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        min_size = 100
        self.add_ch_Button = QPushButton(text="Add")
        self.add_ch_Button.clicked.connect(self._add_channel)
        self.add_ch_Button.setMinimumWidth(min_size)
        self.add_ch_Button.setSizePolicy(btn_sizepolicy)
        self.remove_ch_Button = QPushButton(text="Remove")
        self.remove_ch_Button.clicked.connect(self._remove_channel)
        self.remove_ch_Button.setMinimumWidth(min_size)
        self.remove_ch_Button.setSizePolicy(btn_sizepolicy)
        self.clear_ch_Button = QPushButton(text="Clear")
        self.clear_ch_Button.clicked.connect(self._clear_channel)
        self.clear_ch_Button.setMinimumWidth(min_size)
        self.clear_ch_Button.setSizePolicy(btn_sizepolicy)

        group_layout.addWidget(self.add_ch_Button, 0, 1, 1, 1)
        group_layout.addWidget(self.remove_ch_Button, 1, 1, 1, 2)
        group_layout.addWidget(self.clear_ch_Button, 2, 1, 1, 2)

        return group

    def _spacer(self) -> QLabel:
        spacer = QLabel()
        spacer.setMinimumHeight(0)
        spacer.setMaximumHeight(0)
        return spacer

    def _create_mda_options(self) -> QGroupBox:

        group = QGroupBox(title="MDA Options")
        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 15, 10, 15)
        group.setLayout(group_layout)

        coll_sizepolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)

        self.time_coll = QCollapsible(title="Time")
        self.time_coll.setSizePolicy(coll_sizepolicy)
        self.time_coll.layout().setSpacing(0)
        self.time_coll.layout().setContentsMargins(0, 0, 0, 0)
        spacer = self._spacer()
        self.time_coll.addWidget(spacer)
        self.time_groupBox = self._create_time_groupBox()
        self.time_coll.addWidget(self.time_groupBox)

        group_layout.addWidget(self.time_coll)

        self.stack_coll = QCollapsible(title="Z Stack")
        self.stack_coll.setSizePolicy(coll_sizepolicy)
        self.stack_coll.layout().setSpacing(0)
        self.stack_coll.layout().setContentsMargins(0, 0, 0, 0)
        spacer = self._spacer()
        self.stack_coll.addWidget(spacer)
        self.stack_groupBox = self._create_stack_groupBox()
        self.stack_coll.addWidget(self.stack_groupBox)

        group_layout.addWidget(self.stack_coll)

        return group

    def _create_time_groupBox(self) -> QGroupBox:
        group = QGroupBox(title="Time")
        group.setCheckable(True)
        group.setChecked(False)
        group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        # group_layout = QHBoxLayout()
        group_layout = QGridLayout()
        group_layout.setSpacing(5)
        group_layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(group_layout)

        # Timepoints
        wdg = QWidget()
        wdg_lay = QHBoxLayout()
        wdg_lay.setSpacing(5)
        wdg_lay.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_lay)
        lbl = QLabel(text="Timepoints:")
        lbl.setSizePolicy(LBL_SIZEPOLICY)
        self.timepoints_spinBox = QSpinBox()
        self.timepoints_spinBox.setMinimum(1)
        self.timepoints_spinBox.setMaximum(1000000)
        self.timepoints_spinBox.setSizePolicy(
            QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        )
        self.timepoints_spinBox.setAlignment(Qt.AlignCenter)
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
        lbl1.setSizePolicy(LBL_SIZEPOLICY)
        self.interval_spinBox = QDoubleSpinBox()
        self.interval_spinBox.setMinimum(0)
        self.interval_spinBox.setMaximum(100000)
        self.interval_spinBox.setSizePolicy(
            QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        )
        self.interval_spinBox.setAlignment(Qt.AlignCenter)
        wdg1_lay.addWidget(lbl1)
        wdg1_lay.addWidget(self.interval_spinBox)
        group_layout.addWidget(wdg1)

        self.time_comboBox = QComboBox()
        self.time_comboBox.setSizePolicy(
            QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        )
        self.time_comboBox.addItems(["ms", "sec", "min", "hours"])
        wdg1_lay.addWidget(self.time_comboBox)
        group_layout.addWidget(wdg1, 0, 1)

        wdg2 = QWidget()
        wdg2_lay = QHBoxLayout()
        wdg2_lay.setSpacing(5)
        wdg2_lay.setContentsMargins(0, 0, 0, 0)
        wdg2.setLayout(wdg2_lay)
        self._icon_lbl = QLabel()
        self._icon_lbl.setAlignment(Qt.AlignLeft)
        self._icon_lbl.setSizePolicy(LBL_SIZEPOLICY)
        wdg2_lay.addWidget(self._icon_lbl)
        self._time_lbl = QLabel()
        self._time_lbl.setAlignment(Qt.AlignLeft)
        self._time_lbl.setSizePolicy(LBL_SIZEPOLICY)
        wdg2_lay.addWidget(self._time_lbl)
        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Expanding)
        wdg2_lay.addItem(spacer)
        group_layout.addWidget(wdg2, 1, 0, 1, 2)

        return group

        # self.time_group = QGroupBox()
        # self.time_group.setCheckable(True)
        # self.time_group.setChecked(False)
        # self.time_group.setSizePolicy(
        #     QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        # )
        # group_layout = QHBoxLayout()
        # group_layout.setSpacing(10)
        # group_layout.setContentsMargins(10, 10, 10, 10)
        # self.time_group.setLayout(group_layout)

        # # Timepoints
        # wdg = QWidget()
        # wdg_lay = QHBoxLayout()
        # wdg_lay.setSpacing(5)
        # wdg_lay.setContentsMargins(0, 0, 0, 0)
        # wdg.setLayout(wdg_lay)
        # lbl = QLabel(text="Timepoints:")
        # lbl.setSizePolicy(LBL_SIZEPOLICY)
        # self.timepoints_spinBox = QSpinBox()
        # self.timepoints_spinBox.setMinimum(1)
        # self.timepoints_spinBox.setMaximum(10000)
        # self.timepoints_spinBox.setAlignment(Qt.AlignCenter)
        # wdg_lay.addWidget(lbl)
        # wdg_lay.addWidget(self.timepoints_spinBox)
        # group_layout.addWidget(wdg)

        # # Interval
        # wdg1 = QWidget()
        # wdg1_lay = QHBoxLayout()
        # wdg1_lay.setSpacing(5)
        # wdg1_lay.setContentsMargins(0, 0, 0, 0)
        # wdg1.setLayout(wdg1_lay)
        # lbl1 = QLabel(text="Interval:")
        # lbl1.setSizePolicy(LBL_SIZEPOLICY)
        # self.interval_spinBox = QSpinBox()
        # self.interval_spinBox.setMinimum(0)
        # self.interval_spinBox.setMaximum(10000)
        # self.interval_spinBox.setAlignment(Qt.AlignCenter)
        # wdg1_lay.addWidget(lbl1)
        # wdg1_lay.addWidget(self.interval_spinBox)
        # group_layout.addWidget(wdg1)

        # self.time_comboBox = QComboBox()
        # self.time_comboBox.setSizePolicy(
        #     QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        # )
        # self.time_comboBox.addItems(["ms", "sec", "min"])
        # group_layout.addWidget(self.time_comboBox)

        # wdg2 = QWidget()
        # wdg2_lay = QHBoxLayout()
        # wdg2_lay.setSpacing(5)
        # wdg2_lay.setContentsMargins(0, 0, 0, 0)
        # wdg2.setLayout(wdg2_lay)
        # self._icon_lbl = QLabel()
        # self._icon_lbl.setAlignment(Qt.AlignLeft)
        # self._icon_lbl.setSizePolicy(LBL_SIZEPOLICY)
        # wdg2_lay.addWidget(self._icon_lbl)
        # self._time_lbl = QLabel()
        # self._time_lbl.setAlignment(Qt.AlignLeft)
        # self._time_lbl.setSizePolicy(LBL_SIZEPOLICY)
        # wdg2_lay.addWidget(self._time_lbl)
        # spacer = QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Expanding)
        # wdg2_lay.addItem(spacer)
        # group_layout.addWidget(wdg2)

        # return self.time_group

    def _create_stack_groupBox(self) -> QGroupBox:

        self.stack_group = QGroupBox()
        self.stack_group.setCheckable(True)
        self.stack_group.setChecked(False)
        self.stack_group.setSizePolicy(
            QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        )
        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.stack_group.setLayout(group_layout)

        # tab
        self.z_tabWidget = QTabWidget()
        z_tab_layout = QVBoxLayout()
        z_tab_layout.setSpacing(0)
        z_tab_layout.setContentsMargins(0, 0, 0, 0)
        self.z_tabWidget.setLayout(z_tab_layout)
        group_layout.addWidget(self.z_tabWidget)

        # range around
        ra = QWidget()
        ra_layout = QHBoxLayout()
        ra_layout.setSpacing(10)
        ra_layout.setContentsMargins(10, 10, 10, 10)
        ra.setLayout(ra_layout)

        lbl_range_ra = QLabel(text="Range (µm):")
        lbl_range_ra.setSizePolicy(LBL_SIZEPOLICY)

        self.zrange_spinBox = QSpinBox()
        self.zrange_spinBox.setValue(5)
        self.zrange_spinBox.setAlignment(Qt.AlignCenter)
        self.zrange_spinBox.setMaximum(100000)

        self.range_around_label = QLabel(text="-2.5 µm <- z -> +2.5 µm")
        self.range_around_label.setAlignment(Qt.AlignCenter)

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
        lbl_above.setAlignment(Qt.AlignCenter)
        self.above_doubleSpinBox = QDoubleSpinBox()
        self.above_doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.above_doubleSpinBox.setMinimum(0.05)
        self.above_doubleSpinBox.setMaximum(10000)
        self.above_doubleSpinBox.setSingleStep(0.5)
        self.above_doubleSpinBox.setDecimals(2)

        lbl_below = QLabel(text="Below (µm):")
        lbl_below.setAlignment(Qt.AlignCenter)
        self.below_doubleSpinBox = QDoubleSpinBox()
        self.below_doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.below_doubleSpinBox.setMinimum(0.05)
        self.below_doubleSpinBox.setMaximum(10000)
        self.below_doubleSpinBox.setSingleStep(0.5)
        self.below_doubleSpinBox.setDecimals(2)

        lbl_range = QLabel(text="Range (µm):")
        lbl_range.setAlignment(Qt.AlignCenter)
        self.z_range_abovebelow_doubleSpinBox = QDoubleSpinBox()
        self.z_range_abovebelow_doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.z_range_abovebelow_doubleSpinBox.setMaximum(10000000)
        self.z_range_abovebelow_doubleSpinBox.setButtonSymbols(
            QAbstractSpinBox.NoButtons
        )
        self.z_range_abovebelow_doubleSpinBox.setReadOnly(True)

        ab_layout.addWidget(lbl_above, 0, 0)
        ab_layout.addWidget(self.above_doubleSpinBox, 1, 0)
        ab_layout.addWidget(lbl_below, 0, 1)
        ab_layout.addWidget(self.below_doubleSpinBox, 1, 1)
        ab_layout.addWidget(lbl_range, 0, 2)
        ab_layout.addWidget(self.z_range_abovebelow_doubleSpinBox, 1, 2)

        self.z_tabWidget.addTab(ab, "AboveBelow")

        # z stage and step size
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
        lbl.setSizePolicy(LBL_SIZEPOLICY)
        self.step_size_doubleSpinBox = QDoubleSpinBox()
        self.step_size_doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.step_size_doubleSpinBox.setMinimum(0.05)
        self.step_size_doubleSpinBox.setMaximum(10000)
        self.step_size_doubleSpinBox.setSingleStep(0.5)
        self.step_size_doubleSpinBox.setDecimals(2)
        s_layout.addWidget(lbl)
        s_layout.addWidget(self.step_size_doubleSpinBox)

        self.n_images_label = QLabel(text="Number of Images: 101")

        step_wdg_layout.addWidget(s)
        step_wdg_layout.addWidget(self.n_images_label)
        group_layout.addWidget(step_wdg)

        # connect
        self.zrange_spinBox.valueChanged.connect(self._update_rangearound_label)
        self.above_doubleSpinBox.valueChanged.connect(self._update_abovebelow_range)
        self.below_doubleSpinBox.valueChanged.connect(self._update_abovebelow_range)
        self.z_range_abovebelow_doubleSpinBox.valueChanged.connect(
            self._update_n_images
        )
        self.zrange_spinBox.valueChanged.connect(self._update_n_images)
        self.step_size_doubleSpinBox.valueChanged.connect(self._update_n_images)
        self.z_tabWidget.currentChanged.connect(self._update_n_images)
        self.stack_group.toggled.connect(self._update_n_images)

        return self.stack_group

    def _on_sys_cfg_loaded(self) -> None:
        if channel_group := self._mmc.getChannelGroup() or guess_channel_group():
            self._mmc.setChannelGroup(channel_group)
        self._clear_channel()
        self._clear_positions()
        self._update_stage_combo()

    def _set_focus_device(self, focus_device: str) -> None:
        if focus_device == "None":
            return
        self._mmc.setProperty("Core", "Focus", focus_device)

    def _update_stage_combo(self) -> None:
        self.z_combo.clear()
        items = list(self._mmc.getLoadedDevicesOfType(DeviceType.Stage))
        items.append("None")
        self.z_combo.addItems(items)

    def _remove_position(self) -> None:
        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.stage_tableWidget.removeRow(idx)
        self._calculate_total_time()

    def _clear_positions(self) -> None:
        self.stage_tableWidget.clearContents()
        self.stage_tableWidget.setRowCount(0)
        self._calculate_total_time()

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self.stage_tableWidget.currentRow()
        x_val = self.stage_tableWidget.item(curr_row, 1).text()
        y_val = self.stage_tableWidget.item(curr_row, 2).text()
        if z_item := self.stage_tableWidget.item(curr_row, 3):
            z_val = z_item.text()
            self._mmc.setXYPosition(float(x_val), float(y_val))
            self._mmc.setPosition(self._mmc.getFocusDevice(), float(z_val))

    def _add_channel(self) -> bool:
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
        channel_exp_spinBox.valueChanged.connect(self._calculate_total_time)

        if channel_group := self._mmc.getChannelGroup():
            channel_list = list(self._mmc.getAvailableConfigs(channel_group))
            channel_comboBox.addItems(channel_list)

        self.channel_tableWidget.setCellWidget(idx, 0, channel_comboBox)
        self.channel_tableWidget.setCellWidget(idx, 1, channel_exp_spinBox)

        self._calculate_total_time()

        return True

    def _remove_channel(self) -> None:
        rows = {r.row() for r in self.channel_tableWidget.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.channel_tableWidget.removeRow(idx)
        self._calculate_total_time()

    def _clear_channel(self) -> None:
        self.channel_tableWidget.clearContents()
        self.channel_tableWidget.setRowCount(0)
        self._calculate_total_time()

    def _update_rangearound_label(self, value: int) -> None:
        self.range_around_label.setText(f"-{value/2} µm <- z -> +{value/2} µm")

    def _update_abovebelow_range(self) -> None:
        self.z_range_abovebelow_doubleSpinBox.setValue(
            self.above_doubleSpinBox.value() + self.below_doubleSpinBox.value()
        )

    def _update_n_images(self) -> None:
        step = self.step_size_doubleSpinBox.value()
        # set what is the range to consider depending on the z_stack mode
        if self.z_tabWidget.currentIndex() == 0:
            _range = self.zrange_spinBox.value()
        if self.z_tabWidget.currentIndex() == 1:
            _range = self.z_range_abovebelow_doubleSpinBox.value()
        self.n_images_label.setText(f"Number of Images: {round((_range / step) + 1)}")
        self._calculate_total_time()

    def _assign_to_wells(self) -> None:
        if self.z_combo.currentText() == "None":
            return
        rows = {r.row() for r in self.stage_tableWidget.selectedIndexes()}
        for row in rows:
            item = QTableWidgetItem(str(self.z_doublespinbox.value()))
            item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
            self.stage_tableWidget.setItem(row, 3, item)

    def _calculate_total_time(self) -> None:

        # positions
        n_pos = self.stage_tableWidget.rowCount()
        if not n_pos:
            self._tot_time_label_parent._total_time_lbl.clear()
            self._icon_lbl.clear()
            return

        # channel
        exp: list = []
        ch = self.channel_tableWidget.rowCount()
        if ch > 0:
            exp.extend(
                self.channel_tableWidget.cellWidget(r, 1).value() for r in range(ch)
            )
        else:
            exp = []

        # time
        if self.time_groupBox.isChecked():
            timepoints = self.timepoints_spinBox.value()
            interval = self.interval_spinBox.value()
            int_unit = self.time_comboBox.currentText()
            if int_unit != "sec":
                interval = _time_in_sec(interval, int_unit)
        else:
            timepoints = 1
            interval = -1.0

        # z stack
        if self.stack_groupBox.isChecked():
            n_z_images = int(self.n_images_label.text()[18:])
        else:
            n_z_images = 1

        # acq time per timepoint
        time_chs: float = 0.0  # s
        for e in exp:
            time_chs = time_chs + ((e / 1000) * n_z_images * n_pos)

        warning_msg = ""

        min_aq_tp, unit_1 = _select_output_unit(time_chs)

        if interval <= 0:
            effective_interval = 0.0
            addition_time = 0
            _icon = None
            stylesheet = ""

        elif interval < time_chs:
            addition_time = 0
            effective_interval = 0.0
            warning_msg = "Interval shorter than acquisition time per timepoint."
            _icon = icon(MDI6.exclamation_thick, color="magenta").pixmap(QSize(30, 30))
            stylesheet = "color:magenta"

        else:
            effective_interval = float(interval) - time_chs  # s
            addition_time = effective_interval * timepoints  # s
            _icon = None
            stylesheet = ""

        min_tot_time, unit_4 = _select_output_unit(
            (time_chs * timepoints) + addition_time - effective_interval
        )

        self._icon_lbl.clear()
        self._time_lbl.clear()
        self._time_lbl.setStyleSheet(stylesheet)
        if _icon:
            self._icon_lbl.setPixmap(_icon)
            self._time_lbl.show()
            self._time_lbl.setText(f"{warning_msg}")
            self._time_lbl.adjustSize()
        else:
            self._time_lbl.hide()

        t_per_tp_msg = ""
        tot_acq_msg = f"Minimum total acquisition time: {min_tot_time:.4f} {unit_4}.\n"
        if self.time_groupBox.isChecked():
            t_per_tp_msg = (
                f"Minimum acquisition time per timepoint: {min_aq_tp:.4f} {unit_1}."
            )
        self._tot_time_label_parent._total_time_lbl.setText(
            f"{tot_acq_msg}{t_per_tp_msg}"
        )
