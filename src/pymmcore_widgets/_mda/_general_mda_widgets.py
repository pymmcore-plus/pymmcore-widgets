from __future__ import annotations

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QCheckBox,
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


class _AutofocusZDeviceWidget(QWidget):
    valueChanged = Signal(dict)

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._autofocus_device: str = self._mmc.getAutoFocusDevice() or ""

        layout = QHBoxLayout()
        layout.setSpacing(30)
        layout.setContentsMargins(0, 0, 0, 0)
        self.setLayout(layout)

        self._autofocus_checkbox = QCheckBox(
            f"Use {self._autofocus_device or 'Autofocus Device'}"
        )
        self._autofocus_checkbox.toggled.connect(self._on_checkbox_toggled)

        self._selector_wdg = QWidget()
        _selector_wdg_layout = QHBoxLayout()
        _selector_wdg_layout.setSpacing(5)
        _selector_wdg_layout.setContentsMargins(0, 0, 0, 0)
        self._selector_wdg.setLayout(_selector_wdg_layout)
        self._autofocus_label = QLabel(f"{self._autofocus_device} Z Device:")
        self._autofocus_label.setSizePolicy(
            QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed
        )
        self._autofocus_device_combo = QComboBox()
        self._autofocus_device_combo.currentTextChanged.connect(self._on_combo_changed)
        self._autofocus_device_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        _selector_wdg_layout.addWidget(self._autofocus_label)
        _selector_wdg_layout.addWidget(self._autofocus_device_combo)

        layout.addWidget(self._autofocus_checkbox)
        layout.addWidget(self._selector_wdg)

        self.setMinimumHeight(self.sizeHint().height())

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self._autofocus_device = self._mmc.getAutoFocusDevice() or ""
        self._autofocus_checkbox.setText(
            f"Use {self._autofocus_device or 'Autofocus Device'}"
        )
        self._autofocus_label = QLabel(f"{self._autofocus_device} Z Device:")
        self._autofocus_checkbox.setEnabled(bool(self._mmc.getAutoFocusDevice()))
        self._on_checkbox_toggled(self._autofocus_checkbox.isChecked())
        items = list(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
        self._autofocus_device_combo.clear()
        self._autofocus_device_combo.addItems(items)

        if len(items) == 1:
            return

        for i in items:
            if i != self._mmc.getFocusDevice():
                self._autofocus_device_combo.setCurrentText(i)
                break

    def _on_property_changed(self, device: str, prop: str, value: str) -> None:
        if device != "Core" and prop != "Autofocus":
            return
        self._autofocus_checkbox.setChecked(False)
        self._autofocus_checkbox.setEnabled(bool(value))

        self._autofocus_device = self._mmc.getAutoFocusDevice() or ""
        self._autofocus_checkbox.setText(
            f"Use {self._autofocus_device or 'Autofocus Device'}"
        )
        self._autofocus_label = QLabel(f"{self._autofocus_device} Z Device:")

    def _on_checkbox_toggled(self, checked: bool) -> None:
        if not self._mmc.getAutoFocusDevice():
            self._autofocus_checkbox.setChecked(False)
            self._selector_wdg.hide()
        else:
            self._selector_wdg.show() if checked else self._selector_wdg.hide()
        self.valueChanged.emit(self.value())

    def _on_combo_changed(self, z_autofocus_device: str) -> None:
        self.valueChanged.emit(self.value())

    def value(self) -> dict[str, bool | str | None]:
        """Return in a dict the autofocus checkbox state and the autofocus z_device."""
        return {
            "z_device": (
                self._autofocus_device_combo.currentText()
                if self._autofocus_checkbox.isChecked()
                and self._mmc.getAutoFocusDevice()
                else None
            ),
            "use_one_shot_focus": (
                self._autofocus_checkbox.isChecked()
                if self._mmc.getAutoFocusDevice()
                else False
            ),
        }

    def setValue(self, value: dict[str, bool | str | None]) -> None:
        """Set the autofocus checkbox state and the autofocus z_device to use."""
        if not self._mmc.getAutoFocusDevice():
            self._selector_wdg.hide()
            return

        self._autofocus_checkbox.setChecked(value.get("use_one_shot_focus", False))
        if value.get("z_device") is not None:
            self._autofocus_device_combo.setCurrentText(value.get("z_device"))

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
