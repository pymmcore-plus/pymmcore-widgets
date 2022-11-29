from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible

from pymmcore_widgets._general_mda_widgets import (
    _MDAChannelTable,
    _MDAControlButtons,
    _MDAPositionTable,
    _MDATimeLabel,
    _MDATimeWidget,
)
from pymmcore_widgets._zstack_widget import ZStackWidget

LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class SampleExplorerGui(QWidget):
    """Just the UI of the explorer widget. Runtime logic in MMExploreSample."""

    def __init__(self, *, parent: QWidget | None = None) -> None:
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

        self.time_lbl = _MDATimeLabel()
        self.layout().addWidget(self.time_lbl)

        self.buttons_wdg = _MDAControlButtons()
        self.layout().addWidget(self.buttons_wdg)

    def _create_gui(self) -> QWidget:

        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(15)
        wdg_layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(wdg_layout)

        self.scan_props = self._create_row_cols_overlap_group()
        wdg_layout.addWidget(self.scan_props)

        self.channel_groupbox = _MDAChannelTable()
        wdg_layout.addWidget(self.channel_groupbox)
        self.channel_groupbox.channel_tableWidget.model().rowsInserted.connect(
            self._enable_run_btn
        )
        self.channel_groupbox.channel_tableWidget.model().rowsRemoved.connect(
            self._enable_run_btn
        )

        mda_options = self._create_mda_options()
        wdg_layout.addWidget(mda_options)

        spacer = QSpacerItem(
            10, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding
        )
        wdg_layout.addItem(spacer)

        return wdg

    def _enable_run_btn(self) -> None:
        self.buttons_wdg.run_button.setEnabled(
            self.channel_groupbox.channel_tableWidget.rowCount() > 0
        )

    def _create_row_cols_overlap_group(self) -> QGroupBox:

        group = QGroupBox(title="Grid Parameters")
        group.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
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
        self.scan_size_spinBox_r.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.scan_size_spinBox_c.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.ovelap_spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ovl_wdg_lay.addWidget(overlap_label)
        ovl_wdg_lay.addWidget(self.ovelap_spinBox)

        group_layout.addWidget(self.row_wdg, 0, 0)
        group_layout.addWidget(self.col_wdg, 1, 0)
        group_layout.addWidget(self.ovl_wdg, 0, 1)
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

        coll_sizepolicy = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )

        self.time_coll = QCollapsible(title="Time")
        self.time_coll.setSizePolicy(coll_sizepolicy)
        self.time_coll.layout().setSpacing(0)
        self.time_coll.layout().setContentsMargins(0, 0, 0, 0)
        spacer = self._spacer()
        self.time_coll.addWidget(spacer)
        self.time_groupbox = _MDATimeWidget()
        self.time_groupbox.setTitle("")
        self.time_coll.addWidget(self.time_groupbox)

        group_layout.addWidget(self.time_coll)

        self.stack_coll = QCollapsible(title="Z Stack")
        self.stack_coll.setSizePolicy(coll_sizepolicy)
        self.stack_coll.layout().setSpacing(0)
        self.stack_coll.layout().setContentsMargins(0, 0, 0, 0)
        spacer = self._spacer()
        self.stack_coll.addWidget(spacer)
        self.stack_groupbox = ZStackWidget()
        self.stack_groupbox.setChecked(False)
        self.stack_groupbox.setTitle("")
        self.stack_coll.addWidget(self.stack_groupbox)

        group_layout.addWidget(self.stack_coll)

        self.pos_coll = QCollapsible(title="Grid Starting Positions")
        self.pos_coll.setSizePolicy(coll_sizepolicy)
        self.pos_coll.layout().setSpacing(0)
        self.pos_coll.layout().setContentsMargins(0, 0, 0, 0)
        spacer = self._spacer()
        self.pos_coll.addWidget(spacer)
        self.stage_pos_groupbox = _MDAPositionTable(["Grid #", "X", "Y", "Z"])
        self.stage_pos_groupbox.setTitle("")
        self.stage_pos_groupbox.grid_button.hide()
        self.pos_coll.addWidget(self.stage_pos_groupbox)

        group_layout.addWidget(self.pos_coll)

        return group


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = SampleExplorerGui()
    win.show()
    sys.exit(app.exec_())
