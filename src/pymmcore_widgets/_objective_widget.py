from __future__ import annotations

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QLabel, QSizePolicy, QWidget

from ._device_widget import StateDeviceWidget
from ._util import guess_objective_or_prompt


class ObjectivesWidget(QWidget):
    """A QComboBox-based Widget to select the microscope objective.

    Parameters
    ----------
    objective_device : str | None
        Device label for the micromanager objective device. By default, it will be
        guessed using the
        [`CMMCorePlus.guessObjectiveDevices`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.guessObjectiveDevices]
        method and a choice dialog will be presented if there are multiple options.
        This method looks for a micromanager device matching the default regex
        `re.compile("(.+)?(nosepiece|obj(ective)?)(turret)?s?", re.IGNORECASE)`.
        To change the search pattern, set
        [`CMMCorePlus.objective_device_pattern`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.objective_device_pattern].
    parent : QWidget | None
        Optional parent widget, by default None
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        objective_device: str | None = None,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)
        self._mmc = mmcore or CMMCorePlus.instance()
        self._objective_device = objective_device or guess_objective_or_prompt(
            parent=self
        )
        self._combo = self._create_objective_combo(objective_device)

        lbl = QLabel("Objectives:")
        lbl.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(lbl)
        self.layout().addWidget(self._combo)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)
        self.destroyed.connect(self._disconnect)
        self._on_sys_cfg_loaded()

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)

    def _on_sys_cfg_loaded(self) -> None:
        """When config is loaded, check objective still exists, recreate combo."""
        loaded = self._mmc.getLoadedDevices()
        if self._objective_device not in loaded:
            self._objective_device = None
        if len(loaded) > 1:
            if not self._objective_device:
                self._objective_device = guess_objective_or_prompt(parent=self)
            self._combo.setParent(QWidget())
            self._combo = self._create_objective_combo(self._objective_device)
            self.layout().addWidget(self._combo)

    def _create_objective_combo(
        self, device_label: str | None
    ) -> StateDeviceWidget | QComboBox:
        if device_label:
            combo = (
                _ObjectiveStateWidget(device_label, parent=self, mmcore=self._mmc)
                if self._mmc.getFocusDevice()
                else StateDeviceWidget(device_label, parent=self, mmcore=self._mmc)
            )
            combo._combo.currentIndexChanged.connect(self._on_obj_changed)
        else:
            combo = QComboBox(parent=self)
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
