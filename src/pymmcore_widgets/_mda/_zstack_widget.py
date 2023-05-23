from __future__ import annotations

from typing import cast

from pymmcore_plus import CMMCorePlus
from qtpy.QtCore import Qt, Signal
from qtpy.QtWidgets import (
    QAbstractSpinBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)
from superqt.utils import signals_blocked
from useq import NoZ

from ._general_mda_widgets import _ZDeviceSelector


class _BasicWidget(QWidget):
    """Basic Z widget."""

    valueChanged = Signal(dict)

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()
        self._z_device = self._mmc.getFocusDevice() or ""

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self.destroyed.connect(self._disconnect)

    @property
    def z_device(self) -> str:
        """The name of the z device."""
        return self._z_device

    @z_device.setter
    def z_device(self, device: str) -> None:
        self._z_device = device

    def _on_sys_cfg_loaded(self) -> None:
        self._z_device = self._mmc.getFocusDevice() or ""

    def value(self) -> dict:
        """Return the current value."""
        return NoZ().dict()

    def z_range(self) -> float:
        """Return the current z range."""
        return 0.0

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)


class ZTopBottomSelect(_BasicWidget):
    """Widget to select the top and bottom of a z-stack."""

    _MIN_Z = -1000000
    _MAX_Z = 1000000

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent, mmcore=mmcore)

        # cached for top and bottom values
        self._chached_values: dict[str, tuple[float, float]] = (
            {self._z_device: (0.0, 0.0)} if self._z_device else {}
        )

        # set top button
        self._top_btn = QPushButton(text="Set Top")
        self._top_btn.clicked.connect(self._set_top)

        # set bottom button
        self._bottom_btn = QPushButton(text="Set Bottom")
        self._bottom_btn.clicked.connect(self._set_bottom)

        # current top position spinbox
        self._top_spinbox = QDoubleSpinBox()
        self._top_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._top_spinbox.setRange(self._MIN_Z, self._MAX_Z)
        self._top_spinbox.valueChanged.connect(self._update_zrange_and_emit)
        self._top_spinbox.valueChanged.connect(self._update_chached_values)

        # current bottom position spinbox
        self._bottom_spinbox = QDoubleSpinBox()
        self._bottom_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._bottom_spinbox.setRange(self._MIN_Z, self._MAX_Z)
        self._bottom_spinbox.valueChanged.connect(self._update_zrange_and_emit)
        self._bottom_spinbox.valueChanged.connect(self._update_chached_values)

        # read only z range spinbox
        self._zrange_spinbox = QDoubleSpinBox()
        self._zrange_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zrange_spinbox.setMaximum(self._MAX_Z - self._MIN_Z)
        self._zrange_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._zrange_spinbox.setReadOnly(True)

        grid = QGridLayout()
        grid.setContentsMargins(10, 10, 10, 10)
        grid.addWidget(self._top_btn, 0, 0)
        grid.addWidget(self._top_spinbox, 1, 0)
        grid.addWidget(self._bottom_btn, 0, 1)
        grid.addWidget(self._bottom_spinbox, 1, 1)
        grid.addWidget(QLabel("Range (µm):"), 0, 2, Qt.AlignmentFlag.AlignHCenter)
        grid.addWidget(self._zrange_spinbox, 1, 2)
        self.setLayout(grid)

    def _on_sys_cfg_loaded(self) -> None:
        super()._on_sys_cfg_loaded()
        self._chached_values = {self._z_device: (0.0, 0.0)} if self._z_device else {}

    def _set_top(self) -> None:
        self._top_spinbox.setValue(self._mmc.getPosition(self._z_device))

    def _set_bottom(self) -> None:
        self._bottom_spinbox.setValue(self._mmc.getPosition(self._z_device))

    def _update_chached_values(self) -> None:
        """Update the cached values."""
        self._chached_values[self._z_device] = (
            self._top_spinbox.value(),
            self._bottom_spinbox.value(),
        )

    def _update_zrange_and_emit(self) -> None:
        self._zrange_spinbox.setValue(self.z_range())
        self.valueChanged.emit(self.value())

    def value(self) -> dict:
        return {
            "top": max(self._top_spinbox.value(), self._bottom_spinbox.value()),
            "bottom": min(self._top_spinbox.value(), self._bottom_spinbox.value()),
            "z_device": self._z_device or None,
        }

    def z_range(self) -> float:
        diff = self._top_spinbox.value() - self._bottom_spinbox.value()
        return abs(diff)  # type: ignore


class ZRangeAroundSelect(_BasicWidget):
    """Widget to select the range of a symmetric z-stack."""

    _MAX_RANGE = 100000
    _UNIT = "µm"

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent, mmcore=mmcore)

        # left label
        lbl_range_ra = QLabel(f"Range ({self._UNIT}):")
        lbl_range_ra.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        # right label (to show the +/-)
        self._range_label = QLabel()
        self._range_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # spinbox for the actual value
        self._zrange_spinbox = QDoubleSpinBox()
        self._zrange_spinbox.valueChanged.connect(self._on_range_changed)
        self._zrange_spinbox.setValue(5)
        self._zrange_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zrange_spinbox.setMaximum(self._MAX_RANGE)

        self.setLayout(QHBoxLayout())
        self.layout().setSpacing(10)
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().addWidget(lbl_range_ra)
        self.layout().addWidget(self._zrange_spinbox)
        self.layout().addWidget(self._range_label)

    def _on_range_changed(self, value: int) -> None:
        val = f"-{value/2} {self._UNIT} <- z -> +{value/2} {self._UNIT}"
        self._range_label.setText(val)
        self.valueChanged.emit(self.value())

    def value(self) -> dict:
        return {
            "range": self._zrange_spinbox.value(),
            "z_device": self._z_device or None,
        }

    def z_range(self) -> float:
        return self._zrange_spinbox.value()  # type: ignore


class ZAboveBelowSelect(_BasicWidget):
    """Widget to select the range of an asymmetric z-stack."""

    _MAX_RANGE = 1000000
    _UNIT = "µm"

    def __init__(
        self, parent: QWidget | None = None, *, mmcore: CMMCorePlus | None = None
    ) -> None:
        super().__init__(parent, mmcore=mmcore)

        self._above_spinbox = QDoubleSpinBox()
        self._above_spinbox.setValue(2.5)
        self._above_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._above_spinbox.setMaximum(self._MAX_RANGE // 2)
        self._above_spinbox.valueChanged.connect(self._on_range_changed)

        self._below_spinbox = QDoubleSpinBox()
        self._below_spinbox.setValue(2.5)
        self._below_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._below_spinbox.setMaximum(self._MAX_RANGE // 2)
        self._below_spinbox.valueChanged.connect(self._on_range_changed)

        # read only z range spinbox
        self._zrange_spinbox = QDoubleSpinBox()
        self._zrange_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zrange_spinbox.setMaximum(self._MAX_RANGE)
        self._zrange_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._zrange_spinbox.setReadOnly(True)

        center = Qt.AlignmentFlag.AlignHCenter
        grid = QGridLayout()
        grid.setContentsMargins(10, 4, 10, 12)  # FIXME: it's still weird...
        grid.addWidget(QLabel(f"Above ({self._UNIT}):"), 0, 0, center)
        grid.addWidget(self._above_spinbox, 1, 0)
        grid.addWidget(QLabel(f"Below ({self._UNIT}):"), 0, 1, center)
        grid.addWidget(self._below_spinbox, 1, 1)
        grid.addWidget(QLabel(f"Range ({self._UNIT}):"), 0, 2, center)
        grid.addWidget(self._zrange_spinbox, 1, 2)
        self.setLayout(grid)

    def _on_range_changed(self) -> None:
        self._zrange_spinbox.setValue(self.z_range())
        self.valueChanged.emit(self.value())

    def value(self) -> dict:
        return {
            "above": self._above_spinbox.value(),
            "below": self._below_spinbox.value(),
            "z_device": self._z_device or None,
        }

    def z_range(self) -> float:
        return self._above_spinbox.value() + self._below_spinbox.value()  # type: ignore


class ZStackWidget(QWidget):
    """Widget providing options for setting up a z-stack range and step size.

    Each tab represents a different way of specifying a z-stack range. The `value()`
    method returns a dictionary with the current state of the widget, in a format that
    matches one of the [useq-schema Z Plan
    specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans).

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    mmcore : CMMCorePlus | None
        Optional [`pymmcore_plus.CMMCorePlus`][] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    valueChanged = Signal(dict)

    _MAX_STEP = 100000
    _NIMG_PREFIX = "Number of Images:"

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        mmcore: CMMCorePlus | None = None,
    ) -> None:
        super().__init__(parent=parent)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self._mmc = mmcore or CMMCorePlus.instance()

        # selection for z device
        z_dev_row = QGroupBox()
        z_dev_row_layout = QHBoxLayout()
        z_dev_row_layout.setContentsMargins(0, 0, 0, 0)
        z_dev_row.setLayout(z_dev_row_layout)
        self._z_device_combo = _ZDeviceSelector(
            mmcore=self._mmc, include_none_in_list=True
        )
        self._z_device_combo.valueChanged.connect(self._on_z_dev_combo_changed)
        z_dev_row_layout.addWidget(self._z_device_combo)

        # tabs for each z selection mode
        self._zmode_tabs = QTabWidget()
        self._zmode_tabs.setLayout(QVBoxLayout())
        self._zmode_tabs.layout().setSpacing(0)
        self._zmode_tabs.layout().setContentsMargins(0, 0, 0, 0)
        # all of the tabs have a valueChanged signal which we connect to _on_tab-change
        for tab_cls in [ZTopBottomSelect, ZRangeAroundSelect, ZAboveBelowSelect]:
            tab_cls = cast("type[_BasicWidget]", tab_cls)
            wdg = tab_cls(mmcore=self._mmc)
            wdg.z_device = self._z_device_combo.value()
            wdg.valueChanged.connect(self._on_tab_change)
            name = tab_cls.__name__.replace("Z", "").replace("Select", "")
            self._zmode_tabs.addTab(wdg, name)
        self._zmode_tabs.currentChanged.connect(self._update_and_emit)

        # spinbox for the step size
        self._zstep_spinbox = QDoubleSpinBox()
        self._zstep_spinbox.setValue(1)
        self._zstep_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zstep_spinbox.setMinimum(0.05)
        self._zstep_spinbox.setMaximum(self._MAX_STEP)
        self._zstep_spinbox.setSingleStep(0.1)
        self._zstep_spinbox.valueChanged.connect(self._update_and_emit)

        # readout for the number of images
        self.n_images_label = QLabel(self._NIMG_PREFIX)

        # bottom row with step size and number of images
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(5, 5, 5, 5)
        bottom_layout.addWidget(QLabel("Step Size (µm):"))
        bottom_layout.addWidget(self._zstep_spinbox)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.n_images_label)
        bottom_row = QGroupBox()
        bottom_row.setLayout(bottom_layout)

        # layout
        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(15)
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().addWidget(z_dev_row)
        self.layout().addWidget(self._zmode_tabs)
        self.layout().addWidget(bottom_row)

        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_cfg_loaded)

        self.destroyed.connect(self._disconnect)

        self._on_sys_cfg_loaded()

    def _on_sys_cfg_loaded(self) -> None:
        self._zmode_tabs.setEnabled(self._z_device_combo.value() != "None")
        self._zstep_spinbox.setEnabled(self._z_device_combo.value() != "None")
        self.n_images_label.setEnabled(self._z_device_combo.value() != "None")
        self._update_and_emit()

    def _on_z_dev_combo_changed(self, text: str) -> None:
        """Enable/Disable the widgets, set z_device property and set chached values."""
        self._zmode_tabs.setEnabled(text != "None")
        self._zstep_spinbox.setEnabled(text != "None")
        self.n_images_label.setEnabled(text != "None")
        wdg = cast("_BasicWidget", self._zmode_tabs.currentWidget())
        wdg.z_device = text if text != "None" else ""

        if isinstance(wdg, ZTopBottomSelect):
            if wdg.z_device in wdg._chached_values and text != "None":
                with signals_blocked(wdg._top_spinbox):
                    wdg._top_spinbox.setValue(wdg._chached_values[text][0])
                with signals_blocked(wdg._bottom_spinbox):
                    wdg._bottom_spinbox.setValue(wdg._chached_values[text][1])
            else:
                with signals_blocked(wdg._top_spinbox):
                    wdg._top_spinbox.setValue(0)
                with signals_blocked(wdg._bottom_spinbox):
                    wdg._bottom_spinbox.setValue(0)
            wdg._update_zrange_and_emit()

        self.valueChanged.emit(self.value() if text != "None" else NoZ().dict())

    def _on_tab_change(self) -> None:
        """Only update the number of images when the active tab changes."""
        if self.sender() is self._zmode_tabs.currentWidget():
            self._update_and_emit()

    def _update_and_emit(self) -> None:
        """Update the number of images readout and emit the valueChanged signal."""
        self.n_images_label.setText(f"{self._NIMG_PREFIX} {self.n_images()}")
        self.valueChanged.emit(self.value())

    def value(self) -> dict:
        """Return the current z-stack settings as a dictionary.

        Note that the output will match one of the [useq-schema Z Plan
        specifications](https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans).
        """
        if not self._zmode_tabs.isEnabled():
            return NoZ().dict()
        value = cast("_BasicWidget", self._zmode_tabs.currentWidget()).value()
        value["step"] = self._zstep_spinbox.value()
        return value

    def n_images(self) -> int:
        """Return the current number of images in the z-stack."""
        step = self._zstep_spinbox.value()
        _range = cast("_BasicWidget", self._zmode_tabs.currentWidget()).z_range()
        return int(round((_range / step) + 1))

    def set_state(self, z_plan: dict) -> None:
        """Set the state of the widget.

        Parameters
        ----------
        z_plan : dict
            A dictionary following the [useq-schema Z Plan specifications](
            https://pymmcore-plus.github.io/useq-schema/schema/axes/#z-plans).
        """
        tabs = self._zmode_tabs
        wdg: _BasicWidget
        if "top" in z_plan and "bottom" in z_plan:
            wdg = cast(ZTopBottomSelect, tabs.findChild(ZTopBottomSelect))
            wdg._top_spinbox.setValue(z_plan["top"])
            wdg._bottom_spinbox.setValue(z_plan["bottom"])
            tabs.setCurrentWidget(wdg)
        elif "above" in z_plan and "below" in z_plan:
            wdg = cast(ZAboveBelowSelect, tabs.findChild(ZAboveBelowSelect))
            wdg._above_spinbox.setValue(z_plan["above"])
            wdg._below_spinbox.setValue(z_plan["below"])
            tabs.setCurrentWidget(wdg)
        elif "range" in z_plan:
            wdg = cast(ZRangeAroundSelect, tabs.findChild(ZRangeAroundSelect))
            wdg._zrange_spinbox.setValue(z_plan["range"])
            tabs.setCurrentWidget(wdg)

        if "step" in z_plan:
            self._zstep_spinbox.setValue(z_plan["step"])

        if "z_device" in z_plan:
            self._z_device_combo.setValue(z_plan["z_device"])

    def _disconnect(self) -> None:
        self._mmc.events.systemConfigurationLoaded.disconnect(self._on_sys_cfg_loaded)
