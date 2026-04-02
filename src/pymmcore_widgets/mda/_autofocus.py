from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter, sleep
from typing import TYPE_CHECKING, Any, Protocol

import numpy as np
from pymmcore_plus import CMMCorePlus
from pymmcore_plus._logger import logger
from pymmcore_plus.mda import MDAEngine
from qtpy.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)
from useq import HardwareAutofocus, MDAEvent, MDASequence

from pymmcore_widgets.useq_widgets._autofocus import (
    PYMMCW_AUTOFOCUS_KEY,
    PYMMCW_SOFTWARE_AUTOFOCUS_KEY,
    AutofocusMode,
    normalize_software_af_settings,
)
from pymmcore_widgets.useq_widgets._mda_sequence import PYMMCW_METADATA_KEY

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from pymmcore_plus.mda._protocol import PImagePayload


@dataclass(frozen=True)
class SoftwareAutofocusResult:
    backend: str
    best_z: float
    start_z: float
    best_score: float
    elapsed_s: float
    attempts: int

    @property
    def correction_um(self) -> float:
        return self.best_z - self.start_z

    def summary(self) -> str:
        return (
            f"{self.backend}: z {self.start_z:.3f} -> {self.best_z:.3f} um, "
            f"score {self.best_score:.3f}, dt {self.elapsed_s:.2f} s"
        )


class AutofocusScorer(Protocol):
    backend_id: str
    display_name: str

    def score(self, image: np.ndarray) -> float: ...


class TenengradScorer:
    backend_id = "tenengrad"
    display_name = "Tenengrad"

    def score(self, image: np.ndarray) -> float:
        gx, gy = np.gradient(image.astype(np.float32, copy=False))
        return float(np.mean(gx * gx + gy * gy))


class LaplacianVarianceScorer:
    backend_id = "laplacian_variance"
    display_name = "Laplacian Variance"

    def score(self, image: np.ndarray) -> float:
        image = image.astype(np.float32, copy=False)
        center = image[1:-1, 1:-1]
        lap = (
            -4 * center
            + image[:-2, 1:-1]
            + image[2:, 1:-1]
            + image[1:-1, :-2]
            + image[1:-1, 2:]
        )
        return float(lap.var())


AUTOFOCUS_SCORERS: dict[str, AutofocusScorer] = {
    scorer.backend_id: scorer
    for scorer in (TenengradScorer(), LaplacianVarianceScorer())
}


def _coerce_2d(image: np.ndarray) -> np.ndarray:
    if image.ndim == 2:
        return image
    if image.ndim == 3:
        return image.mean(axis=-1)
    return np.squeeze(image)


def _center_crop(image: np.ndarray, crop_size_px: int | None) -> np.ndarray:
    image = _coerce_2d(image)
    if not crop_size_px or crop_size_px <= 0:
        return image

    height, width = image.shape[:2]
    size = min(crop_size_px, height, width)
    y0 = max((height - size) // 2, 0)
    x0 = max((width - size) // 2, 0)
    return image[y0 : y0 + size, x0 : x0 + size]


def _z_positions(start_z: float, search_range_um: float, step_um: float) -> list[float]:
    if step_um <= 0:
        raise ValueError("step_um must be > 0")
    if search_range_um <= 0:
        return [start_z]
    half_range = search_range_um / 2
    n_steps = max(int(round(search_range_um / step_um)), 1)
    positions = np.linspace(start_z - half_range, start_z + half_range, n_steps + 1)
    return [float(x) for x in positions]


def _software_af_channel_label(settings: dict[str, Any]) -> str:
    if settings.get("channel_mode") != "fixed":
        return "Current microscope state"
    group = settings.get("channel_group") or "current group"
    channel = settings.get("channel") or "current preset"
    return f"{group} / {channel}"


def run_software_autofocus(
    core: CMMCorePlus, settings: Any
) -> SoftwareAutofocusResult:
    options = normalize_software_af_settings(settings)
    params = options["params"]
    focus_device = core.getFocusDevice()
    if not focus_device:
        raise RuntimeError("No focus device is configured.")

    scorer = AUTOFOCUS_SCORERS.get(options["backend"])
    if scorer is None:
        raise RuntimeError(f"Unknown autofocus backend: {options['backend']!r}")

    start_z = float(core.getZPosition())
    z_positions = _z_positions(
        start_z=start_z,
        search_range_um=float(params["search_range_um"]),
        step_um=float(params["step_um"]),
    )
    exposure_ms = params.get("exposure_ms")
    settle_s = max(float(params.get("settle_ms", 0.0)) / 1000.0, 0.0)
    max_retries = max(int(params.get("max_retries", 1)), 1)
    crop_size_px = int(params.get("crop_size_px", 0) or 0)

    t0 = perf_counter()
    best_score = float("-inf")
    best_z = start_z
    attempts = 0

    previous_exposure = float(core.getExposure()) if exposure_ms is not None else None
    restore_group: str | None = None
    restore_channel: str | None = None

    try:
        if exposure_ms is not None:
            core.setExposure(float(exposure_ms))

        if options.get("channel_mode") == "fixed":
            channel_group = options.get("channel_group") or core.getChannelGroup()
            channel = options.get("channel")
            if channel_group and channel:
                restore_group = core.getChannelGroup() or None
                if restore_group:
                    try:
                        restore_channel = core.getCurrentConfig(restore_group)
                    except Exception:
                        restore_channel = None
                core.setConfig(str(channel_group), str(channel))
                core.waitForSystem()

        for _retry_idx in range(max_retries):
            attempts += 1
            for z in z_positions:
                core.setZPosition(z)
                core.waitForDevice(focus_device)
                if settle_s:
                    sleep(settle_s)
                core.snapImage()
                image = np.asarray(core.getImage())
                score = scorer.score(_center_crop(image, crop_size_px))
                if score > best_score:
                    best_score = score
                    best_z = z
    finally:
        core.setZPosition(best_z)
        core.waitForDevice(focus_device)
        if restore_group and restore_channel:
            core.setConfig(restore_group, restore_channel)
            core.waitForSystem()
        if previous_exposure is not None:
            core.setExposure(previous_exposure)

    return SoftwareAutofocusResult(
        backend=scorer.display_name,
        best_z=best_z,
        start_z=start_z,
        best_score=best_score,
        elapsed_s=perf_counter() - t0,
        attempts=attempts,
    )


class SoftwareAutofocusDialog(QDialog):
    def __init__(
        self,
        settings: Any,
        *,
        core: CMMCorePlus | None = None,
        test_callback: Callable[[dict[str, Any]], str] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Software Autofocus")
        self._core = core
        self._test_callback = test_callback

        self._backend = QComboBox()
        for scorer in AUTOFOCUS_SCORERS.values():
            self._backend.addItem(scorer.display_name, scorer.backend_id)

        self._channel_mode = QComboBox()
        self._channel_mode.addItem("Use current state", "current")
        self._channel_mode.addItem("Force channel preset", "fixed")

        self._channel_group = QComboBox()
        self._channel = QComboBox()

        self._search_range = QDoubleSpinBox()
        self._search_range.setRange(0.5, 500.0)
        self._search_range.setDecimals(3)
        self._search_range.setSuffix(" um")

        self._step = QDoubleSpinBox()
        self._step.setRange(0.05, 100.0)
        self._step.setDecimals(3)
        self._step.setSuffix(" um")

        self._crop = QSpinBox()
        self._crop.setRange(0, 4096)
        self._crop.setSpecialValueText("Full frame")
        self._crop.setSingleStep(64)
        self._crop.setSuffix(" px")

        self._exposure = QDoubleSpinBox()
        self._exposure.setRange(0.0, 10000.0)
        self._exposure.setDecimals(2)
        self._exposure.setSpecialValueText("Current")
        self._exposure.setSuffix(" ms")

        self._settle = QDoubleSpinBox()
        self._settle.setRange(0.0, 5000.0)
        self._settle.setDecimals(1)
        self._settle.setSuffix(" ms")

        self._retries = QSpinBox()
        self._retries.setRange(1, 10)

        self._channel_mode.currentIndexChanged.connect(self._update_channel_widgets)
        self._channel_group.currentIndexChanged.connect(self._populate_channels)
        self._populate_channel_groups()

        form = QFormLayout()
        form.addRow("Backend", self._backend)
        form.addRow("Focus Channel", self._channel_mode)
        form.addRow("Channel Group", self._channel_group)
        form.addRow("Channel Preset", self._channel)
        form.addRow("Search Range", self._search_range)
        form.addRow("Step", self._step)
        form.addRow("Crop", self._crop)
        form.addRow("Exposure", self._exposure)
        form.addRow("Settle", self._settle)
        form.addRow("Retries", self._retries)

        group = QGroupBox("Parameters")
        group.setLayout(form)

        self._status = QLabel("Ready.")
        self._status.setWordWrap(True)

        self._test_btn = QPushButton("Test on Current Position")
        self._test_btn.setEnabled(test_callback is not None)
        self._test_btn.clicked.connect(self._on_test_clicked)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        buttons = QHBoxLayout()
        buttons.addWidget(self._test_btn)
        buttons.addStretch()
        buttons.addWidget(button_box)

        layout = QVBoxLayout(self)
        layout.addWidget(group)
        layout.addWidget(self._status)
        layout.addLayout(buttons)

        self.setValue(settings)

    def value(self) -> dict[str, Any]:
        exposure = float(self._exposure.value())
        return {
            "backend": str(self._backend.currentData()),
            "channel_mode": str(self._channel_mode.currentData()),
            "channel_group": self._selected_channel_group(),
            "channel": self._selected_channel(),
            "params": {
                "search_range_um": float(self._search_range.value()),
                "step_um": float(self._step.value()),
                "crop_size_px": int(self._crop.value()),
                "exposure_ms": None if exposure <= 0 else exposure,
                "settle_ms": float(self._settle.value()),
                "max_retries": int(self._retries.value()),
            },
        }

    def setValue(self, settings: Any) -> None:
        value = normalize_software_af_settings(settings)
        params = value["params"]
        idx = self._backend.findData(value["backend"])
        if idx >= 0:
            self._backend.setCurrentIndex(idx)
        idx = self._channel_mode.findData(value["channel_mode"])
        if idx >= 0:
            self._channel_mode.setCurrentIndex(idx)
        self._set_combo_to_value(self._channel_group, value["channel_group"])
        self._populate_channels()
        self._set_combo_to_value(self._channel, value["channel"])
        self._search_range.setValue(float(params["search_range_um"]))
        self._step.setValue(float(params["step_um"]))
        self._crop.setValue(int(params["crop_size_px"] or 0))
        self._exposure.setValue(float(params["exposure_ms"] or 0.0))
        self._settle.setValue(float(params["settle_ms"]))
        self._retries.setValue(int(params["max_retries"]))
        self._update_channel_widgets()

    def _on_test_clicked(self) -> None:
        if self._test_callback is None:
            return
        settings = self.value()
        self._status.setText(
            f"Running software autofocus on {_software_af_channel_label(settings)}..."
        )
        self.repaint()
        try:
            self._status.setText(self._test_callback(settings))
        except Exception as e:
            self._status.setText(f"Autofocus failed: {e}")

    def _populate_channel_groups(self) -> None:
        self._channel_group.clear()
        current_group = self._core.getChannelGroup() if self._core else ""
        if current_group:
            self._channel_group.addItem(current_group, current_group)
        if self._core:
            for group in self._core.getAvailableConfigGroups():
                if self._channel_group.findData(group) < 0:
                    self._channel_group.addItem(group, group)
        self._populate_channels()

    def _populate_channels(self) -> None:
        current_value = self._selected_channel()
        self._channel.clear()
        group = self._selected_channel_group()
        if self._core and group:
            for config in self._core.getAvailableConfigs(group):
                self._channel.addItem(config, config)
        self._set_combo_to_value(self._channel, current_value)
        self._update_channel_widgets()

    def _selected_channel_group(self) -> str | None:
        value = self._channel_group.currentData()
        return str(value) if value else None

    def _selected_channel(self) -> str | None:
        value = self._channel.currentData()
        return str(value) if value else None

    def _set_combo_to_value(self, combo: QComboBox, value: str | None) -> None:
        if not value:
            return
        idx = combo.findData(value)
        if idx >= 0:
            combo.setCurrentIndex(idx)

    def _update_channel_widgets(self) -> None:
        fixed = self._channel_mode.currentData() == "fixed"
        self._channel_group.setEnabled(fixed)
        self._channel.setEnabled(fixed)


class SoftwareAutofocusMDAEngine(MDAEngine):
    def __init__(self, mmc: CMMCorePlus) -> None:
        super().__init__(mmc)
        self._af_mode = AutofocusMode.NONE
        self._software_af_settings = normalize_software_af_settings(None)

    def setup_sequence(self, sequence: MDASequence) -> dict | None:
        af_meta = sequence.metadata.get(PYMMCW_METADATA_KEY, {}).get(
            PYMMCW_AUTOFOCUS_KEY, {}
        )
        self._af_mode = AutofocusMode(str(af_meta.get("mode", AutofocusMode.NONE.value)))
        self._software_af_settings = normalize_software_af_settings(
            af_meta.get(PYMMCW_SOFTWARE_AUTOFOCUS_KEY)
        )
        meta = super().setup_sequence(sequence)
        if self._af_mode is AutofocusMode.SOFTWARE:
            self._af_was_engaged = False
        return meta

    def exec_event(self, event: MDAEvent) -> Iterable[PImagePayload | None]:
        action = getattr(event, "action", None)
        if (
            self._af_mode is AutofocusMode.SOFTWARE
            and isinstance(action, HardwareAutofocus)
        ):
            try:
                result = run_software_autofocus(self.mmcore, self._software_af_settings)
            except Exception as e:
                logger.warning("Software autofocus failed. %s", e)
                self._af_succeeded = False
            else:
                self._af_succeeded = True
                p_idx = event.index.get("p", None)
                self._z_correction[p_idx] = result.correction_um + self._z_correction.get(
                    p_idx, 0.0
                )
                logger.info("Software autofocus succeeded: %s", result.summary())
            return ()

        return super().exec_event(event)
