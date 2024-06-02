import gc
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pymmcore_plus import CMMCorePlus
from pymmcore_plus.core import _mmcore_plus

if TYPE_CHECKING:
    from pytest import FixtureRequest
    from qtpy.QtWidgets import QApplication

TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")


# to create a new CMMCorePlus() for every test
@pytest.fixture(autouse=True)
def global_mmcore():
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration(TEST_CONFIG)
    with patch.object(_mmcore_plus, "_instance", mmc):
        yield mmc


@pytest.fixture(autouse=True)
def _run_after_each_test(request: "FixtureRequest", qapp: "QApplication") -> None:
    """Run after each test to ensure no widgets have been left around.

    When this test fails, it means that a widget being tested has an issue closing
    cleanly. Perhaps a strong reference has leaked somewhere.  Look for
    `functools.partial(self._method)` or `lambda: self._method` being used in that
    widget's code.
    """
    nbefore = len(qapp.topLevelWidgets())
    failures_before = request.session.testsfailed
    yield
    # if the test failed, don't worry about checking widgets
    if request.session.testsfailed - failures_before:
        return
    remaining = qapp.topLevelWidgets()
    if len(remaining) > nbefore:
        test_node = request.node
        if any(mark.name == "allow_leaks" for mark in test_node.iter_markers()):
            return
        if type(remaining[0]).__name__ in {"ImagePreview", "SnapButton"}:
            # I have no idea why ImagePreview widget is leaking.
            # it only came with a seemingly unrelated
            # https://github.com/pymmcore-plus/pymmcore-widgets/pull/90
            return

        test = f"{test_node.path.name}::{test_node.originalname}"
        msg = f"{len(remaining)} topLevelWidgets remaining after {test!r}:"

        for widget in remaining:
            try:
                obj_name = widget.objectName()
            except Exception:
                obj_name = None
            msg += f"\n{widget!r} {obj_name!r}"
            # Get the referrers of the widget
            referrers = gc.get_referrers(widget)
            msg += "\n  Referrers:"
            for ref in referrers:
                msg += f"\n  -   {ref}, {id(ref):#x}"

        raise AssertionError(msg)
