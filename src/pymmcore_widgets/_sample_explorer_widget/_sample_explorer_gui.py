from typing import Optional

from fonticon_mdi6 import MDI6
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
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible
from superqt.fonticon import icon

LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)


class SampleExplorerGui(QWidget):
    """Just the UI of the explorer widget. Runtime logic in MMExploreSample."""

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent=parent)

        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(10)
        self.layout().setContentsMargins(10, 10, 10, 10)

        # general scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.explorer_wdg = self._create_gui()
        self._scroll.setWidget(self.explorer_wdg)
        self.layout().addWidget(self._scroll)

        lbl = self._create_label()
        self.layout().addWidget(lbl)

        self.btns = self._create_start_stop_buttons()
        self.layout().addWidget(self.btns)

    def _create_gui(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(15)
        wdg_layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(wdg_layout)

        self.scan_props = self._create_row_cols_overlap_group()
        wdg_layout.addWidget(self.scan_props)

        self.channel_explorer_groupBox = self._create_channel_group()
        wdg_layout.addWidget(self.channel_explorer_groupBox)

        mda_options = self._create_mda_options()
        wdg_layout.addWidget(mda_options)

        spacer = QSpacerItem(10, 10, QSizePolicy.Minimum, QSizePolicy.Expanding)
        wdg_layout.addItem(spacer)

        return wdg

    def _create_row_cols_overlap_group(self) -> QGroupBox:

        group = QGroupBox(title="Grid Parameters")
        group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        group_layout = QGridLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 20, 10, 20)
        group.setLayout(group_layout)

        fix_lbl_size = 80

        # row
        self.row_wdg = QWidget()
        row_wdg_lay = QHBoxLayout()
        row_wdg_lay.setSpacing(0)
        row_wdg_lay.setContentsMargins(0, 0, 0, 0)
        self.row_wdg.setLayout(row_wdg_lay)
        row_label = QLabel(text="Rows:")
        row_label.setMaximumWidth(fix_lbl_size)
        row_label.setSizePolicy(LBL_SIZEPOLICY)
        self.scan_size_spinBox_r = QSpinBox()
        self.scan_size_spinBox_r.setMinimum(1)
        self.scan_size_spinBox_r.setAlignment(Qt.AlignCenter)
        row_wdg_lay.addWidget(row_label)
        row_wdg_lay.addWidget(self.scan_size_spinBox_r)

        # col
        self.col_wdg = QWidget()
        col_wdg_lay = QHBoxLayout()
        col_wdg_lay.setSpacing(0)
        col_wdg_lay.setContentsMargins(0, 0, 0, 0)
        self.col_wdg.setLayout(col_wdg_lay)
        col_label = QLabel(text="Columns:")
        col_label.setMaximumWidth(fix_lbl_size)
        col_label.setSizePolicy(LBL_SIZEPOLICY)
        self.scan_size_spinBox_c = QSpinBox()
        self.scan_size_spinBox_c.setSizePolicy
        self.scan_size_spinBox_c.setMinimum(1)
        self.scan_size_spinBox_c.setAlignment(Qt.AlignCenter)
        col_wdg_lay.addWidget(col_label)
        col_wdg_lay.addWidget(self.scan_size_spinBox_c)

        # overlay
        self.ovl_wdg = QWidget()
        ovl_wdg_lay = QHBoxLayout()
        ovl_wdg_lay.setSpacing(0)
        ovl_wdg_lay.setContentsMargins(0, 0, 0, 0)
        self.ovl_wdg.setLayout(ovl_wdg_lay)
        overlap_label = QLabel(text="Overlap (%):")
        overlap_label.setMaximumWidth(100)
        overlap_label.setSizePolicy(LBL_SIZEPOLICY)
        self.ovelap_spinBox = QSpinBox()
        self.ovelap_spinBox.setAlignment(Qt.AlignCenter)
        ovl_wdg_lay.addWidget(overlap_label)
        ovl_wdg_lay.addWidget(self.ovelap_spinBox)

        group_layout.addWidget(self.row_wdg, 0, 0)
        group_layout.addWidget(self.col_wdg, 1, 0)
        group_layout.addWidget(self.ovl_wdg, 0, 1)
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
        self.channel_explorer_tableWidget = QTableWidget()
        self.channel_explorer_tableWidget.model().rowsInserted.connect(
            self._enable_run_btn
        )
        self.channel_explorer_tableWidget.model().rowsRemoved.connect(
            self._enable_run_btn
        )
        self.channel_explorer_tableWidget.setMinimumHeight(90)
        hdr = self.channel_explorer_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        self.channel_explorer_tableWidget.verticalHeader().setVisible(False)
        self.channel_explorer_tableWidget.setTabKeyNavigation(True)
        self.channel_explorer_tableWidget.setColumnCount(2)
        self.channel_explorer_tableWidget.setRowCount(0)
        self.channel_explorer_tableWidget.setHorizontalHeaderLabels(
            ["Channel", "Exposure Time (ms)"]
        )
        group_layout.addWidget(self.channel_explorer_tableWidget, 0, 0, 3, 1)

        # buttons
        btn_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        min_size = 100
        self.add_ch_explorer_Button = QPushButton(text="Add")
        self.add_ch_explorer_Button.setMinimumWidth(min_size)
        self.add_ch_explorer_Button.setSizePolicy(btn_sizepolicy)
        self.remove_ch_explorer_Button = QPushButton(text="Remove")
        self.remove_ch_explorer_Button.setMinimumWidth(min_size)
        self.remove_ch_explorer_Button.setSizePolicy(btn_sizepolicy)
        self.clear_ch_explorer_Button = QPushButton(text="Clear")
        self.clear_ch_explorer_Button.setMinimumWidth(min_size)
        self.clear_ch_explorer_Button.setSizePolicy(btn_sizepolicy)

        group_layout.addWidget(self.add_ch_explorer_Button, 0, 1, 1, 1)
        group_layout.addWidget(self.remove_ch_explorer_Button, 1, 1, 1, 2)
        group_layout.addWidget(self.clear_ch_explorer_Button, 2, 1, 1, 2)

        return group

    def _enable_run_btn(self) -> None:
        self.start_scan_Button.setEnabled(
            self.channel_explorer_tableWidget.rowCount() > 0
        )

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
        self.time_groupBox = self._create_time_group()
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

        self.pos_coll = QCollapsible(title="Grid Starting Positions")
        self.pos_coll.setSizePolicy(coll_sizepolicy)
        self.pos_coll.layout().setSpacing(0)
        self.pos_coll.layout().setContentsMargins(0, 0, 0, 0)
        spacer = self._spacer()
        self.pos_coll.addWidget(spacer)
        self.stage_pos_groupBox = self._create_stage_pos_groupBox()
        self.pos_coll.addWidget(self.stage_pos_groupBox)

        group_layout.addWidget(self.pos_coll)

        return group

    def _create_time_group(self) -> QGroupBox:

        group = QGroupBox()
        group.setCheckable(True)
        group.setChecked(False)
        group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        group_layout = QGridLayout()
        group_layout.setHorizontalSpacing(20)
        group_layout.setVerticalSpacing(5)
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
        self.timepoints_spinBox.setMaximum(10000)
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
        lbl1 = QLabel(text="Interval:")
        lbl1.setSizePolicy(LBL_SIZEPOLICY)
        self.interval_spinBox = QSpinBox()
        self.interval_spinBox.setMinimum(0)
        self.interval_spinBox.setMaximum(10000)
        self.interval_spinBox.setAlignment(Qt.AlignCenter)
        wdg1_lay.addWidget(lbl1)
        wdg1_lay.addWidget(self.interval_spinBox)
        group_layout.addWidget(wdg1, 0, 1)

        self.time_comboBox = QComboBox()
        self.time_comboBox.setSizePolicy(
            QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        )
        self.time_comboBox.addItems(["ms", "sec", "min", "hours"])
        group_layout.addWidget(self.time_comboBox, 0, 2)

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

        self._time_lbl.hide()
        self._icon_lbl.hide()

        return group

    def _create_stack_groupBox(self) -> QGroupBox:

        group = QGroupBox()
        group.setCheckable(True)
        group.setChecked(False)
        group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        group_layout = QVBoxLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 10, 10, 10)
        group.setLayout(group_layout)

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

        self.set_top_Button = QPushButton(text="Set Top")
        self.set_bottom_Button = QPushButton(text="Set Bottom")

        lbl_range_tb = QLabel(text="Range (µm):")
        lbl_range_tb.setAlignment(Qt.AlignCenter)

        self.z_top_doubleSpinBox = QDoubleSpinBox()
        self.z_top_doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.z_top_doubleSpinBox.setMinimum(0.0)
        self.z_top_doubleSpinBox.setMaximum(100000)
        self.z_top_doubleSpinBox.setDecimals(2)

        self.z_bottom_doubleSpinBox = QDoubleSpinBox()
        self.z_bottom_doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.z_bottom_doubleSpinBox.setMinimum(0.0)
        self.z_bottom_doubleSpinBox.setMaximum(100000)
        self.z_bottom_doubleSpinBox.setDecimals(2)

        self.z_range_topbottom_doubleSpinBox = QDoubleSpinBox()
        self.z_range_topbottom_doubleSpinBox.setAlignment(Qt.AlignCenter)
        self.z_range_topbottom_doubleSpinBox.setMaximum(10000000)
        self.z_range_topbottom_doubleSpinBox.setButtonSymbols(
            QAbstractSpinBox.NoButtons
        )
        self.z_range_topbottom_doubleSpinBox.setReadOnly(True)

        tb_layout.addWidget(self.set_top_Button, 0, 0)
        tb_layout.addWidget(self.z_top_doubleSpinBox, 1, 0)
        tb_layout.addWidget(self.set_bottom_Button, 0, 1)
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
        lbl.setSizePolicy(LBL_SIZEPOLICY)
        self.step_size_doubleSpinBox = QDoubleSpinBox()
        self.step_size_doubleSpinBox.setAlignment(Qt.AlignCenter)
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

        return group

    def _create_stage_pos_groupBox(self) -> QGroupBox:

        group = QGroupBox(title="(double-click to move to position)")
        group.setCheckable(True)
        group.setChecked(False)
        group.setMinimumHeight(230)
        group_layout = QGridLayout()
        group_layout.setHorizontalSpacing(15)
        group_layout.setVerticalSpacing(0)
        group_layout.setContentsMargins(10, 0, 10, 0)
        group.setLayout(group_layout)

        # table
        self.stage_tableWidget = QTableWidget()
        self.stage_tableWidget.setSelectionBehavior(QAbstractItemView.SelectRows)
        hdr = self.stage_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.Stretch)
        self.stage_tableWidget.verticalHeader().setVisible(False)
        self.stage_tableWidget.setTabKeyNavigation(True)
        self.stage_tableWidget.setColumnCount(4)
        self.stage_tableWidget.setRowCount(0)
        self.stage_tableWidget.setHorizontalHeaderLabels(["Grid #", "X", "Y", "Z"])
        group_layout.addWidget(self.stage_tableWidget, 0, 0, 4, 1)

        # buttons
        btn_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        min_size = 100
        self.add_pos_Button = QPushButton(text="Add")
        self.add_pos_Button.setMinimumWidth(min_size)
        self.add_pos_Button.setSizePolicy(btn_sizepolicy)
        self.remove_pos_Button = QPushButton(text="Remove")
        self.remove_pos_Button.setMinimumWidth(min_size)
        self.remove_pos_Button.setSizePolicy(btn_sizepolicy)
        self.clear_pos_Button = QPushButton(text="Clear")
        self.clear_pos_Button.setMinimumWidth(min_size)
        self.clear_pos_Button.setSizePolicy(btn_sizepolicy)
        self.go = QPushButton(text="Go")
        self.go.setMinimumWidth(min_size)
        self.go.setSizePolicy(btn_sizepolicy)

        group_layout.addWidget(self.add_pos_Button, 0, 1, 1, 1)
        group_layout.addWidget(self.remove_pos_Button, 1, 1, 1, 2)
        group_layout.addWidget(self.clear_pos_Button, 2, 1, 1, 2)
        group_layout.addWidget(self.go, 3, 1, 1, 2)

        return group

    def _create_start_stop_buttons(self) -> QWidget:

        wdg = QWidget()
        wdg.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(10, 5, 10, 10)
        wdg.setLayout(wdg_layout)

        acq_wdg = QWidget()
        acq_wdg_layout = QHBoxLayout()
        acq_wdg_layout.setSpacing(0)
        acq_wdg_layout.setContentsMargins(0, 0, 0, 0)
        acq_wdg.setLayout(acq_wdg_layout)
        acquisition_order_label = QLabel(text="Acquisition Order:")
        acquisition_order_label.setSizePolicy(LBL_SIZEPOLICY)
        self.acquisition_order_comboBox = QComboBox()
        self.acquisition_order_comboBox.setMinimumWidth(100)
        self.acquisition_order_comboBox.addItems(["tpcz", "tpzc", "ptzc", "ptcz"])
        acq_wdg_layout.addWidget(acquisition_order_label)
        acq_wdg_layout.addWidget(self.acquisition_order_comboBox)
        wdg_layout.addWidget(acq_wdg)

        spacer = QSpacerItem(10, 10, QSizePolicy.Expanding, QSizePolicy.Fixed)
        wdg_layout.addItem(spacer)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        min_width = 100
        icon_size = 40
        self.start_scan_Button = QPushButton(text="Run")
        self.start_scan_Button.setEnabled(False)
        self.start_scan_Button.setMinimumWidth(min_width)
        self.start_scan_Button.setStyleSheet("QPushButton { text-align: center; }")
        self.start_scan_Button.setSizePolicy(btn_sizepolicy)
        self.start_scan_Button.setIcon(
            icon(MDI6.play_circle_outline, color=(0, 255, 0))
        )
        self.start_scan_Button.setIconSize(QSize(icon_size, icon_size))

        self.pause_scan_Button = QPushButton(text="Pause")
        self.pause_scan_Button.setMinimumWidth(min_width)
        self.pause_scan_Button.setStyleSheet("QPushButton { text-align: center; }")
        self.pause_scan_Button.setSizePolicy(btn_sizepolicy)
        self.pause_scan_Button.setIcon(icon(MDI6.pause_circle_outline, color="green"))
        self.pause_scan_Button.setIconSize(QSize(icon_size, icon_size))

        self.cancel_scan_Button = QPushButton(text="Cancel")
        self.cancel_scan_Button.setMinimumWidth(min_width)
        self.cancel_scan_Button.setStyleSheet("QPushButton { text-align: center; }")
        self.cancel_scan_Button.setSizePolicy(btn_sizepolicy)
        self.cancel_scan_Button.setIcon(icon(MDI6.stop_circle_outline, color="magenta"))
        self.cancel_scan_Button.setIconSize(QSize(icon_size, icon_size))

        wdg_layout.addWidget(self.start_scan_Button)
        wdg_layout.addWidget(self.pause_scan_Button)
        wdg_layout.addWidget(self.cancel_scan_Button)

        return wdg

    def _create_label(self) -> QWidget:

        # wdg = QGroupBox()
        wdg = QWidget()
        wdg_lay = QHBoxLayout()
        wdg_lay.setSpacing(3)
        wdg_lay.setContentsMargins(10, 5, 10, 5)
        wdg_lay.setAlignment(Qt.AlignLeft)
        wdg.setLayout(wdg_lay)

        self._total_time_lbl = QLabel()
        self._total_time_lbl.setAlignment(Qt.AlignLeft)
        self._total_time_lbl.setSizePolicy(LBL_SIZEPOLICY)
        wdg_lay.addWidget(self._total_time_lbl)

        return wdg


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = SampleExplorerGui()
    win.show()
    sys.exit(app.exec_())
