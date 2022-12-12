from __future__ import annotations

import warnings
from typing import cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible
from useq import MDASequence

from pymmcore_widgets._mda import MDAWidget

LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class SampleExplorerWidget(MDAWidget):
    """Widget to create and run grid acquisitions.

    The `SampleExplorerWidget` provides a GUI to construct a
    [`useq.MDASequence`](https://github.com/tlambert03/useq-schema) object.
    If the `include_run_button` parameter is set to `True`, a "run" button is added
    to the GUI and, when clicked, the generated
    [`useq.MDASequence`](https://github.com/tlambert03/useq-schema)
    is passed to the
    [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.run_mda]
    method and the acquisition is executed.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    include_run_button: bool
        By default, `False`. If `True`, a "run" button is added to the widget.
        The acquisition defined by the
        [`useq.MDASequence`](https://github.com/tlambert03/useq-schema)
        built through the widget is executed when clicked.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        *,
        parent: QWidget | None = None,
        include_run_button: bool = False,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(
            parent=parent, include_run_button=include_run_button, mmcore=mmcore
        )

        # add widget elements
        scroll_layout = cast(QVBoxLayout, self._wdg.layout())
        scroll_layout.insertWidget(0, self._create_row_cols_overlap_group())

        self.channel_groupbox.setMinimumHeight(175)

        # groupbox for mda option QCollapsible
        # move Time, Z Stack and Positions in a collapsible
        wdg = QGroupBox(title="MDA Options")
        wdg.setLayout(QVBoxLayout())
        wdg.layout().setSpacing(10)
        wdg.layout().setContentsMargins(10, 10, 10, 10)

        time_coll = self._create_collapsible(title="Time")
        wdg.layout().addWidget(time_coll)
        scroll_layout.removeWidget(self.time_groupbox)
        self.time_groupbox.setTitle("")
        time_coll.addWidget(self.time_groupbox)

        stack_coll = self._create_collapsible(title="Z Stack")
        wdg.layout().addWidget(stack_coll)
        scroll_layout.removeWidget(self.stack_groupbox)
        self.stack_groupbox.setTitle("")
        stack_coll.addWidget(self.stack_groupbox)

        pos_coll = self._create_collapsible(title="Grid Starting Positions")
        wdg.layout().addWidget(pos_coll)
        scroll_layout.removeWidget(self.stage_pos_groupbox)
        self.stage_pos_groupbox.setTitle("")
        self.stage_pos_groupbox.grid_button.hide()
        pos_coll.addWidget(self.stage_pos_groupbox)

        scroll_layout.insertWidget(2, wdg)

        spacer = QSpacerItem(
            30, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        scroll_layout.addItem(spacer)

        # explorer variables
        self.pixel_size = self._mmc.getPixelSizeUm()
        self.return_to_position_x = None
        self.return_to_position_y = None

        # connection for scan size
        self.scan_size_spinBox_r.valueChanged.connect(self._update_total_time)
        self.scan_size_spinBox_c.valueChanged.connect(self._update_total_time)

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

    def _create_collapsible(self, title: str) -> QCollapsible:
        coll = QCollapsible(title=title)
        coll.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        coll.layout().setSpacing(0)
        coll.layout().setContentsMargins(0, 0, 0, 0)
        return coll

    def _set_enabled(self, enabled: bool) -> None:
        super()._set_enabled(enabled)
        self.scan_size_spinBox_r.setEnabled(enabled)
        self.scan_size_spinBox_c.setEnabled(enabled)
        self.ovelap_spinBox.setEnabled(enabled)

    def _on_mda_finished(self) -> None:
        super()._on_mda_finished()

        if not hasattr(self, "return_to_position_x"):
            return

        if (
            self.return_to_position_x is not None
            and self.return_to_position_y is not None
        ):
            self._mmc.setXYPosition(
                self.return_to_position_x, self.return_to_position_y
            )
            self.return_to_position_x = None
            self.return_to_position_y = None

    def _update_total_time(self, *, tiles: int = 1) -> None:
        # use try/except because _update_total_time could be
        # called before the scan_size_spinBox_ are created.
        try:
            tiles = self.scan_size_spinBox_c.value() * self.scan_size_spinBox_r.value()
        except AttributeError:
            return
        super()._update_total_time(tiles=tiles)

    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            idx = self._add_position_row()

            for c, ax in enumerate("GXYZ"):
                if ax == "G":
                    count = self.stage_pos_groupbox.stage_tableWidget.rowCount()
                    item = QTableWidgetItem(f"Grid_{count:03d}")
                    item.setWhatsThis(f"Grid_{count:03d}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.stage_pos_groupbox.stage_tableWidget.setItem(idx, c, item)
                    self._rename_positions()
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue

                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QTableWidgetItem(str(cur))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.stage_pos_groupbox.stage_tableWidget.setItem(idx, c, item)

        self._update_total_time()

    def _remove_position(self) -> None:
        # remove selected position
        rows = {
            r.row() for r in self.stage_pos_groupbox.stage_tableWidget.selectedIndexes()
        }
        for idx in sorted(rows, reverse=True):
            self.stage_pos_groupbox.stage_tableWidget.removeRow(idx)
        self._rename_positions()
        self._update_total_time()

    def _rename_positions(self, names: list = None) -> None:  # type: ignore
        """Rename the positions to keep name's correct counter of 3digits."""
        # name arguments to match super method
        for grid_count, r in enumerate(
            range(self.stage_pos_groupbox.stage_tableWidget.rowCount())
        ):
            item = self.stage_pos_groupbox.stage_tableWidget.item(r, 0)
            item_text = item.text()
            item_whatisthis = item.whatsThis()
            if item_text == item_whatisthis:
                new_name = f"Grid_{grid_count:03d}"
            else:
                new_name = item_text
            new_whatisthis = f"Grid_{grid_count:03d}"

            item = QTableWidgetItem(new_name)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            item.setWhatsThis(new_whatisthis)
            self.stage_pos_groupbox.stage_tableWidget.setItem(r, 0, item)

    def _get_pos_name(self, row: int) -> str:
        """Get position name from table item's whatsThis property."""
        item = self.stage_pos_groupbox.stage_tableWidget.item(row, 0)
        name = item.text()
        whatsthis = item.whatsThis()
        return f"{name}_{whatsthis}" if whatsthis not in name else name  # type: ignore

    def _create_grid_coords(self) -> list[tuple[str, float, float, float | None]]:
        """Calculate the grid coordinates for each grid starting position."""
        scan_size_r = self.scan_size_spinBox_r.value()
        scan_size_c = self.scan_size_spinBox_c.value()
        self.pixel_size = self._mmc.getPixelSizeUm()

        # TODO: fix typing error
        explorer_starting_positions: (
            list[tuple[str, float, float, float] | tuple[str, float, float]]
        ) = []
        if (
            self.stage_pos_groupbox.isChecked()
            and self.stage_pos_groupbox.stage_tableWidget.rowCount() > 0
        ):
            for r in range(self.stage_pos_groupbox.stage_tableWidget.rowCount()):
                name = self._get_pos_name(r)
                x = float(self.stage_pos_groupbox.stage_tableWidget.item(r, 1).text())
                y = float(self.stage_pos_groupbox.stage_tableWidget.item(r, 2).text())
                z = float(self.stage_pos_groupbox.stage_tableWidget.item(r, 3).text())
                pos_info = (
                    (name, x, y, z) if self._mmc.getFocusDevice() else (name, x, y)
                )
                explorer_starting_positions.append(pos_info)  # type: ignore

        else:
            name = "Grid_001"
            x = float(self._mmc.getXPosition())
            y = float(self._mmc.getYPosition())
            if self._mmc.getFocusDevice():
                z = float(self._mmc.getZPosition())
                pos_info = (name, x, y, z)
            else:
                pos_info = (name, x, y)
            explorer_starting_positions.append(pos_info)  # type: ignore

        full_pos_list: (
            list[list[tuple[str, float, float, float]] | list[tuple[str, float, float]]]
        ) = []
        for st_pos in explorer_starting_positions:
            name, x_pos, y_pos = st_pos[0], st_pos[1], st_pos[2]
            if self._mmc.getFocusDevice():
                z_pos = st_pos[3]  # type: ignore

            self.return_to_position_x = x_pos
            self.return_to_position_y = y_pos

            # calculate initial scan position
            _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())

            overlap_percentage = self.ovelap_spinBox.value()
            overlap_px_w = width - (width * overlap_percentage) / 100
            overlap_px_h = height - (height * overlap_percentage) / 100

            move_x = (width / 2) * (scan_size_c - 1) - overlap_px_w
            move_y = (height / 2) * (scan_size_r - 1) - overlap_px_h

            # to match position coordinates with center of the image
            x_pos -= self.pixel_size * (move_x + width)
            y_pos += self.pixel_size * (move_y + height)

            # calculate position increments depending on pixle size
            if overlap_percentage > 0:
                increment_x = overlap_px_w * self.pixel_size
                increment_y = overlap_px_h * self.pixel_size
            else:
                increment_x = width * self.pixel_size
                increment_y = height * self.pixel_size

            list_pos_order: (
                list[tuple[str, float, float, float] | tuple[str, float, float]]
            ) = []
            pos_count = 0
            for r in range(scan_size_r):
                if r % 2:  # for odd rows
                    col = scan_size_c - 1
                    for c in range(scan_size_c):
                        if c == 0:
                            y_pos -= increment_y
                        pos_name = f"{name}_Pos{pos_count:03d}"
                        if self._mmc.getFocusDevice():
                            list_pos_order.append((pos_name, x_pos, y_pos, z_pos))
                        else:
                            list_pos_order.append((pos_name, x_pos, y_pos))
                        if col > 0:
                            col -= 1
                            x_pos -= increment_x
                        pos_count += 1
                else:  # for even rows
                    for c in range(scan_size_c):
                        if r > 0 and c == 0:
                            y_pos -= increment_y
                        pos_name = f"{name}_Pos{pos_count:03d}"
                        if self._mmc.getFocusDevice():
                            list_pos_order.append((pos_name, x_pos, y_pos, z_pos))
                        else:
                            list_pos_order.append((pos_name, x_pos, y_pos))
                        if c < scan_size_c - 1:
                            x_pos += increment_x
                        pos_count += 1

            full_pos_list.extend(list_pos_order)  # type: ignore

        return full_pos_list  # type: ignore

    def get_state(self) -> MDASequence:  # sourcery skip: merge-dict-assign
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        channels = self.channel_groupbox.value()

        z_plan = (
            self.stack_groupbox.value() if self.stack_groupbox.isChecked() else None
        )
        time_plan = (
            self.time_groupbox.value() if self.time_groupbox.isChecked() else None
        )

        stage_positions: list[dict] = []
        for g in self._create_grid_coords():
            pos = {"name": g[0], "x": g[1], "y": g[2]}
            if len(g) == 4:
                pos["z"] = g[3]
            stage_positions.append(pos)

        return MDASequence(
            axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText(),
            channels=channels,
            stage_positions=stage_positions,
            z_plan=z_plan,
            time_plan=time_plan,
        )

    def _on_run_clicked(self) -> None:

        self.pixel_size = self._mmc.getPixelSizeUm()

        if self._mmc.getPixelSizeUm() <= 0:
            # raise ValueError("Pixel Size not set.")
            warnings.warn("Pixel Size not set.")
            return

        super()._on_run_clicked()


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()
    app = QApplication(sys.argv)
    win = SampleExplorerWidget(include_run_button=True)
    win.show()
    sys.exit(app.exec_())
