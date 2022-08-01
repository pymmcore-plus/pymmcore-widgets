import re
from typing import Optional

from pymmcore_plus import CMMCorePlus, PropertyType
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QGridLayout, QLabel, QWidget

from ._core import iter_dev_props
from ._property_widget import PropertyWidget


class SliderDialog(QDialog):
    """A Dialog that shows range-based properties (such as light sources) as sliders.

    Parameters
    ----------
    property_regex : str
        a regex pattern to use to select property names to show.

        e.g. property_regex = "(Intensity|Power)s?" will create a slider
        for each range-based property that contains "I(i)ntensity(s)" or
        "P(p)ower(s)" in the property name.

    parent : Optional[QWidget]
        optional parent widget, by default None
    mmcore : Optional[CMMCorePlus]
        Optional mmcore instance, by default the global instance.
    """

    def __init__(
        self,
        property_regex: str,
        parent: Optional[QWidget] = None,
        *,
        mmcore: Optional[CMMCorePlus] = None,
    ):
        super().__init__(parent)
        ptrn = re.compile(property_regex, re.IGNORECASE)

        _grid = QGridLayout()
        core: CMMCorePlus = mmcore or CMMCorePlus.instance()
        lights = [
            dp
            for dp in iter_dev_props(core)
            if ptrn.search(dp[1])
            and core.hasPropertyLimits(*dp)
            and core.getPropertyType(*dp) in {PropertyType.Integer, PropertyType.Float}
        ]
        for i, (dev, prop) in enumerate(lights):
            _grid.addWidget(QLabel(f"{dev}::{prop}"), i, 0)
            _grid.addWidget(PropertyWidget(dev, prop, core=core), i, 1)

        self.setLayout(_grid)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )
