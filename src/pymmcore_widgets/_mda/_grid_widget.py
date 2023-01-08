from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


class GridWidget(QDialog):
    """A subwidget to setup the acquisition of a grid of images."""

    sendPosList = Signal(list, bool)

    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self._create_gui()

        self._update_info_label()

    def _create_gui(self) -> None:

        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(layout)

        self.setMaximumHeight(200)

        grid_settings = self._create_row_cols_overlap_group()
        layout.addWidget(grid_settings)

        button = self._create_generate_list_button()
        layout.addWidget(button)

    def _create_row_cols_overlap_group(self) -> QGroupBox:
        group = QGroupBox(title="Grid Parameters")
        group.setSizePolicy(
            QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        )
        group_layout = QGridLayout()
        group_layout.setSpacing(10)
        group_layout.setContentsMargins(10, 20, 10, 20)
        group.setLayout(group_layout)

        fix_size = 75
        lbl_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

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
        self.scan_size_spinBox_r.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        self.scan_size_spinBox_c.setAlignment(Qt.AlignmentFlag.AlignCenter)
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
        overlap_label.setMaximumWidth(100)
        overlap_label.setMinimumWidth(100)
        overlap_label.setSizePolicy(lbl_sizepolicy)
        self.ovelap_spinBox = QSpinBox()
        self.ovelap_spinBox.setMinimumWidth(fix_size)
        self.ovelap_spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ovelap_spinBox.valueChanged.connect(self._update_info_label)
        ovl_wdg_lay.addWidget(overlap_label)
        ovl_wdg_lay.addWidget(self.ovelap_spinBox)

        # label info
        self.info_lbl = QLabel(text="_ µm x _ µm")
        self.info_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        group_layout.addWidget(self.row_wdg, 0, 0)
        group_layout.addWidget(self.col_wdg, 1, 0)
        group_layout.addWidget(self.ovl_wdg, 0, 1)
        group_layout.addWidget(self.info_lbl, 1, 1)

        return group

    def _create_generate_list_button(self) -> QWidget:
        wdg = QWidget()
        wdg_layout = QHBoxLayout()
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(wdg_layout)

        self.clear_checkbox = QCheckBox(text="Delete Current Position List")
        self.clear_checkbox.setChecked(True)
        wdg_layout.addWidget(self.clear_checkbox)

        self.generate_position_btn = QPushButton(text="Generate Position List")
        self.generate_position_btn.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.generate_position_btn.clicked.connect(self._send_positions_grid)
        wdg_layout.addWidget(self.generate_position_btn)

        return wdg

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

        y = ((height - overlap_y) * rows) * px_size / 1000  # rows
        x = ((width - overlap_x) * cols) * px_size / 1000  # cols

        self.info_lbl.setText(f"{round(y, 3)} mm x {round(x, 3)} mm")

    def _set_grid(self) -> list[tuple[float, ...]]:

        scan_size_r = self.scan_size_spinBox_r.value()
        scan_size_c = self.scan_size_spinBox_c.value()

        # get current position
        x_pos = float(self._mmc.getXPosition())
        y_pos = float(self._mmc.getYPosition())
        if self._mmc.getFocusDevice():
            z_pos = float(self._mmc.getZPosition())

        # calculate initial scan position
        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())

        pixel_size = self._mmc.getPixelSizeUm()

        overlap_percentage = self.ovelap_spinBox.value()
        overlap_px_w = width - (width * overlap_percentage) / 100
        overlap_px_h = height - (height * overlap_percentage) / 100

        move_x = (width / 2) * (scan_size_c - 1) - overlap_px_w
        move_y = (height / 2) * (scan_size_r - 1) - overlap_px_h

        # to match position coordinates with center of the image
        x_pos -= pixel_size * (move_x + width)
        y_pos += pixel_size * (move_y + height)

        # calculate position increments depending on pixle size
        if overlap_percentage > 0:
            increment_x = overlap_px_w * pixel_size
            increment_y = overlap_px_h * pixel_size
        else:
            increment_x = width * pixel_size
            increment_y = height * pixel_size

        list_pos_order: list[tuple[float, ...]] = []
        for r in range(scan_size_r):
            if r % 2:  # for odd rows
                col = scan_size_c - 1
                for c in range(scan_size_c):
                    if c == 0:
                        y_pos -= increment_y
                    if self._mmc.getFocusDevice():
                        list_pos_order.append((x_pos, y_pos, z_pos))
                    else:
                        list_pos_order.append((x_pos, y_pos))
                    if col > 0:
                        col -= 1
                        x_pos -= increment_x
            else:  # for even rows
                for c in range(scan_size_c):
                    if r > 0 and c == 0:
                        y_pos -= increment_y
                    if self._mmc.getFocusDevice():
                        list_pos_order.append((x_pos, y_pos, z_pos))
                    else:
                        list_pos_order.append((x_pos, y_pos))
                    if c < scan_size_c - 1:
                        x_pos += increment_x

        return list_pos_order

    def _send_positions_grid(self) -> None:
        if self._mmc.getPixelSizeUm() <= 0:
            raise ValueError("Pixel Size Not Set.")
        grid = self._set_grid()
        self.sendPosList.emit(grid, self.clear_checkbox.isChecked())
