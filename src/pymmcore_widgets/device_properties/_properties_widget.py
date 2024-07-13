"""Whereas PropertyWidget shows a single property, PropertiesWidget is a container.

It shows a number of properties, filtered by a given set of tags.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable, cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QGridLayout, QLabel, QWidget

from ._property_widget import PropertyWidget

if TYPE_CHECKING:
    import re


class PropertiesWidget(QWidget):
    """Convenience container to control a specific set of PropertyWidgets.

    Properties can be filtered by a number of criteria, which are passed to
    [`CMMCorePlus.iterProperties`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.iterProperties].

    Parameters
    ----------
    property_type : int | Sequence[int] | None
        PropertyType (or types) to filter by, by default all property types will
        be yielded.
    property_name_pattern : str | re.Pattern | None
        Property name to filter by, by default all property names will be yielded.
        May be a compiled regular expression or a string, in which case it will be
        compiled with `re.IGNORECASE`.
    device_type : DeviceType | None
        DeviceType to filter by, by default all device types will be yielded.
    device_label : str | None
        Device label to filter by, by default all device labels will be yielded.
    has_limits : bool | None
        If provided, only properties with `hasPropertyLimits` matching this value
        will be yielded.
    is_read_only : bool | None
        If provided, only properties with `isPropertyReadOnly` matching this value
        will be yielded.
    is_sequenceable : bool | None
        If provided only properties with `isPropertySequenceable` matching this
        value will be yielded.
    """

    def __init__(
        self,
        property_type: int | Iterable[int] | None = None,
        property_name_pattern: str | re.Pattern | None = None,
        *,
        device_type: int | Iterable[int] | None = None,
        device_label: str | re.Pattern | None = None,
        has_limits: bool | None = None,
        is_read_only: bool | None = None,
        is_sequenceable: bool | None = None,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)
        self.setLayout(QGridLayout())

        self._mmc = mmcore or CMMCorePlus.instance()
        self._mmc.events.systemConfigurationLoaded.connect(self.rebuild)

        self._property_type = property_type
        self._property_name_pattern = property_name_pattern
        self._device_type = device_type
        self._device_label = device_label
        self._has_limits = has_limits
        self._is_read_only = is_read_only
        self._is_sequenceable = is_sequenceable

        self.destroyed.connect(self._disconnect)
        self.rebuild()

    def rebuild(self) -> None:
        """Rebuild the layout, populating based on current filters."""
        # clear
        while self.layout().count():
            self.layout().takeAt(0).widget().deleteLater()

        # get properties
        properties = self._mmc.iterProperties(
            property_name_pattern=self._property_name_pattern,
            property_type=self._property_type,
            device_type=self._device_type,
            device_label=self._device_label,
            has_limits=self._has_limits,
            is_read_only=self._is_read_only,
            is_sequenceable=self._is_sequenceable,
            as_object=False,
        )

        # create and add widgets
        layout = cast(QGridLayout, self.layout())
        for i, (dev, prop) in enumerate(properties):
            layout.addWidget(QLabel(f"{dev}::{prop}"), i, 0)
            layout.addWidget(PropertyWidget(dev, prop, mmcore=self._mmc), i, 1)

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self.rebuild)
