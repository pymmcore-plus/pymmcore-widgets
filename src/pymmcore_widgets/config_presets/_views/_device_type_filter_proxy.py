from pymmcore_plus import DeviceType
from qtpy.QtCore import QModelIndex, QSortFilterProxyModel, Qt
from qtpy.QtWidgets import QWidget

from pymmcore_widgets._models import Device, DevicePropertySetting


class DeviceTypeFilter(QSortFilterProxyModel):
    def __init__(self, allowed: set[DeviceType], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setRecursiveFilteringEnabled(True)
        self.allowed = allowed  # e.g. {"Camera", "Shutter"}
        self.show_read_only = False
        self.show_pre_init = False

    def _device_allowed_for_index(self, idx: QModelIndex) -> bool:
        """Walk up to the closest Device ancestor and check its type."""
        while idx.isValid():
            data = idx.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, Device):
                return DeviceType.Any in self.allowed or data.type in self.allowed
            idx = idx.parent()  # keep climbing
        return True  # no Device ancestor (root rows etc.)

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        if (sm := self.sourceModel()) is None:
            return super().filterAcceptsRow(source_row, source_parent)  # type: ignore [no-any-return]

        idx = sm.index(source_row, 0, source_parent)

        # 1. Bail out whole subtree when its Device type is disallowed
        if not self._device_allowed_for_index(idx):
            return False

        data = idx.data(Qt.ItemDataRole.UserRole)

        # 2. Per-property flags
        if isinstance(data, DevicePropertySetting):
            if data.is_read_only and not self.show_read_only:
                return False
            if data.is_pre_init and not self.show_pre_init:
                return False
            if data.is_advanced:
                return False

        # 3. Text / regex filter (superclass logic)
        text_match = super().filterAcceptsRow(source_row, source_parent)

        # 4. Special rule for Device rows: hide when it ends up child-less
        if isinstance(data, Device):
            # If the device name itself matches, keep it only if at least
            # one child survives *after all rules above*.
            if text_match:
                for i in range(sm.rowCount(idx)):
                    if self.filterAcceptsRow(i, idx):  # child survives
                        return True
            #     # no surviving children -> drop the device row
            #     return False

            # # If the device row didn't match the text filter, just return
            # # False here; Qt will re-accept it automatically if any child
            # # is accepted (thanks to recursiveFilteringEnabled).
            # return False

        # 5. For non-Device rows, the decision is simply the text match
        return text_match  # type: ignore [no-any-return]

    def setReadOnlyVisible(self, show: bool) -> None:
        """Set whether to show read-only properties."""
        if self.show_read_only != show:
            self.show_read_only = show
            self.invalidate()

    def setPreInitVisible(self, show: bool) -> None:
        """Set whether to show pre-init properties."""
        if self.show_pre_init != show:
            self.show_pre_init = show
            self.invalidate()

    def setAllowedDeviceTypes(self, allowed: set[DeviceType]) -> None:
        """Set the allowed device types."""
        if self.allowed != allowed:
            self.allowed = allowed
            self.invalidate()
