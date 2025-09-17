from __future__ import annotations

import weakref
from typing import ClassVar, cast

from pymmcore_plus import AbstractChangeAccumulator, CMMCorePlus, core
from qtpy.QtCore import QObject, QTimerEvent, Signal


class QStageMoveAccumulator(QObject):
    """Object to accumulate stage moves and poll for completion.

    This class is meant to be shared by multiple widgets/users that need to share
    control of a stage device, possibly accumulating relative moves.

    Create using the `for_device` class method, which will return a cached instance
    for the given device and core.

    Attributes
    ----------
    moveFinished : Signal
        Emitted when the move is finished. This is a signal that can be connected to
        other slots to perform actions after the move is completed.
    snap_on_finish : bool
        If True, a snap will be performed after the move is finished.  Prefer using
        this to connecting a callback to the `moveFinished` signal, so that multiple
        snaps can be avoided if multiple widgets are connected to the signal.
    """

    moveFinished = Signal()
    snap_on_finish: bool = False

    @classmethod
    def for_device(
        cls, device: str, mmcore: CMMCorePlus | None = None
    ) -> QStageMoveAccumulator:
        """Get a stage controller for the given device."""
        mmcore = mmcore or CMMCorePlus.instance()
        key = (id(mmcore), device)
        if key not in cls._CACHE:
            dev_obj = mmcore.getDeviceObject(device)
            if not isinstance(dev_obj, (core.XYStageDevice, core.StageDevice)):
                raise TypeError(
                    f"Cannot {device} is not a stage device. "
                    f"It is a {dev_obj.type().name!r}."
                )
            accum = dev_obj.getPositionAccumulator()
            cls._CACHE[key] = QStageMoveAccumulator(accum)
            weakref.finalize(mmcore, cls._CACHE.pop, key, None)
        return cls._CACHE[key]

    _CACHE: ClassVar[dict[tuple[int, str], QStageMoveAccumulator]] = {}

    def __init__(self, accumulator: AbstractChangeAccumulator, *, poll_ms: int = 20):
        super().__init__()
        self._accum = accumulator
        self._poll_ms = poll_ms
        self._timer_id: int | None = None
        # mutable field that may be set by any caller.
        # will always be set to False when the move is finished (after snapping)
        self.snap_on_finish: bool = False

    def move_relative(self, delta: float | tuple[float, float]) -> None:
        """Move the stage relative to its current position."""
        self._accum.add_relative(delta)
        if self._timer_id is None:
            self._timer_id = self.startTimer(self._poll_ms)

    def move_absolute(self, target: float | tuple[float, float]) -> None:
        """Move the stage to an absolute position."""
        self._accum.set_absolute(target)
        if self._timer_id is None:
            self._timer_id = self.startTimer(self._poll_ms)

    def timerEvent(self, event: QTimerEvent | None) -> None:
        try:
            done_polling = self._accum.poll_done()
        except RuntimeError:
            # If an error occurs while polling, stop the timer.
            done_polling = True

        if done_polling is True:
            if self._timer_id is not None:
                self.killTimer(self._timer_id)
                self._timer_id = None

            if self.snap_on_finish:
                if (core := getattr(self._accum, "_mmcore", None)) is not None:
                    _core = cast("CMMCorePlus", core)
                    if not _core.isSequenceRunning():
                        _core.snapImage()
                self.snap_on_finish = False

            self.moveFinished.emit()
