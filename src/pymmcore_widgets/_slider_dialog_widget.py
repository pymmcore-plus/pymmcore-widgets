from __future__ import annotations

import re

from pymmcore_plus import CMMCorePlus, PropertyType
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QDialog, QGridLayout, QLabel, QWidget

from ._core import iter_dev_props
from ._property_widget import PropertyWidget


class SliderDialog(QDialog):
    """A Widget to display an control range-based properties as sliders.

    For example, this widget can be used to control light sources .

    Parameters
    ----------
    property_regex : str
        a regex pattern to use to select property names to show.

        e.g. property_regex = "(Intensity|Power)s?" will create a slider
        for each range-based property that contains "I(i)ntensity(s)" or
        "P(p)ower(s)" in the property name.
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
        property_regex: str,
        *,
        parent: QWidget | None = None,
        mmcore: CMMCorePlus | None = None,
    ):
        super().__init__(parent=parent)
        ptrn = re.compile(property_regex, re.IGNORECASE)

        _grid = QGridLayout()
        mmcore = mmcore or CMMCorePlus.instance()
        lights = [
            dp
            for dp in iter_dev_props(mmcore)
            if ptrn.search(dp[1])
            and mmcore.hasPropertyLimits(*dp)
            and mmcore.getPropertyType(*dp)
            in {PropertyType.Integer, PropertyType.Float}
        ]
        for i, (dev, prop) in enumerate(lights):
            _grid.addWidget(QLabel(f"{dev}::{prop}"), i, 0)
            _grid.addWidget(PropertyWidget(dev, prop, mmcore=mmcore), i, 1)

        self.setLayout(_grid)
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowCloseButtonHint
        )
