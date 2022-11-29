from __future__ import annotations

from qtpy.QtCore import Qt
from qtpy.QtWidgets import QScrollArea, QSizePolicy, QVBoxLayout, QWidget

from pymmcore_widgets._general_mda_widgets import (
    _MDAChannelTable,
    _MDAControlButtons,
    _MDAPositionTable,
    _MDATimeLabel,
    _MDATimeWidget,
)
from pymmcore_widgets._zstack_widget import ZStackWidget

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

        self.channel_groupbox = _MDAChannelTable()
        wdg_layout.addWidget(self.channel_groupbox)
        self.channel_groupbox.channel_tableWidget.model().rowsInserted.connect(
            self._enable_run_btn
        )
        self.channel_groupbox.channel_tableWidget.model().rowsRemoved.connect(
            self._enable_run_btn
        )

        self.time_groupbox = _MDATimeWidget()
        wdg_layout.addWidget(self.time_groupbox)

        self.stack_groupbox = ZStackWidget()
        self.stack_groupbox.setChecked(False)
        wdg_layout.addWidget(self.stack_groupbox)

        self.stage_pos_groupbox = _MDAPositionTable(["Pos", "X", "Y", "Z"])
        wdg_layout.addWidget(self.stage_pos_groupbox)

        return wdg

    def _enable_run_btn(self) -> None:
        self.buttons_wdg.run_button.setEnabled(
            self.channel_groupbox.channel_tableWidget.rowCount() > 0
        )


if __name__ == "__main__":
    import sys

    from qtpy.QtWidgets import QApplication

    app = QApplication(sys.argv)
    win = _MDAWidgetGui()
    win.show()
    sys.exit(app.exec_())
