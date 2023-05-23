from __future__ import annotations

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import QSize, Qt, Signal
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
from superqt.utils import signals_blocked


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
        self.acquisition_order_comboBox.addItems(
            ["tpgcz", "tpgzc", "tpcgz", "tpzgc", "pgtzc", "ptzgc", "ptcgz", "pgtcz"]
        )
        acq_wdg_layout.addWidget(acquisition_order_label)
        acq_wdg_layout.addWidget(self.acquisition_order_comboBox)

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


class _ZDeviceSelector(QWidget):
    valueChanged = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
        include_none_in_list: bool = False,
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._with_none = include_none_in_list

        wdg_layout = QHBoxLayout()
        wdg_layout.setContentsMargins(5, 5, 5, 5)
        wdg_layout.setSpacing(5)
        self.setLayout(wdg_layout)
        z_dev_label = QLabel("Z Device:")
        z_dev_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._z_dev_combo = QComboBox()
        self._z_dev_combo.currentTextChanged.connect(self.valueChanged.emit)
        wdg_layout.addWidget(z_dev_label)
        wdg_layout.addWidget(self._z_dev_combo)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self.destroyed.connect(self._disconnect)

        self._refresh()

    def _on_sys_cfg_loaded(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        items = list(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
        if self._with_none:
            items = ["None", *items]
        with signals_blocked(self._z_dev_combo):
            self._z_dev_combo.clear()
            self._z_dev_combo.addItems(items)
            self._z_dev_combo.setCurrentText(self._mmc.getFocusDevice() or items[0])

    def value(self) -> str:
        """Return the currently selected Z device."""
        return str(self._z_dev_combo.currentText())

    def set_value(self, value: str) -> None:
        """Set the which Z device to use."""
        self._z_dev_combo.setCurrentText(value)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
