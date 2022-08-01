from typing import Optional, Union

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QWidget

from ._device_widget import StateDeviceWidget
from ._util import ComboMessageBox


class ObjectivesWidget(QWidget):
    """Objective selector widget.

    Parameters
    ----------
    objective_device : Optional[str]
        Device label for the objective device, by default will be guessed using
        `mmc.guessObjectiveDevices`, and a dialog will be presented if there are
        multiples
    parent : Optional[QWidget]
        Optional parent widget, by default None
    """

    def __init__(
        self,
        objective_device: str = None,  # type: ignore
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None
    ):
        super().__init__(parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._objective_device = objective_device or self._guess_objective_device()
        self._combo = self._create_objective_combo(objective_device)

        lbl = QLabel("Objectives:")
        lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(lbl)
        self.layout().addWidget(self._combo)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self.destroyed.connect(self._disconnect_from_core)
        self._on_sys_cfg_loaded()

    def _disconnect_from_core(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)

    def _on_sys_cfg_loaded(self) -> None:
        """When config is loaded, check objective still exists, recreate combo."""
        loaded = self._mmc.getLoadedDevices()
        if self._objective_device not in loaded:
            self._objective_device = None
        if len(loaded) > 1:
            if not self._objective_device:
                self._objective_device = self._guess_objective_device()
            self._clear_previous_device_widget()
            self._combo = self._create_objective_combo(self._objective_device)
            self.layout().addWidget(self._combo)

    def _guess_objective_device(self) -> Union[str, None]:
        """Try to update the list of objective choices.

        1. get a list of potential objective devices from pymmcore
        2. if there is only one, use it, if there are >1, show a dialog box
        """
        candidates = self._mmc.guessObjectiveDevices()
        if len(candidates) == 1:
            return candidates[0]
        elif candidates:
            dialog = ComboMessageBox(candidates, "Select Objective Device:", self)
            if dialog.exec_() == dialog.DialogCode.Accepted:
                return dialog.currentText()
        return None

    def _clear_previous_device_widget(self) -> None:
        self._combo.setParent(None)
        self._combo.deleteLater()

    def _create_objective_combo(
        self, device_label: Union[str, None]
    ) -> Union[StateDeviceWidget, QComboBox]:
        if device_label:
            combo = _ObjectiveStateWidget(device_label, mmcore=self._mmc)
            combo.setMinimumWidth(285)
            combo._combo.currentIndexChanged.connect(self._on_obj_changed)
        else:
            combo = QComboBox()
            combo.setEnabled(False)
        return combo

    def _on_obj_changed(self) -> None:
        self._mmc.events.pixelSizeChanged.emit(self._mmc.getPixelSizeUm() or 0.0)


class _ObjectiveStateWidget(StateDeviceWidget):
    """Subclass of StateDeviceWidget.

    Drops/raises stage when changing objective.
    """

    # This logic tries to makes it so that that objective drops before changing...
    # It should be made clear, however, that this *ONLY* works when one controls the
    # objective through the widget, and not if one directly controls it through core

    # TODO: this should be a preference, not a requirement.

    def _pre_change_hook(self) -> None:
        # drop focus motor
        zdev = self._mmc.getFocusDevice()
        self._previous_z = self._mmc.getZPosition()
        self._mmc.setPosition(zdev, 0)
        self._mmc.waitForDevice(zdev)

    def _post_change_hook(self) -> None:
        # raise focus motor
        self._mmc.waitForDevice(self._device_label)
        zdev = self._mmc.getFocusDevice()
        self._mmc.setPosition(zdev, self._previous_z)
        self._mmc.waitForDevice(zdev)
