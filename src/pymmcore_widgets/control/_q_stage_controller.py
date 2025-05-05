from __future__ import annotations

from typing import Any, Callable, Generic, TypeVar

import psygnal
from pymmcore_plus import CMMCorePlus, DeviceType
from qtpy.QtCore import QObject, QTimerEvent, Signal

# ------------------ Qt agnostic ... could move to pymmcore-plus ---------

T = TypeVar("T")


class _ValueBatcher(Generic[T]):
    """Batches a series of setX calls to a device.

    Abstractly, any device that can get/set a numeric value (i.e. something that can be
    added) can be used with this class.

    For example, this could be used with a stage device to batch a series of relative
    moves. Each time set_relative() is called, the target value is updated
    internally. Some external event loop (polling, timer, etc.) should call
    `poll_done()` to check if the device is busy.  If it returns `True`, it means that
    the device is idle and has reached the target position.

    Decoupling here makes it easier to use this class with different event loops or
    threading models.

    This class is not thread-safe. It is assumed that the event loop calling poll_done()
    is the same thread that called set_relative().  If you need to call this from
    different threads, you should use a mutex or other synchronization mechanism to
    ensure that only one thread is mutating the state of this class at a time.

    Parameters
    ----------
    fget : Callable[[], T]
        Function to get the current position of the device.
    fset : Callable[[T], None]
        Function to set the position of the device.
    fadd : Callable[[T, T], T]
        Function to add two values together.
    fbusy : Callable[[], bool]
        Function that returns True if the device is busy.
    zero : T
        An identity ("zero") value for the fadd function. Adding this value to any
        value T should return T.  This is used to reset the delta value when moving
        to an absolute position.
    """

    finished = psygnal.Signal()
    """Signal emitted when the device has finished moving."""

    def __init__(
        self,
        fget: Callable[[], T],
        fset: Callable[[T], None],
        fadd: Callable[[T, T], T],
        fbusy: Callable[[], bool],
        zero: T,
    ) -> None:
        self._fget = fget
        self._fset = fset
        self._fadd = fadd
        self._fbusy = fbusy
        self._zero = zero
        self._reset()

    def _reset(self) -> None:
        # --- batch state ---
        self._seq = 0  # bumps on every move_relative()
        self._last_issued_seq = 0  # seq at time of last fset()
        self._base: T | None = None
        self._delta: T | None = None

    @property
    def is_moving(self) -> bool:
        """Returns True if the device is moving."""
        return self._delta is not None

    def poll_done(self) -> bool:
        """Call repeatedly to check if the device is done moving.

        Returns True exactly once when:
        1. The device is idle (not busy) AND
        2. The last issued move command has been completed

        After returning True it resets its state and will return False until the next
        move_relative() call.
        """
        # if we have no base or delta, we're not moving
        if self._delta is None:
            return False

        # if the device is busy, we're not done
        if self._fbusy():
            return False

        # if new calls arrived since we last fset(), re-issue
        if self._seq != self._last_issued_seq:
            self._issue_move()
            return False

        # no new work, we're done
        self._reset()
        self.finished.emit()
        return True

    def add_relative(self, delta: T) -> None:
        """Add a relative value to the batch."""
        self._seq += 1

        if self._delta is None:
            # start new batch
            self._base = self._fget()
            self._delta = delta
        else:
            self._delta = self._fadd(self._delta, delta)
        self._issue_move()

    def set_absolute(self, target: T) -> None:
        """Assign an absolute target position to the batch.

        This will reset the batch state and issue a move to the target position.
        After the move finishes, new `move_relative()` calls are interpreted
        relative to *target*.
        """
        self._seq += 1  # new batch → new sequence id
        self._base = target  # anchor for later relatives
        self._delta = self._zero  # target == base + delta
        self._issue_move()

    @property
    def target(self) -> T | None:
        """The target position of the stage.  Or None if not moving."""
        if self._base is None or self._delta is None:
            return None
        return self._fadd(self._base, self._delta)

    def _issue_move(self) -> None:
        # self._base and self._delta are guaranteed to be not None here
        target = self._fadd(self._base, self._delta)  # type: ignore[arg-type]
        # issue the move command
        try:
            self._fset(target)
        except Exception as e:  # pragma: no cover
            CMMCorePlus.instance().logMessage(
                f"Error setting ValueBatcher to {target}: {e}"
            )
        self._last_issued_seq = self._seq


class StageBatcher(_ValueBatcher[float]):
    """Batcher for single axis stage devices.

    This is a specialized version of _ValueBatcher that works with single axis stage
    devices. It uses the CMMCorePlus API to get and set the position of the stage.
    """

    def __init__(self, device: str | None, mmcore: CMMCorePlus | None) -> None:
        mmcore = mmcore or CMMCorePlus.instance()
        if device is None:
            device = mmcore.getFocusDevice()
            if not device:
                raise ValueError("No XY stage device found.")
        if not mmcore.getDeviceType(device) == DeviceType.StageDevice:
            raise ValueError(f"Device {device} is not a stage device.")

        super().__init__(
            fget=lambda: mmcore.getPosition(device),
            fset=lambda pos: mmcore.setPosition(device, pos),
            fadd=lambda a, b: a + b,
            fbusy=lambda: mmcore.deviceBusy(device),
            zero=0.0,
        )


class XYStageBatcher(_ValueBatcher[tuple[float, float]]):
    """Batcher for XY stage devices.

    This is a specialized version of _ValueBatcher that works with XY stage devices. It
    uses the CMMCorePlus API to get and set the position of the stage.
    """

    def __init__(self, device: str | None, mmcore: CMMCorePlus | None) -> None:
        mmcore = mmcore or CMMCorePlus.instance()
        if device is None:
            device = mmcore.getXYStageDevice()
            if not device:
                raise ValueError("No XY stage device found.")
        if not mmcore.getDeviceType(device) == DeviceType.XYStageDevice:
            raise ValueError(f"Device {device} is not a stage device.")

        super().__init__(
            fget=lambda: tuple(mmcore.getXYPosition(device)),  # type: ignore
            fset=lambda pos: mmcore.setXYPosition(device, pos[0], pos[1]),
            fadd=lambda a, b: (a[0] + b[0], a[1] + b[1]),
            fbusy=lambda: mmcore.deviceBusy(device),
            zero=(0.0, 0.0),
        )


_STAGE_BATCHERS: dict[tuple[int, str], StageBatcher | XYStageBatcher] = {}


def get_stage_batcher(
    device: str, mmcore: CMMCorePlus | None = None
) -> StageBatcher | XYStageBatcher:
    """Get a stage batcher for the given device."""
    mmcore = mmcore or CMMCorePlus.instance()
    key = (id(mmcore), device)
    if key not in _STAGE_BATCHERS:
        if mmcore.getDeviceType(device) == DeviceType.XYStageDevice:
            _STAGE_BATCHERS[key] = XYStageBatcher(device, mmcore)
        elif mmcore.getDeviceType(device) == DeviceType.StageDevice:
            _STAGE_BATCHERS[key] = StageBatcher(device, mmcore)
        else:
            raise ValueError(f"Device {device} is not a stage device.")

        # pop the key on mmcore.events.systemConfigurationLoaded?
        @mmcore.events.systemConfigurationLoaded.connect
        def _on_system_configuration_loaded() -> None:
            # remove the batcher from the cache
            _STAGE_BATCHERS.pop(key, None)

    return _STAGE_BATCHERS[key]


# -------------------------------- Qt specific --------------------------------


class QStageController(QObject):
    moveFinished = Signal()

    def __init__(self, device: str, mmcore: CMMCorePlus, *, poll_ms: int = 20):
        super().__init__()
        self._batcher = get_stage_batcher(device, mmcore)
        self._batcher.finished.connect(self.moveFinished.emit)
        self._poll_ms = poll_ms
        self._timer_id: int | None = None

    def move_relative(self, delta: Any) -> None:
        self._batcher.add_relative(delta)
        if self._timer_id is None:
            self._timer_id = self.startTimer(self._poll_ms)

    def move_absolute(self, target: Any) -> None:
        self._batcher.set_absolute(target)
        if self._timer_id is None:
            self._timer_id = self.startTimer(self._poll_ms)

    def timerEvent(self, event: QTimerEvent | None) -> None:
        device_idle = self._batcher.poll_done()
        if device_idle is True and self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None


_Q_STAGE_CONTROLLERS: dict[tuple[int, str], QStageController] = {}


def get_q_stage_controller(
    device: str, mmcore: CMMCorePlus | None = None
) -> QStageController:
    """Get a stage controller for the given device."""
    mmcore = mmcore or CMMCorePlus.instance()
    key = (id(mmcore), device)
    if key not in _Q_STAGE_CONTROLLERS:
        _Q_STAGE_CONTROLLERS[key] = QStageController(device, mmcore)
    return _Q_STAGE_CONTROLLERS[key]
