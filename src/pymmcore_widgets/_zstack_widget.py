from typing import TYPE_CHECKING, Optional, cast

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

if TYPE_CHECKING:
    from typing_extensions import Protocol

    # fmt: off
    class ZPicker(Protocol):
        valueChanged: Signal
        def value(self) -> dict:...
        def z_range(self) -> float: ...
    # fmt: on


class ZTopBottomSelect(QWidget):
    """Widget to select the top and bottom of a z-stack."""

    valueChanged = Signal(dict)

    _MIN_Z = -1000000
    _MAX_Z = 1000000

    def __init__(
        self, *, parent: Optional[QWidget] = None, mmcore: Optional[CMMCorePlus] = None
    ) -> None:
        super().__init__(parent)

        self._mmc = mmcore or CMMCorePlus.instance()

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

        # current bottom position spinbox
        self._bottom_spinbox = QDoubleSpinBox()
        self._bottom_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._top_spinbox.setRange(self._MIN_Z, self._MAX_Z)
        self._bottom_spinbox.valueChanged.connect(self._update_zrange_and_emit)

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

    def _set_top(self) -> None:
        self._top_spinbox.setValue(self._mmc.getZPosition())

    def _set_bottom(self) -> None:
        self._bottom_spinbox.setValue(self._mmc.getZPosition())

    def _update_zrange_and_emit(self) -> None:
        self._zrange_spinbox.setValue(self.z_range())
        self.valueChanged.emit(self.value())

    def value(self) -> dict:
        return {
            "top": self._top_spinbox.value(),
            "bottom": self._bottom_spinbox.value(),
        }

    def z_range(self) -> float:
        diff = self._top_spinbox.value() - self._bottom_spinbox.value()
        return abs(diff)  # type: ignore


class ZRangeAroundSelect(QWidget):
    """Widget to select the range of a symmetric z-stack."""

    valueChanged = Signal(dict)

    _MAX_RANGE = 100000
    _UNIT = "µm"

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

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
        return {"range": self._zrange_spinbox.value()}

    def z_range(self) -> float:
        return self._zrange_spinbox.value()  # type: ignore


class ZAboveBelowSelect(QWidget):
    """Widget to select the range of an asymmetric z-stack."""

    valueChanged = Signal(dict)

    _MAX_RANGE = 1000000
    _UNIT = "µm"

    def __init__(self, *, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._above_spinbox = QDoubleSpinBox()
        self._above_spinbox.setValue(2.5)
        self._above_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._above_spinbox.setMaximum(self._MAX_RANGE // 2)
        self._above_spinbox.valueChanged.connect(self._update_abovebelow_range)

        self._below_spinbox = QDoubleSpinBox()
        self._below_spinbox.setValue(2.5)
        self._below_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._below_spinbox.setMaximum(self._MAX_RANGE // 2)
        self._below_spinbox.valueChanged.connect(self._update_abovebelow_range)

        # read only z range spinbox
        self._zrange_spinbox = QDoubleSpinBox()
        self._zrange_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zrange_spinbox.setMaximum(self._MAX_RANGE)
        self._zrange_spinbox.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._zrange_spinbox.setReadOnly(True)

        center = Qt.AlignmentFlag.AlignHCenter
        grid = QGridLayout()
        grid.setContentsMargins(10, 0, 10, 15)
        grid.addWidget(QLabel(f"Above ({self._UNIT}):"), 0, 0, center)
        grid.addWidget(self._above_spinbox, 1, 0)
        grid.addWidget(QLabel(f"Below ({self._UNIT}):"), 0, 1, center)
        grid.addWidget(self._below_spinbox, 1, 1)
        grid.addWidget(QLabel(f"Range ({self._UNIT}):"), 0, 2, center)
        grid.addWidget(self._zrange_spinbox, 1, 2)
        self.setLayout(grid)

    def _update_abovebelow_range(self) -> None:
        self._zrange_spinbox.setValue(self.z_range())

    def value(self) -> dict:
        return {
            "above": self._above_spinbox.value(),
            "below": self._below_spinbox.value(),
        }

    def z_range(self) -> float:
        return self._above_spinbox.value() + self._below_spinbox.value()  # type: ignore


class ZStackWidget(QGroupBox):
    """Widget providing options for setting up a z-stack range and step size."""

    valueChanged = Signal()

    _MAX_STEP = 100000
    _NIMG_PREFIX = "Number of Images:"

    def __init__(
        self, title: str = "Z Stack", parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent=parent)
        self.setTitle(title)
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self._mmc = CMMCorePlus.instance()

        # tabs for each z selection mode
        self._zmode_tabs = QTabWidget()
        self._zmode_tabs.setLayout(QVBoxLayout())
        self._zmode_tabs.layout().setSpacing(0)
        self._zmode_tabs.layout().setContentsMargins(0, 0, 0, 0)
        self._zmode_tabs.addTab(ZTopBottomSelect(), "TopBottom")
        self._zmode_tabs.addTab(ZRangeAroundSelect(), "RangeAround")
        self._zmode_tabs.addTab(ZAboveBelowSelect(), "AboveBelow")
        self._zmode_tabs.currentChanged.connect(self._update_n_images)

        # spinbox for the step size
        self._zstep_spinbox = QDoubleSpinBox()
        self._zstep_spinbox.setValue(1)
        self._zstep_spinbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zstep_spinbox.setMinimum(0.05)
        self._zstep_spinbox.setMaximum(self._MAX_STEP)
        self._zstep_spinbox.setSingleStep(0.1)
        self._zstep_spinbox.valueChanged.connect(self._update_n_images)

        # readout for the number of images
        self.n_images_label = QLabel(self._NIMG_PREFIX)

        # bottom row with step size and number of images
        bottom_layout = QHBoxLayout()
        bottom_layout.setContentsMargins(10, 0, 10, 0)
        bottom_layout.addWidget(QLabel("Step Size (µm):"))
        bottom_layout.addWidget(self._zstep_spinbox)
        bottom_layout.addStretch()
        bottom_layout.addWidget(self.n_images_label)
        bottom_row = QWidget()
        bottom_row.setLayout(bottom_layout)

        # layout
        self.setLayout(QVBoxLayout())
        self.layout().setSpacing(10)
        self.layout().setContentsMargins(10, 10, 10, 10)
        self.layout().addWidget(self._zmode_tabs)
        self.layout().addWidget(bottom_row)

    def _update_n_images(self) -> None:
        self.n_images_label.setText(f"{self._NIMG_PREFIX} {self.n_images()}")
        self.valueChanged.emit()

    def value(self) -> dict:
        """Return the current z-stack settings."""
        value = cast("ZPicker", self._zmode_tabs.currentWidget()).value()
        value["step"] = self._zstep_spinbox.value()
        return value

    def n_images(self) -> int:
        """Return the current number of images in the z-stack."""
        step = self._zstep_spinbox.value()
        _range = cast("ZPicker", self._zmode_tabs.currentWidget()).z_range()
        return round((_range / step) + 1)

    def set_state(self, z_plan: dict) -> None:
        """Set the state of the widget from a dictionary."""
        tabs = self._zmode_tabs
        wdg: "ZPicker"
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

        disabled = set(z_plan).isdisjoint({"top", "bottom", "above", "below", "range"})
        self.setChecked(not disabled)

        if "step" in z_plan:
            self._zstep_spinbox.setValue(z_plan["step"])


if __name__ == "__main__":
    from qtpy.QtWidgets import QApplication

    core = CMMCorePlus.instance()
    core.loadSystemConfiguration()
    app = QApplication([])
    wdg = ZStackWidget()
    wdg.show()
    app.exec_()
