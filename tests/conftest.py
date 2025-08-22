from __future__ import annotations

import inspect
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import Mock, patch

import pymmcore_plus
import pytest
from pymmcore_plus import CMMCorePlus
from pymmcore_plus._accumulator import DeviceAccumulator
from pymmcore_plus.core import _mmcore_plus

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pytest import FixtureRequest
    from qtpy.QtWidgets import QApplication

# ###################################################

# This section of code MUST run before pymmcore_widgets is imported
# It patches the CMMCorePlus class to track calls to CMMCorePlus.instance()
# Because CMMCorePlus is a C-extension, it's not possible to use `patch.object` as
# usual to monkeypatch, which necessitates this workaround.

if "pymmcore_widgets" in sys.modules:
    warnings.warn(
        "pymmcore-widgets has been imported before conftest.py. "
        "core_instance_mock will not work correctly.",
        RuntimeWarning,
        stacklevel=2,
    )


instance_mock = Mock()


# Create a wrapper class that tracks instantiation
class CMMCorePlusTracker(CMMCorePlus):
    @classmethod
    def instance(cls) -> CMMCorePlus:
        # get filename and line of calling function
        caller = inspect.stack()[1]
        instance_mock(filename=caller.filename, lineno=caller.lineno)
        return super().instance()


# patches the original object
pymmcore_plus.CMMCorePlus = CMMCorePlusTracker  # type: ignore[misc]
_mmcore_plus.CMMCorePlus = CMMCorePlusTracker  # type: ignore[misc]


@pytest.fixture
def core_instance_mock() -> Iterator[Mock]:
    """Fixture that may be used to assert calls to CMMCorePlus.instance()"""
    yield instance_mock


# ###################################################


TEST_CONFIG = str(Path(__file__).parent / "test_config.cfg")


# to create a new CMMCorePlus() for every test
@pytest.fixture(autouse=True)
def global_mmcore() -> Iterator[CMMCorePlus]:
    mmc = CMMCorePlus()
    mmc.loadSystemConfiguration(TEST_CONFIG)
    with patch.object(_mmcore_plus, "_instance", mmc):
        yield mmc
    # FIXME: would be better if this wasn't needed, or was fixed upstream
    DeviceAccumulator._CACHE.clear()
    mmc.reset()
    mmc.__del__()
    del mmc


@pytest.fixture(autouse=True)
def _run_after_each_test(request: FixtureRequest, qapp: QApplication) -> Iterator[None]:
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
        if (
            # os.name == "nt"
            # and sys.version_info[:2] <= (3, 9)
            type(remaining[0]).__name__ in {"ImagePreview", "SnapButton"}
        ):
            # I have no idea why, but the ImagePreview widget is leaking.
            # And it only came with a seemingly unrelated
            # https://github.com/pymmcore-plus/pymmcore-widgets/pull/90
            # we're just ignoring it for now.
            return

        test = f"{request.node.path.name}::{request.node.originalname}"
        warnings.warn(
            f"topLevelWidgets remaining after {test!r}: {remaining}",
            UserWarning,
            stacklevel=2,
        )
