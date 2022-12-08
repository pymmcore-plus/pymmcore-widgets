from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from pymmcore_widgets._channel_table_widget import ChannelTable
from pymmcore_widgets._general_mda_widgets import (
    _MDAControlButtons,
    _MDAPositionTable,
    _MDATimeLabel,
)
from pymmcore_widgets._time_plan_widget import TimePlanWidget
from pymmcore_widgets._zstack_widget import ZStackWidget

from .._util import _select_output_unit

LBL_SIZEPOLICY = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)


class _MDAWidgetGui(QWidget):
    """Just the UI portion of the MDA widget. Runtime logic in MDAWidget."""

    def __init__(self, *, parent: QWidget | None = None):
        super().__init__(parent=parent)

        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(10)
        self.layout().setContentsMargins(10, 10, 10, 10)

        # general scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._wdg = self._create_gui()
        self._scroll.setWidget(self._wdg)
        self.layout().addWidget(self._scroll)

        self.time_lbl = _MDATimeLabel()
        self.layout().addWidget(self.time_lbl)

        # acq order and buttons wdg
        self.buttons_wdg = _MDAControlButtons()
        self.layout().addWidget(self.buttons_wdg)

    def _create_gui(self) -> QWidget:
        wdg = QWidget()
        wdg_layout = QVBoxLayout()
        wdg_layout.setSpacing(20)
        wdg_layout.setContentsMargins(10, 10, 10, 10)
        wdg.setLayout(wdg_layout)

        self.channel_groupbox = ChannelTable()
        self.channel_groupbox.valueChanged.connect(self._enable_run_btn)
        wdg_layout.addWidget(self.channel_groupbox)

        self.time_groupbox = TimePlanWidget()
        self.time_groupbox.setChecked(False)
        wdg_layout.addWidget(self.time_groupbox)

        self.stack_groupbox = ZStackWidget()
        self.stack_groupbox.setChecked(False)
        wdg_layout.addWidget(self.stack_groupbox)

        self.stage_pos_groupbox = _MDAPositionTable(["Pos", "X", "Y", "Z"])
        wdg_layout.addWidget(self.stage_pos_groupbox)

        return wdg

    def _enable_run_btn(self) -> None:
        self.buttons_wdg.run_button.setEnabled(
            self.channel_groupbox._table.rowCount() > 0
        )

    def _update_total_time(self, *, tiles: int = 1) -> None:
        """Update the minimum total acquisition time info."""
        # channel
        exp: list[float] = [
            e for c in self.channel_groupbox.value() if (e := c.get("exposure"))
        ]

        # time
        if self.time_groupbox.isChecked():
            val = self.time_groupbox.value()
            timepoints = val["loops"]
            interval = val["interval"].total_seconds()
        else:
            timepoints = 1
            interval = -1.0

        # z stack
        n_z_images = (
            self.stack_groupbox.n_images() if self.stack_groupbox.isChecked() else 1
        )

        # positions
        if self.stage_pos_groupbox.isChecked():
            n_pos = self.stage_pos_groupbox.stage_tableWidget.rowCount() or 1
        else:
            n_pos = 1

        # acq time per timepoint
        time_chs: float = 0.0  # s
        for e in exp:
            time_chs = time_chs + ((e / 1000) * n_z_images * n_pos * tiles)

        min_aq_tp, unit_1 = _select_output_unit(time_chs)

        addition_time = 0.0
        effective_interval = 0.0
        if interval >= time_chs:
            effective_interval = float(interval) - time_chs  # s
            addition_time = effective_interval * timepoints  # s

        min_tot_time, unit_4 = _select_output_unit(
            (time_chs * timepoints) + addition_time - effective_interval
        )

        self.time_groupbox.setWarningVisible(-1 < interval < time_chs)

        t_per_tp_msg = ""
        tot_acq_msg = f"Minimum total acquisition time: {min_tot_time:.4f} {unit_4}.\n"
        if self.time_groupbox.isChecked():
            t_per_tp_msg = (
                f"Minimum acquisition time per timepoint: {min_aq_tp:.4f} {unit_1}."
            )
        self.time_lbl._total_time_lbl.setText(f"{tot_acq_msg}{t_per_tp_msg}")


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = _MDAWidgetGui()
    win.show()
    sys.exit(app.exec_())
