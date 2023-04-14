from __future__ import annotations

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
    QVBoxLayout,
    QWidget,
)
from superqt import QCollapsible

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

    def value(self) -> dict[str, Any]:
        return {
            "rows": self.scan_size_spinBox_r.value(),
            "columns": self.scan_size_spinBox_c.value(),
            "overlap": (self.overlap_spinBox.value(), self.overlap_spinBox.value()),
            "mode": "row_wise_snake",
            "relative_to": "center",
        }


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
        _mmcore = mmcore or CMMCorePlus.instance()

        super().__init__(
            parent=parent, include_run_button=include_run_button, mmcore=_mmcore
        )

        self.grid_params = _GridParametersWidget()
        self.return_to_position_x: float | None = None
        self.return_to_position_y: float | None = None

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
        self.position_groupbox._advanced_cbox.setChecked(True)
        self.position_groupbox._advanced_cbox.hide()
        self.position_groupbox._table.setColumnHidden(4, True)
        self.position_groupbox.add_button.clicked.disconnect()
        self.position_groupbox.add_button.clicked.connect(self._add_pos)
        pos_coll.addWidget(self.position_groupbox)

        scroll_layout.insertWidget(2, wdg)

        spacer = QSpacerItem(
            30, 10, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )
        scroll_layout.addItem(spacer)

        # connection for scan size
        self.grid_params.valueChanged.connect(self._update_grid_plan)

    def _set_enabled(self, enabled: bool) -> None:
        super()._set_enabled(enabled)
        self.grid_params.setEnabled(enabled)

    def _add_pos(self) -> None:
        self.position_groupbox._add_position()
        for r in range(self.position_groupbox._table.rowCount()):
            self.position_groupbox._add_grid_plan(
                self.grid_params.value(), r  # type: ignore
            )
        super()._update_total_time()

    def _update_grid_plan(self) -> None:
        for r in range(self.position_groupbox._table.rowCount()):
            self.position_groupbox._add_grid_plan(
                self.grid_params.value(), r  # type: ignore
            )
        super()._update_total_time()


class _TightCollapsible(QCollapsible):
    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(title=title, parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self.layout().setSpacing(0)
        self.layout().setContentsMargins(0, 0, 0, 0)
