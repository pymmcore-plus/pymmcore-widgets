from __future__ import annotations

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import QSize, Qt
from qtpy.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QWidget,
)
from superqt.fonticon import icon


class _MDAControlButtons(QWidget):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)

        self._mmc = CMMCorePlus.instance()
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

        self._create_btns_gui()

    def _create_btns_gui(self) -> None:
        self.setMinimumWidth(300)
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

        btn_sizepolicy = QSizePolicy(
            QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed
        )
        min_width = 130
        icon_size = 40
        self.run_button = QPushButton(text="Run")
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

    def _on_mda_started(self) -> None:
        self.run_button.hide()
        self.pause_button.show()
        self.cancel_button.show()

    def _on_mda_finished(self) -> None:
        self.run_button.show()
        self.pause_button.hide()
        self.cancel_button.hide()
        self.pause_button.setText("Pause")

    def _on_mda_paused(self, paused: bool) -> None:
        self.pause_button.setText("Resume" if paused else "Pause")


class _AcquisitionOrderWidget(QWidget):
    def __init__(self, *, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setMaximumWidth(300)
        acq_wdg_layout = QHBoxLayout()
        self.setLayout(acq_wdg_layout)
        acquisition_order_label = QLabel(text="Acquisition Order:")
        acquisition_order_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self.acquisition_order_comboBox = QComboBox()
        self.acquisition_order_comboBox.setMinimumWidth(100)
        self.acquisition_order_comboBox.addItems(
            ["tpgcz", "tpgzc", "tpcgz", "tpzgc", "pgtzc", "ptzgc", "ptcgz", "pgtcz"]
        )
        acq_wdg_layout.addWidget(acquisition_order_label)
        acq_wdg_layout.addWidget(self.acquisition_order_comboBox)


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


class _SaveLoadSequenceWidget(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._save_button = QPushButton("Save")
        self._load_button = QPushButton("Load")

        self._save_button.setMaximumWidth(self._save_button.sizeHint().width())
        self._load_button.setMaximumWidth(self._load_button.sizeHint().width())

        self.setLayout(QHBoxLayout())

        spacer = QSpacerItem(1, 1, QSizePolicy.Expanding, QSizePolicy.Minimum)

        self.layout().addItem(spacer)
        self.layout().addWidget(self._save_button)
        self.layout().addWidget(self._load_button)

        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(10)
