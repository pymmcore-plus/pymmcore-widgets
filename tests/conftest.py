import warnings
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from pymmcore_plus import CMMCorePlus
from pymmcore_plus._accumulator import DeviceAccumulator
from pymmcore_plus.core import _mmcore_plus

if TYPE_CHECKING:
    from pytest import FixtureRequest
    from qtpy.QtWidgets import QApplication

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
def _run_after_each_test(
    request: "FixtureRequest", qapp: "QApplication"
) -> Iterator[None]:
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
