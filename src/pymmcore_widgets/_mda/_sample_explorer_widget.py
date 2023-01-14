from __future__ import annotations

import warnings
from typing import Any, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
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
from useq import MDASequence, Position

from pymmcore_widgets._mda import MDAWidget

LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class _GridParametersWidget(QGroupBox):
    valueChanged = Signal()

    def __init__(self, title: str = "Grid Parameters", parent: QWidget | None = None):
        super().__init__(title, parent)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        # row
        self.row_wdg = QWidget()
        row_label = QLabel(text="Rows:")
        row_label.setMaximumWidth(80)
        row_label.setSizePolicy(LBL_SIZEPOLICY)
        self.scan_size_spinBox_r = QSpinBox()
        self.scan_size_spinBox_r.setMinimum(1)
        self.scan_size_spinBox_r.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row_wdg_lay = QHBoxLayout()
        row_wdg_lay.setSpacing(0)
        row_wdg_lay.setContentsMargins(0, 0, 0, 0)
        row_wdg_lay.addWidget(row_label)
        row_wdg_lay.addWidget(self.scan_size_spinBox_r)
        self.row_wdg.setLayout(row_wdg_lay)

        # col
        self.col_wdg = QWidget()
        col_label = QLabel(text="Columns:")
        col_label.setMaximumWidth(80)
        col_label.setSizePolicy(LBL_SIZEPOLICY)
        self.scan_size_spinBox_c = QSpinBox()
        self.scan_size_spinBox_c.setSizePolicy
        self.scan_size_spinBox_c.setMinimum(1)
        self.scan_size_spinBox_c.setAlignment(Qt.AlignmentFlag.AlignCenter)
        col_wdg_lay = QHBoxLayout()
        col_wdg_lay.setSpacing(0)
        col_wdg_lay.setContentsMargins(0, 0, 0, 0)
        col_wdg_lay.addWidget(col_label)
        col_wdg_lay.addWidget(self.scan_size_spinBox_c)
        self.col_wdg.setLayout(col_wdg_lay)

        # overlay
        self.ovl_wdg = QWidget()
        overlap_label = QLabel(text="Overlap (%):")
        overlap_label.setMaximumWidth(100)
        overlap_label.setSizePolicy(LBL_SIZEPOLICY)
        self.overlap_spinBox = QSpinBox()
        self.overlap_spinBox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ovl_wdg_lay = QHBoxLayout()
        ovl_wdg_lay.setSpacing(0)
        ovl_wdg_lay.setContentsMargins(0, 0, 0, 0)
        ovl_wdg_lay.addWidget(overlap_label)
        ovl_wdg_lay.addWidget(self.overlap_spinBox)
        self.ovl_wdg.setLayout(ovl_wdg_lay)

        grid = QGridLayout()
        self.setLayout(grid)
        grid.setSpacing(10)
        grid.setContentsMargins(10, 20, 10, 20)
        grid.addWidget(self.row_wdg, 0, 0)
        grid.addWidget(self.col_wdg, 1, 0)
        grid.addWidget(self.ovl_wdg, 0, 1)

        self.scan_size_spinBox_r.valueChanged.connect(self.valueChanged)
        self.scan_size_spinBox_c.valueChanged.connect(self.valueChanged)

    def ntiles(self) -> int:
        tiles = self.scan_size_spinBox_r.value() * self.scan_size_spinBox_c.value()
        return cast(int, tiles)


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
        self.grid_params = _GridParametersWidget()
        self.return_to_position_x: float | None = None
        self.return_to_position_y: float | None = None

        super().__init__(
            parent=parent, include_run_button=include_run_button, mmcore=mmcore
        )

        # add widget elements
        scroll_layout = cast(QVBoxLayout, self._central_widget.layout())
        scroll_layout.insertWidget(0, self.grid_params)

        self.channel_groupbox.setMinimumHeight(175)

        # groupbox for mda option QCollapsible
        # move Time, Z Stack and Positions in a collapsible
        wdg = QGroupBox(title="MDA Options")
        wdg.setLayout(QVBoxLayout())
        wdg.layout().setSpacing(10)
        wdg.layout().setContentsMargins(10, 10, 10, 10)

        time_coll = _TightCollapsible(title="Time")
        wdg.layout().addWidget(time_coll)
        scroll_layout.removeWidget(self.time_groupbox)
        self.time_groupbox.setTitle("")
        time_coll.addWidget(self.time_groupbox)

        stack_coll = _TightCollapsible(title="Z Stack")
        wdg.layout().addWidget(stack_coll)
        scroll_layout.removeWidget(self.stack_groupbox)
        self.stack_groupbox.setTitle("")
        stack_coll.addWidget(self.stack_groupbox)

        pos_coll = _TightCollapsible(title="Grid Starting Positions")
        wdg.layout().addWidget(pos_coll)
        scroll_layout.removeWidget(self.position_groupbox)
        self.position_groupbox.setTitle("")
        self.position_groupbox.grid_button.hide()
        self.position_groupbox.add_button.clicked.disconnect()
        self.position_groupbox.add_button.clicked.connect(self._add_position)
        self.position_groupbox.remove_button.clicked.disconnect()
        self.position_groupbox.remove_button.clicked.connect(self._remove_position)
        pos_coll.addWidget(self.position_groupbox)

        scroll_layout.insertWidget(2, wdg)

        spacer = QSpacerItem(
            30, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        scroll_layout.addItem(spacer)

        # explorer variables
        self.pixel_size = self._mmc.getPixelSizeUm()

        # connection for scan size
        self.grid_params.valueChanged.connect(self._update_total_time)

    def _set_enabled(self, enabled: bool) -> None:
        super()._set_enabled(enabled)
        self.grid_params.setEnabled(enabled)

    def _on_mda_finished(self) -> None:
        super()._on_mda_finished()
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
        super()._update_total_time(tiles=self.grid_params.ntiles())

    def _add_position(self) -> None:

        if not self._mmc.getXYStageDevice():
            return

        if len(self._mmc.getLoadedDevices()) > 1:
            # idx = self._add_position_row()
            idx = self.position_groupbox._add_position_row()

            for c, ax in enumerate("GXYZ"):
                if ax == "G":
                    count = self.position_groupbox._table.rowCount()
                    item = QTableWidgetItem(f"Grid{count:03d}")
                    item.setData(self.position_groupbox.POS_ROLE, f"Grid{count:03d}")
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                    )
                    self.position_groupbox._table.setItem(idx, c, item)
                    self._rename_positions()
                    continue

                if not self._mmc.getFocusDevice() and ax == "Z":
                    continue

                cur = getattr(self._mmc, f"get{ax}Position")()
                item = QTableWidgetItem(str(cur))
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
                )
                self.position_groupbox._table.setItem(idx, c, item)

        self._update_total_time()

    def _remove_position(self) -> None:
        # remove selected position
        rows = {r.row() for r in self.position_groupbox._table.selectedIndexes()}
        for idx in sorted(rows, reverse=True):
            self.position_groupbox._table.removeRow(idx)
        self._rename_positions()
        self._update_total_time()

    def _rename_positions(self, _: Any = None) -> None:
        """Rename the positions to keep name's correct counter of 3digits."""
        # name arguments to match super method
        for grid_count, r in enumerate(range(self.position_groupbox._table.rowCount())):
            item = self.position_groupbox._table.item(r, 0)
            item_text = item.text()
            item_whatisthis = item.data(self.position_groupbox.POS_ROLE)
            if item_text == item_whatisthis:
                new_name = f"Grid{grid_count:03d}"
            else:
                new_name = item_text
            pos_role = f"Grid{grid_count:03d}"

            item = QTableWidgetItem(new_name)
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
            )
            item.setData(self.position_groupbox.POS_ROLE, pos_role)
            self.position_groupbox._table.setItem(r, 0, item)

    def _get_pos_name(self, row: int) -> str:
        """Get position name from table item's pos_role."""
        item = self.position_groupbox._table.item(row, 0)
        name = str(item.text())
        pos_role = item.data(self.position_groupbox.POS_ROLE)
        return f"{name}_{pos_role}" if pos_role not in name else name

    def _create_grid_coords(self) -> list[Position]:
        """Calculate the grid coordinates for each grid starting position.

        output should be a compatible input to MDASequence stage_positions.
        """
        table = self.position_groupbox._table
        explorer_starting_positions: list[Position] = []
        if self.position_groupbox.isChecked() and table.rowCount() > 0:
            explorer_starting_positions.extend(
                Position(
                    name=self._get_pos_name(r),
                    x=float(table.item(r, 1).text()),
                    y=float(table.item(r, 2).text()),
                    z=(
                        float(table.item(r, 3).text())
                        if self._mmc.getFocusDevice()
                        else None
                    ),
                )
                for r in range(table.rowCount())
            )
        else:
            explorer_starting_positions.append(
                Position(
                    name="Grid001",
                    x=float(self._mmc.getXPosition()),
                    y=float(self._mmc.getYPosition()),
                    z=float(self._mmc.getZPosition())
                    if self._mmc.getFocusDevice()
                    else None,
                )
            )

        # calculate initial scan position
        _, _, width, height = self._mmc.getROI(self._mmc.getCameraDevice())

        # prepare overlaps and shifts
        scan_size_r = self.grid_params.scan_size_spinBox_r.value()
        scan_size_c = self.grid_params.scan_size_spinBox_c.value()
        self.pixel_size = self._mmc.getPixelSizeUm()

        overlap_percentage = self.grid_params.overlap_spinBox.value()
        overlap_px_w = width - (width * overlap_percentage) / 100
        overlap_px_h = height - (height * overlap_percentage) / 100
        move_x = (width / 2) * (scan_size_c - 1) - overlap_px_w
        move_x = self.pixel_size * (move_x + width)

        move_y = (height / 2) * (scan_size_r - 1) - overlap_px_h
        move_y = self.pixel_size * (move_y + height)

        # calculate position increments depending on pixel size
        if overlap_percentage > 0:
            increment_x = overlap_px_w * self.pixel_size
            increment_y = overlap_px_h * self.pixel_size
        else:
            increment_x = width * self.pixel_size
            increment_y = height * self.pixel_size

        output: list[Position] = []
        for st_pos in explorer_starting_positions:
            # XXX: why are we setting this in a for loop?
            self.return_to_position_x = st_pos.x
            self.return_to_position_y = st_pos.y

            # to match position coordinates with center of the image
            x_pos = cast(float, st_pos.x) - move_x
            y_pos = cast(float, st_pos.y) + move_y

            pos_count = 0
            for r in range(scan_size_r):
                if r % 2:  # for odd rows
                    col = scan_size_c - 1
                    for c in range(scan_size_c):
                        if c == 0:
                            y_pos -= increment_y
                        name = f"{st_pos.name}_Pos{pos_count:03d}"
                        output.append(Position(name=name, x=x_pos, y=y_pos, z=st_pos.z))
                        if col > 0:
                            col -= 1
                            x_pos -= increment_x
                        pos_count += 1
                else:  # for even rows
                    for c in range(scan_size_c):
                        if r > 0 and c == 0:
                            y_pos -= increment_y
                        name = f"{st_pos.name}_Pos{pos_count:03d}"
                        output.append(Position(name=name, x=x_pos, y=y_pos, z=st_pos.z))
                        if c < scan_size_c - 1:
                            x_pos += increment_x
                        pos_count += 1

        return output

    def get_state(self) -> MDASequence:  # sourcery skip: merge-dict-assign
        """Get current state of widget and build a useq.MDASequence.

        Returns
        -------
        useq.MDASequence
        """
        z = self.stack_groupbox.value() if self.stack_groupbox.isChecked() else None
        time = self.time_groupbox.value() if self.time_groupbox.isChecked() else None
        return MDASequence(
            axis_order=self.buttons_wdg.acquisition_order_comboBox.currentText(),
            channels=self.channel_groupbox.value(),
            stage_positions=self._create_grid_coords(),
            z_plan=z,
            time_plan=time,
        )

    def _on_run_clicked(self) -> None:

        self.pixel_size = self._mmc.getPixelSizeUm()

        if self._mmc.getPixelSizeUm() <= 0:
            warnings.warn("Pixel Size not set.")
            return

        super()._on_run_clicked()


class _TightCollapsible(QCollapsible):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(title=title, parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    mmc = CMMCorePlus.instance()
    mmc.loadSystemConfiguration()
    app = QApplication(sys.argv)
    win = SampleExplorerWidget(include_run_button=True)
    win.show()
    sys.exit(app.exec_())
