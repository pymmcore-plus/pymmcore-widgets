from __future__ import annotations

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.fonticon import icon


class _MDAPositionTable(QGroupBox):
    def __init__(self, header: list[str], *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()

        self.header = header

        self._create_pos_gui()

    def _create_pos_gui(self) -> None:

        self.setTitle("Stage Positions")

        self.setCheckable(True)
        self.setChecked(False)

        group_layout = QHBoxLayout()
        group_layout.setSpacing(15)
        group_layout.setContentsMargins(10, 10, 10, 10)
        self.setLayout(group_layout)

        # table
        self.stage_tableWidget = QTableWidget()
        self.stage_tableWidget.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        hdr = self.stage_tableWidget.horizontalHeader()
        hdr.setSectionResizeMode(hdr.ResizeMode.Stretch)
        self.stage_tableWidget.verticalHeader().setVisible(False)
        self.stage_tableWidget.setTabKeyNavigation(True)
        self.stage_tableWidget.setColumnCount(4)
        self.stage_tableWidget.setRowCount(0)
        self.stage_tableWidget.setHorizontalHeaderLabels(self.header)
        group_layout.addWidget(self.stage_tableWidget)

        # buttons
        wdg = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(10)
        layout.setContentsMargins(0, 0, 0, 0)
        wdg.setLayout(layout)

        btn_sizepolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        min_size = 100
        self.add_pos_button = QPushButton(text="Add")
        self.add_pos_button.setMinimumWidth(min_size)
        self.add_pos_button.setSizePolicy(btn_sizepolicy)
        self.remove_pos_button = QPushButton(text="Remove")
        self.remove_pos_button.setMinimumWidth(min_size)
        self.remove_pos_button.setSizePolicy(btn_sizepolicy)
        self.clear_pos_button = QPushButton(text="Clear")
        self.clear_pos_button.setMinimumWidth(min_size)
        self.clear_pos_button.setSizePolicy(btn_sizepolicy)
        self.grid_button = QPushButton(text="Grid")
        self.grid_button.setMinimumWidth(min_size)
        self.grid_button.setSizePolicy(btn_sizepolicy)
        self.go = QPushButton(text="Go")
        self.go.clicked.connect(self._move_to_position)
        self.go.setMinimumWidth(min_size)
        self.go.setSizePolicy(btn_sizepolicy)

        spacer = QSpacerItem(
            10, 0, QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding
        )

        layout.addWidget(self.add_pos_button)
        layout.addWidget(self.remove_pos_button)
        layout.addWidget(self.clear_pos_button)
        layout.addWidget(self.grid_button)
        layout.addWidget(self.go)
        layout.addItem(spacer)

        group_layout.addWidget(wdg)

    def _move_to_position(self) -> None:
        if not self._mmc.getXYStageDevice():
            return
        curr_row = self.stage_tableWidget.currentRow()
        x_val = self.stage_tableWidget.item(curr_row, 1).text()
        y_val = self.stage_tableWidget.item(curr_row, 2).text()
        z_val = self.stage_tableWidget.item(curr_row, 3).text()
        self._mmc.setXYPosition(float(x_val), float(y_val))
        self._mmc.setPosition(self._mmc.getFocusDevice(), float(z_val))


class _MDAControlButtons(QWidget):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)

        self._create_btns_gui()

    def _create_btns_gui(self) -> None:

        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        wdg_layout = QHBoxLayout()
        wdg_layout.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        wdg_layout.setSpacing(10)
        wdg_layout.setContentsMargins(10, 5, 10, 10)
        self.setLayout(wdg_layout)

        acq_wdg = QWidget()
        acq_wdg_layout = QHBoxLayout()
        acq_wdg_layout.setSpacing(0)
        acq_wdg_layout.setContentsMargins(0, 0, 0, 0)
        acq_wdg.setLayout(acq_wdg_layout)
        acquisition_order_label = QLabel(text="Acquisition Order:")
        acquisition_order_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.acquisition_order_comboBox = QComboBox()
        self.acquisition_order_comboBox.setMinimumWidth(100)
        self.acquisition_order_comboBox.addItems(["tpcz", "tpzc", "ptzc", "ptcz"])
        acq_wdg_layout.addWidget(acquisition_order_label)
        acq_wdg_layout.addWidget(self.acquisition_order_comboBox)

        btn_sizepolicy = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        min_width = 130
        icon_size = 40
        self.run_button = QPushButton(text="Run")
        self.run_button.setEnabled(False)
        self.run_button.setMinimumWidth(min_width)
        self.run_button.setStyleSheet("QPushButton { text-align: center; }")
        self.run_button.setSizePolicy(btn_sizepolicy)
        self.run_button.setIcon(icon(MDI6.play_circle_outline, color=(0, 255, 0)))
        self.run_button.setIconSize(QSize(icon_size, icon_size))
        self.pause_button = QPushButton("Pause")
        self.pause_button.setStyleSheet("QPushButton { text-align: center; }")
        self.pause_button.setSizePolicy(btn_sizepolicy)
        self.pause_button.setIcon(icon(MDI6.pause_circle_outline, color="green"))
        self.pause_button.setIconSize(QSize(icon_size, icon_size))
        self.pause_button.hide()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setStyleSheet("QPushButton { text-align: center; }")
        self.cancel_button.setSizePolicy(btn_sizepolicy)
        self.cancel_button.setIcon(icon(MDI6.stop_circle_outline, color="magenta"))
        self.cancel_button.setIconSize(QSize(icon_size, icon_size))
        self.cancel_button.hide()

        spacer = QSpacerItem(
            10, 10, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )

        wdg_layout.addWidget(acq_wdg)
        wdg_layout.addItem(spacer)
        wdg_layout.addWidget(self.run_button)
        wdg_layout.addWidget(self.pause_button)
        wdg_layout.addWidget(self.cancel_button)

    def _on_mda_paused(self, paused: bool) -> None:
        self.pause_button.setText("Resume" if paused else "Pause")


class _MDATimeLabel(QWidget):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        wdg_lay = QHBoxLayout()
        wdg_lay.setSpacing(5)
        wdg_lay.setContentsMargins(10, 5, 10, 5)
        wdg_lay.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.setLayout(wdg_lay)

        self._total_time_lbl = QLabel()
        self._total_time_lbl.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self._total_time_lbl.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        wdg_lay.addWidget(self._total_time_lbl)
