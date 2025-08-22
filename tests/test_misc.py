from __future__ import annotations

import re
from inspect import signature
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QWidget

import pymmcore_widgets

if TYPE_CHECKING:
    from unittest.mock import Mock

    from pytestqt.qtbot import QtBot

ISINSTANCE_RE = re.compile(r"isinstance\s*\(\s*[^,]+,\s*CMMCore", re.MULTILINE)


def test_no_direct_isinstance() -> None:
    # grep the entire codebase for `isinstance(obj, CMMCorePlus)`
    # and ensure that it is not used directly.
    ROOT = Path(pymmcore_widgets.__file__).parent
    for path in ROOT.rglob("*.py"):
        content = path.read_text(encoding="utf-8")
        if match := ISINSTANCE_RE.search(content):
            line_no = content.count("\n", 0, match.start()) + 1
            raise AssertionError(
                f"Direct isinstance check for CMMCore[Plus] found in {path} at line "
                f"{line_no}.\n Use structural checks instead... or open an issue to "
                "discuss."
            )


PUBLIC_WIDGETS = [
    obj
    for name, obj in vars(pymmcore_widgets).items()
    if isinstance(obj, type) and issubclass(obj, QWidget)
]


@pytest.mark.parametrize("widget_cls", PUBLIC_WIDGETS)
def test_widget_creation_propagates_core_instance(
    qtbot: QtBot, widget_cls: type, core_instance_mock: Mock
) -> None:
    instance = CMMCorePlus()
    instance.loadSystemConfiguration()

    ARGS = {
        "group": "Channel",
        "shutter_device": "LED Shutter",
        "device": "XY",
        "device_label": "Camera",
        "prop_name": "BitDepth",
    }

    kwargs: dict = {}
    for param in signature(widget_cls).parameters.values():
        if param.name == "mmcore" or param.annotation == "CMMCorePlus | None":
            kwargs[param.name] = instance
        if param.default is param.empty and param.kind in (
            param.POSITIONAL_OR_KEYWORD,
            param.POSITIONAL_ONLY,
        ):
            if param.name not in ARGS:
                pytest.skip(f"{param.name!r} is a required positional argument")
            kwargs[param.name] = ARGS[param.name]

    core_instance_mock.reset_mock()
    widget = widget_cls(**kwargs)
    if core_instance_mock.call_count:
        kwargs = core_instance_mock.call_args.kwargs
        raise AssertionError(
            f"While creating {widget_cls.__name__!r}, the CMMCorePlus.instance() "
            f"method was called by {kwargs['filename']}:{kwargs['lineno']}. "
            "Ensure that CMMCorePlus instances are propagated through subwidgets."
        )
    qtbot.addWidget(widget)
