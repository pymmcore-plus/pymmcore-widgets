from __future__ import annotations

import inspect
import sys
import warnings
from pathlib import Path
from typing import TYPE_CHECKING, Callable
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
        call_stack = []
        for fi in inspect.stack()[1:]:
            if "_pytest" in fi.filename:
                break
            call_stack.append(f"{fi.filename}:{fi.lineno}")
        instance_mock(call_stack)
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


@pytest.fixture
def assert_max_instance_depth(
    request: FixtureRequest, core_instance_mock: Mock
) -> Iterator[Callable]:
    """Fixture that may be used to assert calls to CMMCorePlus.instance()

    This ensures that no calls to `CMMCorePlus.instance()` are made at a stack depth
    greater than the specified value (relative to the test itself)

    def some_test(assert_max_instance_depth: Callable):
        ...
        assert_max_instance_depth(2)

    """

    def func(depth: int = 2) -> None:
        args = [call.args[0] for call in core_instance_mock.call_args_list]
        if any(len(arg) > depth for arg in args):
            callers = ["\n  ".join(arg) + "\n" for arg in args]
            warnings.warn(
                f"CMMCorePlus.instance() called {core_instance_mock.call_count} times\n"
                f"In test {request.node.nodeid}\n"
                f"Callers:\n" + "\n".join(callers),
                RuntimeWarning,
                stacklevel=2,
            )

    core_instance_mock.reset_mock()
    yield func


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

    # This is a VERY strict test, which can be used to ensure that the test using
    # this fixture always passes through the mmcore instance to all created subwidgets.
    # There are a couple failures for now
    # in test_useq_core_widgets.py and test_config_groups_widgets.py
    # so it remains commented out... but can be uncommented locally for testing.
    # assert_max_instance_depth(2)


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
        if type(remaining[0]).__name__ in {"ImagePreview", "SnapButton"}:
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
