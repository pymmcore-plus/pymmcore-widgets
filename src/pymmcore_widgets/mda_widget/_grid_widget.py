from typing import Optional

from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

# from ..core import get_core_singleton
from pymmcore_widgets.core import get_core_singleton  # to remove


class GridWidget(QWidget):
    """A subwidget to setup the acquisition of a grid of images."""

    sendPosList = Signal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._mmc = get_core_singleton()

        self._mmc.loadSystemConfiguration()  # to remove

        self._create_gui()

        self._update_info_label()

    def _create_gui(self) -> None:

        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        grid_settings = self._create_row_cols_overlap_group()
        layout.addWidget(grid_settings)

        # TODO:
        # create button
        # make grid
        # send pos list

    def _create_row_cols_overlap_group(self) -> QGroupBox:
        group = QGroupBox(title="Grid Parameters")
        group.setSizePolicy(QSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed))
        group_layout = QGridLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 20, 10, 20)
        group.setLayout(group_layout)

        fix_size = 75
        lbl_sizepolicy = QSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        # row
        self.row_wdg = QWidget()
        row_wdg_lay = QHBoxLayout()
        row_wdg_lay.setSpacing(0)
        row_wdg_lay.setContentsMargins(0, 0, 0, 0)
        self.row_wdg.setLayout(row_wdg_lay)
        row_label = QLabel(text="Rows:")
        row_label.setMaximumWidth(fix_size)
        row_label.setMinimumWidth(fix_size)
        row_label.setSizePolicy(lbl_sizepolicy)
        self.scan_size_spinBox_r = QSpinBox()
        self.scan_size_spinBox_r.setMinimumWidth(fix_size)
        self.scan_size_spinBox_r.setMinimum(1)
        self.scan_size_spinBox_r.setAlignment(Qt.AlignCenter)
        self.scan_size_spinBox_r.valueChanged.connect(self._update_info_label)
        row_wdg_lay.addWidget(row_label)
        row_wdg_lay.addWidget(self.scan_size_spinBox_r)

        # col
        self.col_wdg = QWidget()
        col_wdg_lay = QHBoxLayout()
        col_wdg_lay.setSpacing(0)
        col_wdg_lay.setContentsMargins(0, 0, 0, 0)
        self.col_wdg.setLayout(col_wdg_lay)
        col_label = QLabel(text="Columns:")
        col_label.setMaximumWidth(fix_size)
        col_label.setMinimumWidth(fix_size)
        col_label.setSizePolicy(lbl_sizepolicy)
        self.scan_size_spinBox_c = QSpinBox()
        self.scan_size_spinBox_c.setMinimumWidth(fix_size)
        self.scan_size_spinBox_c.setMinimum(1)
        self.scan_size_spinBox_c.setAlignment(Qt.AlignCenter)
        self.scan_size_spinBox_c.valueChanged.connect(self._update_info_label)
        col_wdg_lay.addWidget(col_label)
        col_wdg_lay.addWidget(self.scan_size_spinBox_c)

        # overlay
        self.ovl_wdg = QWidget()
        ovl_wdg_lay = QHBoxLayout()
        ovl_wdg_lay.setSpacing(0)
        ovl_wdg_lay.setContentsMargins(0, 0, 0, 0)
        self.ovl_wdg.setLayout(ovl_wdg_lay)
        overlap_label = QLabel(text="Overlap (%):")
        overlap_label.setMaximumWidth(fix_size)
        overlap_label.setMinimumWidth(fix_size)
        overlap_label.setSizePolicy(lbl_sizepolicy)
        self.ovelap_spinBox = QSpinBox()
        self.ovelap_spinBox.setMinimumWidth(fix_size)
        self.ovelap_spinBox.setAlignment(Qt.AlignCenter)
        self.ovelap_spinBox.valueChanged.connect(self._update_info_label)
        ovl_wdg_lay.addWidget(overlap_label)
        ovl_wdg_lay.addWidget(self.ovelap_spinBox)

        # label info
        self.info_lbl = QLabel(text="_ µm x _ µm")
        self.info_lbl.setAlignment(Qt.AlignCenter)

        group_layout.addWidget(self.row_wdg, 0, 0)
        group_layout.addWidget(self.col_wdg, 1, 0)
        group_layout.addWidget(self.ovl_wdg, 0, 1)
        group_layout.addWidget(self.info_lbl, 1, 1)

        return group

    def _update_info_label(self) -> None:
        if not self._mmc.getPixelSizeUm():
            self.info_lbl.setText("_ mm x _ mm")
            return

        px_size = self._mmc.getPixelSizeUm()
        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())
        rows = self.scan_size_spinBox_r.value()
        cols = self.scan_size_spinBox_c.value()
        overlap_percentage = self.ovelap_spinBox.value()
        overlap_x = width * overlap_percentage / 100
        overlap_y = height * overlap_percentage / 100

        y = ((px_size * height * rows) - overlap_y) / 1000  # rows
        x = ((px_size * width * cols) - overlap_x) / 1000  # cols

        self.info_lbl.setText(f"{round(y, 3)} mm x {round(x, 3)} mm")

    # add, remove, clear, move_to positions table
    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("GXYZ"):
                if ax == "G":
                    count = self.stage_tableWidget.rowCount()
                    item = QTableWidgetItem(f"Grid_{count:03d}")
                    item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                    self.stage_tableWidget.setItem(idx, c, item)
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue

                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QTableWidgetItem(str(cur))
                item.setTextAlignment(int(Qt.AlignHCenter | Qt.AlignVCenter))
                self.stage_tableWidget.setItem(idx, c, item)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = GridWidget()
    win.show()
    sys.exit(app.exec_())
