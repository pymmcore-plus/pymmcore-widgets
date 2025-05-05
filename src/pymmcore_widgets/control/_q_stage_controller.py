from __future__ import annotations

from typing import Any

from pymmcore_plus import AbstractChangeAccumulator, CMMCorePlus, core
from qtpy.QtCore import QObject, QTimerEvent, Signal


class QChangeAccumulator(QObject):
    moveFinished = Signal()

    def __init__(self, accumulator: AbstractChangeAccumulator, *, poll_ms: int = 20):
        super().__init__()
        self._accum = accumulator
        self._accum.finished.connect(self.moveFinished.emit)
        self._poll_ms = poll_ms
        self._timer_id: int | None = None

    def move_relative(self, delta: Any) -> None:
        self._accum.add_relative(delta)
        if self._timer_id is None:
            self._timer_id = self.startTimer(self._poll_ms)

    def move_absolute(self, target: Any) -> None:
        self._accum.set_absolute(target)
        if self._timer_id is None:
            self._timer_id = self.startTimer(self._poll_ms)

    def timerEvent(self, event: QTimerEvent | None) -> None:
        device_idle = self._accum.poll_done()
        if device_idle is True and self._timer_id is not None:
            self.killTimer(self._timer_id)
            self._timer_id = None


_Q_ACCUMULATORS: dict[tuple[int, str], QChangeAccumulator] = {}


def get_q_stage_controller(
    device: str, mmcore: CMMCorePlus | None = None
) -> QChangeAccumulator:
    """Get a stage controller for the given device."""
    mmcore = mmcore or CMMCorePlus.instance()
    key = (id(mmcore), device)
    if key not in _Q_ACCUMULATORS:
        dev_obj = mmcore.getDeviceObject(device)
        if not isinstance(dev_obj, (core.XYStageDevice, core.StageDevice)):
            raise TypeError(
                f"Cannot {device} is not a stage device. "
                f"It is a {dev_obj.type().name!r}."
            )
        accum = dev_obj.getPositionAccumulator()
        _Q_ACCUMULATORS[key] = QChangeAccumulator(accum)
    return _Q_ACCUMULATORS[key]
