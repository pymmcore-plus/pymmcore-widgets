import warnings
from typing import List, Optional, Tuple

from pymmcore_plus import DeviceType
from qtpy.QtCore import Qt
from qtpy.QtGui import QBrush
from qtpy.QtWidgets import QComboBox, QHBoxLayout, QListView, QWidget
from superqt.utils import signals_blocked

from ._core import get_core_singleton


class PresetsWidget(QWidget):
    """Create a QCombobox Widget containing the presets of the specified group."""

    def __init__(
        self,
        group: str,
        parent: Optional[QWidget] = None,
    ) -> None:

        super().__init__(parent)

        self._mmc = get_core_singleton()

        self._group = group

        if self._group not in self._mmc.getAvailableConfigGroups():
            raise ValueError(f"{self._group} group does not exist.")

        self._presets = list(self._mmc.getAvailableConfigs(self._group))

        if not self._presets:
            raise ValueError(f"{self._group} group does not have presets.")

        self._update_presets()

        self.dev_prop = self._get_group_dev_prop(self._group)

        self._check_if_presets_have_same_props()

        self._combo = QComboBox()
        self._combo.currentTextChanged.connect(self._update_tooltip)
        self._combo.addItems(self._presets)
        self._combo.setCurrentText(self._mmc.getCurrentConfig(self._group))
        if len(self._presets) > 1:
            self._set_combo_view()
        self._set_if_props_match_preset()

        self.setLayout(QHBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().addWidget(self._combo)
        self._combo.currentTextChanged.connect(self._on_combo_changed)
        self._combo.textActivated.connect(self._on_text_activate)

        self._mmc.events.configSet.connect(self._on_cfg_set)
        self._mmc.events.systemConfigurationLoaded.connect(self._refresh)
        self._mmc.events.propertyChanged.connect(self._on_property_changed)

        # connections to the new pymmcore-plus presetDeleted and newGroupPreset
        self._mmc.events.presetDeleted.connect(self._on_preset_deleted)
        self._mmc.events.groupDeleted.connect(self._on_group_deleted)
        self._mmc.events.newGroupPreset.connect(self._on_new_group_preset)

        self.destroyed.connect(self._disconnect)

    def _set_combo_view(self) -> None:
        view = QListView()
        view_height = sum(
            self._combo.view().sizeHintForRow(i) for i in range(self._combo.count())
        )
        view.setMinimumHeight(view_height)
        self._combo.setView(view)

    def _check_if_presets_have_same_props(self) -> None:

        # TODO: color the preset that is different

        n_prop = 0
        for idx, preset in enumerate(self._presets):
            if idx == 0:
                n_prop = len(self._get_preset_dev_prop(self._group, preset))
                continue

            device_property = self._get_preset_dev_prop(self._group, preset)

            if len(device_property) != n_prop:
                warnings.warn(f"{self._presets} don't have the same properties!")

    def _on_text_activate(self, text: str) -> None:
        # used if there is only 1 preset and you want to set it
        self._mmc.setConfig(self._group, text)
        self._combo.setStyleSheet("")

    def _on_combo_changed(self, text: str) -> None:
        self._mmc.setConfig(self._group, text)
        self._combo.setStyleSheet("")

    def _set_if_props_match_preset(self) -> None:
        for preset in self._presets:
            _set_combo = True
            for (dev, prop, value) in self._mmc.getConfigData(self._group, preset):
                cache_value = self._mmc.getPropertyFromCache(dev, prop)
                if cache_value != value:
                    _set_combo = False
                    break
            if _set_combo:
                with signals_blocked(self._combo):
                    self._combo.setCurrentText(preset)
                    self._combo.setStyleSheet("")
                    return
        # if None of the presets match the current system state
        self._combo.setStyleSheet("color: magenta;")

    def _on_cfg_set(self, group: str, preset: str) -> None:

        if group == self._group and self._combo.currentText() != preset:
            with signals_blocked(self._combo):
                self._combo.setCurrentText(preset)
                self._combo.setStyleSheet("")
        else:
            dev_prop_list = self._get_group_dev_prop(group)
            if any(dev_prop for dev_prop in dev_prop_list if dev_prop in self.dev_prop):
                self._set_if_props_match_preset()

    def _on_property_changed(self, device: str, property: str, value: str) -> None:
        if (device, property) not in self.dev_prop:
            if self._mmc.getDeviceType(device) != DeviceType.StateDevice:
                return
            # a StateDevice has also a "Label" property. If "Label" is not
            # in dev_prop, we check if the property "State" is in dev_prop.
            if (device, "State") not in self.dev_prop:
                return
        self._set_if_props_match_preset()

    def _get_preset_dev_prop(self, group: str, preset: str) -> list:
        """Return a list with (device, property) for the selected group preset."""
        return [(k[0], k[1]) for k in self._mmc.getConfigData(group, preset)]

    def _get_group_dev_prop(self, group: str) -> List[Tuple[str, str]]:
        """Return list of all (device, prop) used in the config group's presets."""
        dev_props = []
        for preset in self._mmc.getAvailableConfigs(group):
            dev_props.extend(
                [(k[0], k[1]) for k in self._mmc.getConfigData(group, preset)]
            )
        return dev_props

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
            self.dev_prop = self._get_group_dev_prop(self._group)
        self._combo.addItems(self._presets)
        self._combo.setEnabled(True)
        self._combo.setCurrentText(self._mmc.getCurrentConfig(self._group))
        if len(self._presets) > 1:
            self._set_combo_view()
        self._set_if_props_match_preset()

    def value(self) -> str:
        """Get current value."""
        return self._combo.currentText()  # type: ignore [no-any-return]

    def setValue(self, value: str) -> None:
        """Set the combobox to the given value."""
        if value not in self._mmc.getAvailableConfigs(self._group):
            raise ValueError(
                f"{value!r} must be one of {self._mmc.getAvailableConfigs(self._group)}"
            )
        self._combo.setCurrentText(value)

    def allowedValues(self) -> Tuple[str, ...]:
        """Return the allowed values for this widget."""
        return tuple(self._combo.itemText(i) for i in range(self._combo.count()))

    def _update_tooltip(self, preset: str) -> None:
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

    def _on_new_group_preset(
        self, group: str, preset: str, dev_prop_val_list: List[Tuple[str, str, str]]
    ) -> None:

        if group != self._group:
            return

        if not dev_prop_val_list:
            self._refresh()
            return

        _color = False

        # remove any of the [(dev, prop, value), ...] in the new preset
        # that are not in the group
        if (
            self._mmc.isGroupDefined(group)
            and len(self._mmc.getAvailableConfigs(group)) > 1
            and self.dev_prop
        ):
            _to_delete = [
                (dpv[0], dpv[1])
                for dpv in dev_prop_val_list
                if (dpv[0], dpv[1]) not in set(self.dev_prop)
            ]

            if _to_delete:
                warnings.warn(
                    f"{_to_delete} are not included in the group and will not be added!"
                )
                self._mmc.deletePresetDeviceProperties(  # type: ignore
                    self._group, preset, _to_delete, emit=False
                )

            # if the new preset won't have any (dev, prop, val)
            if len(_to_delete) == len(dev_prop_val_list):
                self._refresh()
                return

        preset_dev_props = self._get_preset_dev_prop(self._group, preset)

        # check if all [(dev, prop), ...] in the new preset are also in the other preset
        if (
            any(item not in self.dev_prop for item in preset_dev_props)
            and self.dev_prop
        ):
            warnings.warn(
                f"{preset} preset doesn't have the same properties "
                "as the other presets!"
                f"{set(self.dev_prop)} vs {set(preset_dev_props)}"
            )
            _color = True

        elif len(preset_dev_props) != len(set(self.dev_prop)) and self.dev_prop:
            warnings.warn(
                f"{preset} preset is missing the following properties: "
                f"{set(self.dev_prop) - set(preset_dev_props)}"
            )
            _color = True

        self._refresh()

        idx = self._presets.index(preset)
        if _color:
            self._combo.setItemData(idx, QBrush(Qt.magenta), Qt.TextColorRole)
        else:
            self._combo.setItemData(idx, QBrush(Qt.NoBrush))

    def _disconnect(self) -> None:
        self._mmc.events.configSet.disconnect(self._on_cfg_set)
        self._mmc.events.systemConfigurationLoaded.disconnect(self._refresh)
        self._mmc.events.propertyChanged.disconnect(self._on_property_changed)
        self._mmc.events.presetDeleted.disconnect(self._on_preset_deleted)
        self._mmc.events.groupDeleted.disconnect(self._on_group_deleted)
        self._mmc.events.newGroupPreset.disconnect(self._on_new_group_preset)
