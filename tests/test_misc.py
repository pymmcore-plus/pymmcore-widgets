from __future__ import annotations

import inspect
import re
import warnings
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import PropertyMock, patch

from pymmcore_plus import CMMCorePlus
from qtpy.QtWidgets import QWidget

import pymmcore_widgets

if TYPE_CHECKING:
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


def test_using_existing_mmcore(qtbot: QtBot) -> None:
    # FIXME: Can we get rid of this list?
    blacklist = [
        # Spawns modal dialogs
        "ObjectivesWidget",
        # Spawns modal dialogs
        "ObjectivesPixelConfigurationWidget",
    ]
    # Get an instance
    instance = CMMCorePlus.instance()

    # Patch CMMCorePlus.instance to raise an error if called
    with patch(
        "pymmcore_plus.core._mmcore_plus._instance", new_callable=PropertyMock
    ) as mock_instance:

        def throw_exc() -> None:
            raise RuntimeError("CMMCorePlus instance should not be created")

        mock_instance.side_effect = throw_exc

        # For all API in pymmcore_widgets
        for api in pymmcore_widgets.__all__:
            # Skip if private or in blacklist
            if api.startswith("_") or api in blacklist:
                continue

            # Skip if deprecated
            with warnings.catch_warnings(record=True) as wlist:
                warnings.simplefilter("always")
                obj = getattr(pymmcore_widgets, api)
                # If a warning was raised, skip this widget
                if wlist and any("deprecate" in str(w.message) for w in wlist):
                    continue

            # Skip if not a QWidget
            if not issubclass(obj, QWidget):
                continue

            sig = inspect.signature(obj.__init__)
            # Skip if required positional args (excluding self)
            # Hard to extensibly test these
            if any(
                k
                for k, p in sig.parameters.items()
                if k != "self"
                and p.default is inspect.Parameter.empty
                and p.kind in (p.POSITIONAL_OR_KEYWORD, p.POSITIONAL_ONLY)
            ):
                continue

            # Find if any argument is annotated as CMMCorePlus or "CMMCorePlus | None"
            core_arg = None
            for k, p in sig.parameters.items():
                if k == "self":
                    continue
                if p.annotation == "CMMCorePlus | None":
                    core_arg = k
                    break
            if core_arg:
                widget = obj(**{core_arg: instance})
                qtbot.addWidget(widget)
