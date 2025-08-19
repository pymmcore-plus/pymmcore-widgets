from __future__ import annotations

import warnings

from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QWidget
from superqt.utils import signals_blocked

from pymmcore_widgets._util import block_core

NO_MATCH = "<no match>"


class PresetsWidget(QWidget):
    """A Widget to create a QCombobox containing the presets of the specified group.

    Parameters
    ----------
    group : str
        Group name.
    parent : QWidget | None
        Optional parent widget. By default, None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self,
        group: str,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)

        self._mmc = mmcore or CMMCorePlus.instance()

        self._group = group

        if self._group not in self._mmc.getAvailableConfigGroups():
            raise ValueError(f"{self._group} group does not exist.")

        self._presets = list(self._mmc.getAvailableConfigs(self._group))

        if not self._presets:
            raise ValueError(f"{self._group} group does not have presets.")

        # getting (dev, prop) of the group using the first preset
        # since they must be all the same
        self.dev_prop = self._get_preset_dev_prop(self._group, self._presets[0])

        self._combo = QComboBox()
        self._combo.currentTextChanged.connect(self._update_tooltip)
        self._combo.addItems(self._presets)
        self._combo.setCurrentText(self._mmc.getCurrentConfig(self._group))

        self._update_if_props_not_match_preset()

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._combo)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        self._combo.textActivated.connect(self._on_text_activate)

        self._mmc.events.configSet.connect(self._on_cfg_set)
        self._mmc.events.systemConfigurationLoaded.connect(self._refresh)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        self._mmc.events.configDeleted.connect(self._on_preset_deleted)
        self._mmc.events.configGroupDeleted.connect(self._on_group_deleted)
        self._mmc.events.configDefined.connect(self._on_new_group_preset)

        self.destroyed.connect(self._disconnect)

        self._delete_presets_with_different_properties()

    def _delete_presets_with_different_properties(self) -> None:
        """Prevent the group to have presets containing different properties."""
        for preset in self._presets:
            if preset == self._presets[0]:
                continue

            dpv = [
                (k[0], k[1], k[2]) for k in self._mmc.getConfigData(self._group, preset)
            ]
            d, v, p = dpv[0]
            self._on_new_group_preset(self._group, preset, d, p, v)

            self._presets = list(self._mmc.getAvailableConfigs(self._group))

    def _on_text_activate(self, text: str) -> None:
        # used if there is only 1 preset and you want to set it
        if text != NO_MATCH:
            self._mmc.setConfig(self._group, text)

    def _on_combo_changed(self, text: str) -> None:
        if text != NO_MATCH:
            self._mmc.setConfig(self._group, text)

    def _update_if_props_not_match_preset(self) -> None:
        if not self._mmc.getAvailableConfigs(self._group):
            return
        for preset in self._presets:
            _set_combo = True
            for dev, prop, value in self._mmc.getConfigData(self._group, preset):
                cache_value = self._mmc.getPropertyFromCache(dev, prop)
                if cache_value != value:
                    _set_combo = False
                    break
            if _set_combo:
                # remove NO_MATCH if it exists
                no_match_index = self._combo.findText(NO_MATCH)
                if no_match_index >= 0:
                    self._combo.removeItem(no_match_index)
                with signals_blocked(self._combo):
                    self._combo.setCurrentText(preset)
                    return
        # if None of the presets match the current system state
        # add NO_MATCH to combo if not already there
        current_items = [self._combo.itemText(i) for i in range(self._combo.count())]
        if NO_MATCH not in current_items:
            self._combo.addItem(NO_MATCH)
        with signals_blocked(self._combo):
            self._combo.setCurrentText(NO_MATCH)

    def _on_cfg_set(self, group: str, preset: str) -> None:
        if group == self._group and self._combo.currentText() != preset:
            with signals_blocked(self._combo):
                self._combo.setCurrentText(preset)
        else:
            dev_prop_list = self._get_preset_dev_prop(self._group, self._presets[0])
            if any(dev_prop for dev_prop in dev_prop_list if dev_prop in self.dev_prop):
                self._update_if_props_not_match_preset()

    def _on_property_changed(self, device: str, property: str, value: str) -> None:
        if (device, property) not in self.dev_prop:
            if self._mmc.getDeviceType(device) != DeviceType.StateDevice:
                return
            # a StateDevice has also a "Label" property. If "Label" is not
            # in dev_prop, we check if the property "State" is in dev_prop.
            if (device, "State") not in self.dev_prop:
                return
        self._update_if_props_not_match_preset()

    def _get_preset_dev_prop(self, group: str, preset: str) -> list:
        """Return a list with (device, property) for the selected group preset."""
        return [(k[0], k[1]) for k in self._mmc.getConfigData(group, preset)]

    def _refresh(self) -> None:
        """Refresh widget based on mmcore."""
        with signals_blocked(self._combo):
            self._combo.clear()
            if self._group not in self._mmc.getAvailableConfigGroups():
                self._combo.addItem(f"No group named {self._group}.")
                self._combo.setEnabled(False)
            else:
                self._update_combo()

    def _update_combo(self) -> None:
        self._presets = list(self._mmc.getAvailableConfigs(self._group))
        if self._presets:
            self.dev_prop = self._get_preset_dev_prop(self._group, self._presets[0])
        self._combo.addItems(self._presets)
        self._combo.setEnabled(True)

        # check if current state matches any preset
        current_config = self._mmc.getCurrentConfig(self._group)
        if current_config in self._presets:
            self._combo.setCurrentText(current_config)
        else:
            # add NO_MATCH if not already there
            current_items = [
                self._combo.itemText(i) for i in range(self._combo.count())
            ]
            if NO_MATCH not in current_items:
                self._combo.addItem(NO_MATCH)

        self._update_if_props_not_match_preset()

    def value(self) -> str:
        """Get current value."""
        return self._combo.currentText()  # type: ignore [no-any-return]

    def setValue(self, value: str) -> None:
        """Set the combobox to the given value."""
        if value == NO_MATCH:
            self._combo.setCurrentText(value)
            return
        if value not in self._mmc.getAvailableConfigs(self._group):
            raise ValueError(
                f"{value!r} must be one of {self._mmc.getAvailableConfigs(self._group)}"
            )
        self._combo.setCurrentText(value)

    def allowedValues(self) -> tuple[str, ...]:
        """Return the allowed values for this widget."""
        values = tuple(self._combo.itemText(i) for i in range(self._combo.count()))
        # filter out NO_MATCH as it's not a real preset value
        return tuple(v for v in values if v != NO_MATCH)

    def _update_tooltip(self, preset: str) -> None:
        if preset == NO_MATCH:
            self._combo.setToolTip("No preset matches the current system state.")
        else:
            self._combo.setToolTip(
                str(self._mmc.getConfigData(self._group, preset)) if preset else ""
            )

    def _on_group_deleted(self, group: str) -> None:
        if group != self._group:
            return
        self._disconnect()
        self.close()

    def _on_preset_deleted(self, group: str, preset: str) -> None:
        if group != self._group:
            return
        self._refresh()

    def _find_dev_prop_to_remove(self, preset: str) -> list[tuple[str, str]]:
        _to_delete = []
        group_cfg = list(self._mmc.getAvailableConfigs(self._group))
        new_preset_dp = [
            (k[0], k[1]) for k in self._mmc.getConfigData(self._group, preset)
        ]
        for dp in new_preset_dp:
            for cfg in group_cfg:
                if cfg == preset:
                    continue
                dp_1 = [(k[0], k[1]) for k in self._mmc.getConfigData(self._group, cfg)]
                if dp not in dp_1:
                    _to_delete.append(dp)
                    break
        return _to_delete

    def _on_new_group_preset(
        self, group: str, preset: str, device: str, property: str, value: str
    ) -> None:
        if group != self._group:
            return

        if not device or not property or not value:
            self._refresh()
            return

        # remove any of the [(dev, prop, value), ...] in the new preset
        # that are not in the group
        if (
            self._mmc.isGroupDefined(group)
            and len(self._mmc.getAvailableConfigs(group)) > 1
            and self.dev_prop
        ):
            new_preset_dp = [
                (k[0], k[1]) for k in self._mmc.getConfigData(self._group, preset)
            ]

            _to_delete = self._find_dev_prop_to_remove(preset)

            if _to_delete:
                warnings.warn(
                    f"{_to_delete} are not included in the '{self._group}' "
                    "group and will not be added!",
                    stacklevel=2,
                )

                dev_prop_val = [
                    (k[0], k[1], k[2]) for k in self._mmc.getConfigData(group, preset)
                ]

                with block_core(self._mmc.events):
                    self._mmc.deleteConfig(group, preset)

                    for d, p, v in dev_prop_val:
                        if (d, p) not in _to_delete:
                            self._mmc.defineConfig(group, preset, d, p, v)

            # if the new preset won't have any (dev, prop, val)
            if len(_to_delete) == len(new_preset_dp):
                self._refresh()
                return

        preset_dev_props = self._get_preset_dev_prop(self._group, preset)

        if len(preset_dev_props) != len(set(self.dev_prop)) and self.dev_prop:
            missing_props = set(self.dev_prop) - set(preset_dev_props)
            warnings.warn(
                f"'{preset}' preset is missing the following properties: "
                f"{list(missing_props)}.",
                stacklevel=2,
            )

        self._refresh()

    def _disconnect(self) -> None:
        self._mmc.events.configSet.disconnect(self._on_cfg_set)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._refresh)
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
        self._mmc.events.configDeleted.disconnect(self._on_preset_deleted)
        self._mmc.events.configGroupDeleted.disconnect(self._on_group_deleted)
        self._mmc.events.configDefined.disconnect(self._on_new_group_preset)
