from __future__ import annotations

from typing import TYPE_CHECKING

from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QWidget,
)

if TYPE_CHECKING:
    from typing_extensions import TypedDict

    class AFValueDict(TypedDict, total=False):
        """Autofocus dictionary."""

        axes: tuple[str, ...] | None
        autofocus_device_name: str | None
        autofocus_motor_offset: float | None


class _AutofocusZDeviceWidget(QWidget):
    """Widget to select the hardware autofocus z device."""

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._af_checkbox = QCheckBox()
        self._af_checkbox.toggled.connect(self._on_checkbox_toggled)

        self._af_label = QLabel()
        self._af_label.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._af_combo = QComboBox()
        self._af_combo.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self._selector_wdg = QWidget()
        self._selector_wdg.setLayout(QHBoxLayout())
        self._selector_wdg.layout().setSpacing(5)
        self._selector_wdg.layout().setContentsMargins(0, 0, 0, 0)
        self._selector_wdg.layout().addWidget(self._af_label)
        self._selector_wdg.layout().addWidget(self._af_combo)

        self._update_labels()

        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(30)
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._af_checkbox)
        self.layout().addWidget(self._selector_wdg)

        self.setMinimumHeight(self.sizeHint().height())

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self.destroyed.connect(self._disconnect)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self._update_labels()
        self._af_checkbox.setEnabled(bool(self._mmc.getAutoFocusDevice()))
        self._on_checkbox_toggled(self._af_checkbox.isChecked())
        stage_devices = list(self._mmc.getLoadedDevicesOfType(DeviceType.StageDevice))
        self._af_combo.clear()
        self._af_combo.addItems(stage_devices)

        if len(stage_devices) == 1:
            return

        # set the autofocus device to the first stage device
        # that is not the current focus device
        for dev in stage_devices:
            if dev != self._mmc.getFocusDevice():
                self._af_combo.setCurrentText(dev)
                break

    def _update_labels(self) -> None:
        af_device = self._mmc.getAutoFocusDevice() or "Autofocus"
        self._af_checkbox.setText(f"Use {af_device}")
        self._af_label = QLabel(f"{af_device} Z Device:")

    def _on_property_changed(self, device: str, prop: str, value: str) -> None:
        if device != "Core" or prop != "AutoFocus":
            return
        self._af_checkbox.setChecked(False)
        self._af_checkbox.setEnabled(bool(value))
        self._update_labels()

    def _on_checkbox_toggled(self, checked: bool) -> None:
        if not self._mmc.getAutoFocusDevice():
            self._af_checkbox.setChecked(False)
            self._selector_wdg.hide()
        else:
            self._selector_wdg.show() if checked else self._selector_wdg.hide()

    def value(self) -> AFValueDict:
        """Return in a dict the autofocus checkbox state and the autofocus z_device."""
        value: AFValueDict = {"autofocus_device_name": None}
        if self._should_use_autofocus():
            value = {"autofocus_device_name": self._af_z_device_name()}
            if self._af_z_device_name():
                value["axes"] = ("t", "p", "g")
        return value

    def setValue(self, value: str | AFValueDict | None) -> None:
        """Set the autofocus checkbox state and the autofocus z_device to use."""
        if not self._mmc.getAutoFocusDevice():
            self._selector_wdg.hide()
            return

        af_dev_name: str | None = (
            value
            if isinstance(value, str) or value is None
            else value.get("autofocus_device_name", None)
        )

        self._af_checkbox.setChecked(af_dev_name is not None)
        if af_dev_name is not None:
            self._af_combo.setCurrentText(af_dev_name)

    def _af_z_device_name(self) -> str | None:
        return self._af_combo.currentText() if self._should_use_autofocus() else None

    def _should_use_autofocus(self) -> bool:
        return bool(self._af_checkbox.isChecked() and self._mmc.getAutoFocusDevice())

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
