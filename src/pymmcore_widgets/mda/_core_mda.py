from __future__ import annotations

from contextlib import suppress
from pathlib import Path
from typing import TYPE_CHECKING, Literal, cast

from fonticon_mdi6 import MDI6
from pymmcore_plus import CMMCorePlus, Keyword
from pymmcore_plus.mda.handlers import (  # type: ignore
    ImageSequenceWriter,
    OMETiffWriter,
    OMEZarrWriter,
)
from qtpy.QtCore import QSize, Qt, Signal
from qtpy.QtWidgets import (
    QBoxLayout,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QWidget,
)
from superqt.fonticon import icon
from useq import MDASequence, Position

from pymmcore_widgets.useq_widgets import MDASequenceWidget
from pymmcore_widgets.useq_widgets._mda_sequence import MDATabs
from pymmcore_widgets.useq_widgets._time import TimePlanWidget

from ._core_channels import CoreConnectedChannelTable
from ._core_grid import CoreConnectedGridPlanWidget
from ._core_positions import CoreConnectedPositionTable
from ._core_z import CoreConnectedZPlanWidget

if TYPE_CHECKING:
    from typing import TypedDict

    class SaveInfo(TypedDict):
        save_dir: str
        save_name: str
        save_as: list[Literal["ome-zarr", "ome-tiff", "tiff-sequence"]]


ZARR = "ome-zarr"
TIFF = "ome-tiff"
TIFF_SEQUENCE = "tiff-sequence"
DEFAULT = "Experiment"


class CoreMDATabs(MDATabs):
    def __init__(
        self, parent: QWidget | None = None, core: CMMCorePlus | None = None
    ) -> None:
        self._mmc = core or CMMCorePlus.instance()
        super().__init__(parent)

    def create_subwidgets(self) -> None:
        self.time_plan = TimePlanWidget(1)
        self.stage_positions = CoreConnectedPositionTable(1, self._mmc)
        self.z_plan = CoreConnectedZPlanWidget(self._mmc)
        self.grid_plan = CoreConnectedGridPlanWidget(self._mmc)
        self.channels = CoreConnectedChannelTable(1, self._mmc)

    def _enable_tabs(self, enable: bool) -> None:
        """Enable or disable the tab checkboxes and their contents.

        However, we can still mover through the tabs and see their contents.
        """
        # disable tab checkboxes
        for cbox in self._cboxes:
            cbox.setEnabled(enable)
        # disable tabs contents
        self.time_plan.setEnabled(enable)
        self.stage_positions.setEnabled(enable)
        self.z_plan.setEnabled(enable)
        self.grid_plan.setEnabled(enable)
        self.channels.setEnabled(enable)


class MDAWidget(MDASequenceWidget):
    """Main MDA Widget connected to a [`pymmcore_plus.CMMCorePlus`][] instance.

    It provides a GUI to construct and run a [`useq.MDASequence`][].  Unlike
    [`useq_widgets.MDASequenceWidget`][pymmcore_widgets.MDASequenceWidget], this
    widget is connected to a [`pymmcore_plus.CMMCorePlus`][] instance, enabling
    awareness and control of the current state of the microscope.

    Parameters
    ----------
    parent : QWidget | None
        Optional parent widget, by default None.
    mmcore : CMMCorePlus | None
        Optional [`CMMCorePlus`][pymmcore_plus.CMMCorePlus] micromanager core.
        By default, None. If not specified, the widget will use the active
        (or create a new)
        [`CMMCorePlus.instance`][pymmcore_plus.core._mmcore_plus.CMMCorePlus.instance].
    """

    def __init__(
        self, *, parent: QWidget | None = None, mmcore: CMMCorePlus | None = None
    ) -> None:
        # create a couple core-connected variants of the tab widgets
        self._mmc = mmcore or CMMCorePlus.instance()

        super().__init__(parent=parent, tab_widget=CoreMDATabs(None, self._mmc))

        self.save_info = _SaveGroupBox(parent=self)
        self.save_info.valueChanged.connect(self.valueChanged)
        self.control_btns = _MDAControlButtons(self._mmc, self)

        # -------- initialize -----------

        self._on_sys_config_loaded()

        # ------------ layout ------------

        layout = cast("QBoxLayout", self.layout())
        layout.insertWidget(0, self.save_info)
        layout.addWidget(self.control_btns)

        # ------------ connect signals ------------

        self.control_btns.run_btn.clicked.connect(self._on_run_clicked)
        self.control_btns.pause_btn.released.connect(self._mmc.mda.toggle_pause)
        self.control_btns.cancel_btn.released.connect(self._mmc.mda.cancel)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)
        self._mmc.events.systemConfigurationLoaded.connect(self._on_sys_config_loaded)

        self.destroyed.connect(self._disconnect)

    def _on_sys_config_loaded(self) -> None:
        # TODO: connect objective change event to update suggested step
        self.z_plan.setSuggestedStep(_guess_NA(self._mmc) or 0.5)

    def value(self) -> MDASequence:
        """Set the current state of the widget from a [`useq.MDASequence`][]."""
        val = super().value()
        replace: dict = {}

        # if the z plan is relative and there are stage positions but the 'include z' is
        # unchecked, use the current z stage position as the relative starting one.
        if (
            val.z_plan
            and val.z_plan.is_relative
            and (val.stage_positions and not self.stage_positions.include_z.isChecked())
        ):
            z = self._mmc.getZPosition() if self._mmc.getFocusDevice() else None
            replace["stage_positions"] = tuple(
                pos.replace(z=z) for pos in val.stage_positions
            )

        # if there is an autofocus_plan but the autofocus_motor_offset is None, set it
        # to the current value
        if (afplan := val.autofocus_plan) and afplan.autofocus_motor_offset is None:
            p2 = afplan.replace(autofocus_motor_offset=self._mmc.getAutoFocusOffset())
            replace["autofocus_plan"] = p2

        # if there are no stage positions, use the current stage position
        if not val.stage_positions:
            replace["stage_positions"] = (self._get_current_stage_position(),)
            # if "p" is not in the axis order, we need to add it or the position will
            # not be in the event
            if "p" not in val.axis_order:
                axis_order = list(val.axis_order)
                # add the "p" axis at the beginning or after the "t" as the default
                if "t" in axis_order:
                    axis_order.insert(axis_order.index("t") + 1, "p")
                else:
                    axis_order.insert(0, "p")
                replace["axis_order"] = tuple(axis_order)

        if replace:
            val = val.replace(**replace)

        meta: dict = val.metadata.setdefault("pymmcore_widgets", {})
        if self.save_info.isChecked():
            meta.update(self.save_info.value())
        return val

    def setValue(self, value: MDASequence) -> None:
        """Get the current state of the widget as a [`useq.MDASequence`][]."""
        super().setValue(value)
        self.save_info.setValue(value.metadata.get("pymmcore_widgets", {}))

    # ------------------- private API ----------------------

    def _get_current_stage_position(self) -> Position:
        """Return the current stage position."""
        x = self._mmc.getXPosition() if self._mmc.getXYStageDevice() else None
        y = self._mmc.getYPosition() if self._mmc.getXYStageDevice() else None
        z = self._mmc.getPosition() if self._mmc.getFocusDevice() else None
        return Position(x=x, y=y, z=z)

    def _on_run_clicked(self) -> None:
        """Run the MDA sequence experiment."""
        # if autofocus has been requested, but the autofocus device is not engaged,
        # and position-specific offsets haven't been set, show a warning
        pos = self.stage_positions
        if (
            self.af_axis.value()
            and not self._mmc.isContinuousFocusLocked()
            and not (self.tab_wdg.isChecked(pos) and pos.af_per_position.isChecked())
            and not self._confirm_af_intentions()
        ):
            return

        sequence = self.value()

        # get saving info from the metadata
        metadata = sequence.metadata.get("pymmcore_widgets", None)
        save_dir = metadata.get("save_dir") if metadata else None
        save_name = metadata.get("save_name") if metadata else DEFAULT
        save_as = metadata.get("save_as") if metadata else []

        # create the writers
        writers: list = []
        if save_dir:
            path = Path(save_dir)
            if ZARR in save_as:
                writers.append(OMEZarrWriter(store=path / f"{save_name}.zarr"))
            if TIFF in save_as:
                writers.append(OMETiffWriter(path / f"{save_name}.tif"))
            if TIFF_SEQUENCE in save_as:
                writers.append(ImageSequenceWriter(path / f"{save_name}"))

        # run the MDA experiment asynchronously
        self._mmc.run_mda(sequence, output=writers or None)  # type: ignore

    def _confirm_af_intentions(self) -> bool:
        msg = (
            "You've selected to use autofocus for this experiment, "
            f"but the '{self._mmc.getAutoFocusDevice()!r}' autofocus device "
            "is not currently engaged. "
            "\n\nRun anyway?"
        )

        response = QMessageBox.warning(
            self,
            "Confirm AutoFocus",
            msg,
            QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        return bool(response == QMessageBox.StandardButton.Ok)

    def _enable_widgets(self, enable: bool) -> None:
        for child in self.children():
            if isinstance(child, CoreMDATabs):
                child._enable_tabs(enable)
            elif child is not self.control_btns and hasattr(child, "setEnabled"):
                child.setEnabled(enable)

    def _on_mda_started(self) -> None:
        self._enable_widgets(False)

    def _on_mda_finished(self) -> None:
        self._enable_widgets(True)

    def _disconnect(self) -> None:
        with suppress(Exception):
            self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
            self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)


class _SaveGroupBox(QGroupBox):
    """A Widget to gather information about MDA file saving."""

    valueChanged = Signal()

    def __init__(
        self, title: str = "Save Acquisition", parent: QWidget | None = None
    ) -> None:
        super().__init__(title, parent)
        self.setCheckable(True)
        self.setChecked(False)

        dir_label = QLabel("Directory:")
        name_label = QLabel("Name:")

        self.save_dir = QLineEdit()
        self.save_dir.setPlaceholderText("Select Save Directory")
        self.save_name = QLineEdit()
        self.save_name.setPlaceholderText("Enter Experiment Name")

        browse_btn = QPushButton(text="...")
        browse_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        browse_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        browse_btn.clicked.connect(self._on_browse_clicked)

        save_format_wdg = QWidget()
        save_format_layout = QHBoxLayout(save_format_wdg)
        save_format_layout.setContentsMargins(0, 0, 0, 0)
        save_format_layout.setSpacing(10)
        label = QLabel("Save as:")
        label.setFixedSize(dir_label.sizeHint())
        self.omezarr_checkbox = QCheckBox("ome-zarr")
        self.omezarr_checkbox.setChecked(True)
        self.ometiff_checkbox = QCheckBox("ome-tiff")
        self.tiffsequence_checkbox = QCheckBox("tiff-sequence")
        save_format_layout.addWidget(label)
        save_format_layout.addWidget(self.omezarr_checkbox)
        save_format_layout.addWidget(self.ometiff_checkbox)
        save_format_layout.addWidget(self.tiffsequence_checkbox)
        save_format_layout.addStretch()

        grid = QGridLayout(self)
        grid.addWidget(dir_label, 0, 0)
        grid.addWidget(self.save_dir, 0, 1)
        grid.addWidget(browse_btn, 0, 2)
        grid.addWidget(name_label, 1, 0)
        grid.addWidget(self.save_name, 1, 1)
        grid.addWidget(save_format_wdg, 2, 0, 1, 2)

        # connect
        self.toggled.connect(self.valueChanged)
        self.save_dir.textChanged.connect(self.valueChanged)
        self.save_name.textChanged.connect(self.valueChanged)
        self.omezarr_checkbox.toggled.connect(self._on_toggle)
        self.ometiff_checkbox.toggled.connect(self._on_toggle)
        self.tiffsequence_checkbox.toggled.connect(self._on_toggle)

    def _on_toggle(self, checked: bool) -> None:
        """Emit valueChanged signal when a save format checkbox is toggled."""
        # if none between ome-zarr, ome-tiff, and tiff-sequence is checked, check
        # ome-zarr
        if not self._get_checkboxes_state():
            self.omezarr_checkbox.setChecked(True)
        self.valueChanged.emit()

    def _get_checkboxes_state(
        self,
    ) -> list[Literal["ome-zarr", "ome-tiff", "tiff-sequence"]]:
        """Return the state of the save format checkboxes."""
        state: list = []

        if not self.isChecked():
            return state

        cb = (self.omezarr_checkbox, self.ometiff_checkbox, self.tiffsequence_checkbox)
        state.extend(checkbox.text() for checkbox in cb if checkbox.isChecked())
        return state

    def value(self) -> SaveInfo:
        """Return current state of the dialog."""
        return {
            "save_dir": self.save_dir.text() if self.isChecked() else "",
            "save_name": self.save_name.text() or "Experiment",
            "save_as": self._get_checkboxes_state(),
        }

    def setValue(self, value: SaveInfo | dict) -> None:
        save_dir = value.get("save_dir", "")
        save_name = value.get("save_name", "")
        self.save_dir.setText(save_dir)
        self.save_name.setText(save_name)
        if save_as := value.get("save_as", []):
            self.omezarr_checkbox.setChecked(ZARR in save_as)
            self.ometiff_checkbox.setChecked(TIFF in save_as)
            self.tiffsequence_checkbox.setChecked(TIFF_SEQUENCE in save_as)
        self.setChecked(bool(save_dir and save_as))

    def _on_browse_clicked(self) -> None:
        if save_dir := QFileDialog.getExistingDirectory(
            self, "Select Save Directory", self.save_dir.text()
        ):
            self.save_dir.setText(save_dir)


class _MDAControlButtons(QWidget):
    """Run, pause, and cancel buttons at the bottom of the MDA Widget."""

    def __init__(self, mmcore: CMMCorePlus, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._mmc = mmcore
        self._mmc.mda.events.sequencePauseToggled.connect(self._on_mda_paused)
        self._mmc.mda.events.sequenceStarted.connect(self._on_mda_started)
        self._mmc.mda.events.sequenceFinished.connect(self._on_mda_finished)

        icon_size = QSize(24, 24)
        self.run_btn = QPushButton("Run")
        self.run_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.run_btn.setIcon(icon(MDI6.play_circle_outline, color="lime"))
        self.run_btn.setIconSize(icon_size)

        self.pause_btn = QPushButton("Pause")
        self.pause_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.pause_btn.setIcon(icon(MDI6.pause_circle_outline, color="green"))
        self.pause_btn.setIconSize(icon_size)
        self.pause_btn.hide()

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.cancel_btn.setIcon(icon(MDI6.stop_circle_outline, color="#C33"))
        self.cancel_btn.setIconSize(icon_size)
        self.cancel_btn.hide()

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(self.run_btn)
        layout.addWidget(self.pause_btn)
        layout.addWidget(self.cancel_btn)

        self.destroyed.connect(self._disconnect)

    def _on_mda_started(self) -> None:
        self.run_btn.hide()
        self.pause_btn.show()
        self.cancel_btn.show()

    def _on_mda_finished(self) -> None:
        self.run_btn.show()
        self.pause_btn.hide()
        self.cancel_btn.hide()
        self._on_mda_paused(False)

    def _on_mda_paused(self, paused: bool) -> None:
        if paused:
            self.pause_btn.setIcon(icon(MDI6.play_circle_outline, color="lime"))
            self.pause_btn.setText("Resume")
        else:
            self.pause_btn.setIcon(icon(MDI6.pause_circle_outline, color="green"))
            self.pause_btn.setText("Pause")

    def _disconnect(self) -> None:
        with suppress(Exception):
            self._mmc.mda.events.sequencePauseToggled.disconnect(self._on_mda_paused)
            self._mmc.mda.events.sequenceStarted.disconnect(self._on_mda_started)
            self._mmc.mda.events.sequenceFinished.disconnect(self._on_mda_finished)


def _guess_NA(core: CMMCorePlus) -> float | None:
    with suppress(RuntimeError):
        if not (pix_cfg := core.getCurrentPixelSizeConfig()):
            return None  # pragma: no cover

        data = core.getPixelSizeConfigData(pix_cfg)
        for obj in core.guessObjectiveDevices():
            key = (obj, Keyword.Label)
            if key in data:
                val = data[key]
                for word in val.split():
                    try:
                        na = float(word)
                    except ValueError:
                        continue
                    if 0.1 < na < 1.5:
                        return na
    return None
